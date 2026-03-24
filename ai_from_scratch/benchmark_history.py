from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

try:
    from ai_from_scratch.benchmark_suite import (
        DEFAULT_BENCHMARK_MANIFEST,
        DEFAULT_OUTPUT,
        benchmark_cohort_key,
        run_benchmark_suite,
    )
except ModuleNotFoundError:
    from benchmark_suite import DEFAULT_BENCHMARK_MANIFEST, DEFAULT_OUTPUT, benchmark_cohort_key, run_benchmark_suite


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from zero_os.fast_path_cache import cached_compute
from zero_os.state_cache import json_state_revision

BENCHMARK_HISTORY_DIR = ROOT / ".zero_os" / "benchmarks" / "model"
DEFAULT_GATE_CONFIG = ROOT / "laws" / "model_benchmark_thresholds.json"
DEFAULT_ALERT_ROUTE_CONFIG = ROOT / "laws" / "model_benchmark_alert_routes.json"
HISTORY = BENCHMARK_HISTORY_DIR / "history.jsonl"
LATEST = BENCHMARK_HISTORY_DIR / "latest.json"
SUMMARY = BENCHMARK_HISTORY_DIR / "history_summary.md"
COMPARE = BENCHMARK_HISTORY_DIR / "compare_latest.md"
COHORTS = BENCHMARK_HISTORY_DIR / "cohorts_summary.md"
FAMILIES = BENCHMARK_HISTORY_DIR / "families_summary.md"
CHARTS = BENCHMARK_HISTORY_DIR / "trend_charts.md"
FAMILY_CHARTS = BENCHMARK_HISTORY_DIR / "family_trend_charts.md"
CHARTS_JSON = BENCHMARK_HISTORY_DIR / "trend_charts.json"
GATE = BENCHMARK_HISTORY_DIR / "gate_latest.json"
ALERTS = BENCHMARK_HISTORY_DIR / "alerts_latest.md"
DASHBOARD = BENCHMARK_HISTORY_DIR / "dashboard_latest.md"
DASHBOARD_JSON = BENCHMARK_HISTORY_DIR / "dashboard_latest.json"
ALERT_ROUTES = BENCHMARK_HISTORY_DIR / "alert_routes.json"
REMEDIATION = BENCHMARK_HISTORY_DIR / "remediation_latest.md"
REMEDIATION_JSON = BENCHMARK_HISTORY_DIR / "remediation_latest.json"


def _history_paths(history_dir: Path) -> dict[str, Path]:
    base = Path(history_dir)
    return {
        "dir": base,
        "history": base / "history.jsonl",
        "latest": base / "latest.json",
        "summary": base / "history_summary.md",
        "compare": base / "compare_latest.md",
        "cohorts": base / "cohorts_summary.md",
        "families": base / "families_summary.md",
        "charts": base / "trend_charts.md",
        "family_charts": base / "family_trend_charts.md",
        "charts_json": base / "trend_charts.json",
        "gate": base / "gate_latest.json",
        "alerts": base / "alerts_latest.md",
        "dashboard": base / "dashboard_latest.md",
        "dashboard_json": base / "dashboard_latest.json",
        "alert_routes": base / "alert_routes.json",
        "remediation": base / "remediation_latest.md",
        "remediation_json": base / "remediation_latest.json",
    }


def _benchmark_status_signature(
    *,
    history_dir: str | Path,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    limit: int = 0,
) -> dict:
    paths = _history_paths(Path(history_dir))
    return {
        "history": json_state_revision(paths["history"]),
        "gate_config": json_state_revision(gate_config_path),
        "alert_route_config": json_state_revision(alert_route_config_path),
        "cohort": str(cohort or ""),
        "architecture": str(architecture or ""),
        "tokenizer_mode": str(tokenizer_mode or ""),
        "limit": int(limit or 0),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_gate_payload() -> dict:
    return {
        "max_primary_perplexity": 120.0,
        "max_valid_perplexity": 120.0,
        "max_train_perplexity": 120.0,
        "max_family_primary_perplexity": 130.0,
        "max_primary_regression_delta": 6.0,
        "max_valid_regression_delta": 6.0,
        "max_train_regression_delta": 6.0,
        "max_family_primary_regression_delta": 8.0,
        "max_primary_regression_ratio": 0.12,
        "max_valid_regression_ratio": 0.12,
        "max_train_regression_ratio": 0.12,
        "max_family_primary_regression_ratio": 0.16,
    }


def default_alert_route_payload() -> dict:
    return {
        "default_fail_route": "ci_blocker",
        "default_warn_route": "benchmark_watch",
        "route_actions": {
            "ci_blocker": "block_release",
            "regression_watch": "review_regression",
            "family_watch": "inspect_family_slice",
            "baseline_watch": "collect_baseline",
            "benchmark_watch": "review_benchmark_signal",
        },
        "route_severity": {
            "ci_blocker": "critical",
            "regression_watch": "high",
            "family_watch": "high",
            "baseline_watch": "medium",
            "benchmark_watch": "medium",
        },
        "kind_routes": {
            "absolute_threshold": "ci_blocker",
            "regression_delta": "regression_watch",
            "regression_ratio": "regression_watch",
            "family_absolute_threshold": "family_watch",
            "family_regression_delta": "family_watch",
            "family_regression_ratio": "family_watch",
            "baseline_missing": "baseline_watch",
            "family_baseline_missing": "baseline_watch",
        },
    }


def ensure_default_gate_config(path: str | Path = DEFAULT_GATE_CONFIG) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps(default_gate_payload(), indent=2) + "\n", encoding="utf-8")
    return target


def load_gate_config(path: str | Path = DEFAULT_GATE_CONFIG) -> dict:
    payload = default_gate_payload()
    config_path = ensure_default_gate_config(path)
    raw = json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in payload:
                try:
                    payload[key] = float(value)
                except Exception:
                    continue
    return payload


def ensure_default_alert_route_config(path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps(default_alert_route_payload(), indent=2) + "\n", encoding="utf-8")
    return target


def load_alert_route_config(path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG) -> dict:
    payload = default_alert_route_payload()
    config_path = ensure_default_alert_route_config(path)
    raw = json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        return payload
    for key in ("default_fail_route", "default_warn_route"):
        value = str(raw.get(key, "")).strip()
        if value:
            payload[key] = value
    for key in ("route_actions", "route_severity", "kind_routes"):
        mapping = raw.get(key)
        if not isinstance(mapping, dict):
            continue
        for map_key, map_value in mapping.items():
            item_key = str(map_key).strip()
            item_value = str(map_value).strip()
            if item_key and item_value:
                payload[key][item_key] = item_value
    return payload


def _load_history(history_path: Path = HISTORY) -> list[dict]:
    if not history_path.exists():
        return []
    rows: list[dict] = []
    for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except Exception:
            continue
        if isinstance(record, dict):
            rows.append(record)
    return rows


def _append_history(record: dict, history_path: Path = HISTORY) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _record_cohort(record: dict) -> str:
    cohort = str(record.get("cohort", "")).strip()
    if cohort:
        return cohort
    return benchmark_cohort_key(str(record.get("architecture", "")).strip(), str(record.get("tokenizer_mode", "")).strip())


def _filtered_rows(
    rows: list[dict],
    *,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
) -> list[dict]:
    selected: list[dict] = []
    required_cohort = str(cohort or "").strip()
    required_arch = str(architecture or "").strip()
    required_tokenizer = str(tokenizer_mode or "").strip()
    for row in rows:
        row_cohort = _record_cohort(row)
        row_arch = str(row.get("architecture", "")).strip()
        row_tokenizer = str(row.get("tokenizer_mode", "")).strip()
        if required_cohort and row_cohort != required_cohort:
            continue
        if required_arch and row_arch != required_arch:
            continue
        if required_tokenizer and row_tokenizer != required_tokenizer:
            continue
        selected.append(row)
    return selected


