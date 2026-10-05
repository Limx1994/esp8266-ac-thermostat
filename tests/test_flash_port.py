import unittest
from unittest.mock import MagicMock, patch

import flash


class FlashPortTest(unittest.TestCase):
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
