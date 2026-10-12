"""Verify real CMake pin selection and Ninja header rebuilding in local fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "repair_validation"
NINJA = r"D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe"
CMAKE = r"D:\APPS\Espressif\tools\cmake\3.13.4\bin\cmake.exe"


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return {"command": command, "exit": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    OUT.mkdir(exist_ok=True)
    records = {}
    with tempfile.TemporaryDirectory(dir=OUT) as directory:
        folder = Path(directory)
        for name in ("main", "tests", "build_ascii"):
            (folder / name).mkdir()
        for name in ("rules.c", "rules.h"):
            shutil.copy2(ROOT / "Sof/main" / name, folder / "main" / name)
        for name in ("rules_test.c", "rules_cases.h", "build.ninja"):
            shutil.copy2(ROOT / "Sof/tests" / name, folder / "tests" / name)
        command = [NINJA, "-f", "tests/build.ninja", "-j", "12"]
        records["ninja_initial"] = run(command, folder)
        assert records["ninja_initial"]["exit"] == 0
        records["ninja_unchanged"] = run(command, folder)
        assert "no work to do" in records["ninja_unchanged"]["stdout"]
        header = folder / "tests/rules_cases.h"
        original = header.read_bytes()
        header.write_bytes(original + b"\n#error header_dependency_verified\n")
        records["ninja_header"] = run(command, folder)
        assert records["ninja_header"]["exit"] != 0
        assert "header_dependency_verified" in records["ninja_header"]["stdout"]
        header.write_bytes(original)
        records["ninja_recovered"] = run(command, folder)
        assert records["ninja_recovered"]["exit"] == 0
        records["rules_test"] = run([str(folder / "build_ascii/rules_test.exe")], folder)
        assert records["rules_test"]["exit"] == 0
        local = folder / "components/esp8266"
        shutil.copytree(ROOT / "Sof/components/esp8266", local)
        spec = importlib.util.spec_from_file_location("eval_tool", ROOT / "Sof/tools/wifi_driver_eval.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        candidate = Path(r"D:\APPS\Espressif\frameworks\ESP8266_RTOS_SDK\components\esp8266\lib")
        tool.install_driver(candidate, local, tool.BASE)
        shutil.copy2(OUT.parent / "driver_probe/CMakeLists.txt", folder / "CMakeLists.txt")
        assert not Path("Y:/").exists(), "Y: occupied"
        subst = str(Path(os.environ["SystemRoot"]) / "System32/subst.exe")
        subprocess.run([subst, "Y:", str(folder)], check=True)
        try:
            records["driver_configure"] = run([CMAKE, "-S", "Y:/", "-B", "Y:/build",
                                              "-G", "Ninja", "-DCMAKE_MAKE_PROGRAM=" + NINJA], folder)
        finally:
            subprocess.run([subst, "Y:", "/D"], check=True)
        assert records["driver_configure"]["exit"] == 0
        paths = (folder / "build/paths.txt").read_text()
        assert "revision|" + tool.BASE in paths
        for name in ("core", "net80211", "pp", "phy", "rtc", "espnow", "smartconfig"):
            actual = local / "lib" / ("lib" + name + ".a")
            assert tool.sha256(actual) == tool.sha256(candidate / actual.name)
            row = next(line for line in paths.splitlines() if line.startswith(name + "|after|"))
            selected = Path(row.split("|", 2)[2].replace("Y:/", folder.as_posix() + "/"))
            assert selected.resolve() == actual.resolve(), (selected, actual, paths)
        records["driver_paths"] = paths
        records["boundary"] = "Real installed SDK archives used as selected-source fixture; no remote candidate download, complete evaluation or flashing."
    (OUT / "results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ninja header rebuild and real CMake selected-library/hash probes passed")


if __name__ == "__main__":
    main()