def _group_by_cohort(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(_record_cohort(row), []).append(row)
    return grouped


def _row_families(row: dict) -> list[dict]:
    raw_families = row.get("families", [])
    if not isinstance(raw_families, list):
        return []
    families: list[dict] = []
    for entry in raw_families:
        if not isinstance(entry, dict):
            continue
        family = str(entry.get("family", "")).strip()
        if not family:
            continue
        families.append(entry)
    return families


def _family_map(row: dict) -> dict[str, dict]:
    return {str(item.get("family", "")).strip(): item for item in _row_families(row)}


def _extract_metric_values(items: list[dict]) -> dict[str, list[float]]:
    return {
        "primary": [float(item.get("primary_perplexity", 0.0)) for item in items],
        "valid": [float(item.get("valid", {}).get("perplexity", 0.0)) for item in items],
        "train": [float(item.get("train", {}).get("perplexity", 0.0)) for item in items],
    }


def _build_chart_payload(
    name: str,
    items: list[dict],
    *,
    run_count: int,
    metadata: dict | None = None,
) -> dict:
    labels = [str(item.get("run_label", "") or item.get("recorded_utc", item.get("generated_utc", ""))) for item in items]
    values = _extract_metric_values(items)
    primary_values = values["primary"]
    valid_values = values["valid"]
    train_values = values["train"]
    payload = {
        "name": name,
        "run_count": int(run_count),
        "labels": labels,
        "latest_primary_perplexity": float(primary_values[-1]) if primary_values else 0.0,
        "best_primary_perplexity": float(min(primary_values)) if primary_values else 0.0,
        "primary": {"chart": _trend_chart(primary_values), "values": primary_values},
        "valid": {"chart": _trend_chart(valid_values), "values": valid_values},
        "train": {"chart": _trend_chart(train_values), "values": train_values},
    }
    if metadata:
        payload.update(metadata)
    return payload


def _cohort_summary_rows(rows: list[dict]) -> list[dict]:
    summaries: list[dict] = []
    for cohort, cohort_rows in _group_by_cohort(rows).items():
        latest = cohort_rows[-1]
        best = min(cohort_rows, key=lambda item: float(item.get("primary_perplexity", 0.0)))
        if len(cohort_rows) >= 2:
            delta = _metric_delta(
                float(cohort_rows[-2].get("primary_perplexity", 0.0)),
                float(cohort_rows[-1].get("primary_perplexity", 0.0)),
            )
        else:
            delta = {"previous": float(latest.get("primary_perplexity", 0.0)), "latest": float(latest.get("primary_perplexity", 0.0)), "delta": 0.0, "trend": "stable"}
        summaries.append(
            {
                "cohort": cohort,
                "architecture": str(latest.get("architecture", "")),
                "tokenizer_mode": str(latest.get("tokenizer_mode", "")),
                "run_count": len(cohort_rows),
                "latest_primary_perplexity": float(latest.get("primary_perplexity", 0.0)),
                "best_primary_perplexity": float(best.get("primary_perplexity", 0.0)),
                "trend": str(delta.get("trend", "stable")),
                "delta": float(delta.get("delta", 0.0)),
                "latest_utc": str(latest.get("recorded_utc", latest.get("generated_utc", ""))),
            }
        )
    return sorted(summaries, key=lambda item: item["cohort"])


def _trend_chart(values: list[float]) -> str:
    if not values:
        return ""
    levels = "._-:=+*#%@"
    if len(values) == 1:
        return levels[len(levels) // 2]
    low = min(values)
    high = max(values)
    if abs(high - low) < 1e-12:
        return levels[len(levels) // 2] * len(values)
    chars: list[str] = []
    span = high - low
    for value in values:
        index = int(round(((value - low) / span) * (len(levels) - 1)))
        index = min(max(index, 0), len(levels) - 1)
        chars.append(levels[index])
    return "".join(chars)


def _history_markdown(rows: list[dict], limit: int = 20) -> str:
    lines = [
        "# Model Benchmark History",
        "",
        "| UTC | Label | Suite | Architecture | Tokenizer | Cohort | Gate | Primary | Valid PPL | Train PPL | Corpora |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows[-max(1, int(limit)):][::-1]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("recorded_utc", row.get("generated_utc", ""))),
                    str(row.get("run_label", "")),
                    str(row.get("suite", "")),
                    str(row.get("architecture", "")),
                    str(row.get("tokenizer_mode", "")),
                    _record_cohort(row),
                    str(dict(row.get("gate", {})).get("status", "")),
                    f"{float(row.get('primary_perplexity', 0.0)):.4f}",
                    f"{float(row.get('valid', {}).get('perplexity', 0.0)):.4f}",
                    f"{float(row.get('train', {}).get('perplexity', 0.0)):.4f}",
                    str(int(row.get("corpus_count", 0))),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _cohort_markdown(rows: list[dict]) -> str:
    lines = [
        "# Benchmark Cohorts",
        "",
        "| Cohort | Architecture | Tokenizer | Runs | Latest PPL | Best PPL | Last Trend | Delta | Latest UTC |",
        "|---|---|---|---:|---:|---:|---|---:|---|",
    ]
    for item in _cohort_summary_rows(rows):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["cohort"]),
                    str(item["architecture"]),
                    str(item["tokenizer_mode"]),
                    str(int(item["run_count"])),
                    f"{float(item['latest_primary_perplexity']):.4f}",
                    f"{float(item['best_primary_perplexity']):.4f}",
                    str(item["trend"]),
                    f"{float(item['delta']):.4f}",
                    str(item["latest_utc"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _family_summary_markdown(rows: list[dict]) -> str:
    lines = ["# Latest Benchmark Family Slices", ""]
    if not rows:
        lines.append("_No benchmark history available._")
        return "\n".join(lines) + "\n"
    latest = rows[-1]
    families = sorted(_row_families(latest), key=lambda item: str(item.get("family", "")))
    lines.extend(
        [
            f"- Run: {latest.get('run_label', '')}",
            f"- UTC: {latest.get('recorded_utc', latest.get('generated_utc', ''))}",
            f"- Cohort: {_record_cohort(latest)}",
            "",
            "| Family | Corpora | Primary PPL | Valid PPL | Train PPL | Corpus Names |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for item in families:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("family", "")),
                    str(int(item.get("corpus_count", 0))),
                    f"{float(item.get('primary_perplexity', 0.0)):.4f}",
                    f"{float(item.get('valid', {}).get('perplexity', 0.0)):.4f}",
                    f"{float(item.get('train', {}).get('perplexity', 0.0)):.4f}",
                    ", ".join(str(name) for name in item.get("corpus_names", [])) or "(none)",
                ]
            )
            + " |"
        )
    if not families:
        lines.append("| (none) | 0 | 0.0000 | 0.0000 | 0.0000 | (none) |")
    return "\n".join(lines) + "\n"


def _metric_delta(previous: float, latest: float) -> dict:
    delta = float(latest - previous)
    if abs(delta) < 1e-12:
        trend = "stable"
    elif delta < 0.0:
        trend = "improved"
    else:
        trend = "regressed"
    return {
        "previous": float(previous),
        "latest": float(latest),
        "delta": delta,
        "trend": trend,
    }


def _metric_ratio(previous: float, latest: float) -> float:
    baseline = float(previous)
    if baseline <= 0.0:
        return 0.0
    return float((float(latest) - baseline) / baseline)


def _gate_alert(
    level: str,
    kind: str,
    *,
    message: str,
    metric: str = "",
    actual: float | None = None,
    threshold: float | None = None,
    previous: float | None = None,
    cohort: str = "",
    family: str = "",
) -> dict:
    payload = {
        "level": str(level),
        "kind": str(kind),
        "message": str(message),
        "metric": str(metric),
    }
    if actual is not None:
        payload["actual"] = float(actual)
    if threshold is not None:
        payload["threshold"] = float(threshold)
    if previous is not None:
        payload["previous"] = float(previous)
    if cohort:
        payload["cohort"] = str(cohort)
    if family:
        payload["family"] = str(family)
    return payload


def evaluate_benchmark_gate(
    report: dict,
    *,
    previous: dict | None = None,
    gate_config: dict | None = None,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
) -> dict:
    config = dict(gate_config or load_gate_config(gate_config_path))
    cohort = _record_cohort(report)
    alerts: list[dict] = []

    def fail(kind: str, *, message: str, metric: str = "", actual: float | None = None, threshold: float | None = None, previous_value: float | None = None, family: str = "") -> None:
        alerts.append(
            _gate_alert(
                "fail",
                kind,
                message=message,
                metric=metric,
                actual=actual,
                threshold=threshold,
                previous=previous_value,
                cohort=cohort,
                family=family,
            )
        )

    def warn(kind: str, *, message: str, metric: str = "", family: str = "") -> None:
        alerts.append(_gate_alert("warn", kind, message=message, metric=metric, cohort=cohort, family=family))

    primary_ppl = float(report.get("primary_perplexity", 0.0))
    valid_ppl = float(report.get("valid", {}).get("perplexity", 0.0))
    train_ppl = float(report.get("train", {}).get("perplexity", 0.0))

    absolute_checks = [
        ("primary_perplexity", primary_ppl, float(config["max_primary_perplexity"])),
        ("valid_perplexity", valid_ppl, float(config["max_valid_perplexity"])),
        ("train_perplexity", train_ppl, float(config["max_train_perplexity"])),
    ]
    for metric, actual, threshold in absolute_checks:
        if actual > threshold:
            fail(
                "absolute_threshold",
                message=f"{metric} exceeded threshold",
                metric=metric,
                actual=actual,
                threshold=threshold,
            )

    for family_item in _row_families(report):
        family_name = str(family_item.get("family", "")).strip()
        family_primary = float(family_item.get("primary_perplexity", 0.0))
        family_threshold = float(config["max_family_primary_perplexity"])
        if family_primary > family_threshold:
            fail(
                "family_absolute_threshold",
                message=f"family {family_name} primary perplexity exceeded threshold",
                metric="family_primary_perplexity",
                actual=family_primary,
                threshold=family_threshold,
                family=family_name,
            )

    comparison: dict = {}
    if previous is None:
        warn("baseline_missing", message="No previous cohort run available for regression checks.")
    else:
        comparison = compare_records(previous, report)
        regression_checks = [
            (
                "primary_perplexity",
                comparison["primary_perplexity"],
                float(config["max_primary_regression_delta"]),
                float(config["max_primary_regression_ratio"]),
            ),
            (
                "valid_perplexity",
                comparison["valid_perplexity"],
                float(config["max_valid_regression_delta"]),
                float(config["max_valid_regression_ratio"]),
            ),
            (
                "train_perplexity",
                comparison["train_perplexity"],
                float(config["max_train_regression_delta"]),
                float(config["max_train_regression_ratio"]),
            ),
        ]
        for metric, delta_payload, delta_threshold, ratio_threshold in regression_checks:
            delta = float(delta_payload.get("delta", 0.0))
            previous_value = float(delta_payload.get("previous", 0.0))
            latest_value = float(delta_payload.get("latest", 0.0))
            ratio = _metric_ratio(previous_value, latest_value)
            if delta > delta_threshold:
                fail(
                    "regression_delta",
                    message=f"{metric} regressed beyond delta threshold",
                    metric=metric,
                    actual=delta,
                    threshold=delta_threshold,
                    previous_value=previous_value,
                )
            if ratio > ratio_threshold:
                fail(
                    "regression_ratio",
                    message=f"{metric} regressed beyond ratio threshold",
                    metric=metric,
                    actual=ratio,
                    threshold=ratio_threshold,
                    previous_value=previous_value,
                )

        previous_families = _family_map(previous)
        for family_item in _row_families(report):
            family_name = str(family_item.get("family", "")).strip()
            previous_family = previous_families.get(family_name)
            if previous_family is None:
                warn("family_baseline_missing", message=f"No previous family baseline for {family_name}.", family=family_name)
                continue
            previous_value = float(previous_family.get("primary_perplexity", 0.0))
            latest_value = float(family_item.get("primary_perplexity", 0.0))
            delta = latest_value - previous_value
            ratio = _metric_ratio(previous_value, latest_value)
            if delta > float(config["max_family_primary_regression_delta"]):
                fail(
                    "family_regression_delta",
                    message=f"family {family_name} primary perplexity regressed beyond delta threshold",
                    metric="family_primary_perplexity",
                    actual=delta,
                    threshold=float(config["max_family_primary_regression_delta"]),
                    previous_value=previous_value,
                    family=family_name,
                )
            if ratio > float(config["max_family_primary_regression_ratio"]):
                fail(
                    "family_regression_ratio",
                    message=f"family {family_name} primary perplexity regressed beyond ratio threshold",
                    metric="family_primary_perplexity",
                    actual=ratio,
                    threshold=float(config["max_family_primary_regression_ratio"]),
                    previous_value=previous_value,
                    family=family_name,
                )

    failed = any(str(item.get("level", "")) == "fail" for item in alerts)
    return {
        "status": "fail" if failed else "pass",
        "failed": bool(failed),
        "cohort": cohort,
        "gate_config_path": str(Path(gate_config_path).resolve()),
        "thresholds": config,
        "comparison": comparison,
        "alerts": alerts,
        "alert_count": len(alerts),
        "failure_count": sum(1 for item in alerts if str(item.get("level", "")) == "fail"),
        "warning_count": sum(1 for item in alerts if str(item.get("level", "")) == "warn"),
        "baseline_available": previous is not None,
    }


def compare_records(previous: dict, latest: dict) -> dict:
    return {
        "previous_label": str(previous.get("run_label", "")),
        "latest_label": str(latest.get("run_label", "")),
        "previous_utc": str(previous.get("recorded_utc", previous.get("generated_utc", ""))),
        "latest_utc": str(latest.get("recorded_utc", latest.get("generated_utc", ""))),
        "suite": str(latest.get("suite", previous.get("suite", ""))),
        "previous_architecture": str(previous.get("architecture", "")),
        "latest_architecture": str(latest.get("architecture", "")),
        "previous_tokenizer_mode": str(previous.get("tokenizer_mode", "")),
        "latest_tokenizer_mode": str(latest.get("tokenizer_mode", "")),
        "cohort": _record_cohort(latest),
        "primary_perplexity": _metric_delta(
            float(previous.get("primary_perplexity", 0.0)),
            float(latest.get("primary_perplexity", 0.0)),
        ),
        "valid_perplexity": _metric_delta(
            float(previous.get("valid", {}).get("perplexity", 0.0)),
            float(latest.get("valid", {}).get("perplexity", 0.0)),
        ),
        "train_perplexity": _metric_delta(
            float(previous.get("train", {}).get("perplexity", 0.0)),
            float(latest.get("train", {}).get("perplexity", 0.0)),
        ),
        "corpus_count_delta": int(latest.get("corpus_count", 0)) - int(previous.get("corpus_count", 0)),
    }


def _comparison_markdown(comparison: dict) -> str:
    primary = comparison.get("primary_perplexity", {})
    valid = comparison.get("valid_perplexity", {})
    train = comparison.get("train_perplexity", {})
    return "\n".join(
        [
            "# Latest Model Benchmark Comparison",
            "",
            f"- Previous: {comparison.get('previous_utc', '')} ({comparison.get('previous_label', '')})",
            f"- Latest: {comparison.get('latest_utc', '')} ({comparison.get('latest_label', '')})",
            f"- Suite: {comparison.get('suite', '')}",
            f"- Cohort: {comparison.get('cohort', '')}",
            f"- Primary perplexity: {float(primary.get('previous', 0.0)):.4f} -> {float(primary.get('latest', 0.0)):.4f} ({primary.get('trend', 'stable')}, delta {float(primary.get('delta', 0.0)):.4f})",
            f"- Valid perplexity: {float(valid.get('previous', 0.0)):.4f} -> {float(valid.get('latest', 0.0)):.4f} ({valid.get('trend', 'stable')}, delta {float(valid.get('delta', 0.0)):.4f})",
            f"- Train perplexity: {float(train.get('previous', 0.0)):.4f} -> {float(train.get('latest', 0.0)):.4f} ({train.get('trend', 'stable')}, delta {float(train.get('delta', 0.0)):.4f})",
            f"- Corpus count delta: {int(comparison.get('corpus_count_delta', 0))}",
            "",
        ]
    )


def _gate_markdown(gate: dict) -> str:
    lines = [
        "# Benchmark Gate Status",
        "",
        f"- Status: {str(gate.get('status', 'pass')).upper()}",
        f"- Cohort: {gate.get('cohort', '')}",
        f"- Failures: {int(gate.get('failure_count', 0))}",
        f"- Warnings: {int(gate.get('warning_count', 0))}",
        f"- Threshold config: {gate.get('gate_config_path', '')}",
        "",
    ]
    alerts = list(gate.get("alerts", []))
    if not alerts:
        lines.append("- No alerts.")
        lines.append("")
        return "\n".join(lines)
    for alert in alerts:
        suffix: list[str] = []
        if alert.get("metric"):
            suffix.append(f"metric={alert.get('metric', '')}")
        if "actual" in alert:
            suffix.append(f"actual={float(alert.get('actual', 0.0)):.4f}")
        if "threshold" in alert:
            suffix.append(f"threshold={float(alert.get('threshold', 0.0)):.4f}")
        if "previous" in alert:
            suffix.append(f"previous={float(alert.get('previous', 0.0)):.4f}")
        if alert.get("family"):
            suffix.append(f"family={alert.get('family', '')}")
        detail = f" ({', '.join(suffix)})" if suffix else ""
        lines.append(f"- [{str(alert.get('level', '')).upper()}] {alert.get('message', '')}{detail}")
    lines.append("")
    return "\n".join(lines)


def _severity_rank(level: str) -> int:
    order = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "info": 0,
    }
    return int(order.get(str(level).strip().lower(), 0))


def route_benchmark_alerts(
    gate: dict,
    *,
    route_config: dict | None = None,
    route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
) -> dict:
    config = dict(route_config or load_alert_route_config(route_config_path))
    kind_routes = dict(config.get("kind_routes", {}))
    route_actions = dict(config.get("route_actions", {}))
    route_severity = dict(config.get("route_severity", {}))
    default_fail_route = str(config.get("default_fail_route", "ci_blocker"))
    default_warn_route = str(config.get("default_warn_route", "benchmark_watch"))

    grouped: dict[str, dict] = {}
    routed_items: list[dict] = []
    for alert in list(gate.get("alerts", [])):
        level = str(alert.get("level", "")).strip().lower()
        kind = str(alert.get("kind", "")).strip()
        route = str(kind_routes.get(kind, default_fail_route if level == "fail" else default_warn_route))
        severity = str(route_severity.get(route, "critical" if level == "fail" else "medium"))
        action = str(route_actions.get(route, "review_signal"))
        enriched = dict(alert)
        enriched["route"] = route
        enriched["severity"] = severity
        enriched["action"] = action
        routed_items.append(enriched)
        bucket = grouped.setdefault(
            route,
            {
                "route": route,
                "severity": severity,
                "action": action,
                "count": 0,
                "alerts": [],
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["alerts"].append(enriched)
        if _severity_rank(severity) > _severity_rank(str(bucket.get("severity", ""))):
            bucket["severity"] = severity

    routes = sorted(
        grouped.values(),
        key=lambda item: (-_severity_rank(str(item.get("severity", ""))), str(item.get("route", ""))),
    )
    route_counts = {str(item["route"]): int(item["count"]) for item in routes}
    highest_severity = routes[0]["severity"] if routes else "info"
    return {
        "generated_utc": _utc_now(),
        "status": str(gate.get("status", "pass")),
        "failed": bool(gate.get("failed", False)),
        "cohort": str(gate.get("cohort", "")),
        "route_config_path": str(Path(route_config_path).resolve()),
        "alert_count": len(routed_items),
        "route_count": len(routes),
        "failure_count": int(gate.get("failure_count", 0)),
        "warning_count": int(gate.get("warning_count", 0)),
        "highest_severity": highest_severity,
        "route_counts": route_counts,
        "routes": routes,
        "alerts": routed_items,
    }


def _dashboard_payload(rows: list[dict], routed_alerts: dict, limit: int = 8) -> dict:
    if not rows:
        return {
            "generated_utc": _utc_now(),
            "history_count": 0,
            "latest_run": {},
            "recent_runs": [],
            "cohort_summaries": [],
            "family_slices": [],
            "routed_alerts": routed_alerts,
            "current_cohort_chart": {},
            "current_family_charts": [],
            "comparison": {},
            "remediation": {},
        }

    latest = rows[-1]
    latest_cohort = _record_cohort(latest)
    cohort_rows = _filtered_rows(rows, cohort=latest_cohort)
    comparison = compare_records(cohort_rows[-2], cohort_rows[-1]) if len(cohort_rows) >= 2 else {}
    current_cohort_chart = next(
        (item for item in _cohort_chart_payloads(rows, limit=limit) if str(item.get("cohort", "")) == latest_cohort),
        {},
    )
    current_family_charts = [
        item
        for item in _family_chart_payloads(rows, limit=limit)
        if str(item.get("cohort", "")) == latest_cohort
    ]
    recent_runs = [
        {
            "recorded_utc": str(row.get("recorded_utc", row.get("generated_utc", ""))),
            "run_label": str(row.get("run_label", "")),
            "cohort": _record_cohort(row),
            "gate_status": str(dict(row.get("gate", {})).get("status", "")),
            "primary_perplexity": float(row.get("primary_perplexity", 0.0)),
        }
        for row in rows[-max(1, int(limit)):][::-1]
    ]
    family_slices = sorted(
        _row_families(latest),
        key=lambda item: (-float(item.get("primary_perplexity", 0.0)), str(item.get("family", ""))),
    )
    return {
        "generated_utc": _utc_now(),
        "history_count": len(rows),
        "latest_run": {
            "recorded_utc": str(latest.get("recorded_utc", latest.get("generated_utc", ""))),
            "run_label": str(latest.get("run_label", "")),
            "suite": str(latest.get("suite", "")),
            "cohort": latest_cohort,
            "architecture": str(latest.get("architecture", "")),
            "tokenizer_mode": str(latest.get("tokenizer_mode", "")),
            "gate_status": str(dict(latest.get("gate", {})).get("status", "")),
            "primary_split": str(latest.get("primary_split", "")),
            "primary_perplexity": float(latest.get("primary_perplexity", 0.0)),
            "valid_perplexity": float(latest.get("valid", {}).get("perplexity", 0.0)),
            "train_perplexity": float(latest.get("train", {}).get("perplexity", 0.0)),
        },
        "comparison": comparison,
        "recent_runs": recent_runs,
        "cohort_summaries": _cohort_summary_rows(rows),
        "family_slices": family_slices,
        "routed_alerts": routed_alerts,
        "current_cohort_chart": current_cohort_chart,
        "current_family_charts": current_family_charts,
        "remediation": {},
    }


def _candidate_checkpoint_path(source_checkpoint: str) -> Path:
    checkpoint_path = Path(str(source_checkpoint or "").strip() or (ROOT / "ai_from_scratch" / "checkpoint.json"))
    suffix = checkpoint_path.suffix or ".json"
    return checkpoint_path.with_name(f"{checkpoint_path.stem}.remediation_candidate{suffix}")


def _candidate_dataset_path(candidate_checkpoint: Path) -> Path:
    if candidate_checkpoint.suffix:
        return candidate_checkpoint.with_suffix(".dataset.json")
    return candidate_checkpoint.parent / f"{candidate_checkpoint.name}.dataset.json"


def _remediation_label(latest_run_label: str) -> str:
    base = str(latest_run_label or "benchmark").strip() or "benchmark"
    return f"{base}-remediation-proposed"


def _remediation_step_count(gate: dict, routed_alerts: dict, adaptive_status: dict, targeted_families: list[str]) -> int:
    base = 8
    if bool(gate.get("failed", False)):
        base += 8
    base += min(8, int(routed_alerts.get("route_count", 0)) * 2)
    base += min(8, len(targeted_families) * 2)
    if bool(adaptive_status.get("applied", False)):
        base += 4
    return min(32, max(6, base))


def _remediation_learning_rates(gate: dict, targeted_families: list[str]) -> tuple[float, float]:
    if bool(gate.get("failed", False)):
        start = 0.008
    elif targeted_families:
        start = 0.006
    else:
        start = 0.004
    final = max(0.0015, start * 0.35)
    return float(start), float(final)


def _benchmark_remediation_payload(
    rows: list[dict],
    gate: dict,
    routed_alerts: dict,
    *,
    history_dir: str | Path,
) -> dict:
    history_dir_path = Path(history_dir)
    if not rows:
        return {
            "generated_utc": _utc_now(),
            "missing": True,
            "status": "missing",
            "history_dir": str(history_dir_path.resolve()),
            "proposal": {},
            "targeted_families": [],
            "reasons": ["No benchmark history available."],
        }

    latest = rows[-1]
    latest_checkpoint = str(latest.get("checkpoint", "")).strip() or str((ROOT / "ai_from_scratch" / "checkpoint.json").resolve())
    latest_manifest = str(latest.get("manifest_path", "")).strip() or str(DEFAULT_BENCHMARK_MANIFEST.resolve())
    latest_cohort = _record_cohort(latest)
    adaptive_status = benchmark_adaptive_curriculum_status(
        history_dir=history_dir_path,
        cohort=latest_cohort,
        architecture=str(latest.get("architecture", "")).strip(),
        tokenizer_mode=str(latest.get("tokenizer_mode", "")).strip(),
    )
    targeted_family_names = {
        str(item.get("family", "")).strip()
        for item in list(adaptive_status.get("family_signals", []))
        if bool(item.get("regressed", False))
    }
    for alert in list(gate.get("alerts", [])):
        family_name = str(alert.get("family", "")).strip()
        if family_name:
            targeted_family_names.add(family_name)
    targeted_families = sorted(name for name in targeted_family_names if name)

    reasons = [
        f"Gate status: {str(gate.get('status', 'missing'))}",
        f"Alert routes: {int(routed_alerts.get('alert_count', 0))} alerts across {int(routed_alerts.get('route_count', 0))} routes",
        f"Adaptive curriculum: {str(adaptive_status.get('reason', 'missing'))}",
    ]
    if targeted_families:
        reasons.append("Targeted families: " + ", ".join(targeted_families))

    latest_checkpoint_path = Path(latest_checkpoint)
    latest_manifest_path = Path(latest_manifest)
    source_checkpoint_exists = latest_checkpoint_path.exists()
    blocked = not latest_manifest_path.exists() or not str(latest_checkpoint).strip()
    if blocked:
        missing_parts: list[str] = []
        if not str(latest_checkpoint).strip():
            missing_parts.append("checkpoint path missing from latest benchmark record")
        if not latest_manifest_path.exists():
            missing_parts.append(f"manifest missing: {latest_manifest_path}")
        reasons.extend(missing_parts)
        return {
            "generated_utc": _utc_now(),
            "missing": False,
            "status": "blocked",
            "history_dir": str(history_dir_path.resolve()),
            "latest_run_label": str(latest.get("run_label", "")),
            "cohort": latest_cohort,
            "targeted_families": targeted_families,
            "adaptive_status": adaptive_status,
            "gate": gate,
            "alert_routes": routed_alerts,
            "reasons": reasons,
            "proposal": {},
        }
    if not source_checkpoint_exists:
        reasons.append(
            "Latest checkpoint artifact is not present in this workspace; remediation remains proposal-only until the checkpoint is restored."
        )

    candidate_checkpoint = _candidate_checkpoint_path(latest_checkpoint)
    candidate_dataset = _candidate_dataset_path(candidate_checkpoint)
    candidate_report = history_dir_path / "remediation_candidate_benchmark.json"
    suggested_label = _remediation_label(str(latest.get("run_label", "")))
    train_steps = _remediation_step_count(gate, routed_alerts, adaptive_status, targeted_families)
    lr, lr_final = _remediation_learning_rates(gate, targeted_families)
    train_argv = [
        sys.executable,
        str((ROOT / "ai_from_scratch" / "train.py").resolve()),
        "--resume",
        str(latest_checkpoint_path.resolve()),
        "--manifest",
        str(latest_manifest_path.resolve()),
        "--steps",
        str(train_steps),
        "--lr",
        f"{lr:.4f}",
        "--lr-final",
        f"{lr_final:.4f}",
        "--keep-best-valid",
        "--eval-interval",
        "1",
        "--adaptive-history-dir",
        str(history_dir_path.resolve()),
        "--out",
        str(candidate_checkpoint.resolve()),
        "--dataset-out",
        str(candidate_dataset.resolve()),
    ]
    benchmark_argv = [
        sys.executable,
        str((ROOT / "ai_from_scratch" / "benchmark_history.py").resolve()),
        "run",
        "--ckpt",
        str(candidate_checkpoint.resolve()),
        "--manifest",
        str(latest_manifest_path.resolve()),
        "--out",
        str(candidate_report.resolve()),
        "--label",
        suggested_label,
        "--history-dir",
        str(history_dir_path.resolve()),
        "--strict-gate",
    ]
    should_propose = bool(gate.get("failed", False)) or bool(targeted_families) or int(routed_alerts.get("alert_count", 0)) > 0
    status = "proposed" if should_propose else "observe"
    if status == "observe":
        reasons.append("Current cohort is stable or improving, so no remediation run is proposed.")
    else:
        reasons.append("Proposal is safe: it writes a candidate checkpoint instead of overwriting the live model.")
    proposal = {}
    if should_propose:
        proposal = {
            "mode": "proposal_only",
            "safe": True,
            "requires_manual_run": True,
            "source_checkpoint": str(latest_checkpoint_path.resolve()),
            "source_checkpoint_exists": bool(source_checkpoint_exists),
            "candidate_checkpoint": str(candidate_checkpoint.resolve()),
            "candidate_dataset": str(candidate_dataset.resolve()),
            "candidate_benchmark_report": str(candidate_report.resolve()),
            "suggested_run_label": suggested_label,
            "train_steps": int(train_steps),
            "learning_rate": float(lr),
            "final_learning_rate": float(lr_final),
            "train_argv": train_argv,
            "train_command": subprocess.list2cmdline(train_argv),
            "benchmark_argv": benchmark_argv,
            "benchmark_command": subprocess.list2cmdline(benchmark_argv),
        }
    return {
        "generated_utc": _utc_now(),
        "missing": False,
        "status": status,
        "history_dir": str(history_dir_path.resolve()),
        "latest_run_label": str(latest.get("run_label", "")),
        "cohort": latest_cohort,
        "targeted_families": targeted_families,
        "adaptive_status": adaptive_status,
        "gate": gate,
        "alert_routes": routed_alerts,
        "reasons": reasons,
        "proposal": proposal,
    }


def _benchmark_remediation_markdown(payload: dict) -> str:
    lines = ["# Benchmark Remediation Proposal", ""]
    if bool(payload.get("missing", False)):
        lines.append("_No benchmark history available._")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"- Status: {str(payload.get('status', 'missing'))}",
            f"- Latest run: {str(payload.get('latest_run_label', ''))}",
            f"- Cohort: {str(payload.get('cohort', ''))}",
            f"- Targeted families: {', '.join(str(item) for item in payload.get('targeted_families', [])) or '(none)'}",
            "",
            "## Reasons",
            "",
        ]
    )
    for reason in list(payload.get("reasons", [])):
        lines.append(f"- {reason}")
    proposal = dict(payload.get("proposal", {}))
    if proposal:
        lines.extend(
            [
                "",
                "## Safe Follow-Up",
                "",
                f"- Candidate checkpoint: {proposal.get('candidate_checkpoint', '')}",
                f"- Candidate dataset: {proposal.get('candidate_dataset', '')}",
                f"- Candidate benchmark report: {proposal.get('candidate_benchmark_report', '')}",
                f"- Suggested run label: {proposal.get('suggested_run_label', '')}",
                f"- Train steps: {int(proposal.get('train_steps', 0))}",
                f"- Learning rate: {float(proposal.get('learning_rate', 0.0)):.4f} -> {float(proposal.get('final_learning_rate', 0.0)):.4f}",
                "",
                "### Train Command",
                "",
                f"`{proposal.get('train_command', '')}`",
                "",
                "### Benchmark Command",
                "",
                f"`{proposal.get('benchmark_command', '')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _dashboard_markdown(payload: dict) -> str:
    latest = dict(payload.get("latest_run", {}))
    comparison = dict(payload.get("comparison", {}))
    primary_delta = dict(comparison.get("primary_perplexity", {}))
    routed = dict(payload.get("routed_alerts", {}))
    remediation = dict(payload.get("remediation", {}))
    lines = [
        "# Benchmark Dashboard",
        "",
    ]
    if not latest:
        lines.append("_No benchmark history available._")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            f"- Latest run: {latest.get('run_label', '')}",
            f"- UTC: {latest.get('recorded_utc', '')}",
            f"- Suite: {latest.get('suite', '')}",
            f"- Cohort: {latest.get('cohort', '')}",
            f"- Gate: {str(latest.get('gate_status', '')).upper()}",
            f"- Primary perplexity: {float(latest.get('primary_perplexity', 0.0)):.4f}",
            f"- Valid perplexity: {float(latest.get('valid_perplexity', 0.0)):.4f}",
            f"- Train perplexity: {float(latest.get('train_perplexity', 0.0)):.4f}",
            f"- Routed alerts: {int(routed.get('alert_count', 0))} across {int(routed.get('route_count', 0))} routes",
            "",
        ]
    )
    if primary_delta:
        lines.extend(
            [
                "## Regression Snapshot",
                "",
                f"- Trend: {primary_delta.get('trend', 'stable')}",
                f"- Delta: {float(primary_delta.get('delta', 0.0)):.4f}",
                f"- Previous -> Latest: {float(primary_delta.get('previous', 0.0)):.4f} -> {float(primary_delta.get('latest', 0.0)):.4f}",
                "",
            ]
        )
    current_chart = dict(payload.get("current_cohort_chart", {}))
    if current_chart:
        lines.extend(
            [
                "## Cohort Chart",
                "",
                f"- Primary: `{dict(current_chart.get('primary', {})).get('chart', '')}`",
                f"- Valid: `{dict(current_chart.get('valid', {})).get('chart', '')}`",
                f"- Train: `{dict(current_chart.get('train', {})).get('chart', '')}`",
                "",
            ]
        )
    if remediation:
        proposal = dict(remediation.get("proposal", {}))
        lines.extend(
            [
                "## Remediation",
                "",
                f"- Status: {remediation.get('status', 'missing')}",
                f"- Targeted families: {', '.join(str(item) for item in remediation.get('targeted_families', [])) or '(none)'}",
            ]
        )
        for reason in list(remediation.get("reasons", []))[:4]:
            lines.append(f"- Reason: {reason}")
        if proposal:
            lines.append(f"- Candidate checkpoint: {proposal.get('candidate_checkpoint', '')}")
            lines.append(f"- Suggested run label: {proposal.get('suggested_run_label', '')}")
        lines.append("")
    lines.extend(
        [
            "## Top Family Slices",
            "",
            "| Family | Primary PPL | Valid PPL | Train PPL | Corpora |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in list(payload.get("family_slices", []))[:5]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("family", "")),
                    f"{float(item.get('primary_perplexity', 0.0)):.4f}",
                    f"{float(item.get('valid', {}).get('perplexity', 0.0)):.4f}",
                    f"{float(item.get('train', {}).get('perplexity', 0.0)):.4f}",
                    str(int(item.get("corpus_count", 0))),
                ]
            )
            + " |"
        )
    if not list(payload.get("family_slices", [])):
        lines.append("| (none) | 0.0000 | 0.0000 | 0.0000 | 0 |")
    lines.extend(["", "## Alert Routes", ""])
    for route in list(routed.get("routes", [])):
        lines.append(
            f"- {route.get('route', '')}: severity={route.get('severity', '')} "
            f"count={int(route.get('count', 0))} action={route.get('action', '')}"
        )
    if not list(routed.get("routes", [])):
        lines.append("- clear: no active alert routes")
    lines.extend(["", "## Recent Runs", "", "| UTC | Label | Cohort | Gate | Primary PPL |", "|---|---|---|---|---:|"])
    for item in list(payload.get("recent_runs", []))[:8]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("recorded_utc", "")),
                    str(item.get("run_label", "")),
                    str(item.get("cohort", "")),
                    str(item.get("gate_status", "")),
                    f"{float(item.get('primary_perplexity', 0.0)):.4f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _selected_history_rows(
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    *,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
) -> tuple[dict[str, Path], list[dict]]:
    paths = _history_paths(Path(history_dir))
    rows = _load_history(paths["history"])
    rows = _filtered_rows(rows, cohort=cohort, architecture=architecture, tokenizer_mode=tokenizer_mode)
    return paths, rows


