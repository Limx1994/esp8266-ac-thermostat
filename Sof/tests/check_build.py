"""直接检查构建产物和启动诊断；不插桩、不依赖覆盖工具、不访问设备。"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "build_check"
sys.path.insert(0, str(ROOT))
import flash


def check_startup():
    gcc = shutil.which("gcc")
    if not gcc:
        raise FileNotFoundError("启动诊断测试需要 PATH 中的 GCC")
    folder = OUT / "startup"
    (folder / "rom").mkdir(parents=True, exist_ok=True)
    (folder / "esp_log.h").write_text(
        '#pragma once\nvoid mock_log(const char *, const char *, ...);\n'
        '#define ESP_LOGI(...) mock_log(__VA_ARGS__)\n', encoding="utf-8")
    (folder / "esp_phy_init.h").write_text('typedef int phy_rf_module_t;\n', encoding="utf-8")
    (folder / "rom/uart.h").write_text('', encoding="utf-8")
    exe = folder / "startup_test.exe"
    subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(folder), "-I", str(ROOT / "main"),
                    str(ROOT / "tests/startup_test.c"), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
    print("启动诊断：通过", flush=True)


def check_products():
    mode, size, freq, segments = flash.read_layout()
    folder = ROOT / "build/auto"
    image = (folder / "full_flash.bin").read_bytes()
    capacity = int(size[:-2]) * (1024 * 1024 if size.endswith("MB") else 1024)
    if len(image) != capacity:
        raise AssertionError("完整镜像容量不匹配")
    end = 0
    for offset, name, path, length in segments:
        if image[end:offset] != b"\xff" * (offset - end):
            raise AssertionError(f"镜像间隙不是擦除态：{name}")
        if image[offset:offset + length] != path.read_bytes():
            raise AssertionError(f"镜像与分段不一致：{name}")
        end = offset + length
    if image[end:] != b"\xff" * (len(image) - end):
        raise AssertionError("镜像尾部不是擦除态")
    high = position = 0
    eof = False
    for line in (folder / "full_flash.hex").read_text(encoding="ascii").splitlines():
        if eof or not line.startswith(":"):
            raise AssertionError("HEX 记录边界无效")
        data = bytes.fromhex(line[1:])
        if len(data) != data[0] + 5 or sum(data) & 255:
            raise AssertionError("HEX 校验和或长度无效")
        address = int.from_bytes(data[1:3], "big")
        if data[3] == 4:
            if data[0] != 2:
                raise AssertionError("HEX 扩展地址长度无效")
            high = int.from_bytes(data[4:-1], "big") << 16
        elif data[3] == 0:
            if high + address != position or image[position:position + data[0]] != data[4:-1]:
                raise AssertionError("HEX 与 BIN 不一致")
            position += data[0]
        elif data[3] == 1:
            if data[0] != 0:
                raise AssertionError("HEX EOF 长度无效")
            eof = True
        else:
            raise AssertionError("HEX 记录类型不支持")
    if not eof or position != len(image):
        raise AssertionError("HEX 镜像不完整")
    app = (folder / "ac_thermostat.bin").read_bytes()
    magic = (0xABCD5432).to_bytes(4, "little")
    if app.count(magic) != 1:
        raise AssertionError("应用描述缺失或不唯一")
    offset = app.index(magic)
    version = app[offset + 16:offset + 48].split(b"\0", 1)[0].decode("ascii")
    expected = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    if version != expected:
        raise AssertionError(f"镜像版本不一致：{version}，预期 {expected}")
    print(f"镜像布局、BIN/HEX 和版本：通过（{version}，{mode}/{size}/{freq}）", flush=True)


def check_drivers():
    folder = ROOT / "components/esp8266/lib"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, info in manifest["archives"].items():
        data = (folder / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if hashlib.sha256(data).hexdigest() != info["sha256"] or blob != info["git_blob"]:
            raise AssertionError(f"固定驱动哈希不匹配：{name}")
    build = ROOT / "build/auto"
    app = (build / "build.ninja").read_text(encoding="utf-8").replace("\\", "/")
    boot = (build / "bootloader/build.ninja").read_text(encoding="utf-8").replace("\\", "/")
    app_links = " ".join(line for line in app.splitlines() if line.strip().startswith("LINK_LIBRARIES ="))
    boot_links = " ".join(line for line in boot.splitlines() if line.strip().startswith("LINK_LIBRARIES ="))
    for name in ("gcc", "hal", "net80211", "phy", "rtc", "clk", "smartconfig", "ssc", "espnow"):
        if f"../../components/esp8266/lib/lib{name}.a" not in app_links:
            raise AssertionError(f"应用未链接项目固定库：{name}")
    for name in ("core", "pp"):
        if f"noise_power/lib{name}.a" not in app_links:
            raise AssertionError(f"应用缺少固定库生成的定时器别名：{name}")
    if "Z:/components/esp8266/lib -lcore" not in boot_links:
        raise AssertionError("bootloader 未使用项目固定 core 库")
    for label, links in (("应用", app_links), ("bootloader", boot_links)):
        paths = re.findall(r"\S*components/esp8266/lib\S*", links)
        if any(not (path.startswith("../../components/") or path.startswith("Z:/components/")) for path in paths):
            raise AssertionError(f"{label} 存在外部 SDK 驱动引用：{paths}")
    print(f"应用与 bootloader 驱动来源：通过；{len(manifest['archives'])} 个固定文件哈希一致", flush=True)


if __name__ == "__main__":
    check_drivers()
    check_products()
    check_startup()
    print("构建与启动检查通过，失败 0、跳过 0；未烧录设备")
