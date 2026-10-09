"""Actual build/flash helpers, with all files confined to ignored build output."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
import runpy
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import build
import flash
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import expose_timers

ROOT = Path(__file__).resolve().parents[1]


class ToolsTest(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "build" / "coverage" / "fixtures"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = {
            "flash_settings": {"flash_mode": "dio", "flash_size": "64KB", "flash_freq": "26m"},
            "flash_files": {"0x0": "bootloader/bootloader.bin",
                            "0x2000": "partition_table/partition-table.bin",
                            "0x4000": "ac_thermostat.bin"}}
        for name in self.config["flash_files"].values():
            path = self.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x01\x02\x03")

    def layout(self):
        (self.folder / "flasher_args.json").write_text(json.dumps(self.config), encoding="utf-8")
        with patch.object(flash, "BUILD", self.folder):
            return flash.read_layout()

    def image(self):
        (self.folder / "flasher_args.json").write_text(json.dumps(self.config), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            return build.write_full_images(self.folder)

    def test_layout_and_image(self):
        for capacity in ("64KB", "1MB"):
            self.config["flash_settings"]["flash_size"] = capacity
            mode, size, freq, segments = self.layout()
            self.assertEqual((mode, size, freq), ("dio", capacity, "26m"))
            self.assertEqual([s[0] for s in segments], [0, 8192, 16384])
        self.config["flash_settings"]["flash_size"] = "64KB"
        self.image()
        data = (self.folder / "full_flash.bin").read_bytes()
        self.assertEqual(len(data), 65536)
        for start in (0, 8192, 16384):
            self.assertEqual(data[start:start + 3], b"\x01\x02\x03")
        self.assertEqual(data[3:8192], b"\xff" * 8189)
        text = (self.folder / "full_flash.hex").read_text()
        decoded = bytearray()
        for line in text.splitlines():
            row = bytes.fromhex(line[1:])
            self.assertEqual(sum(row) & 255, 0)
            if row[3] == 0:
                decoded.extend(row[4:-1])
        self.assertEqual(decoded, data)
        self.assertTrue(text.endswith(":00000001FF\n"))

    def test_bad_settings(self):
        for key, value in [("flash_freq", "40m"), ("flash_mode", None),
                           ("flash_size", "0KB"), ("flash_size", "64GB")]:
            with self.subTest(key=key, value=value):
                old = self.config["flash_settings"][key]
                self.config["flash_settings"][key] = value
                with self.assertRaises(ValueError):
                    self.layout()
                self.config["flash_settings"][key] = old
        for files in ([], {}, {"bad": "ac_thermostat.bin"}, {"0x0": "../escape.bin"},
                      {"0x0": 3}, {"0x0": "missing.bin"}):
            with self.subTest(files=files):
                self.config["flash_files"] = files
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.layout()

    def test_missing_and_invalid_json(self):
        with patch.object(flash, "BUILD", self.folder):
            with self.assertRaises(FileNotFoundError):
                flash.read_layout()
            for text in ("{", "{}", "null", '{"flash_settings":null}'):
                (self.folder / "flasher_args.json").write_text(text)
                with self.assertRaises(ValueError):
                    flash.read_layout()

    def test_layout_conflicts(self):
        original = dict(self.config["flash_files"])
        for offset in ("0x1", "0x10000"):
            with self.subTest(offset=offset):
                self.config["flash_files"] = dict(original)
                del self.config["flash_files"]["0x4000"]
                self.config["flash_files"][offset] = "ac_thermostat.bin"
                with self.assertRaises(ValueError):
                    self.layout()
                with self.assertRaises(ValueError):
                    self.image()
        self.config["flash_files"] = original
        (self.folder / "ac_thermostat.bin").write_bytes(b"")
        with self.assertRaises(ValueError):
            self.layout()
        with self.assertRaises(ValueError):
            self.image()
        del self.config["flash_files"]["0x4000"]
        with self.assertRaises(ValueError):
            self.layout()
        with self.assertRaises(ValueError):
            self.image()

    def test_image_settings(self):
        for key, value in [("flash_freq", "40m"), ("flash_size", "0KB"),
                           ("flash_size", "64GB")]:
            old = self.config["flash_settings"][key]
            self.config["flash_settings"][key] = value
            with self.assertRaises(ValueError):
                self.image()
            self.config["flash_settings"][key] = old
        del self.config["flash_settings"]["flash_mode"]
        with self.assertRaises(ValueError):
            self.image()

    def test_arguments_and_tool_lookup(self):
        self.assertEqual(flash.parse_port("com12"), "COM12")
        for port in ("COM0", "COM-1", "COM", "ttyUSB0"):
            with self.assertRaises(argparse.ArgumentTypeError):
                flash.parse_port(port)
        for baud in ("9600", "921600"):
            self.assertEqual(flash.parse_baud(baud), int(baud))
        for baud in ("x", "9599", "921601"):
            with self.assertRaises(argparse.ArgumentTypeError):
                flash.parse_baud(baud)
        path = self.folder / "tool.exe"
        path.write_bytes(b"mock")
        self.assertEqual(build.find_tool(path, "unused"), path)
        with patch.object(build.shutil, "which", return_value=str(path)):
            self.assertEqual(build.find_tool(self.folder / "missing", "tool"), path)
        with patch.object(build.shutil, "which", return_value=None):
            with self.assertRaises(FileNotFoundError):
                build.find_tool(self.folder / "missing", "tool")

    def test_flash_execution_is_mocked(self):
        segments = self.layout()[3]
        tool = self.folder / "tool.exe"
        for exists in (False, True):
            if exists:
                tool.write_bytes(b"mock")
            with patch.object(flash.sys, "argv", ["flash.py", "--port", "COM3"]), \
                    patch.object(flash, "read_layout", return_value=("dio", "64KB", "26m", segments)), \
                    patch.object(flash, "ESPTOOL", tool), \
                    patch.object(flash.subprocess, "run") as run, redirect_stdout(io.StringIO()):
                if exists:
                    flash.main()
                    run.assert_called_once()
                    self.assertEqual(run.call_args.args[0][0], str(tool))
                    self.assertTrue(run.call_args.kwargs["check"])
                else:
                    with self.assertRaises(FileNotFoundError):
                        flash.main()
                    run.assert_not_called()

    def test_build_lifecycle(self):
        (self.folder / "main").mkdir()
        source = self.folder / "main/mock.c"
        source.write_text("/* fixture */")
        sdk = self.folder / "sdk"
        (sdk / "tools/cmake").mkdir(parents=True)
        sdk_entry = sdk / "tools/cmake/project.cmake"
        sdk_entry.write_text("")
        (self.folder / "bin").mkdir()
        compiler = self.folder / "bin/xtensa-lx106-elf-gcc.exe"
        compiler.write_bytes(b"mock")
        output = self.folder / "build/auto"
        output.mkdir(parents=True)
        for name in self.config["flash_files"].values():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"mock")
        (output / "flasher_args.json").write_text(json.dumps(self.config))
        config = self.folder / "sdkconfig"
        config.write_text("CONFIG_ESPTOOLPY_FLASHFREQ_26M=y\n")
        original_exists = Path.exists
        def free_drive(path):
            return False if path == self.folder else original_exists(path)
        with patch.object(build, "ROOT", self.folder), \
                patch.object(build, "DRIVE", str(self.folder)), \
                patch.object(build, "TOOLCHAIN", compiler.parent), \
                patch.dict(os.environ, {"IDF_PATH": str(sdk)}), \
                patch.object(build, "find_tool", return_value=self.folder / "tool.exe"), \
                patch.object(Path, "exists", free_drive), redirect_stdout(io.StringIO()):
            with patch.object(build.subprocess, "run") as run:
                build.main()
                self.assertEqual(run.call_count, 4)
                self.assertIn("12", run.call_args_list[2].args[0])
                self.assertEqual(run.call_args_list[-1].args[0][-1], "/D")
            def failed_config(args, **kwargs):
                if "-S" in args:
                    raise subprocess.CalledProcessError(2, args)
            with patch.object(build.subprocess, "run", side_effect=failed_config) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    build.main()
                self.assertEqual(run.call_args_list[-1].args[0][-1], "/D")
            config.write_text("CONFIG_ESPTOOLPY_FLASHFREQ_40M=y\n")
            with patch.object(build.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    build.main()
                self.assertEqual(run.call_args_list[-1].args[0][-1], "/D")
            config.write_text("CONFIG_ESPTOOLPY_FLASHFREQ_26M=y\n")
            (output / "ac_thermostat.bin").unlink()
            with patch.object(build.subprocess, "run") as run:
                with self.assertRaises(FileNotFoundError):
                    build.main()
                self.assertEqual(run.call_args_list[-1].args[0][-1], "/D")
            with patch.object(Path, "exists", original_exists):
                with self.assertRaises(FileExistsError):
                    build.main()
            compiler.unlink()
            with patch.object(build.shutil, "which", return_value=None):
                with self.assertRaises(FileNotFoundError):
                    build.main()
            with patch.object(build.shutil, "which", return_value=str(compiler)), \
                    patch.object(build.subprocess, "run"):
                with self.assertRaises(FileNotFoundError):
                    build.main()  # PATH fallback succeeds; missing application still fails.
            sdk_entry.unlink()
            with self.assertRaises(FileNotFoundError):
                build.main()
            source.unlink()
            with self.assertRaises(FileNotFoundError):
                build.main()

    def test_elf_sections(self):
        path = self.folder / "timer.o"
        names = b"\0.shstrtab\0.text\0.bss\0"
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<I", header, 32, 52)
        struct.pack_into("<HHH", header, 46, 40, 4, 1)
        rows = [(0,) * 10, (1, 3, 0, 0, 212, len(names), 0, 0, 1, 0),
                (11, 1, 6, 0, 212 + len(names), 3, 0, 0, 1, 0),
                (17, 8, 3, 0, 0, 4, 0, 0, 4, 0)]
        path.write_bytes(header + b"".join(struct.pack("<10I", *row) for row in rows) + names + b"abc")
        self.assertEqual(expose_timers.sections(path)[".text"], (1, 6, 3, b"abc"))
        self.assertEqual(expose_timers.sections(path)[".bss"], (8, 3, 4, b""))
        path.write_bytes(b"not ELF")
        with self.assertRaises(ValueError):
            expose_timers.sections(path)

    def test_timer_alias_integrity(self):
        lib = self.folder / "components/esp8266/lib"
        lib.mkdir(parents=True)
        for name in ("libcore.a", "libpp.a"):
            (lib / name).write_bytes(b"original")
        target = self.folder / "aliases"
        argv = ["expose_timers.py", "--sdk", str(self.folder), "--out", str(target),
                "--ar", "mock-ar", "--objcopy", "mock-objcopy"]
        sections = {".bss.s_timer_list": (8, 3, 4, b""),
                    ".bss.noise_test_timer": (8, 3, 28, b""), ".text": (1, 6, 3, b"abc")}
        with patch.object(sys, "argv", argv), patch.object(expose_timers.subprocess, "run") as run, \
                patch.object(expose_timers, "sections", return_value=sections), redirect_stdout(io.StringIO()):
            expose_timers.main()
            self.assertEqual(run.call_count, 6)
            self.assertEqual((target / "libcore.a").read_bytes(), b"original")
            for original in lib.glob("*.a"):
                self.assertEqual(original.read_bytes(), b"original")
        changed = dict(sections, **{".text": (1, 6, 3, b"xyz")})
        for responses in ([{}, sections], [sections, changed]):
            with patch.object(sys, "argv", argv), patch.object(expose_timers.subprocess, "run"), \
                    patch.object(expose_timers, "sections", side_effect=responses):
                with self.assertRaises(ValueError):
                    expose_timers.main()

    def test_alias_script_dispatch(self):
        lib = self.folder / "components/esp8266/lib"
        lib.mkdir(parents=True)
        for name in ("libcore.a", "libpp.a"):
            (lib / name).write_bytes(b"original")
        def mock_tool(args, **kwargs):
            if args[1] == "x":
                member = args[-1]
                section = ".bss.s_timer_list" if member == "ets_timer.o" else ".bss.noise_test_timer"
                size = 4 if member == "ets_timer.o" else 28
                names = b"\0.shstrtab\0" + section.encode() + b"\0"
                header = bytearray(52); header[:6] = b"\x7fELF\x01\x01"
                struct.pack_into("<I", header, 32, 52)
                struct.pack_into("<HHH", header, 46, 40, 3, 1)
                rows = [(0,) * 10, (1, 3, 0, 0, 172, len(names), 0, 0, 1, 0),
                        (11, 8, 3, 0, 0, size, 0, 0, 4, 0)]
                (Path(kwargs["cwd"]) / member).write_bytes(
                    header + b"".join(struct.pack("<10I", *row) for row in rows) + names)
            elif args[1] == "--add-symbol":
                Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())
        argv = ["expose_timers.py", "--sdk", str(self.folder), "--out", str(self.folder / "out"),
                "--ar", "mock-ar", "--objcopy", "mock-objcopy"]
        with patch.object(sys, "argv", argv), patch.object(subprocess, "run", side_effect=mock_tool) as run, \
                redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / "tools/expose_timers.py"), run_name="__main__")
            self.assertEqual(run.call_count, 6)

    def test_script_error_exit(self):
        path_exists = Path.exists
        for filename in ("flash.py", "build.py"):
            for error, expected in [(OSError("injected"), 1),
                                    (subprocess.CalledProcessError(9, ["mock"]), 9)]:
                with self.subTest(script=filename, error=type(error).__name__), \
                        patch.object(sys, "argv", [filename, "--port", "COM3"]), \
                        patch.object(subprocess, "run", side_effect=error), \
                        patch.object(Path, "exists", lambda path: False if str(path) == "Z:\\" else path_exists(path)), \
                        redirect_stdout(io.StringIO()), patch.object(sys, "stderr", io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        runpy.run_path(str(ROOT / filename), run_name="__main__")
                    self.assertEqual(raised.exception.code, expected)
        # Normal script dispatch also remains mocked: it cannot open a serial port.
        with patch.object(sys, "argv", ["flash.py", "--port", "COM3"]), \
                patch.object(subprocess, "run") as run, redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / "flash.py"), run_name="__main__")
            run.assert_called_once()

    def test_non_windows_rejected(self):
        with patch.object(build.os, "name", "posix"), redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                build.main()


if __name__ == "__main__":
    unittest.main()