def _latest_comparison(rows: list[dict]) -> dict:
    if len(rows) < 2:
        return {}
    latest = rows[-1]
    latest_cohort_rows = _filtered_rows(rows, cohort=_record_cohort(latest))
    if len(latest_cohort_rows) >= 2:
        return compare_records(latest_cohort_rows[-2], latest_cohort_rows[-1])
    return compare_records(rows[-2], rows[-1])


def _write_benchmark_status_artifacts(
    paths: dict[str, Path],
    rows: list[dict],
    gate: dict,
    routed_alerts: dict,
    dashboard: dict,
    remediation: dict,
    *,
    limit: int = 12,
) -> None:
    paths["summary"].write_text(_history_markdown(rows), encoding="utf-8")
    paths["cohorts"].write_text(_cohort_markdown(rows), encoding="utf-8")
    paths["families"].write_text(_family_summary_markdown(rows), encoding="utf-8")
    paths["charts"].write_text(_charts_markdown(rows, limit=limit), encoding="utf-8")
    paths["family_charts"].write_text(_family_charts_markdown(rows, limit=limit), encoding="utf-8")
    paths["charts_json"].write_text(json.dumps(_charts_export(rows, limit=limit), indent=2) + "\n", encoding="utf-8")
    paths["gate"].write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    paths["alerts"].write_text(_gate_markdown(gate), encoding="utf-8")
    paths["alert_routes"].write_text(json.dumps(routed_alerts, indent=2) + "\n", encoding="utf-8")
    paths["dashboard"].write_text(_dashboard_markdown(dashboard), encoding="utf-8")
    paths["dashboard_json"].write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")
    paths["remediation"].write_text(_benchmark_remediation_markdown(remediation), encoding="utf-8")
    paths["remediation_json"].write_text(json.dumps(remediation, indent=2) + "\n", encoding="utf-8")
    comparison = _latest_comparison(rows)
    if comparison:
        paths["compare"].write_text(_comparison_markdown(comparison), encoding="utf-8")


