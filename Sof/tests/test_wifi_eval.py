"""Test the real driver evaluation tool; network, compiler and drive mapping are mocked."""
import argparse
import base64
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/wifi_driver_eval.py"


class WifiEvalTest(unittest.TestCase):
    def run_case(self, case="normal", latest=False, entry=False):
        parent = ROOT / "build/full_coverage/wifi_fixtures"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root = Path(directory)
            spec = importlib.util.spec_from_file_location("wifi_eval_tested", SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sdk = root / "sdk"
            libs = sdk / "components/esp8266/lib"
            libs.mkdir(parents=True)
            names = ["VERSION", "libpp.a", "libnet80211.a", "libpp_dbg.a", "libphy.a"]
            data = {n: (b"fixture-version" if n == "VERSION" else b"!<arch>\n" + n.encode())
                    for n in names}
            pins = {n: hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
                    for n, b in data.items()}
            for name in names:
                (libs / name).write_bytes(b"old-" + data[name])
            (libs / "keep.a").write_bytes(b"unchanged")
            for name in ("main", "components", "tools", "tests"):
                (root / name).mkdir()
                (root / name / "fixture.txt").write_text(name)
            component = root / "components/esp8266"
            component.mkdir()
            (component / "driver.cmake").write_text(
                'set(esp8266_driver_rev "production")\n' +
                '\n'.join('"' + n + '|' + '0' * 64 + '"' for n in names))
            for name in ("CMakeLists.txt", "sdkconfig", "sdkconfig.defaults", "version.txt"):
                (root / name).write_text("fixture")
            production = root / "build/auto"
            for name in ("ac_thermostat.bin", "ac_thermostat.elf", "full_flash.bin",
                         "bootloader/bootloader.bin", "partition_table/partition-table.bin",
                         "bootloader/config/sdkconfig.h"):
                p = production / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"production")
            out = root / ("build/wifi_driver_later" if latest else "build/wifi_driver_eval")
            if case == "cached":
                (out / "official").mkdir(parents=True)
                for name, value in data.items():
                    (out / "official" / name).write_bytes(value)
            module.ROOT = root
            module.OUT = out
            module.FILES = dict(pins)
            module.LATER_FILES = dict(pins)
            if case == "archive":
                data["libpp.a"] = b"invalid archive"
                pins["libpp.a"] = hashlib.sha1(b"blob 15\0" + data["libpp.a"]).hexdigest()
                module.FILES = dict(pins)
            nm_calls = []
            hooks = ("app_noise_timer", "app_ets_timer_head", "pp_noise_test",
                     "reset_noise_timer", "__wrap_os_timer_arm", "__wrap_esp_sleep_start")

            def output(command, **kwargs):
                if command[0] == "git":
                    return "wrong\n" if case == "revision" else module.BASE + "\n"
                nm_calls.append(command)
                if len(command) == 2:
                    return "" if case == "hooks" else "\n".join("0 T " + h for h in hooks)
                path = Path(command[-1])
                if path.name == "ac_thermostat.elf":
                    return "0 T phy_debug_print\n" if case == "used_phy" else "0 T app\n"
                old = path.parent == libs
                if command[2] == "--undefined-only":
                    return "         U imported\n"
                removed = case in ("removed", "used_phy", "phy_debug", "phy_other", "old_phy")
                symbol = "phy_debug_print" if case in ("used_phy", "phy_debug", "old_phy") else "lost"
                if removed and old and path.name == "libphy.a":
                    return "0 T retained\n0 T " + symbol + "\ninvalid\n"
                return "0 T retained\ninvalid\n"

            def network(request, timeout):
                self.assertEqual(timeout, 20)
                url = request.full_url
                if "api.github" in url:
                    name = next(n for n in names if pins[n] == url.rsplit("/", 1)[-1])
                    payload = {"encoding": "hex" if case == "encoding" else "base64",
                               "content": base64.b64encode(data[name]).decode()}
                    return io.BytesIO(json.dumps(payload).encode())
                name = url.rsplit("/", 1)[-1]
                if case in ("fallback", "encoding"):
                    raise urllib.error.URLError("injected offline")
                if case == "timeout":
                    raise TimeoutError("injected timeout")
                return io.BytesIO(b"wrong" if case == "hash" else data[name])

            def images(folder):
                (folder / "full_flash.bin").write_bytes(b"image")
                (folder / "full_flash.hex").write_bytes(b"hex")

            project = types.SimpleNamespace(ROOT=root, SDK=sdk, TOOLCHAIN=root / "bin",
                                            write_full_images=images)

            def build():
                if case == "build":
                    raise subprocess.CalledProcessError(7, "compiler-mock")
                selected = out / "components/esp8266"
                for name, value in data.items():
                    self.assertEqual((selected / "lib" / name).read_bytes(), value)
                    self.assertIn(hashlib.sha256(value).hexdigest(),
                                  (selected / "driver.cmake").read_text())
                self.assertIn(module.REV, (selected / "driver.cmake").read_text())
                folder = out / "build/auto"
                (folder / "bootloader/config").mkdir(parents=True)
                (folder / "bootloader/config/sdkconfig.h").write_bytes(
                    b"wrong" if case == "boot_config" else b"production")
                (folder / "ac_thermostat.bin").write_bytes(b"candidate")
                (folder / "ac_thermostat.elf").write_bytes(b"elf")
                link = "  LINK_LIBRARIES = ../../components/esp8266/lib/libnet80211.a noise_power/libcore.a noise_power/libpp.a"
                if case == "link_net":
                    link = "  LINK_LIBRARIES = ../../sdk/components/esp8266/lib/libnet80211.a noise_power/libcore.a noise_power/libpp.a"
                if case == "link_timer":
                    link = "  LINK_LIBRARIES = ../../components/esp8266/lib/libnet80211.a"
                (folder / "build.ninja").write_text(link)
                if case == "sdk_changed":
                    (libs / "keep.a").write_bytes(b"changed")
                if case == "production_changed":
                    (root / "sdkconfig").write_text("changed")
                if case == "snapshot_changed":
                    (out / "main/fixture.txt").write_text("changed")
                if case == "candidate_changed":
                    (selected / "lib/libnet80211.a").write_bytes(b"changed")

            project.main = build
            actual_copy = module.shutil.copytree

            def copytree(source, dest, *args, **kwargs):
                result = actual_copy(source, dest, *args, **kwargs)
                if case == "unrelated" and Path(source) == sdk:
                    (Path(dest) / "components/esp8266/lib/keep.a").write_bytes(b"changed")
                return result

            actual_exists = Path.exists

            def exists(path):
                return case == "drive" if str(path).replace("\\", "/").rstrip("/") == "Y:" else actual_exists(path)

            def arguments(*args, **kwargs):
                if entry:
                    scope = inspect.currentframe().f_back.f_globals
                    # unittest mock's frame is between parse_args and the actual main.
                    frame = inspect.currentframe().f_back
                    while frame.f_code.co_name != "main":
                        frame = frame.f_back
                    scope = frame.f_globals
                    scope.update(ROOT=root, OUT=out, FILES=dict(module.FILES),
                                 LATER_FILES=dict(module.LATER_FILES))
                return argparse.Namespace(latest=latest)

            with ExitStack() as stack, redirect_stdout(io.StringIO()):
                stack.enter_context(patch.object(argparse.ArgumentParser, "parse_args", side_effect=arguments))
                stack.enter_context(patch.object(module.subprocess, "check_output", side_effect=output))
                mapper = stack.enter_context(patch.object(module.subprocess, "run"))
                stack.enter_context(patch.object(module.urllib.request, "urlopen", side_effect=network))
                stack.enter_context(patch.object(module.shutil, "copytree", side_effect=copytree))
                stack.enter_context(patch.object(Path, "exists", exists))
                stack.enter_context(patch.dict(os.environ, {"SystemRoot": "C:\\Windows"}))
                if case == "no_env":
                    stack.enter_context(patch.dict(os.environ))
                    os.environ.pop("IDF_PATH", None)
                else:
                    stack.enter_context(patch.dict(os.environ, {"IDF_PATH": str(sdk)}))
                stack.enter_context(patch.object(module.importlib.util, "spec_from_file_location",
                                                wraps=importlib.util.spec_from_file_location))
                actual_load = module.load_module
                # Keep the actual loader covered while supplying a safe build module.
                fixture = root / "project_fixture.py"
                fixture.write_text("value = 1\n")
                self.assertEqual(actual_load("fixture", fixture).value, 1)
                stack.enter_context(patch.object(module.importlib.util, "module_from_spec",
                                                return_value=project))
                fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda mod: None))
                stack.enter_context(patch.object(module.importlib.util, "spec_from_file_location",
                                                return_value=fake_spec))
                errors = {"revision", "hash", "archive", "encoding", "unrelated", "removed",
                          "used_phy", "phy_other", "old_phy", "drive", "build", "boot_config",
                          "link_net", "link_timer", "hooks", "sdk_changed", "production_changed",
                          "snapshot_changed", "candidate_changed"}
                if case in errors:
                    with self.assertRaises((ValueError, FileExistsError, subprocess.CalledProcessError)):
                        if entry:
                            runpy.run_path(str(SOURCE), run_name="__main__")
                        else:
                            module.main()
                    if entry and (out / "validation.json").is_file():
                        result = json.loads((out / "validation.json").read_text())
                        self.assertEqual(result["status"], "failed")
                else:
                    if entry:
                        runpy.run_path(str(SOURCE), run_name="__main__")
                    else:
                        module.main()
                    result = json.loads((out / "validation.json").read_text())
                    self.assertEqual(result["status"], "built; regressions pending")
                    self.assertTrue(result["installed_sdk_unchanged"] and result["production_unchanged"])
                    self.assertEqual(result["ninja_jobs"], 12)
                    self.assertEqual(mapper.call_count, 2)
                if case == "build":
                    self.assertEqual(mapper.call_count, 2)  # Mapping is released on build error.

    def test_scenarios(self):
        for case in ("normal", "cached", "fallback", "timeout", "no_env", "revision", "hash",
                     "archive", "encoding", "unrelated", "removed", "drive", "build", "boot_config",
                     "link_net", "link_timer", "hooks", "sdk_changed", "production_changed",
                     "snapshot_changed", "candidate_changed", "old_phy"):
            with self.subTest(case=case):
                self.run_case(case)
        for case in ("normal", "phy_debug", "used_phy", "phy_other"):
            with self.subTest(case=case, latest=True):
                self.run_case(case, latest=True)

    def test_entry(self):
        for case in ("normal", "revision", "hash"):
            with self.subTest(case=case):
                self.run_case(case, entry=True)


if __name__ == "__main__":
    unittest.main()
