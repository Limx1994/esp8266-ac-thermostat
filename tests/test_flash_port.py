from contextlib import redirect_stdout
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import flash


# mock 注册表和烧录子进程，验证串口选择及 dry-run 参数，不访问真实串口。
class FlashPortTest(unittest.TestCase):
    # 显式端口应跳过扫描；dry-run 应构造命令但不执行烧录。
    def check_baud(self, extra_args, expected):
        segments = [(0x10000, "ac_thermostat.bin",
                     Path("ac_thermostat.bin"), 4096)]
        with patch.object(flash.sys, "argv",
                          ["flash.py", "--port", "COM3", "--dry-run"]
                          + extra_args), \
                patch.object(flash, "read_layout",
                             return_value=("dio", "4MB", "26m", segments)), \
                patch.object(flash.winreg, "OpenKey",
                             side_effect=AssertionError("不应扫描串口")), \
                patch.object(flash.subprocess, "run") as run, \
                patch.object(flash, "build_command",
                             wraps=flash.build_command) as build, \
                redirect_stdout(io.StringIO()):
            flash.main()
        self.assertEqual(build.call_args.args[1], expected)
        command = build(*build.call_args.args)
        self.assertEqual(command[command.index("--baud") + 1], str(expected))
        run.assert_not_called()

    def test_default_fast_baud(self):
        self.check_baud([], 230400)

    def test_explicit_slow_baud(self):
        self.check_baud(["--baud", "115200"], 115200)

    # 通过模拟端口列表覆盖唯一选择和歧义拒绝分支。
    def check_ports(self, names, expected=None):
        key = MagicMock()
        with patch.object(flash.winreg, "OpenKey", return_value=key), \
                patch.object(flash.winreg, "QueryInfoKey",
                             return_value=(0, len(names), 0)), \
                patch.object(flash.winreg, "EnumValue",
                             side_effect=[(str(i), name, 1)
                                          for i, name in enumerate(names)]):
            if expected is None:
                with self.assertRaisesRegex(ValueError, "请用 --port 指定"):
                    flash.resolve_port(None)
            else:
                self.assertEqual(flash.resolve_port(None), expected)

    def test_selects_other_port(self):
        self.check_ports(["COM1", "com5"], "COM5")

    def test_rejects_ambiguous_ports(self):
        self.check_ports(["COM1"])
        self.check_ports(["COM2", "COM5"])
        self.check_ports(["COM1", "COM5", "COM6"])

    def test_explicit_port_skips_scan(self):
        with patch.object(flash.winreg, "OpenKey",
                          side_effect=AssertionError("不应扫描串口")):
            self.assertEqual(flash.resolve_port("COM9"), "COM9")

    def test_missing_port_list(self):
        with patch.object(flash.winreg, "OpenKey",
                          side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, "检测到：无"):
                flash.resolve_port(None)


if __name__ == "__main__":
    unittest.main()