def _build_benchmark_gate_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    paths, rows = _selected_history_rows(
        history_dir,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
    )
    if not rows:
        return {
            "ok": True,
            "missing": True,
            "status": "missing",
            "failed": False,
            "cohort": str(cohort or ""),
            "history_dir": str(paths["dir"].resolve()),
            "alert_count": 0,
            "failure_count": 0,
            "warning_count": 0,
        }
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    gate = evaluate_benchmark_gate(latest, previous=previous, gate_config_path=gate_config_path)
    payload = {
        "ok": True,
        "missing": False,
        "history_dir": str(paths["dir"].resolve()),
        "latest_run_label": str(latest.get("run_label", "")),
        **gate,
    }
    if write:
        paths["gate"].write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
        paths["alerts"].write_text(_gate_markdown(gate), encoding="utf-8")
    return payload


def benchmark_gate_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    if write:
        payload = _build_benchmark_gate_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=True,
        )
        payload["fast_path_cache"] = {"hit": False, "age_seconds": 0.0, "ttl_seconds": None}
        return payload
    payload, cache_meta = cached_compute(
        "benchmark_gate_status",
        json.dumps(
            {
                "history_dir": str(Path(history_dir).resolve()),
                "cohort": str(cohort or ""),
                "architecture": str(architecture or ""),
                "tokenizer_mode": str(tokenizer_mode or ""),
            },
            sort_keys=True,
        ),
        lambda: _benchmark_status_signature(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
        ),
        lambda: _build_benchmark_gate_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=False,
        ),
        ttl_seconds=2.0,
    )
    payload["fast_path_cache"] = cache_meta
    return payload


