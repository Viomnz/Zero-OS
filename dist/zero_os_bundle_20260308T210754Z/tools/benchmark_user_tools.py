from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark_security_stack import _to_markdown, _preset_config, run_benchmark


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "security" / "artifacts"
BENCHMARKS = ROOT / "security" / "benchmarks"
HISTORY = BENCHMARKS / "history.jsonl"
LATEST = BENCHMARKS / "latest.json"
SUMMARY = BENCHMARKS / "history_summary.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_history(record: dict) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as h:
        h.write(json.dumps(record, sort_keys=True) + "\n")


def _load_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    out: list[dict] = []
    for ln in HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _history_markdown(rows: list[dict]) -> str:
    lines = [
        "# Benchmark History",
        "",
        "| UTC | Preset | Seed | Detect | FP | Throughput | Q/R | Beacon |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows[-20:][::-1]:
        c = r.get("config", {})
        s = r.get("summary", {})
        avg = r.get("av_scan", {}).get("avg", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("generated_utc", "")),
                    str(c.get("preset", "")),
                    str(c.get("seed", "")),
                    f"{float(s.get('antivirus_detection_rate', 0.0)):.4f}",
                    f"{float(s.get('antivirus_false_positive_rate', 0.0)):.4f}",
                    f"{float(avg.get('throughput_files_per_sec', 0.0)):.2f}",
                    str(bool(s.get("quarantine_restore_reliable", False))),
                    str(bool(s.get("cure_firewall_beacon_verified", False))),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def cmd_run(args: argparse.Namespace) -> int:
    clean, mal, iters = _preset_config(args.preset)
    result = run_benchmark(
        clean_count=clean,
        malicious_count=mal,
        iterations=iters,
        seed=int(args.seed),
        preset=args.preset,
    )
    result["run_label"] = args.label or f"{args.preset}-{args.seed}"
    result["recorded_utc"] = _utc_now()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    BENCHMARKS.mkdir(parents=True, exist_ok=True)

    (ARTIFACTS / "security_benchmark.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ARTIFACTS / "security_benchmark.md").write_text(_to_markdown(result), encoding="utf-8")
    (BENCHMARKS / "dataset_manifest_v1.json").write_text(
        json.dumps(result.get("dataset_manifest", {}), indent=2) + "\n", encoding="utf-8"
    )
    LATEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    _append_history(result)

    rows = _load_history()
    SUMMARY.write_text(_history_markdown(rows), encoding="utf-8")
    print(f"Saved latest: {LATEST}")
    print(f"Appended history: {HISTORY}")
    print(f"History summary: {SUMMARY}")
    return 0


def cmd_history(_: argparse.Namespace) -> int:
    rows = _load_history()
    print(f"History entries: {len(rows)}")
    if not rows:
        return 0
    for r in rows[-10:][::-1]:
        c = r.get("config", {})
        s = r.get("summary", {})
        avg = r.get("av_scan", {}).get("avg", {})
        print(
            f"{r.get('generated_utc')} preset={c.get('preset')} seed={c.get('seed')} "
            f"detect={float(s.get('antivirus_detection_rate', 0.0)):.4f} "
            f"fp={float(s.get('antivirus_false_positive_rate', 0.0)):.4f} "
            f"throughput={float(avg.get('throughput_files_per_sec', 0.0)):.2f}"
        )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    rows = _load_history()
    if len(rows) < 2:
        print("Need at least 2 benchmark history entries.")
        return 1
    a = rows[-2]
    b = rows[-1]
    sa = a.get("summary", {})
    sb = b.get("summary", {})
    ta = float(a.get("av_scan", {}).get("avg", {}).get("throughput_files_per_sec", 0.0))
    tb = float(b.get("av_scan", {}).get("avg", {}).get("throughput_files_per_sec", 0.0))
    print("Compare previous -> latest")
    print(
        f"Detection rate: {float(sa.get('antivirus_detection_rate', 0.0)):.4f} -> "
        f"{float(sb.get('antivirus_detection_rate', 0.0)):.4f}"
    )
    print(
        f"False positive rate: {float(sa.get('antivirus_false_positive_rate', 0.0)):.4f} -> "
        f"{float(sb.get('antivirus_false_positive_rate', 0.0)):.4f}"
    )
    print(f"Throughput files/sec: {ta:.2f} -> {tb:.2f}")
    if args.write:
        BENCHMARKS.mkdir(parents=True, exist_ok=True)
        target = BENCHMARKS / "compare_latest.md"
        target.write_text(
            "\n".join(
                [
                    "# Latest Benchmark Comparison",
                    "",
                    f"- Previous: {a.get('generated_utc')}",
                    f"- Latest: {b.get('generated_utc')}",
                    f"- Detection rate: {float(sa.get('antivirus_detection_rate', 0.0)):.4f} -> {float(sb.get('antivirus_detection_rate', 0.0)):.4f}",
                    f"- False positive rate: {float(sa.get('antivirus_false_positive_rate', 0.0)):.4f} -> {float(sb.get('antivirus_false_positive_rate', 0.0)):.4f}",
                    f"- Throughput files/sec: {ta:.2f} -> {tb:.2f}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"Wrote comparison: {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="User-friendly benchmark tools for Zero-OS security stack.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run benchmark and save history.")
    p_run.add_argument("--preset", choices=["small", "medium", "large"], default="medium")
    p_run.add_argument("--seed", type=int, default=1337)
    p_run.add_argument("--label", default="")
    p_run.set_defaults(func=cmd_run)

    p_hist = sub.add_parser("history", help="Show recent benchmark history.")
    p_hist.set_defaults(func=cmd_history)

    p_cmp = sub.add_parser("compare", help="Compare previous and latest benchmark.")
    p_cmp.add_argument("--write", action="store_true")
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
