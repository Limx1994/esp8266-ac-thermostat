r"""构建 ESP8266 固件，并避开项目路径中的非 ASCII 字符。

使用方法（Windows PowerShell）：在项目目录运行 `python build.py`；无需设置环境变量。
从其他目录运行时，传入本脚本的绝对路径。默认使用下方配置的 SDK 和工具路径。
仅当 SDK 不在默认路径时，才需在当前 PowerShell 会话中临时设置
`$env:IDF_PATH = 'SDK 路径'`；其他工具找不到时会从 PATH 查找。
脚本只向构建子进程传递所需环境，不修改用户或系统环境变量。
运行前确保 Z: 盘符空闲。脚本会临时映射 Z:，产物保存在 build\auto\，
包括分段固件、full_flash.bin、full_flash.hex 和 flasher_args.json。
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
DRIVE = "Z:"
SDK = Path(r"D:\APPS\Espressif\frameworks\ESP8266_RTOS_SDK")
TOOLCHAIN = Path(
    r"D:\APPS\Espressif\tools\xtensa-lx106-elf"
    r"\esp-2020r3-49-gd5524c1-8.4.0\xtensa-lx106-elf\bin"
)
CMAKE = Path(r"D:\APPS\Espressif\tools\cmake\3.13.4\bin\cmake.exe")
NINJA = Path(r"D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe")
PYTHON = Path(r"D:\APPS\Espressif\python_env\idf5.2_py3.11_env\Scripts\python.exe")


def find_tool(default, name):
    if default.is_file():
        return default
    found = shutil.which(name)
    if found:
        return Path(found)
    raise FileNotFoundError(f"找不到 {name}；请按 ESP8266编译环境路径.md 配置工具链")


def hex_record(address, kind, data):
    record = bytes((len(data), address >> 8, address & 0xFF, kind)) + data
    return ":" + record.hex().upper() + f"{(-sum(record)) & 0xFF:02X}\n"


def write_full_images(build):
    config = json.loads((build / "flasher_args.json").read_text(encoding="utf-8"))
    try:
        settings = config["flash_settings"]
        size_text = settings["flash_size"]
        settings["flash_mode"]
        settings["flash_freq"]
        files = config["flash_files"]
    except (KeyError, TypeError) as exc:
        raise ValueError("flasher_args.json 缺少 Flash 布局信息") from exc
    if settings["flash_freq"] != "26m":
        raise ValueError(f"Flash 频率应为 26m，实际为 {settings['flash_freq']}")
    unit = size_text[-2:]
    if unit not in {"MB", "KB"}:
        raise ValueError(f"不支持的 Flash 容量：{size_text}")
    size = int(size_text[:-2]) * (1024 * 1024 if unit == "MB" else 1024)
    if size <= 0 or not files:
        raise ValueError("Flash 容量或烧录文件列表无效")
    required = {"bootloader/bootloader.bin", "partition_table/partition-table.bin", "ac_thermostat.bin"}
    if not required.issubset(name.replace("\\", "/") for name in files.values()):
        raise ValueError("烧录文件列表缺少 bootloader、partition table 或应用程序")

    image = bytearray(b"\xFF" * size)
    previous_end = 0
    segments = []
    for offset_text, name in sorted(files.items(), key=lambda item: int(item[0], 0)):
        offset = int(offset_text, 0)
        data = (build / name).read_bytes()
        end = offset + len(data)
        if not data or offset < previous_end or end > size:
            raise ValueError(f"烧录文件越界、重叠或为空：{name} @ {offset_text}")
        image[offset:end] = data
        previous_end = end
        segments.append((offset, name, len(data)))
        print(f"  写入布局：0x{offset:06X}  {name}  {len(data):,} 字节", flush=True)

    print(f"  生成完整镜像：{size_text}，未使用区域填充 0xFF", flush=True)
    (build / "full_flash.bin").write_bytes(image)
    with (build / "full_flash.hex").open("w", encoding="ascii", newline="\n") as output:
        for offset in range(0, size, 16):
            if offset % 0x10000 == 0:
                output.write(hex_record(0, 4, (offset >> 16).to_bytes(2, "big")))
            output.write(hex_record(offset & 0xFFFF, 0, bytes(image[offset:offset + 16])))
        output.write(hex_record(0, 1, b""))
    return settings, segments


def main():
    started = time.perf_counter()
    print("[1/4] 检查构建环境", flush=True)
    if os.name != "nt":
        raise OSError("此脚本需要 Windows 的 subst 命令")

    sources = sorted(
        path.name for path in (ROOT / "main").iterdir()
        if path.is_file() and path.suffix in {".c", ".cpp", ".S"}
    )
    if not sources:
        raise FileNotFoundError("main 目录中没有可编译的源文件")
    print(f"发现 {len(sources)} 个源文件：{', '.join(sources)}", flush=True)

    sdk = Path(os.environ.get("IDF_PATH") or SDK)
    if not (sdk / "tools" / "cmake" / "project.cmake").is_file():
        raise FileNotFoundError(f"无效的 IDF_PATH：{sdk}")
    cmake = find_tool(CMAKE, "cmake.exe")
    ninja = find_tool(NINJA, "ninja.exe")
    python = find_tool(PYTHON, "python.exe")
    toolchain = TOOLCHAIN if (TOOLCHAIN / "xtensa-lx106-elf-gcc.exe").is_file() else None
    if not toolchain and not shutil.which("xtensa-lx106-elf-gcc.exe"):
        raise FileNotFoundError("找不到 xtensa-lx106-elf-gcc.exe")
    subst = find_tool(Path(os.environ.get("SystemRoot", "")) / "System32" / "subst.exe", "subst.exe")
    print(f"  项目：{ROOT}\n  SDK：{sdk}\n  CMake：{cmake}\n  Ninja：{ninja}\n  Python：{python}\n  并行任务：12", flush=True)

    if Path(DRIVE + "\\").exists():
        raise FileExistsError(f"{DRIVE} 已被占用，无法映射项目目录")

    env = os.environ.copy()
    env["IDF_PATH"] = str(sdk)
    tool_dirs = [python.parent, cmake.parent, ninja.parent]
    if toolchain:
        tool_dirs.insert(0, toolchain)
    env["PATH"] = os.pathsep.join(str(path) for path in tool_dirs) + os.pathsep + env.get("PATH", "")

    mapped = Path(DRIVE + "\\")
    build = mapped / "build" / "auto"
    subprocess.run([str(subst), DRIVE, str(ROOT)], check=True)
    try:
        print(f"[2/4] 配置 CMake：{build}", flush=True)
        step_started = time.perf_counter()
        subprocess.run(
            [str(cmake), "-S", str(mapped), "-B", str(build), "-G", "Ninja",
             f"-DPYTHON_EXECUTABLE={python}"],
            env=env, check=True,
        )
        print(f"  CMake 配置完成，耗时 {time.perf_counter() - step_started:.1f} 秒", flush=True)
        config_lines = (ROOT / "sdkconfig").read_text(encoding="utf-8").splitlines()
        if "CONFIG_ESPTOOLPY_FLASHFREQ_26M=y" not in config_lines:
            raise ValueError("本地 sdkconfig 未设置 26 MHz Flash；请更新配置后重试")
        print("[3/4] 使用 Ninja 编译固件（-j 12）", flush=True)
        step_started = time.perf_counter()
        subprocess.run([str(ninja), "-C", str(build), "-j", "12"], env=env, check=True)
        print(f"  Ninja 编译完成，耗时 {time.perf_counter() - step_started:.1f} 秒", flush=True)
        print("[4/4] 检查固件并生成完整 Flash 镜像", flush=True)
        step_started = time.perf_counter()
        for name in (
            "ac_thermostat.bin",
            r"bootloader\bootloader.bin",
            r"partition_table\partition-table.bin",
        ):
            if not (build / name).is_file():
                raise FileNotFoundError(f"构建结束但缺少产物：{build / name}")
        settings, segments = write_full_images(build)
        print(f"  镜像生成完成，耗时 {time.perf_counter() - step_started:.1f} 秒", flush=True)
    finally:
        subprocess.run([str(subst), DRIVE, "/D"], check=True)
    output = ROOT / "build" / "auto"
    products = [(output / name, (output / name).stat().st_size) for name in
                ("full_flash.bin", "full_flash.hex", "flasher_args.json")]
    print(f"构建成功，总耗时 {time.perf_counter() - started:.1f} 秒", flush=True)
    print(f"Flash：{settings['flash_size']}，模式 {settings['flash_mode']}，频率 {settings['flash_freq']}", flush=True)
    print("烧录分段：", flush=True)
    for offset, name, size in segments:
        print(f"  0x{offset:06X}  {name}  {size:,} 字节", flush=True)
    print("产物：", flush=True)
    for path, size in products:
        print(f"  {path}  {size:,} 字节", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        sys.exit(exc.returncode if isinstance(exc, subprocess.CalledProcessError) else 1)