def benchmark_adaptive_curriculum_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    window: int = 3,
    min_runs: int = 2,
    max_focus_families: int = 2,
    min_regression_delta: float = 0.0,
    min_regression_ratio: float = 0.0,
    max_stage_weight_scale: int = 3,
) -> dict:
    paths, rows = _selected_history_rows(
        history_dir,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
    )
    effective_history_dir = str(paths["dir"].resolve())
    effective_cohort = str(cohort or "").strip()
    required_runs = max(2, int(min_runs))
    if not rows:
        return {
            "ok": True,
            "missing": True,
            "applied": False,
            "history_dir": effective_history_dir,
            "cohort": effective_cohort,
            "history_count": 0,
            "required_runs": required_runs,
            "window": max(2, int(window)),
            "family_signals": [],
            "recommended_stage": {},
            "reason": "missing_history",
        }

    latest = rows[-1]
    effective_cohort = _record_cohort(latest)
    if len(rows) < required_runs:
        return {
            "ok": True,
            "missing": False,
            "applied": False,
            "history_dir": effective_history_dir,
            "cohort": effective_cohort,
            "history_count": len(rows),
            "required_runs": required_runs,
            "window": max(2, int(window)),
            "latest_run_label": str(latest.get("run_label", "")),
            "family_signals": [],
            "recommended_stage": {},
            "reason": "insufficient_runs",
        }

    effective_window = max(2, int(window))
    baseline_rows = rows[-effective_window:-1]
    if not baseline_rows:
        baseline_rows = rows[:-1]
    baseline_primary_values = [float(item.get("primary_perplexity", 0.0)) for item in baseline_rows]
    baseline_primary = float(sum(baseline_primary_values) / max(1, len(baseline_primary_values)))
    latest_primary = float(latest.get("primary_perplexity", 0.0))
    overall_ratio = _metric_ratio(baseline_primary, latest_primary)
    overall_delta = latest_primary - baseline_primary
    overall = {
        "baseline_primary_perplexity": baseline_primary,
        "latest_primary_perplexity": latest_primary,
        "delta": overall_delta,
        "ratio": overall_ratio,
        "trend": str(_metric_delta(baseline_primary, latest_primary).get("trend", "stable")),
        "regressed": bool(overall_delta > float(min_regression_delta) or overall_ratio > float(min_regression_ratio)),
    }

    latest_families = _family_map(latest)
    baseline_family_values: dict[str, list[float]] = {}
    for row in baseline_rows:
        for family_name, family_item in _family_map(row).items():
            baseline_family_values.setdefault(family_name, []).append(float(family_item.get("primary_perplexity", 0.0)))

    signals: list[dict] = []
    for family_name, latest_family in latest_families.items():
        history_values = baseline_family_values.get(family_name, [])
        if not history_values:
            continue
        baseline_value = float(sum(history_values) / len(history_values))
        latest_value = float(latest_family.get("primary_perplexity", 0.0))
        delta = latest_value - baseline_value
        ratio = _metric_ratio(baseline_value, latest_value)
        trend = str(_metric_delta(baseline_value, latest_value).get("trend", "stable"))
        regressed = bool(delta > float(min_regression_delta) or ratio > float(min_regression_ratio))
        severity = max(max(delta, 0.0) / max(1.0, baseline_value), max(ratio, 0.0))
        recommended_weight = 1.0 + min(1.5, severity * 4.0) if regressed else 1.0
        signals.append(
            {
                "family": family_name,
                "baseline_primary_perplexity": baseline_value,
                "latest_primary_perplexity": latest_value,
                "delta": delta,
                "ratio": ratio,
                "trend": trend,
                "regressed": regressed,
                "severity": severity,
                "recommended_weight": recommended_weight,
                "history_points": len(history_values),
            }
        )
    signals.sort(
        key=lambda item: (
            0 if bool(item.get("regressed", False)) else 1,
            -float(item.get("severity", 0.0)),
            str(item.get("family", "")),
        )
    )
    focus_signals = [item for item in signals if bool(item.get("regressed", False))][: max(1, int(max_focus_families))]
    max_severity = max((float(item.get("severity", 0.0)) for item in focus_signals), default=0.0)
    stage_weight_scale = min(max(1, int(max_stage_weight_scale)), max(1, 1 + int(math.ceil(max_severity * 4.0))))
    recommended_stage = {}
    if focus_signals:
        recommended_stage = {
            "name": "adaptive_regression_focus",
            "weight_scale": stage_weight_scale,
            "family_sampling": "weighted",
            "family_weights": {
                str(item["family"]): float(item["recommended_weight"])
                for item in focus_signals
            },
            "include_families": [str(item["family"]) for item in focus_signals],
            "include_corpora": [],
            "adaptive_source": "benchmark_regression",
        }
    return {
        "ok": True,
        "missing": False,
        "applied": bool(focus_signals),
        "history_dir": effective_history_dir,
        "cohort": effective_cohort,
        "history_count": len(rows),
        "required_runs": required_runs,
        "window": effective_window,
        "latest_run_label": str(latest.get("run_label", "")),
        "baseline_run_labels": [str(item.get("run_label", "")) for item in baseline_rows],
        "overall": overall,
        "family_signals": signals,
        "recommended_stage": recommended_stage,
        "reason": "regression_focus" if focus_signals else ("stable_or_improved" if not overall["regressed"] else "no_family_regression"),
    }


