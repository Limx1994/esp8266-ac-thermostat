r"""Build a production-function evaluation with pinned official WiFi archives.

Run from Sof: python tools\wifi_driver_eval.py
默认及 --latest 均只使用固定新驱动；不修改已安装 SDK 或生产构建。
"""
import hashlib
import argparse
import base64
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import urllib.request
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "wifi_driver_eval"
BASE = "89a3f254b63819035f65d9c5dcdae8864f1a6a8a"
REV = "858c7c2eb9004691f2c736c64a23715f6ea900c4"
FILES = {
    "VERSION": "2873e0c84d99387b79a09890f9f305ebfb797690",
    "libclk.a": "fb911f79fcbee5f59abd9a57a392d5e34b23b2f5",
    "libgcc.a": "050268e658b2360f06a7611a192c429f3fe5ac89",
    "libhal.a": "9408dec005663767163381d31ad449491d7b0c96",
    "libssc.a": "b9918d9973b4f070fa6456bbf11c71d075ed6fd2",
    "libcore.a": "8beb25fae1a526487b1312062de4712ec4ad02ad",
    "libcore_dbg.a": "45b00afe0339b849dc96a0e44addc88d216827f1",
    "libespnow.a": "e1af2020a78dd5130e4fbc29d273d01f8286d6c9",
    "libespnow_dbg.a": "2c7346c7b2ebafcbda4395a36e780b5abc29f8ae",
    "libnet80211.a": "a6da69b90208784affb1c44ff31cc16d5cd6c0fb",
    "libnet80211_dbg.a": "d74f6f5c7e3c6b3c0b390eb994dab44b0c42b2ce",
    "libphy.a": "6f3b75e9339546b4d1535c352c244a1d18e87ba0",
    "libpp.a": "de933338008d632ae1cd57625263054666ce821e",
    "libpp_dbg.a": "89786fcc466bec7518209ace1d3871838d0a609b",
    "librtc.a": "8a809ee92b3658556bae4eed725fe3043991fbd1",
    "libsmartconfig.a": "cdadb3a398e749ebe49d0c24e5863c709d4fcb6a",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_text(command):
    return subprocess.check_output(command, text=True, encoding="utf-8")


def file_hashes(folder):
    return {p.relative_to(folder).as_posix(): sha256(p)
            for p in folder.rglob("*") if p.is_file()}


def read_symbols(nm, archive, defined):
    flag = "--defined-only" if defined else "--undefined-only"
    result = set()
    for row in run_text([str(nm), "-g", flag, str(archive)]).splitlines():
        parts = row.split()
        if len(parts) >= 2 and len(parts[-2]) == 1:
            result.add(parts[-1])
    return result


def install_driver(candidate_lib, component, revision):
    """Pin the evaluation component and timer aliases to the same SDK snapshot."""
    shutil.copytree(candidate_lib, component / "lib", dirs_exist_ok=True)
    driver = component / "driver.cmake"
    text = driver.read_text(encoding="utf-8")
    text = re.sub(r'(set\(esp8266_driver_rev ")[^"]+("\))',
                  lambda m: m[1] + revision + m[2], text)
    text = re.sub(r'"([^"|]+)\|[0-9a-f]{64}"',
                  lambda m: '"' + m[1] + '|' + sha256(candidate_lib / m[1]) + '"', text)
    text = text.replace("; PHY 1167.0", "")
    driver.write_text(text, encoding="utf-8")


def main():
    global OUT, REV, FILES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest", action="store_true",
                        help="兼容旧命令；默认与此选项均使用固定 858c7c2 新驱动")
    args = parser.parse_args()
    if args.latest:
        OUT = ROOT / "build" / "wifi_driver_later"
    project = load_module("project_build", ROOT / "build.py")
    sdk = Path(os.environ.get("IDF_PATH") or project.SDK)
    if (sdk / "manifest.json").is_file():
        actual = project.verify_sdk(sdk)
    else:
        actual = run_text(["git", "-C", str(sdk), "rev-parse", "HEAD"]).strip()
    if actual != BASE:
        raise ValueError(f"Expected SDK {BASE}; got {actual}")
    local_lib = sdk / "components/esp8266/lib"
    sdk_before = file_hashes(local_lib)
    saved = {str(p): sha256(p) for p in (
        ROOT / "sdkconfig", ROOT / "build/auto/ac_thermostat.bin",
        ROOT / "build/auto/full_flash.bin", ROOT / "build/auto/bootloader/bootloader.bin",
        ROOT / "build/auto/partition_table/partition-table.bin")}
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "validation.json"
    report = {"status": "preparing", "base_sdk": BASE,
              "official_driver_commit": REV, "ninja_jobs": 12,
              "hardware": "pending", "scope": "Official binary archives only; SDK C sources retained"}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[1/4] Copy SDK and application into project-local evaluation", flush=True)
    shadow = OUT / "sdk"
    shutil.copytree(sdk, shadow, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "docs",
                                                 "examples", ".github"))
    # Supply the SDK version without inheriting the application's Git version.
    (shadow / "version.txt").write_text("v3.4-wifi-" + REV[:7] + "\n", encoding="ascii")
    for name in ("main", "components", "tools", "tests"):
        shutil.copytree(ROOT / name, OUT / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("CMakeLists.txt", "sdkconfig", "sdkconfig.defaults", "version.txt"):
        shutil.copy2(ROOT / name, OUT / name)
    print("[2/4] Verify and install pinned upstream archives in local SDK", flush=True)
    downloads = OUT / "official"
    downloads.mkdir(exist_ok=True)
    manifest = {}
    for name, expected in FILES.items():
        url = ("https://raw.githubusercontent.com/espressif/ESP8266_RTOS_SDK/"
               + REV + "/components/esp8266/lib/" + name)
        request = urllib.request.Request(url, headers={"User-Agent": "Codex-research"})
        cached = downloads / name
        if cached.is_file():
            data = cached.read_bytes()
        else:
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = response.read()
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"Raw download failed for {name}: {exc}; trying official Git blob API once", flush=True)
                blob_url = ("https://api.github.com/repos/espressif/ESP8266_RTOS_SDK/git/blobs/"
                            + expected)
                fallback = urllib.request.Request(blob_url, headers={"User-Agent": "Codex-research"})
                with urllib.request.urlopen(fallback, timeout=20) as response:
                    payload = json.load(response)
                if payload.get("encoding") != "base64":
                    raise ValueError(f"Unsupported Git blob encoding: {name}")
                data = base64.b64decode(payload["content"])
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != expected:
            raise ValueError(f"Official Git blob mismatch: {name}: {blob}")
        if name.endswith(".a") and not data.startswith(b"!<arch>\n"):
            raise ValueError(f"Not an archive: {name}")
        (downloads / name).write_bytes(data)
        (shadow / "components/esp8266/lib" / name).write_bytes(data)
        manifest[name] = {"url": url, "git_blob": blob, "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()}
    candidate_lib = shadow / "components/esp8266/lib"
    for name, digest in sdk_before.items():
        if name not in FILES and sha256(candidate_lib / name) != digest:
            raise ValueError(f"Unrelated SDK archive changed: {name}")
    install_driver(candidate_lib, OUT / "components/esp8266", REV)
    source_hashes = {name: file_hashes(OUT / name)
                     for name in ("main", "components", "tools")}
    report["source_snapshot"] = source_hashes
    nm = project.TOOLCHAIN / "xtensa-lx106-elf-nm.exe"
    abi = {}
    libraries = [name for name in FILES if name.endswith(".a") and "_dbg" not in name]
    used_exports = read_symbols(nm, ROOT / "build/auto/ac_thermostat.elf", True)
    candidate_undefined = set()
    for name in libraries:
        candidate_undefined.update(read_symbols(nm, candidate_lib / name, False))
    for name in libraries:
        old_defs = read_symbols(nm, local_lib / name, True)
        new_defs = read_symbols(nm, candidate_lib / name, True)
        removed = sorted(old_defs - new_defs)
        # Upstream PHY removed two debug/test exports. Neither is in the actual
        # application ELF, SDK C/header callers, or candidate library imports.
        debug_removed = set(removed) <= {"phy_debug_print", "rx_blocking_test"}
        unused = not set(removed) & (used_exports | candidate_undefined)
        if removed and not (name == "libphy.a" and debug_removed and unused):
            raise ValueError(f"Exported symbols removed: {name}: {removed}")
        abi[name] = {"exports_removed": removed,
                     "removal_check": "unused PHY debug/test exports only" if removed else "none",
                     "exports_added": sorted(new_defs - old_defs),
                     "new_undefined": sorted(read_symbols(nm, candidate_lib / name, False)
                                             - read_symbols(nm, local_lib / name, False))}
    report.update(archives=manifest, symbol_checks=abi, status="building")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if (shadow / "manifest.json").is_file():
        snapshot = json.loads((shadow / "manifest.json").read_text(encoding="utf-8"))
        for name in FILES:
            snapshot["files"]["components/esp8266/lib/" + name] = sha256(shadow / "components/esp8266/lib" / name)
        snapshot["files"]["version.txt"] = sha256(shadow / "version.txt")
        (shadow / "manifest.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    # Reuse build.py's environment, drive mapping, Ninja and image generation.
    print("[3/4] Build the full application using existing build.py", flush=True)
    project.ROOT = OUT
    # build.py checks IDF_PATH before mapping Z:. Give the SDK its own ASCII
    # drive so both that check and the Xtensa compiler can resolve it.
    if Path("Y:/").exists():
        raise FileExistsError("Y: is occupied")
    subst = Path(os.environ["SystemRoot"]) / "System32/subst.exe"
    subprocess.run([str(subst), "Y:", str(OUT)], check=True)
    project.SDK = Path("Y:/sdk")
    previous = os.environ.pop("IDF_PATH", None)
    try:
        project.main()
    finally:
        if previous is not None:
            os.environ["IDF_PATH"] = previous
        subprocess.run([str(subst), "Y:", "/D"], check=True)
    print("[4/4] Check actual linked archives and unchanged source/SDK", flush=True)
    build = OUT / "build/auto"
    # SDK version/path metadata can change the newly built bootloader. This
    # evaluation only updates WiFi in the application, so retain the existing
    # bootloader after checking identical bootloader configuration. Application
    # driver libraries are not linked into this retained bootloader image.
    config_name = "bootloader/config/sdkconfig.h"
    if (build / config_name).read_bytes() != (ROOT / "build/auto" / config_name).read_bytes():
        raise ValueError("Bootloader configuration differs; refusing image reuse")
    shutil.copy2(ROOT / "build/auto/bootloader/bootloader.bin",
                 build / "bootloader/bootloader.bin")
    project.write_full_images(build)
    link = (build / "build.ninja").read_text(encoding="utf-8")
    linked = [token for line in link.replace("\\", "/").splitlines()
              if line.strip().startswith("LINK_LIBRARIES =") for token in line.split()[2:]]
    if "../../components/esp8266/lib/libnet80211.a" not in linked:
        raise ValueError("Candidate net80211 archive missing from linker inputs")
    if not all("noise_power/lib" + name + ".a" in linked for name in ("core", "pp")):
        raise ValueError("Timer alias archive missing from linker inputs")
    for name, info in manifest.items():
        if sha256(OUT / "components/esp8266/lib" / name) != info["sha256"]:
            raise ValueError(f"Linked candidate archive changed: {name}")
    elf_symbols = run_text([str(nm), str(build / "ac_thermostat.elf")])
    for symbol in ("app_noise_timer", "app_ets_timer_head", "pp_noise_test",
                   "reset_noise_timer", "__wrap_os_timer_arm", "__wrap_esp_sleep_start"):
        if not any(row.split()[-1:] == [symbol] for row in elf_symbols.splitlines()):
            raise ValueError(f"Required timer hook missing: {symbol}")
    if file_hashes(local_lib) != sdk_before:
        raise ValueError("Installed SDK archives changed")
    for path, digest in saved.items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"Production input/output changed: {path}")
    for name, hashes in source_hashes.items():
        if file_hashes(OUT / name) != hashes:
            raise ValueError(f"Application snapshot changed during build: {name}")
    report.update(status="built; regressions pending", installed_sdk_unchanged=True,
                  bootloader="production image reused; identical bootloader config",
                  production_unchanged=True, timer_hooks="linked; storage aliases verified",
                  artifacts={name: {"sha256": sha256(build / name),
                                    "bytes": (build / name).stat().st_size}
                             for name in ("ac_thermostat.bin", "full_flash.bin",
                                          "full_flash.hex")})
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items()
                      if key != "source_snapshot"}, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        path = OUT / "validation.json"
        if path.is_file():
            report = json.loads(path.read_text(encoding="utf-8"))
            report.update(status="failed", error=str(exc))
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise
