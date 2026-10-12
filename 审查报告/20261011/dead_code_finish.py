"""Persist completion of read-only dead-code review metadata."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
path = OUT / "dead_code_recovery_result.json"
data = json.loads(path.read_text(encoding="utf-8"))
inherited = {
    "Sof\\flash.py", "Sof\\tests\\test_power.py",
    "Sof\\components\\esp_http_server\\httpd_main.c",
    "Sof\\components\\esp_http_server\\httpd_parse.c",
    "Sof\\components\\esp_http_server\\httpd_txrx.c",
}
completed = {row["path"] for row in data["semantic_gaps"]}
changes = []
for row in data["ledger"]:
    source = ROOT / row["path"]
    observed = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    row["observed_sha256"] = observed
    row["baseline_match"] = observed == row["baseline_sha256"].upper()
    if not row["baseline_match"]:
        changes.append(row["path"])
    if row["path"] in completed:
        if not row["baseline_match"]:
            raise RuntimeError("Review input changed: " + row["path"])
        row["reading"] = "semantic_full"
        row["gap"] = ""
        row["review_origin"] = (
            "previous specialist full-read progress explicitly inherited from Lead"
            if row["path"] in inherited else "dead_code_finish full block reads"
        )
        row["lines_read"] = len(source.read_text(encoding="utf-8-sig").splitlines())
        if source.name == "LICENSE":
            row["reading"] = "full_license_text_no_legal_review"
            row["gap"] = "仅确认许可文件及文档引用，未进行法律解释"
non_generated = [p for p in changes if not p.startswith("Sof\\build\\")]
if non_generated:
    raise RuntimeError("Input drift: " + repr(non_generated))
data["read_full"] = sorted(set(data["read_full"]) | completed)
data["semantic_gaps"] = []
data["source_gaps"] = []
data["complete_semantic_review"] = True
data["status"] = "completed_current_business_text_no_confirmed_dead_code"
data["hash_drift_count"] = len(changes)
data["completion"] = {
    "previous_gap_files": len(completed),
    "inherited_full_reads": sorted(inherited),
    "new_full_block_reads": sorted(completed - inherited),
    "scope": "业务代码/脚本/MD/配置全文补齐；二进制、几何和生成物保留原逐文件限制",
    "generated_changes": changes,
    "non_generated_changes": non_generated,
    "new_confirmed_dead_code": 0,
    "new_tests_run": False,
    "business_files_modified": False,
}
data["cross"][2]["independent_evidence"] = (
    "main.c:621-625 是实际启动AP配置路径；test_power.py SDK生成缺少对应wifi_config_t/"
    "ESP_IF_WIFI_AP/get_config/set_config接口，CONTROL runner为活跃测试入口；"
    "继承专员完整阅读及Bug独立编译/Lead当前coverage失败证据，本人未再运行测试"
)
data["validation"]["scope_warnings"][0] = (
    "当前业务文本语义读全；0确认不等于证明全项目或外部SDK内部无死代码"
)
data["validation"]["baseline_sha256_checked_all"] = len(data["ledger"])
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ledger": len(data["ledger"]), "read_full": len(data["read_full"]),
                  "source_gaps": [], "confirmed": 0, "generated_drift": len(changes)},
                 ensure_ascii=False))
