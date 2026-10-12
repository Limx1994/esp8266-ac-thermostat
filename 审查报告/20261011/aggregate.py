"""Combine reviewer ledgers without upgrading their recorded review scope."""
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def key(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return str(path.resolve()).lower()


def index(items):
    result = {}
    for item in items:
        name = key(item.get("absolute_path") or item["path"])
        if name in result:
            raise ValueError("Duplicate ledger entry: " + name)
        result[name] = item
    return result


def main():
    baseline = read("recovery_baseline.json")
    roles = {
        "bug": index(read("bug_recovery_result.json")["file_ledger"]),
        "performance": index(read("performance_result.json")["current_ledger"]),
        "completeness": index(read("completeness_current_coverage.json")),
        "dead_code": index(read("dead_code_recovery_result.json")["ledger"]),
    }
    names = {key(item["Path"]) for item in baseline}
    for role, items in roles.items():
        if set(items) != names:
            raise ValueError("Ledger scope mismatch: " + role)
    rows = []
    input_changes = []
    output_changes = []
    missing = []
    for item in baseline:
        path = ROOT / item["Path"]
        row = {"path": str(path), "baseline_sha256": item["SHA256"]}
        if path.is_file():
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            row["current_sha256"] = actual
            row["hash_matches"] = actual.lower() == item["SHA256"].lower()
        else:
            missing.append(item["Path"])
            row["current_sha256"] = "MISSING"
            row["hash_matches"] = False
        generated = item["Path"].startswith("Sof\\build\\")
        if not row["hash_matches"]:
            (output_changes if generated else input_changes).append(item["Path"])
        for role, items in roles.items():
            entry = items[key(item["Path"])]
            row[role] = entry.get("status") or entry.get("reading")
            if not row[role]:
                raise ValueError("Missing review status: " + role + ":" + item["Path"])
        rows.append(row)
    with (OUT / "coverage.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"baseline_files": len(baseline),
               "role_ledger_counts": {name: len(items) for name, items in roles.items()},
               "missing": missing, "input_changes": input_changes,
               "generated_changes": output_changes,
               "boundary": "Statuses retain each reviewer's actual scope; registration is not semantic review."}
    (OUT / "coverage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if missing or input_changes:
        raise RuntimeError("Review inputs changed or disappeared; finalization stopped")


if __name__ == "__main__":
    main()
