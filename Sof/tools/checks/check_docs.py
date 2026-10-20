"""Repository-tracked document checks: relative links, anchors and credentials.

The release audit that produced the v1.0F evidence lived only under the ignored
build/release_* directory, so a fresh clone could not reproduce it. This script
keeps the deterministic part in the repository; it needs no release baseline and
no network access. Markdown style rules are separate: see
tools/checks/markdownlint-cli2.jsonc and the command in Sof/README.md.
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

SOF = Path(__file__).resolve().parents[2]
ROOT = SOF.parent
MAX_LINES = 4800
EXCLUDED = ("Sof/vendor/", "esptool-v4.12.0", "flash_download_tool")
CREDENTIAL = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def tracked(pattern):
    names = subprocess.check_output(["git", "ls-files", "-z", pattern], cwd=ROOT)
    return [name for name in names.decode("utf-8").split("\0") if name]


def anchors(path):
    result, counts = set(), {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^#{1,6} ", line):
            continue
        title = re.sub(r"[^\w\-\s]", "", line.lstrip("# ").lower())
        slug = title.replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug + (f"-{count}" if count else ""))
    return result


def check_links(errors, name, path, text):
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        file, _, anchor = unquote(target).partition("#")
        resolved = (path.parent / file).resolve() if file else path
        if not resolved.exists():
            errors.append(f"{name}: 链接目标不存在 -> {target}")
        elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            errors.append(f"{name}: 锚点不存在 -> {target}")


def main():
    errors, docs = [], tracked("*.md")
    for name in docs:
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        check_links(errors, name, path, text)
        if CREDENTIAL.search(text):
            errors.append(f"{name}: 疑似凭据（不输出内容）")
    sources = []
    for pattern in ("*.c", "*.h", "*.py", "*.js"):
        sources.extend(tracked(pattern))
    checked = 0
    for name in sources:
        if any(token in name for token in EXCLUDED):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        checked += 1
        lines = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if lines > MAX_LINES:
            errors.append(f"{name}: 超过 {MAX_LINES} 行（{lines}）")
    for error in errors:
        print(error)
    print(f"文档 {len(docs)} 份、源码 {checked} 份：链接/锚点/凭据/行数检查"
          f"{'通过' if not errors else f'发现 {len(errors)} 项问题'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