def _build_benchmark_remediation_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    paths, rows = _selected_history_rows(
        history_dir,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
    )
    if not rows:
        payload = {
            "ok": True,
            "missing": True,
            "status": "missing",
            "history_dir": str(paths["dir"].resolve()),
            "proposal": {},
            "reasons": ["No benchmark history available."],
        }
        if write:
            paths["remediation"].write_text(_benchmark_remediation_markdown(payload), encoding="utf-8")
            paths["remediation_json"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    gate_status = benchmark_gate_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    alert_status = benchmark_alert_routes_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        alert_route_config_path=alert_route_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    gate = {
        key: value
        for key, value in gate_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    routed = {
        key: value
        for key, value in alert_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    remediation = _benchmark_remediation_payload(rows, gate, routed, history_dir=paths["dir"])
    payload = {
        "ok": True,
        "missing": False,
        "history_dir": str(paths["dir"].resolve()),
        "latest_run_label": str(rows[-1].get("run_label", "")),
        **remediation,
    }
    if write:
        paths["remediation"].write_text(_benchmark_remediation_markdown(remediation), encoding="utf-8")
        paths["remediation_json"].write_text(json.dumps(remediation, indent=2) + "\n", encoding="utf-8")
    return payload


def benchmark_remediation_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    if write:
        payload = _build_benchmark_remediation_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=True,
        )
        payload["fast_path_cache"] = {"hit": False, "age_seconds": 0.0, "ttl_seconds": None}
        return payload
    payload, cache_meta = cached_compute(
        "benchmark_remediation_status",
        json.dumps(
            {
                "history_dir": str(Path(history_dir).resolve()),
                "cohort": str(cohort or ""),
                "architecture": str(architecture or ""),
                "tokenizer_mode": str(tokenizer_mode or ""),
            },
            sort_keys=True,
        ),
        lambda: _benchmark_status_signature(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
        ),
        lambda: _build_benchmark_remediation_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=False,
        ),
        ttl_seconds=2.0,
    )
    payload["fast_path_cache"] = cache_meta
    return payload


def _build_benchmark_alert_routes_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    paths, rows = _selected_history_rows(
        history_dir,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
    )
    if not rows:
        return {
            "ok": True,
            "missing": True,
            "status": "missing",
            "failed": False,
            "history_dir": str(paths["dir"].resolve()),
            "alert_count": 0,
            "route_count": 0,
            "routes": [],
        }
    gate_status = benchmark_gate_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    gate = {
        key: value
        for key, value in gate_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    routed = route_benchmark_alerts(gate, route_config_path=alert_route_config_path)
    payload = {
        "ok": True,
        "missing": False,
        "history_dir": str(paths["dir"].resolve()),
        "latest_run_label": str(rows[-1].get("run_label", "")),
        **routed,
    }
    if write:
        paths["alert_routes"].write_text(json.dumps(routed, indent=2) + "\n", encoding="utf-8")
    return payload


def benchmark_alert_routes_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    write: bool = False,
) -> dict:
    if write:
        payload = _build_benchmark_alert_routes_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=True,
        )
        payload["fast_path_cache"] = {"hit": False, "age_seconds": 0.0, "ttl_seconds": None}
        return payload
    payload, cache_meta = cached_compute(
        "benchmark_alert_routes_status",
        json.dumps(
            {
                "history_dir": str(Path(history_dir).resolve()),
                "cohort": str(cohort or ""),
                "architecture": str(architecture or ""),
                "tokenizer_mode": str(tokenizer_mode or ""),
            },
            sort_keys=True,
        ),
        lambda: _benchmark_status_signature(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
        ),
        lambda: _build_benchmark_alert_routes_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            write=False,
        ),
        ttl_seconds=2.0,
    )
    payload["fast_path_cache"] = cache_meta
    return payload


