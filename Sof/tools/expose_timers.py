"""Add aliases to SDK timer storage in build-local archive copies only."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess


def sections(path):
    data = path.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        raise ValueError("SDK timer object must be ELF32 little-endian")
    offset = struct.unpack_from("<I", data, 32)[0]
    stride, count, strings = struct.unpack_from("<HHH", data, 46)
    rows = [struct.unpack_from("<10I", data, offset + i * stride) for i in range(count)]
    names = rows[strings]
    names = data[names[4]:names[4] + names[5]]
    result = {}
    for row in rows:
        name = names[row[0]:].split(b"\0", 1)[0].decode()
        result[name] = (row[1], row[2], row[5],
                        b"" if row[1] == 8 else data[row[4]:row[4] + row[5]])
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("sdk", "out", "ar", "objcopy"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    library_dir = Path(args.sdk) / "components/esp8266/lib"
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    entries = [("core", "ets_timer.o", ".bss.s_timer_list", 4, "app_ets_timer_head"),
               ("pp", "pp.o", ".bss.noise_test_timer", 28, "app_noise_timer")]
    for library, member, section, size, alias in entries:
        original = library_dir / ("lib" + library + ".a")
        copied = output / original.name
        shutil.copy2(original, copied)
        work = output / library
        work.mkdir(exist_ok=True)
        subprocess.run([args.ar, "x", str(original), member], cwd=work, check=True)
        obj = work / member
        before = sections(obj)
        if section not in before or before[section][:3] != (8, 3, size):
            raise ValueError(f"unsupported SDK timer storage layout: {section}")
        patched = work / "patched"
        patched.mkdir(exist_ok=True)
        modified = patched / member
        subprocess.run([args.objcopy, "--add-symbol", alias + "=" + section + ":0,global,object",
                        str(obj), str(modified)], check=True)
        after = sections(modified)
        for name, row in before.items():
            if row[1] & 2 and after.get(name) != row:
                raise ValueError(f"SDK allocated section changed: {name}")
        subprocess.run([args.ar, "r", str(copied), str(modified)], check=True)
        print(f"Exposed {alias}; SDK code/data sections unchanged")


if __name__ == "__main__":
    main()
