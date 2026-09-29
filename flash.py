"""
按本次构建生成的 flasher_args.json 分段烧录 ESP-12F（ESP8266）。

快速用法（Windows PowerShell）：
    python build.py
    python flash.py --port COM3 --dry-run
    python flash.py --port COM3
将 COM3 改为实际串口；--baud 可指定烧录波特率，默认 115200。

用途
====
本脚本读取：

    build/auto/flasher_args.json

并按照其中的 flash_settings 和 flash_files 信息，将本次构建生成的
bootloader、partition table、应用程序以及其他烧录段写入 ESP-12F Flash。

烧录布局完全以本次构建生成的 flasher_args.json 为准，脚本本身不硬编码
各 BIN 文件的烧录地址。

运行环境
========
1. Windows
2. Python 3.9 或更高版本
3. 项目目录中应存在：

    flash.py
    build/
      auto/
        flasher_args.json
        bootloader/
          bootloader.bin
        partition_table/
          partition-table.bin
        ac_thermostat.bin
        ...

    tools/
      esptool-v4.12.0/
        esptool.exe

其中 flash.py 指本脚本。

烧录前准备
==========
本脚本使用：

    --before no_reset
    --after no_reset

因此不会通过串口 DTR/RTS 自动控制 ESP8266 进入下载模式，也不会在烧录完成后
自动复位运行应用程序。

烧录前应按硬件设计手动使 ESP-12F 进入 UART 下载模式，例如：

1. 按硬件要求短接 P4；
2. 复位或重新上电 ESP-12F；
3. 确认设备已进入下载模式；
4. 执行本脚本；
5. 烧录完成后断开 P4；
6. 再次复位设备，使其正常启动。

具体进入下载模式的方法应以实际硬件设计为准。

基本用法
========
烧录 COM3，使用默认 115200 波特率：

    python flash.py --port COM3

指定烧录波特率：

    python flash.py --port COM3 --baud 460800

只检查本次构建生成的 Flash 布局和 BIN 文件，不访问串口、不执行烧录：

    python flash.py --port COM3 --dry-run

查看帮助：

    python flash.py --help

参数
====
--port COMx
    必填。
    Windows 串口名称，例如 COM3、COM12。

--baud N
    可选。
    烧录波特率，允许范围 9600～921600。
    默认值为 115200。

--dry-run
    可选。
    仅检查：
      - flasher_args.json 是否存在且格式正确；
      - Flash 参数是否合法；
      - Flash 频率是否为 26m；
      - 所有烧录 BIN 是否存在且非空；
      - 必需的 bootloader、partition table 和应用程序是否存在；
      - 各烧录区域是否超出 Flash 容量；
      - 各烧录区域占用的 4 KiB Flash sector 是否发生冲突。

    dry-run 不检查 esptool.exe，不访问串口，也不会写 Flash。

安全检查
========
脚本在真正执行 esptool 前会检查：

1. Flash 频率必须为 26m；
2. Flash 容量必须采用类似 4MB、2MB、512KB 的格式；
3. 烧录偏移必须采用 0x... 格式；
4. 烧录文件路径不得逃逸出 build/auto 目录；
5. 烧录文件必须存在且不能为空；
6. 布局必须包含：
       bootloader/bootloader.bin
       partition_table/partition-table.bin
       ac_thermostat.bin
7. 任意烧录段不得超出 Flash 总容量；
8. 不同烧录文件占用的 4 KiB Flash 擦除 sector 不得重叠。

注意
====
ESP8266 Flash 的擦除单位为 4 KiB。

因此即使两个 BIN 的实际字节范围没有直接重叠，只要它们占用了同一个
4 KiB sector，也不能作为两个独立烧录段安全写入。本脚本会在执行 esptool
之前检测这种情况。

烧录完成后，本脚本不会自动复位 ESP-12F。请按提示退出下载模式并手动复位。
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# 项目路径
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "auto"
ESPTOOL = ROOT / "tools" / "esptool-v4.12.0" / "esptool.exe"


# ESP8266 Flash sector / erase block 最小单位：4 KiB
FLASH_SECTOR_SIZE = 4096


# flasher_args.json 中必须存在的关键烧录文件
REQUIRED = {
    "bootloader/bootloader.bin",
    "partition_table/partition-table.bin",
    "ac_thermostat.bin",
}


def parse_port(value):
    """检查 Windows COM 串口名称。"""
    if not re.fullmatch(r"COM[1-9][0-9]*", value, re.IGNORECASE):
        raise argparse.ArgumentTypeError(
            "端口格式应为 COM3、COM12 等 Windows 串口名"
        )

    return value.upper()


def parse_baud(value):
    """检查烧录波特率。"""
    try:
        baud = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("波特率必须为整数") from exc

    if not 9600 <= baud <= 921600:
        raise argparse.ArgumentTypeError(
            "波特率必须在 9600 到 921600 之间"
        )

    return baud


def align_down(value, alignment):
    """向下对齐到 alignment 边界。"""
    return value & ~(alignment - 1)


def align_up(value, alignment):
    """向上对齐到 alignment 边界。"""
    return (value + alignment - 1) & ~(alignment - 1)


def read_layout():
    """
    读取并检查 build/auto/flasher_args.json。

    返回：
        mode:
            Flash mode，例如 dio。

        size_text:
            Flash 容量，例如 4MB。

        freq:
            Flash 频率，本项目要求为 26m。

        segments:
            已按烧录偏移排序的列表：

            [
                (offset, name, path, size),
                ...
            ]
    """
    layout = BUILD / "flasher_args.json"

    if not layout.is_file():
        raise FileNotFoundError(
            "缺少 flasher_args.json；请先运行 python build.py"
        )

    try:
        config = json.loads(layout.read_text(encoding="utf-8"))

        settings = config["flash_settings"]
        files = config["flash_files"]

        mode = settings["flash_mode"]
        size_text = settings["flash_size"]
        freq = settings["flash_freq"]

    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(
            "flasher_args.json 无效或缺少 Flash 布局信息"
        ) from exc

    # -----------------------------------------------------------------------
    # 检查 Flash 参数
    # -----------------------------------------------------------------------

    if not all(
        isinstance(item, str) and item
        for item in (mode, size_text, freq)
    ):
        raise ValueError(
            "flasher_args.json 的 Flash 参数无效"
        )

    if freq != "26m":
        raise ValueError(
            f"Flash 频率应为 26m，实际为 {freq}；"
            "请重新运行 python build.py"
        )

    match = re.fullmatch(
        r"([1-9][0-9]*)(MB|KB)",
        size_text,
    )

    if not match:
        raise ValueError(
            f"不支持的 Flash 容量：{size_text}"
        )

    capacity = int(match[1])

    if match[2] == "MB":
        capacity *= 1024 * 1024
    else:
        capacity *= 1024

    if not isinstance(files, dict):
        raise ValueError(
            "flasher_args.json 的烧录文件列表无效"
        )

    if not files:
        raise ValueError(
            "flasher_args.json 的烧录文件列表为空"
        )

    # -----------------------------------------------------------------------
    # 检查各烧录文件
    # -----------------------------------------------------------------------

    segments = []
    build_root = BUILD.resolve()

    for offset_text, name in files.items():
        if (
            not isinstance(offset_text, str)
            or not re.fullmatch(r"0x[0-9a-fA-F]+", offset_text)
        ):
            raise ValueError(
                f"无效的烧录偏移：{offset_text}"
            )

        if not isinstance(name, str) or not name:
            raise ValueError(
                f"无效的烧录文件名：{name}"
            )

        path = (BUILD / name).resolve()

        # 防止 flasher_args.json 使用 ../ 等方式引用构建目录外的文件
        if not path.is_relative_to(build_root):
            raise ValueError(
                f"烧录文件超出构建目录：{name}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"缺少烧录文件：{path}；"
                "请先运行 python build.py"
            )

        size = path.stat().st_size

        if size <= 0:
            raise ValueError(
                f"烧录文件为空：{path}"
            )

        offset = int(offset_text, 16)

        segments.append(
            (offset, name, path, size)
        )

    # -----------------------------------------------------------------------
    # 检查关键文件
    # -----------------------------------------------------------------------

    normalized_names = {
        name.replace("\\", "/")
        for _, name, _, _ in segments
    }

    missing_required = REQUIRED - normalized_names

    if missing_required:
        missing_text = ", ".join(
            sorted(missing_required)
        )

        raise ValueError(
            "烧录布局缺少必需文件："
            f"{missing_text}"
        )

    # -----------------------------------------------------------------------
    # 按地址排序
    # -----------------------------------------------------------------------

    segments.sort(
        key=lambda item: item[0]
    )

    # -----------------------------------------------------------------------
    # 检查容量和 sector 重叠
    #
    # Flash 实际擦除以 4 KiB sector 为单位。
    #
    # 例如：
    #
    # 文件 A：
    #     0x1000 ～ 0x17FF
    #
    # 文件 B：
    #     0x1800 ～ 0x1FFF
    #
    # 字节范围虽然不重叠，但都位于 0x1000 ～ 0x1FFF sector，
    # 因此不能作为两个独立写入段安全处理。
    # -----------------------------------------------------------------------

    previous_sector_end = 0
    previous_name = None

    for offset, name, _, size in segments:
        end = offset + size

        if end > capacity:
            raise ValueError(
                f"烧录文件超出 Flash：{name}；"
                f"结束地址 0x{end:X}，"
                f"Flash 容量 0x{capacity:X}"
            )

        sector_start = align_down(
            offset,
            FLASH_SECTOR_SIZE,
        )

        sector_end = align_up(
            end,
            FLASH_SECTOR_SIZE,
        )

        if sector_start < previous_sector_end:
            raise ValueError(
                "烧录文件占用的 4 KiB Flash sector 重叠："
                f"{previous_name} 与 {name}"
            )

        previous_sector_end = sector_end
        previous_name = name

    return mode, size_text, freq, segments


def build_command(
    port,
    baud,
    mode,
    size_text,
    freq,
    segments,
):
    """生成 esptool write_flash 命令。"""
    command = [
        str(ESPTOOL),
        "--chip",
        "esp8266",
        "--port",
        port,
        "--baud",
        str(baud),
        "--before",
        "no_reset",
        "--after",
        "no_reset",
        "write_flash",
        "--flash_mode",
        mode,
        "--flash_size",
        size_text,
        "--flash_freq",
        freq,
    ]

    for offset, _, path, _ in segments:
        command.extend(
            (
                f"0x{offset:X}",
                str(path),
            )
        )

    return command


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--port",
        required=True,
        type=parse_port,
        help="Windows 串口，例如 COM3",
    )

    parser.add_argument(
        "--baud",
        type=parse_baud,
        default=115200,
        help="烧录波特率，默认 115200",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查 Flash 布局和 BIN 文件，不访问串口或写入 Flash",
    )

    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # 读取并检查本次构建生成的烧录布局
    # -----------------------------------------------------------------------

    print("[1/3] 检查本次构建的烧录配置", flush=True)
    print(f"  配置文件：{BUILD / 'flasher_args.json'}")
    mode, size_text, freq, segments = read_layout()

    print(
        f"  端口：{args.port}，波特率：{args.baud}；"
        f"Flash：{size_text}，模式：{mode}，频率：{freq}"
    )

    print(f"[2/3] 检查 {len(segments)} 个烧录分段及 4 KiB sector")

    for offset, name, _, size in segments:
        end = offset + size
        sector_start = align_down(
            offset,
            FLASH_SECTOR_SIZE,
        )
        sector_end = align_up(
            end,
            FLASH_SECTOR_SIZE,
        )

        print(
            f"  0x{offset:06X}  "
            f"{name}  "
            f"{size} 字节  "
            f"[sector 0x{sector_start:06X}"
            f"-0x{sector_end - 1:06X}]"
        )

    print("  仅写入上述分段；未覆盖的 NVS 区域保持原状")
    command = build_command(
        args.port,
        args.baud,
        mode,
        size_text,
        freq,
        segments,
    )
    print("[3/3] 准备执行烧录命令")
    print(f"  工具：{ESPTOOL}")
    print(f"  命令：{subprocess.list2cmdline(command)}")

    # -----------------------------------------------------------------------
    # dry-run 到此结束
    #
    # 不要求 esptool.exe 存在，也不会访问串口。
    # -----------------------------------------------------------------------

    if args.dry_run:
        print(
            "预检通过；dry-run 未检查工具文件，"
            "未访问串口或写入 Flash"
        )
        return

    # -----------------------------------------------------------------------
    # 真正烧录时才检查 esptool
    # -----------------------------------------------------------------------

    if not ESPTOOL.is_file():
        raise FileNotFoundError(
            f"找不到烧录工具：{ESPTOOL}"
        )

    print("开始执行 esptool；以下为工具原始输出：", flush=True)
    subprocess.run(
        command,
        check=True,
    )

    print(
        "烧录命令完成；"
        "请断开 P4 短接并复位设备"
    )


if __name__ == "__main__":
    try:
        main()

    except (
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(
            f"烧录失败：{exc}",
            file=sys.stderr,
        )

        if isinstance(
            exc,
            subprocess.CalledProcessError,
        ):
            sys.exit(exc.returncode)

        sys.exit(1)