def _build_benchmark_dashboard_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    limit: int = 8,
    write: bool = False,
) -> dict:
    paths, rows = _selected_history_rows(
        history_dir,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
    )
    if not rows:
        return {
            "ok": True,
            "missing": True,
            "history_dir": str(paths["dir"].resolve()),
            "history_count": 0,
            "dashboard": {},
            "gate": {"status": "missing", "failed": False},
            "alert_routes": {"status": "missing", "routes": []},
            "remediation": {"status": "missing", "proposal": {}},
        }
    gate_status = benchmark_gate_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    alert_status = benchmark_alert_routes_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        alert_route_config_path=alert_route_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    gate = {
        key: value
        for key, value in gate_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    routed = {
        key: value
        for key, value in alert_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    dashboard = _dashboard_payload(rows, routed, limit=limit)
    remediation_status = benchmark_remediation_status(
        history_dir=history_dir,
        gate_config_path=gate_config_path,
        alert_route_config_path=alert_route_config_path,
        cohort=cohort,
        architecture=architecture,
        tokenizer_mode=tokenizer_mode,
        write=False,
    )
    remediation = {
        key: value
        for key, value in remediation_status.items()
        if key not in {"ok", "missing", "history_dir", "latest_run_label"}
    }
    dashboard["remediation"] = remediation
    payload = {
        "ok": True,
        "missing": False,
        "history_dir": str(paths["dir"].resolve()),
        "history_count": len(rows),
        "latest_run_label": str(rows[-1].get("run_label", "")),
        "dashboard": dashboard,
        "gate": gate,
        "alert_routes": routed,
        "remediation": remediation,
    }
    if write:
        _write_benchmark_status_artifacts(paths, rows, gate, routed, dashboard, remediation, limit=max(12, int(limit)))
    return payload


def benchmark_dashboard_status(
    *,
    history_dir: str | Path = BENCHMARK_HISTORY_DIR,
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
    cohort: str = "",
    architecture: str = "",
    tokenizer_mode: str = "",
    limit: int = 8,
    write: bool = False,
) -> dict:
    if write:
        payload = _build_benchmark_dashboard_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            limit=limit,
            write=True,
        )
        payload["fast_path_cache"] = {"hit": False, "age_seconds": 0.0, "ttl_seconds": None}
        payload["cache_surfaces"] = {
            "gate": {"hit": False},
            "alert_routes": {"hit": False},
            "remediation": {"hit": False},
        }
        return payload
    payload, cache_meta = cached_compute(
        "benchmark_dashboard_status",
        json.dumps(
            {
                "history_dir": str(Path(history_dir).resolve()),
                "cohort": str(cohort or ""),
                "architecture": str(architecture or ""),
                "tokenizer_mode": str(tokenizer_mode or ""),
                "limit": int(limit),
            },
            sort_keys=True,
        ),
        lambda: _benchmark_status_signature(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            limit=limit,
        ),
        lambda: _build_benchmark_dashboard_status(
            history_dir=history_dir,
            gate_config_path=gate_config_path,
            alert_route_config_path=alert_route_config_path,
            cohort=cohort,
            architecture=architecture,
            tokenizer_mode=tokenizer_mode,
            limit=limit,
            write=False,
        ),
        ttl_seconds=2.0,
    )
    payload["fast_path_cache"] = cache_meta
    payload["cache_surfaces"] = {
        "gate": dict((payload.get("gate") or {}).get("fast_path_cache") or {}),
        "alert_routes": dict((payload.get("alert_routes") or {}).get("fast_path_cache") or {}),
        "remediation": dict((payload.get("remediation") or {}).get("fast_path_cache") or {}),
    }
    return payload


def _cohort_chart_payloads(rows: list[dict], limit: int = 12) -> list[dict]:
    payloads: list[dict] = []
    for cohort, cohort_rows in sorted(_group_by_cohort(rows).items()):
        window = cohort_rows[-max(1, int(limit)) :]
        latest = cohort_rows[-1]
        payloads.append(
            _build_chart_payload(
                cohort,
                window,
                run_count=len(cohort_rows),
                metadata={
                    "cohort": cohort,
                    "architecture": str(latest.get("architecture", "")),
                    "tokenizer_mode": str(latest.get("tokenizer_mode", "")),
                },
            )
        )
    return payloads


def _family_chart_payloads(rows: list[dict], limit: int = 12, family: str = "") -> list[dict]:
    requested_family = str(family or "").strip()
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        cohort = _record_cohort(row)
        for family_item in _row_families(row):
            family_name = str(family_item.get("family", "")).strip()
            if requested_family and family_name != requested_family:
                continue
            grouped.setdefault((cohort, family_name), []).append(
                {
                    "run_label": str(row.get("run_label", "")),
                    "recorded_utc": str(row.get("recorded_utc", row.get("generated_utc", ""))),
                    "primary_perplexity": float(family_item.get("primary_perplexity", 0.0)),
                    "valid": dict(family_item.get("valid", {})),
                    "train": dict(family_item.get("train", {})),
                    "architecture": str(row.get("architecture", "")),
                    "tokenizer_mode": str(row.get("tokenizer_mode", "")),
                    "family": family_name,
                    "cohort": cohort,
                }
            )
    payloads: list[dict] = []
    for (cohort, family_name), family_rows in sorted(grouped.items()):
        latest = family_rows[-1]
        window = family_rows[-max(1, int(limit)) :]
        payloads.append(
            _build_chart_payload(
                f"{cohort} / {family_name}",
                window,
                run_count=len(family_rows),
                metadata={
                    "cohort": cohort,
                    "family": family_name,
                    "architecture": str(latest.get("architecture", "")),
                    "tokenizer_mode": str(latest.get("tokenizer_mode", "")),
                },
            )
        )
    return payloads


def _chart_block_lines(payload: dict, heading: str) -> list[str]:
    primary = dict(payload.get("primary", {}))
    valid = dict(payload.get("valid", {}))
    train = dict(payload.get("train", {}))
    lines = [f"## {heading}", ""]
    if payload.get("family"):
        lines.append(f"- Family: {payload.get('family', '')}")
    lines.append(f"- Runs: {int(payload.get('run_count', 0))}")
    lines.append(f"- Architecture: {payload.get('architecture', '')}")
    lines.append(f"- Tokenizer: {payload.get('tokenizer_mode', '')}")
    lines.append(f"- Latest primary perplexity: {float(payload.get('latest_primary_perplexity', 0.0)):.4f}")
    lines.append(f"- Best primary perplexity: {float(payload.get('best_primary_perplexity', 0.0)):.4f}")
    lines.append(f"- Primary chart: `{primary.get('chart', '')}`")
    lines.append(f"- Valid chart: `{valid.get('chart', '')}`")
    lines.append(f"- Train chart: `{train.get('chart', '')}`")
    lines.append(f"- Labels: {', '.join(str(label) for label in payload.get('labels', [])) or '(none)'}")
    lines.append(
        f"- Primary values: {', '.join(f'{float(value):.4f}' for value in primary.get('values', [])) or '(none)'}"
    )
    lines.append(
        f"- Valid values: {', '.join(f'{float(value):.4f}' for value in valid.get('values', [])) or '(none)'}"
    )
    lines.append(
        f"- Train values: {', '.join(f'{float(value):.4f}' for value in train.get('values', [])) or '(none)'}"
    )
    lines.append("")
    return lines


def _charts_markdown(rows: list[dict], limit: int = 12) -> str:
    lines = ["# Benchmark Trend Charts", ""]
    for payload in _cohort_chart_payloads(rows, limit):
        lines.extend(_chart_block_lines(payload, str(payload.get("cohort", payload.get("name", "")))))
    return "\n".join(lines)


def _family_charts_markdown(rows: list[dict], limit: int = 12, family: str = "") -> str:
    lines = ["# Benchmark Family Trend Charts", ""]
    for payload in _family_chart_payloads(rows, limit=limit, family=family):
        lines.extend(_chart_block_lines(payload, str(payload.get("name", ""))))
    return "\n".join(lines)


def _charts_export(rows: list[dict], limit: int = 12) -> dict:
    return {
        "generated_utc": _utc_now(),
        "cohort_charts": _cohort_chart_payloads(rows, limit=limit),
        "family_charts": _family_chart_payloads(rows, limit=limit),
        "latest_family_slices": _row_families(rows[-1]) if rows else [],
    }


def record_benchmark_run(
    checkpoint_path: str,
    *,
    manifest_path: str | Path = DEFAULT_BENCHMARK_MANIFEST,
    out_path: str | Path = DEFAULT_OUTPUT,
    history_dir: Path = BENCHMARK_HISTORY_DIR,
    label: str = "",
    gate_config_path: str | Path = DEFAULT_GATE_CONFIG,
    alert_route_config_path: str | Path = DEFAULT_ALERT_ROUTE_CONFIG,
) -> dict:
    report = run_benchmark_suite(checkpoint_path, manifest_path=manifest_path)
    report["recorded_utc"] = _utc_now()
    report["run_label"] = str(label or f"{Path(checkpoint_path).stem}-{report.get('suite', 'benchmark')}")

    paths = _history_paths(history_dir)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    rows_before = _load_history(paths["history"])
    previous_rows = _filtered_rows(rows_before, cohort=_record_cohort(report))
    previous = previous_rows[-1] if previous_rows else None
    report["gate"] = evaluate_benchmark_gate(report, previous=previous, gate_config_path=gate_config_path)
    report["alert_routes"] = route_benchmark_alerts(report["gate"], route_config_path=alert_route_config_path)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    paths["latest"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _append_history(report, paths["history"])

    rows = _load_history(paths["history"])
    dashboard = _dashboard_payload(rows, report["alert_routes"])
    remediation = _benchmark_remediation_payload(rows, report["gate"], report["alert_routes"], history_dir=paths["dir"])
    dashboard["remediation"] = remediation
    report["remediation"] = remediation
    out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    paths["latest"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_benchmark_status_artifacts(paths, rows, report["gate"], report["alert_routes"], dashboard, remediation)
    return report


def cmd_run(args: argparse.Namespace) -> int:
    history_dir = Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR
    paths = _history_paths(history_dir)
    report = record_benchmark_run(
        args.ckpt,
        manifest_path=args.manifest,
        out_path=args.out,
        history_dir=history_dir,
        label=args.label,
        gate_config_path=args.gate_config,
        alert_route_config_path=args.alert_route_config,
    )
    print(json.dumps(report, indent=2))
    print(f"Saved latest: {paths['latest']}")
    print(f"Appended history: {paths['history']}")
    print(f"History summary: {paths['summary']}")
    print(f"Cohort summary: {paths['cohorts']}")
    print(f"Family summary: {paths['families']}")
    print(f"Trend charts: {paths['charts']}")
    print(f"Family charts: {paths['family_charts']}")
    print(f"Chart export JSON: {paths['charts_json']}")
    print(f"Gate status: {paths['gate']}")
    print(f"Gate alerts: {paths['alerts']}")
    print(f"Alert routes: {paths['alert_routes']}")
    print(f"Dashboard: {paths['dashboard']}")
    print(f"Dashboard JSON: {paths['dashboard_json']}")
    print(f"Remediation: {paths['remediation']}")
    print(f"Remediation JSON: {paths['remediation_json']}")
    if paths["compare"].exists():
        print(f"Latest comparison: {paths['compare']}")
    if args.strict_gate and bool(dict(report.get("gate", {})).get("failed", False)):
        return 1
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    rows = _load_history(_history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    print(f"History entries: {len(rows)}")
    if not rows:
        return 0
    for row in rows[-max(1, int(args.limit)):][::-1]:
        print(
            f"{row.get('recorded_utc', row.get('generated_utc', ''))} "
            f"label={row.get('run_label', '')} suite={row.get('suite', '')} "
            f"architecture={row.get('architecture', '')} tokenizer={row.get('tokenizer_mode', '')} "
            f"cohort={_record_cohort(row)} "
            f"gate={dict(row.get('gate', {})).get('status', '')} "
            f"primary_ppl={float(row.get('primary_perplexity', 0.0)):.4f} "
            f"valid_ppl={float(row.get('valid', {}).get('perplexity', 0.0)):.4f} "
            f"train_ppl={float(row.get('train', {}).get('perplexity', 0.0)):.4f}"
        )
    return 0


def cmd_cohorts(args: argparse.Namespace) -> int:
    rows = _load_history(_history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)["history"])
    summaries = _cohort_summary_rows(rows)
    print(f"Cohorts: {len(summaries)}")
    for item in summaries:
        print(
            f"cohort={item['cohort']} architecture={item['architecture']} tokenizer={item['tokenizer_mode']} "
            f"runs={int(item['run_count'])} latest_ppl={float(item['latest_primary_perplexity']):.4f} "
            f"best_ppl={float(item['best_primary_perplexity']):.4f} trend={item['trend']} delta={float(item['delta']):.4f}"
        )
    return 0


def cmd_families(args: argparse.Namespace) -> int:
    rows = _load_history(_history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if not rows:
        print("No benchmark rows available for the requested family filter.")
        return 0
    latest = rows[-1]
    families = _row_families(latest)
    requested_family = str(args.family or "").strip()
    if requested_family:
        families = [item for item in families if str(item.get("family", "")).strip() == requested_family]
    print(
        f"Family slices: {len(families)} "
        f"run={latest.get('run_label', '')} "
        f"cohort={_record_cohort(latest)}"
    )
    for item in families:
        print(
            f"family={item.get('family', '')} corpora={int(item.get('corpus_count', 0))} "
            f"primary_ppl={float(item.get('primary_perplexity', 0.0)):.4f} "
            f"valid_ppl={float(item.get('valid', {}).get('perplexity', 0.0)):.4f} "
            f"train_ppl={float(item.get('train', {}).get('perplexity', 0.0)):.4f} "
            f"names={','.join(str(name) for name in item.get('corpus_names', []))}"
        )
    return 0


def cmd_chart(args: argparse.Namespace) -> int:
    rows = _load_history(_history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if not rows:
        print("No benchmark rows available for the requested chart filter.")
        return 0
    if str(args.family or "").strip():
        print(_family_charts_markdown(rows, limit=args.limit, family=args.family))
    else:
        print(_charts_markdown(rows, limit=args.limit))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    paths = _history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)
    rows = _load_history(paths["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if len(rows) < 2:
        print("Need at least 2 benchmark history entries.")
        return 1
    comparison = compare_records(rows[-2], rows[-1])
    print(json.dumps(comparison, indent=2))
    if args.write:
        paths["compare"].parent.mkdir(parents=True, exist_ok=True)
        paths["compare"].write_text(_comparison_markdown(comparison), encoding="utf-8")
        print(f"Wrote comparison: {paths['compare']}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    paths = _history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)
    rows = _load_history(paths["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if not rows:
        print("No benchmark rows available for gate evaluation.")
        return 1 if args.strict else 0
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    gate = evaluate_benchmark_gate(latest, previous=previous, gate_config_path=args.gate_config)
    print(json.dumps(gate, indent=2))
    if args.write:
        paths["gate"].write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
        paths["alerts"].write_text(_gate_markdown(gate), encoding="utf-8")
        print(f"Wrote gate: {paths['gate']}")
        print(f"Wrote alerts: {paths['alerts']}")
    if args.strict and bool(gate.get("failed", False)):
        return 1
    return 0


def cmd_alerts(args: argparse.Namespace) -> int:
    paths = _history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)
    rows = _load_history(paths["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if not rows:
        print("No benchmark rows available for alert routing.")
        return 1 if args.strict else 0
    latest = rows[-1]
    gate = dict(latest.get("gate", {}))
    if not gate:
        previous = rows[-2] if len(rows) >= 2 else None
        gate = evaluate_benchmark_gate(latest, previous=previous, gate_config_path=args.gate_config)
    routed = route_benchmark_alerts(gate, route_config_path=args.alert_route_config)
    print(json.dumps(routed, indent=2))
    if args.write:
        paths["alert_routes"].write_text(json.dumps(routed, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote alert routes: {paths['alert_routes']}")
    if args.strict and bool(routed.get("failed", False)):
        return 1
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    paths = _history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)
    rows = _load_history(paths["history"])
    rows = _filtered_rows(rows, cohort=args.cohort, architecture=args.architecture, tokenizer_mode=args.tokenizer_mode)
    if not rows:
        print("No benchmark rows available for dashboard rendering.")
        return 0
    latest = rows[-1]
    gate = dict(latest.get("gate", {}))
    if not gate:
        previous = rows[-2] if len(rows) >= 2 else None
        gate = evaluate_benchmark_gate(latest, previous=previous, gate_config_path=args.gate_config)
    routed = route_benchmark_alerts(gate, route_config_path=args.alert_route_config)
    dashboard = _dashboard_payload(rows, routed, limit=args.limit)
    markdown = _dashboard_markdown(dashboard)
    print(markdown)
    if args.write:
        paths["dashboard"].write_text(markdown, encoding="utf-8")
        paths["dashboard_json"].write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote dashboard: {paths['dashboard']}")
        print(f"Wrote dashboard JSON: {paths['dashboard_json']}")
    return 0


def cmd_remediation(args: argparse.Namespace) -> int:
    remediation = benchmark_remediation_status(
        history_dir=Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR,
        gate_config_path=args.gate_config,
        alert_route_config_path=args.alert_route_config,
        cohort=args.cohort,
        architecture=args.architecture,
        tokenizer_mode=args.tokenizer_mode,
        write=args.write,
    )
    print(json.dumps(remediation, indent=2))
    if args.write:
        paths = _history_paths(Path(args.history_dir) if args.history_dir else BENCHMARK_HISTORY_DIR)
        print(f"Wrote remediation: {paths['remediation']}")
        print(f"Wrote remediation JSON: {paths['remediation_json']}")
    if args.strict and str(remediation.get("status", "")) in {"blocked", "proposed"}:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="History and trend tools for Zero AI model benchmarks.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run benchmark suite and record history.")
    p_run.add_argument("--ckpt", default="ai_from_scratch/checkpoint.json")
    p_run.add_argument("--manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    p_run.add_argument("--out", default=str(DEFAULT_OUTPUT))
    p_run.add_argument("--label", default="")
    p_run.add_argument("--history-dir", default="")
    p_run.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    p_run.add_argument("--alert-route-config", default=str(DEFAULT_ALERT_ROUTE_CONFIG))
    p_run.add_argument("--strict-gate", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_history = sub.add_parser("history", help="Show recent model benchmark history.")
    p_history.add_argument("--limit", type=int, default=10)
    p_history.add_argument("--history-dir", default="")
    p_history.add_argument("--cohort", default="")
    p_history.add_argument("--architecture", default="")
    p_history.add_argument("--tokenizer-mode", default="")
    p_history.set_defaults(func=cmd_history)

    p_cohorts = sub.add_parser("cohorts", help="Show benchmark cohort summaries.")
    p_cohorts.add_argument("--history-dir", default="")
    p_cohorts.set_defaults(func=cmd_cohorts)

    p_families = sub.add_parser("families", help="Show family slices from the latest benchmark run.")
    p_families.add_argument("--history-dir", default="")
    p_families.add_argument("--cohort", default="")
    p_families.add_argument("--architecture", default="")
    p_families.add_argument("--tokenizer-mode", default="")
    p_families.add_argument("--family", default="")
    p_families.set_defaults(func=cmd_families)

    p_chart = sub.add_parser("chart", help="Show simple ASCII trend charts for benchmark cohorts.")
    p_chart.add_argument("--history-dir", default="")
    p_chart.add_argument("--limit", type=int, default=12)
    p_chart.add_argument("--cohort", default="")
    p_chart.add_argument("--architecture", default="")
    p_chart.add_argument("--tokenizer-mode", default="")
    p_chart.add_argument("--family", default="")
    p_chart.set_defaults(func=cmd_chart)

    p_compare = sub.add_parser("compare", help="Compare previous vs latest benchmark run.")
    p_compare.add_argument("--write", action="store_true")
    p_compare.add_argument("--history-dir", default="")
    p_compare.add_argument("--cohort", default="")
    p_compare.add_argument("--architecture", default="")
    p_compare.add_argument("--tokenizer-mode", default="")
    p_compare.set_defaults(func=cmd_compare)

    p_gate = sub.add_parser("gate", help="Evaluate benchmark gate status for the latest filtered run.")
    p_gate.add_argument("--history-dir", default="")
    p_gate.add_argument("--cohort", default="")
    p_gate.add_argument("--architecture", default="")
    p_gate.add_argument("--tokenizer-mode", default="")
    p_gate.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    p_gate.add_argument("--write", action="store_true")
    p_gate.add_argument("--strict", action="store_true")
    p_gate.set_defaults(func=cmd_gate)

    p_alerts = sub.add_parser("alerts", help="Route latest benchmark alerts into named action lanes.")
    p_alerts.add_argument("--history-dir", default="")
    p_alerts.add_argument("--cohort", default="")
    p_alerts.add_argument("--architecture", default="")
    p_alerts.add_argument("--tokenizer-mode", default="")
    p_alerts.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    p_alerts.add_argument("--alert-route-config", default=str(DEFAULT_ALERT_ROUTE_CONFIG))
    p_alerts.add_argument("--write", action="store_true")
    p_alerts.add_argument("--strict", action="store_true")
    p_alerts.set_defaults(func=cmd_alerts)

    p_dashboard = sub.add_parser("dashboard", help="Render a compact benchmark dashboard for the latest filtered run.")
    p_dashboard.add_argument("--history-dir", default="")
    p_dashboard.add_argument("--cohort", default="")
    p_dashboard.add_argument("--architecture", default="")
    p_dashboard.add_argument("--tokenizer-mode", default="")
    p_dashboard.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    p_dashboard.add_argument("--alert-route-config", default=str(DEFAULT_ALERT_ROUTE_CONFIG))
    p_dashboard.add_argument("--limit", type=int, default=8)
    p_dashboard.add_argument("--write", action="store_true")
    p_dashboard.set_defaults(func=cmd_dashboard)

    p_remediation = sub.add_parser("remediation", help="Propose a safe follow-up benchmark remediation run.")
    p_remediation.add_argument("--history-dir", default="")
    p_remediation.add_argument("--cohort", default="")
    p_remediation.add_argument("--architecture", default="")
    p_remediation.add_argument("--tokenizer-mode", default="")
    p_remediation.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    p_remediation.add_argument("--alert-route-config", default=str(DEFAULT_ALERT_ROUTE_CONFIG))
    p_remediation.add_argument("--write", action="store_true")
    p_remediation.add_argument("--strict", action="store_true")
    p_remediation.set_defaults(func=cmd_remediation)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
