"""Re-run the two probes already agreed by the review specialists."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SRC = ROOT / "Sof"
NINJA = Path(r"D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe")
CMAKE = Path(r"D:\APPS\Espressif\tools\cmake\3.13.4\bin\cmake.exe")


def run(args, folder, name):
    result = subprocess.run([str(arg) for arg in args], cwd=folder,
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    item = {"command": [str(arg) for arg in args], "cwd": str(folder),
            "exit": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr}
    (folder / name).write_text(json.dumps(item, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    return item


def ninja_probe():
    folder = OUT / "ninja_probe"
    folder.mkdir()
    for name in ("main", "tests", "build_ascii"):
        (folder / name).mkdir()
    for name in ("rules.c", "rules.h"):
        shutil.copy2(SRC / "main" / name, folder / "main" / name)
    for name in ("rules_test.c", "rules_cases.h", "build.ninja"):
        shutil.copy2(SRC / "tests" / name, folder / "tests" / name)
    cmd = [NINJA, "-f", "tests/build.ninja", "-j", "12"]
    first = run(cmd, folder, "initial_build.json")
    assert first["exit"] == 0, first
    header = folder / "tests" / "rules_cases.h"
    with header.open("a", encoding="utf-8") as stream:
        stream.write("\n#error review_header_changed\n")
    stamp = time.time() + 2
    os.utime(header, (stamp, stamp))
    stale = run(cmd, folder, "after_header.json")
    test = run([folder / "build_ascii" / "rules_test.exe"], folder,
               "stale_test.json")
    fresh = run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", "main", "-c", "tests/rules_test.c", "-o",
                 "build_ascii/fresh.o"], folder, "fresh_compile.json")
    assert stale["exit"] == 0 and "no work to do" in stale["stdout"], stale
    assert test["exit"] == 0, test
    assert fresh["exit"] != 0 and "review_header_changed" in fresh["stderr"], fresh
    return {"confirmed": True, "initial": first["exit"],
            "stale_ninja": stale["exit"], "stale_test": test["exit"],
            "fresh_compile": fresh["exit"], "evidence": str(folder)}


def driver_probe():
    folder = OUT / "driver_probe"
    folder.mkdir()
    local = folder / "components" / "esp8266"
    shutil.copytree(SRC / "components" / "esp8266", local)
    shadow = folder / "sdk" / "components" / "esp8266" / "lib"
    shadow.mkdir(parents=True)
    cmake_text = '''cmake_minimum_required(VERSION 3.5)
project(review_driver NONE)
set(esp8266_local_dir "${CMAKE_CURRENT_LIST_DIR}/components/esp8266")
set(review_shadow "${CMAKE_CURRENT_LIST_DIR}/sdk/components/esp8266/lib")
file(WRITE "${CMAKE_BINARY_DIR}/paths.txt" "")
foreach(blob core net80211 pp phy rtc espnow smartconfig)
  add_library(${blob} STATIC IMPORTED)
  set_property(TARGET ${blob} PROPERTY IMPORTED_LOCATION "${review_shadow}/lib${blob}.a")
  get_target_property(before ${blob} IMPORTED_LOCATION)
  file(APPEND "${CMAKE_BINARY_DIR}/paths.txt" "${blob}|before|${before}\\n")
endforeach()
include("${esp8266_local_dir}/driver.cmake")
file(APPEND "${CMAKE_BINARY_DIR}/paths.txt" "revision|${esp8266_driver_rev}\\n")
foreach(blob core net80211 pp phy rtc espnow smartconfig)
  get_target_property(after ${blob} IMPORTED_LOCATION)
  file(APPEND "${CMAKE_BINARY_DIR}/paths.txt" "${blob}|after|${after}\\n")
endforeach()
'''
    (folder / "CMakeLists.txt").write_text(cmake_text, encoding="utf-8")
    result = run([CMAKE, "-S", folder, "-B", folder / "build", "-G", "Ninja",
                  "-DCMAKE_MAKE_PROGRAM=" + str(NINJA)], folder, "configure.json")
    assert result["exit"] == 0, result
    lines = (folder / "build" / "paths.txt").read_text(encoding="utf-8").splitlines()
    paths = {}
    revision = None
    for line in lines:
        fields = line.split("|")
        if fields[0] == "revision":
            revision = fields[1]
        else:
            paths.setdefault(fields[0], {})[fields[1]] = fields[2]
    assert revision.startswith("858c7c2"), revision
    assert len(paths) == 7, paths
    for blob, pair in paths.items():
        assert Path(pair["before"]).resolve() == (shadow / ("lib" + blob + ".a")).resolve(), pair
        assert Path(pair["after"]).resolve() == (local / "lib" / ("lib" + blob + ".a")).resolve(), pair
    return {"confirmed": True, "configure_exit": result["exit"],
            "actual_revision": revision, "paths": paths,
            "boundary": "Candidate paths are placeholders; no download, complete evaluator run, or flashing.",
            "evidence": str(folder)}


if __name__ == "__main__":
    data = {"ninja": ninja_probe(), "driver": driver_probe()}
    (OUT / "reproductions.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
