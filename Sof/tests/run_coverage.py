"""Run real-source host tests and retain coverage gaps, without flashing hardware.

Run from Sof: python tests\run_coverage.py
Python coverage must be installed in build/coverage/packages or the environment.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "coverage"
sys.path[:0] = [str(ROOT), str(OUT / "packages")]
import coverage

REAL_RUN = subprocess.run
RECORDS = []
OBJECTS = []


def profiles(folder, stem, suffix):
    return list(folder.glob(stem + "-*" + suffix)) + list(folder.glob(stem + suffix))


def execute(args, **kwargs):
    """Each executable gets fresh, isolated profile data on every invocation."""
    args = [str(arg) for arg in args]
    if Path(args[0]).name.lower() in ("gcc", "gcc.exe"):
        args[1:1] = ["--coverage", "-O0", "-fprofile-abs-path"]
        exe = Path(args[args.index("-o") + 1])
        for old in profiles(exe.parent, exe.stem, ".gc*"):
            old.unlink()
        for old in profiles(OUT / "profiles", exe.stem, ".gcda"):
            old.unlink()
        OBJECTS.append(exe)
    if Path(args[0]).suffix.lower() == ".exe" and Path(args[0]) in OBJECTS:
        env = os.environ.copy()
        env.update(kwargs.pop("env", {}))
        env["GCOV_PREFIX"] = "build/coverage/profiles"
        env["GCOV_PREFIX_STRIP"] = "99"
        kwargs["env"] = env
    result = REAL_RUN(args, **kwargs)
    if Path(args[0]) in OBJECTS:
        exe = Path(args[0])
        data_files = profiles(OUT / "profiles", exe.stem, ".gcda")
        if not data_files:
            raise AssertionError(f"Missing runtime coverage: {exe}")
        for data in data_files:
            shutil.copy2(data, exe.parent / data.name)
            data.unlink()
    return result


def check(name, fn):
    try:
        fn()
    except Exception as exc:
        RECORDS.append({"name": name, "status": "failed", "error": str(exc)})
        print(f"FAIL {name}: {exc}", flush=True)
    else:
        RECORDS.append({"name": name, "status": "passed"})
        print(f"PASS {name}", flush=True)


def script(name):
    runpy.run_path(str(ROOT / "tests" / name), run_name="__main__")


def python_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), "test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    RECORDS.append({"name": "Python 单测计数", "status": "passed" if result.wasSuccessful() else "failed",
                    "kind": "summary",
                    "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)})
    if not result.wasSuccessful():
        raise AssertionError(f"{len(result.failures)} failures, {len(result.errors)} errors")
    for test, reason in result.skipped:
        RECORDS.append({"name": str(test), "status": "skipped", "reason": reason})


def rules():
    exe = OUT / "rules_test.exe"
    execute([shutil.which("gcc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", ROOT / "main", ROOT / "main/rules.c",
             ROOT / "tests/rules_test.c", "-o", exe], check=True, cwd=ROOT)
    execute([str(exe)], check=True, cwd=ROOT)


def startup():
    folder = OUT / "startup"
    (folder / "rom").mkdir(parents=True, exist_ok=True)
    (folder / "esp_log.h").write_text(
        '#pragma once\nvoid mock_log(const char *, const char *, ...);\n'
        '#define ESP_LOGI(...) mock_log(__VA_ARGS__)\n', encoding="utf-8")
    (folder / "esp_phy_init.h").write_text('typedef int phy_rf_module_t;\n', encoding="utf-8")
    (folder / "rom/uart.h").write_text('', encoding="utf-8")
    exe = folder / "startup_test.exe"
    execute([shutil.which("gcc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", folder, "-I", ROOT / "main", ROOT / "tests/startup_test.c",
             "-o", exe], check=True, cwd=ROOT)
    execute([str(exe)], check=True, cwd=ROOT)


def collect_c():
    files = {}
    variants = []
    for exe in OBJECTS:
        for data in profiles(exe.parent, exe.stem, ".gcda"):
            result = REAL_RUN(["gcov", "-j", "-b", "-c", data.name],
                              check=True, cwd=data.parent, capture_output=True, text=True)
            (OUT / (data.stem + ".gcov.log")).write_text(result.stdout + result.stderr,
                                                        encoding="utf-8")
            archive = data.parent / (data.stem + ".gcov.json.gz")
            with gzip.open(archive, "rt", encoding="utf-8") as stream:
                document = json.load(stream)
            if archive.parent != OUT:
                shutil.copy2(archive, OUT / archive.name)
            for entry in document["files"]:
                source = Path(entry["file"]).resolve()
                if not source.is_relative_to(ROOT):
                    continue
                rel = source.relative_to(ROOT).as_posix()
                if not (rel.startswith("main/") or rel.startswith("components/") or rel == "tools/lwip_timers.inc"):
                    continue
                row = files.setdefault(rel, {"lines": {}, "functions": {}, "branches": [], "graphs": {}})
                structure = {
                    "functions": [{key: fn[key] for key in ("name", "start_line", "end_line", "blocks")}
                                  for fn in entry["functions"]],
                    "lines": [{"line": line["line_number"], "function": line.get("function_name"),
                               "blocks": line.get("block_ids", []),
                               "branches": [{key: value for key, value in branch.items() if key != "count"}
                                            for branch in line.get("branches", [])]}
                              for line in entry["lines"]]}
                graph_id = hashlib.sha256(json.dumps(structure, sort_keys=True).encode()).hexdigest()
                graph = row["graphs"].setdefault(graph_id, {"variants": [], "branches": {}})
                graph["variants"].append(exe.stem)
                for line in entry["lines"]:
                    number = str(line["line_number"])
                    row["lines"][number] = row["lines"].get(number, 0) + line["count"]
                for fn in entry["functions"]:
                    key = f"{fn['start_line']}:{fn['name']}"
                    row["functions"][key] = row["functions"].get(key, 0) + fn["execution_count"]
                branches = [{"line": line["line_number"], "index": index,
                             "count": branch["count"], "variant": exe.stem}
                            for line in entry["lines"]
                            for index, branch in enumerate(line.get("branches", []))]
                row["branches"].extend(branches)
                for branch in branches:
                    key = f"{branch['line']}:{branch['index']}"
                    graph["branches"][key] = graph["branches"].get(key, 0) + branch["count"]
                variants.append({"file": rel, "variant": exe.stem,
                                 "lines": len(entry["lines"]),
                                 "lines_hit": sum(line["count"] > 0 for line in entry["lines"]),
                                 "branches": len(branches),
                                 "branches_hit": sum(branch["count"] > 0 for branch in branches)})
    for folder in (ROOT / "main", ROOT / "components"):
        for path in folder.rglob("*.c"):
            files.setdefault(path.relative_to(ROOT).as_posix(),
                             {"lines": {}, "functions": {}, "branches": [],
                              "uninstrumented": True})
    files.setdefault("tools/lwip_timers.inc", {"lines": {}, "functions": {}, "branches": [],
                                               "uninstrumented": True})
    return {"files": files, "variants": variants}


def collect_page():
    folder = OUT / "v8"
    folder.mkdir(exist_ok=True)
    for old in folder.glob("*.json"):
        old.unlink()
    env = os.environ.copy()
    env["NODE_V8_COVERAGE"] = str(folder)
    REAL_RUN(["node", "--check", "tests/check_page.js"], check=True, cwd=ROOT)
    REAL_RUN(["node", "tests/check_page.js"], check=True, cwd=ROOT, env=env)
    entries = []
    for path in folder.glob("*.json"):
        for entry in json.loads(path.read_text(encoding="utf-8"))["result"]:
            if entry["url"] == "thermostat-page.js":
                entries.append(entry)
    if not entries:
        raise AssertionError("Missing V8 coverage for actual embedded page")
    (OUT / "page.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")


def verify_products():
    import flash
    mode, size, freq, segments = flash.read_layout()
    folder = ROOT / "build/auto"
    image = (folder / "full_flash.bin").read_bytes()
    capacity = int(size[:-2]) * (1024 * 1024 if size.endswith("MB") else 1024)
    if len(image) != capacity:
        raise AssertionError("Full image capacity mismatch")
    end = 0
    for offset, name, path, length in segments:
        if image[end:offset] != b"\xff" * (offset - end):
            raise AssertionError(f"Non-erased gap before {name}")
        if image[offset:offset + length] != path.read_bytes():
            raise AssertionError(f"Segment mismatch: {name}")
        end = offset + length
    if image[end:] != b"\xff" * (len(image) - end):
        raise AssertionError("Non-erased trailing region")
    high = position = 0
    eof = False
    for line in (folder / "full_flash.hex").read_text(encoding="ascii").splitlines():
        if eof or not line.startswith(":"):
            raise AssertionError("Invalid HEX record boundary")
        data = bytes.fromhex(line[1:])
        if len(data) != data[0] + 5 or sum(data) & 255:
            raise AssertionError("Invalid HEX record checksum/length")
        address = int.from_bytes(data[1:3], "big")
        if data[3] == 4:
            if data[0] != 2:
                raise AssertionError("Invalid HEX extended address")
            high = int.from_bytes(data[4:-1], "big") << 16
        elif data[3] == 0:
            if high + address != position or image[position:position + data[0]] != data[4:-1]:
                raise AssertionError("HEX/BIN mismatch")
            position += data[0]
        elif data[3] == 1:
            eof = True
        else:
            raise AssertionError("Unsupported HEX record")
    if not eof or position != len(image):
        raise AssertionError("Incomplete HEX image")
    config = (folder / "config/sdkconfig.h").read_text(encoding="utf-8")
    expected = {"ESP8266_DEFAULT_CPU_FREQ_MHZ": "80", "ESP8266_XTAL_FREQ": "26",
                "ESPTOOLPY_FLASHFREQ": '"26m"', "PM_ENABLE": "1",
                "APP_TEMP_OFFSET10": "0", "HTTPD_MAX_REQ_HDR_LEN": "2048", "HTTPD_MAX_URI_LEN": "1024"}
    for name, value in expected.items():
        if f"#define CONFIG_{name} {value}" not in config.splitlines():
            raise AssertionError(f"Unexpected build config: {name}")
    products = {path.relative_to(folder).as_posix(): {"bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in [folder / "full_flash.bin", folder / "full_flash.hex",
                             folder / "flasher_args.json"] + [s[2] for s in segments]}
    (OUT / "products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")


def report(c_data, py_data):
    rows = ["# 软件覆盖验收报告", "",
            "覆盖缺口存在时状态为未完成；通过测试不表示全覆盖。",
            "C 行/函数按源码位置合并；分支按各编译变体分别计数，汇总为变体机会总数，不能视为去重语义分支覆盖率。",
            "SDK、第三方工具及测试源码不计入业务覆盖率。未插桩源码单列，不从验收范围删除。", "",
            "| 模块 | 行命中/总数 | 函数命中/总数 | 分支命中/变体总数 |", "|---|---:|---:|---:|"]
    gaps = []
    totals = [0] * 6
    for name, row in sorted(c_data["files"].items()):
        if row.get("uninstrumented"):
            rows.append(f"| {name} | 未插桩 | 未插桩 | 未插桩 |")
            gaps.append({"file": name, "reason": "现有主机测试未编译该源文件；需增加实际源码 mock harness", "lines": "全部"})
            continue
        values = [sum(n > 0 for n in row["lines"].values()), len(row["lines"]),
                  sum(n > 0 for n in row["functions"].values()), len(row["functions"]),
                  sum(b["count"] > 0 for b in row["branches"]), len(row["branches"])]
        totals = [a + b for a, b in zip(totals, values)]
        rows.append(f"| {name} | {values[0]}/{values[1]} | {values[2]}/{values[3]} | {values[4]}/{values[5]} |")
        missing = [int(line) for line, count in row["lines"].items() if not count]
        branches = [b for b in row["branches"] if not b["count"]]
        if missing or branches:
            gaps.append({"file": name, "lines": missing, "branches": branches,
                         "reason": "当前场景未命中；不能据此认定不可达",
                         "verification": "按源码位置追加输入/错误注入，并复跑对应变体"})
    rows.append(f"| 已插桩 C 总计 | {totals[0]}/{totals[1]} | {totals[2]}/{totals[3]} | {totals[4]}/{totals[5]} |")
    rows += ["", "## 相同 gcov 图结构汇总", "",
             "仅将函数块数、源行 block IDs 和全部分支边结构完全相同的图汇总；用于识别重复测量，不代替逐配置验收或语义路径证明。原始分母和缺口保留。", "",
             "| 模块 | 图结构数 | 汇总命中/总数 |", "|---|---:|---:|"]
    for name, row in sorted(c_data["files"].items()):
        graphs = row.get("graphs", {})
        counts = [count for graph in graphs.values() for count in graph["branches"].values()]
        if graphs:
            rows.append(f"| {name} | {len(graphs)} | {sum(count > 0 for count in counts)}/{len(counts)} |")
    rows += ["", "## Python", "", "| 模块 | 行命中/总数 | 分支命中/总数 |", "|---|---:|---:|"]
    for name, entry in py_data["files"].items():
        summary = entry["summary"]
        rows.append(f"| {name} | {summary['covered_lines']}/{summary['num_statements']} | {summary['covered_branches']}/{summary['num_branches']} |")
        if entry["missing_lines"] or entry["missing_branches"]:
            gaps.append({"file": name, "lines": entry["missing_lines"],
                         "branches": entry["missing_branches"],
                         "reason": "当前测试未命中；工具启动及环境错误路径需子进程 mock 验证"})
    page = OUT / "page.json"
    if page.exists():
        functions = [fn for entry in json.loads(page.read_text()) for fn in entry["functions"]]
        ranges = [r for fn in functions for r in fn["ranges"]]
        missing = [r for r in ranges if not r["count"]]
        rows += ["", f"页面 V8：函数 {sum(fn['ranges'][0]['count'] > 0 for fn in functions)}/{len(functions)}；块范围 {sum(r['count'] > 0 for r in ranges)}/{len(ranges)}。",
                 "V8 块范围不是 GCC 分支或源码行指标；偏移针对 page.h 解码后的 script（UTF-16）。"]
        if missing:
            gaps.append({"file": "main/page.h", "ranges": missing,
                         "reason": "页面脚本块未命中；按 page.json 偏移增加交互/网络异常场景"})
    for path in (ROOT / "tools").glob("*.py"):
        if not any(Path(name).name == path.name for name in py_data["files"]):
            gaps.append({"file": path.relative_to(ROOT).as_posix(), "reason": "未纳入 Python 插桩；需 SDK ELF/archive mock 验证"})
    checks = [r for r in RECORDS if r.get("kind") != "summary"]
    failed = sum(r["status"] == "failed" for r in checks)
    skipped = sum(r["status"] == "skipped" for r in checks)
    rows += ["", "## 执行结果", "", f"检查组：通过 {sum(r['status'] == 'passed' for r in checks)}，失败 {failed}，跳过 {skipped}。",
             "详情见 results.json；单测数量见执行日志。", "",
             f"验收状态：{'未完成' if gaps or failed else '通过'}；覆盖缺口模块 {len(gaps)}。",
             "未执行实机验收 6 类：波形、真实休眠/功耗、温度准确度、手机弹页、ADC 多电压点、24 小时运行；本次范围仅软件。",
             "", "## 缺口位置与处理", ""]
    for gap in gaps:
        numbers = gap.get("lines", [])
        detail = ", ".join(str(n) for n in numbers) if isinstance(numbers, list) else numbers
        rows.append(f"- {gap['file']}：{gap['reason']}；未命中行：{detail or '无'}；分支/范围见 gaps.json。")
        if isinstance(numbers, list):
            path = ROOT / gap["file"]
            if path.is_file():
                source = path.read_text(encoding="utf-8").splitlines()
                gap["source_lines"] = {str(n): source[n - 1] for n in numbers}
                branches = gap.get("branches", [])
                if branches and isinstance(branches[0], dict):
                    gap["branch_source_lines"] = {
                        str(n): source[n - 1] for n in sorted({b["line"] for b in branches})}
    matrix = [
        ("规则/趋势", "等号、禁用、首次满足、两组计时、噪声/尖峰、速度饱和、回绕", "匹配结果、独立成功时间、120～600 秒间隔", "tests/rules_test.c；tests/test_power.py CONTROL"),
        ("传感器/ADC", "CRC/无设备、12 位修正、校准正负舍入、清理失败、ADC越界", "失败不发布有效温度；校准与规则共享结果", "tests/test_power.py SENSOR/CONTROL"),
        ("红外学习/NVS", "采集超时、溢出、错误段、set/commit/readback失败、损坏编码", "错误上报、旧 RAM 编码保持、成功断电模拟重载一致", "tests/test_power.py IR"),
        ("红外发送", "I2S/软件发送、36/38/40kHz、NMI延迟、计数回绕、清理失败", "包络边沿、返回错误、休眠锁/资源释放和重试", "tests/test_power.py IR"),
        ("按键/休眠", "S1/S2、忙碌延后、长按、PM失败、定时器暂停/恢复", "状态转换、采样继续、降级、保留真实定时期限", "tests/test_power.py CONTROL/TRACE/SDK checks"),
        ("热点/DNS/API", "超时、DNS非法/A/AAAA查询、资源失败、分片JSON、非法参数与动作失败", "状态码、槽位转换、动作计数、RF/socket清理", "tests/test_portal.py TEST"),
        ("HTTP", "长URI/header、非法协议、截断POST、chunk、socket errno、分配失败、unrecv过长", "一次错误回复、连接清理、分块内容、截断不破坏状态、重试注册", "tests/test_portal.py WIRE"),
        ("页面", "温度空值/非数、保存/发送/学习、错误状态、网络失败、低电边界", "请求参数、阻止非法提交、提示内容与恢复", "tests/check_page.js"),
        ("工具/产物", "布局缺失/越界/重叠、HEX校验、COM歧义、构建失败、ELF布局变化", "拒绝非法输入、释放映射、SDK保护、真实BIN/HEX一致", "tests/test_tools.py；tests/test_flash_port.py；run_coverage.py"),
        ("启动跟踪", "PHY范围内/外UART和RF调用、RF错误返回", "原调用次数、返回值、日志范围与标记恢复", "tests/startup_test.c"),
    ]
    matrix_rows = ["# 关键路径矩阵", "", "每行代表一组有实际断言的场景，不代表所有可能路径均已覆盖。", "",
                   "| 路径组 | 输入/故障 | 断言 | 依据 |", "|---|---|---|---|"]
    matrix_rows += ["| " + " | ".join(row) + " |" for row in matrix]
    (OUT / "path_matrix.md").write_text("\n".join(matrix_rows) + "\n", encoding="utf-8")
    rows += ["", "## 修复与验证边界", "",
             "- httpd_txrx.c：unrecv 使用截断后的长度复制；过长输入先复现 pending_len 被覆盖，再修复并回归。",
             "- httpd_uri.c：strdup 分配失败后将已释放槽位置空；先复现悬空槽位，再修复并验证重新注册/注销。",
             "- httpd_parse.c：按主版本拒绝非 HTTP/1.x，修复 2.1 被放行；保留 1.0 和同主版本兼容。日志见 version_repro.log 和 branch_http.log。",
             "- portal.c：部分启动状态再次 start 返回 INVALID_STATE；RF/Wi-Fi 停止后独立清理 noise/network 定时器，避免首个错误跳过第二组清理。日志见 portal_cleanup_repro.log、portal_pause_repro.log 和 portal_cleanup_fixed.log。",
             "- ir.c：发送脚初始化为低电平失败时立即返回错误，避免忽略 GPIO 故障；10 个初始化步骤独立注入。日志见 ir_init_repro.log 和 ir_init_fixed.log。",
             "- main.c：关闭热点请求仅在 portal_stop 成功后清除，首次停止失败后仍会重试。日志见 control_stop_repro.log 和 control_stop_fixed.log。",
             "- 复现和修复日志分别为 unrecv_repro.log/unrecv_fixed.log、uri_alloc_repro.log/uri_alloc_fixed.log。",
             "- 固件构建日志见 final_build.log；真实镜像布局、HEX校验及生成配置由本次运行重新验证，哈希见 products.json。",
             "- 关键路径矩阵见 path_matrix.md。所有未命中分支均保留，未自动豁免；不可达判定需逐项源码证明。",
             "- tools/*.cmake 和组件 CMakeLists 由真实固件构建验证，无行/分支插桩；clean.ps1 不在本次构建/烧录测试范围。",
             "- 主机 GPIO/寄存器、任务与网络均为 mocks；代码覆盖不证明芯片时序、真实并发或电气特性。"]
    rows.append("- HTTP 发送返回零字节时立即报错，避免无进展循环；复现及修复日志见 zero_send_repro.log/zero_send_fixed.log。")
    rows.append("- URI 缺少路径字段时 default 可达，已有失败返回和无发送断言；已删除此前错误的不可达说明。")
    rows.append("- 主机宏中的 assert 也会映射到自有源码行（临界区、SDK 错误检查及核心线程锁）；原始分支数包含这些检查，未自动排除。")
    (OUT / "gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "report.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return bool(gaps or failed)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("report.md", "results.json", "gaps.json", "c.json", "python.json", "page.json", "products.json"):
        (OUT / name).unlink(missing_ok=True)
    os.chdir(ROOT)
    # Source directories are unnecessary: include keeps test harnesses out of totals.
    cov = coverage.Coverage(data_file=str(OUT / ".coverage"), branch=True,
                            include=[str(ROOT / "build.py"), str(ROOT / "flash.py"),
                                     str(ROOT / "tools" / "*.py")])
    cov.start()
    check("Python 工具", python_tests)
    with patch.object(subprocess, "run", side_effect=execute):
        check("规则", rules)
        check("启动诊断", startup)
        check("功耗 28 组合与 SDK 定时器", lambda: script("test_power.py"))
        check("热点与 HTTP", lambda: script("test_portal.py"))
    cov.stop()
    cov.save()
    cov.json_report(outfile=str(OUT / "python.json"))
    cov.html_report(directory=str(OUT / "python_html"))
    check("页面", collect_page)
    check("烧录 dry-run", lambda: REAL_RUN([sys.executable, "flash.py", "--port", "COM3", "--dry-run"], check=True, cwd=ROOT))
    check("实际构建配置及 BIN/HEX", verify_products)
    check("差异空白", lambda: REAL_RUN(["git", "diff", "--check"], check=True, cwd=ROOT))
    c_data = collect_c()
    metadata = {"executables": len(OBJECTS), "python": sys.version,
                "revision": REAL_RUN(["git", "rev-parse", "HEAD"], check=True, cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip()}
    for name in ("gcc", "gcov", "node"):
        metadata[name] = REAL_RUN([name, "--version"], check=True, capture_output=True,
                                 text=True).stdout.splitlines()[0]
    sources = list((ROOT / "main").glob("*")) + list((ROOT / "components/esp_http_server").glob("*.c"))
    sources += list((ROOT / "tests").glob("*")) + list((ROOT / "tools").glob("*.py"))
    sources += [ROOT / "build.py", ROOT / "flash.py", ROOT / "sdkconfig"]
    metadata["source_sha256"] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sources if p.is_file()}
    (OUT / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (OUT / "c.json").write_text(json.dumps(c_data, indent=2), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(RECORDS, ensure_ascii=False, indent=2), encoding="utf-8")
    incomplete = report(c_data, json.loads((OUT / "python.json").read_text()))
    print(f"Report: {OUT / 'report.md'}", flush=True)
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
