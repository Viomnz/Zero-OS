from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os.smart_logic_governance import apply_governance

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "antivirus"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sig_path(cwd: str) -> Path:
    return _state_root(cwd) / "threat_feed.json"


def _policy_path(cwd: str) -> Path:
    return _state_root(cwd) / "policy.json"


def _monitor_path(cwd: str) -> Path:
    return _state_root(cwd) / "monitor.json"


def _snapshot_path(cwd: str) -> Path:
    return _state_root(cwd) / "monitor_snapshot.json"


def _quarantine_dir(cwd: str) -> Path:
    p = _state_root(cwd) / "quarantine"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _q_index_path(cwd: str) -> Path:
    return _state_root(cwd) / "quarantine_index.json"


def _suppression_path(cwd: str) -> Path:
    return _state_root(cwd) / "suppressions.json"


def _incident_path(cwd: str) -> Path:
    return _state_root(cwd) / "incidents.jsonl"


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _feed_key(cwd: str) -> bytes:
    key_path = Path(cwd).resolve() / ".zero_os" / "keys" / "antivirus_feed.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_text(hashlib.sha256(str(key_path).encode("utf-8")).hexdigest(), encoding="utf-8")
    return key_path.read_text(encoding="utf-8", errors="replace").strip().encode("utf-8")


def _sign_feed_payload(cwd: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_feed_key(cwd), canonical, hashlib.sha256).hexdigest()


def default_threat_feed() -> dict:
    return {
        "version": 1,
        "updated_utc": _utc_now(),
        "signatures": [
            {"id": "EICAR-SIM", "kind": "contains", "value": "EICAR-STANDARD-ANTIVIRUS-TEST-FILE", "severity": "high"},
            {"id": "QVIR-SIM", "kind": "contains", "value": "quantum-virus-signature", "severity": "high"},
            {"id": "PS-ENC", "kind": "contains", "value": "FromBase64String(", "severity": "medium"},
            {"id": "CMD-DROP", "kind": "contains", "value": "powershell -enc", "severity": "high"},
            {"id": "WGET-EXE", "kind": "contains", "value": "wget http", "severity": "medium"},
        ],
    }


def threat_feed_status(cwd: str) -> dict:
    path = _sig_path(cwd)
    if not path.exists():
        feed = default_threat_feed()
        _save(path, feed)
        return feed
    return _load(path, default_threat_feed())


def threat_feed_update(cwd: str) -> dict:
    current = threat_feed_status(cwd)
    current["updated_utc"] = _utc_now()
    current["version"] = int(current.get("version", 1)) + 1
    _save(_sig_path(cwd), current)
    return current


def threat_feed_export_signed(cwd: str, out_path: str) -> dict:
    feed = threat_feed_status(cwd)
    payload = {"feed": feed, "signed_utc": _utc_now()}
    payload["signature"] = _sign_feed_payload(cwd, {"feed": feed, "signed_utc": payload["signed_utc"]})
    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(target), "version": feed.get("version")}


def threat_feed_import_signed(cwd: str, in_path: str) -> dict:
    p = Path(in_path).resolve()
    if not p.exists():
        return {"ok": False, "reason": "signed feed file missing"}
    data = _load(p, {})
    if not isinstance(data, dict):
        return {"ok": False, "reason": "invalid signed feed file"}
    sig = str(data.get("signature", ""))
    core = {"feed": data.get("feed", {}), "signed_utc": data.get("signed_utc", "")}
    expected = _sign_feed_payload(cwd, core)
    if not sig or not hmac.compare_digest(sig, expected):
        return {"ok": False, "reason": "invalid signature"}
    feed = core["feed"] if isinstance(core["feed"], dict) else {}
    if not isinstance(feed.get("signatures", []), list):
        return {"ok": False, "reason": "invalid feed payload"}
    _save(_sig_path(cwd), feed)
    return {"ok": True, "version": int(feed.get("version", 0)), "signature_valid": True}


def policy_status(cwd: str) -> dict:
    default = {
        "heuristic_threshold": 65,
        "auto_quarantine": False,
        "exclude_paths": [".git", ".zero_os/production/snapshots"],
        "exclude_extensions": [".png", ".jpg", ".jpeg", ".mp3", ".mp4"],
        "max_files_per_scan": 5000,
        "max_file_mb": 8,
        "archive_max_depth": 2,
        "archive_max_entries": 700,
        "restore_overwrite": False,
        "response_mode": "manual",
    }
    path = _policy_path(cwd)
    if not path.exists():
        _save(path, default)
        return default
    cur = _load(path, default)
    for k, v in default.items():
        cur.setdefault(k, v)
    _save(path, cur)
    return cur


def policy_set(cwd: str, key: str, value: str) -> dict:
    p = policy_status(cwd)
    k = key.strip().lower()
    if k in {"heuristic_threshold", "max_files_per_scan", "max_file_mb", "archive_max_depth", "archive_max_entries"}:
        p[k] = max(0, int(value))
    elif k in {"auto_quarantine", "restore_overwrite"}:
        p[k] = value.strip().lower() in {"1", "true", "yes", "on"}
    elif k == "response_mode":
        v = value.strip().lower()
        if v not in {"manual", "quarantine_high", "quarantine_critical"}:
            raise ValueError("unsupported response_mode")
        p[k] = v
    else:
        raise ValueError("unsupported policy key")
    _save(_policy_path(cwd), p)
    return p


def suppression_list(cwd: str) -> dict:
    data = _load(_suppression_path(cwd), {"items": []})
    items = [x for x in data.get("items", []) if isinstance(x, dict)]
    return {"ok": True, "count": len(items), "items": items}


def suppression_add(cwd: str, signature_id: str, path_prefix: str = "", hours: int = 24) -> dict:
    data = _load(_suppression_path(cwd), {"items": []})
    rec = {
        "id": hashlib.sha1((signature_id + path_prefix + _utc_now()).encode("utf-8")).hexdigest()[:10],
        "signature_id": signature_id.strip(),
        "path_prefix": path_prefix.strip().replace("\\", "/"),
        "created_utc": _utc_now(),
        "expires_utc": (datetime.now(timezone.utc) + timedelta(hours=max(1, int(hours)))).isoformat(),
    }
    data["items"].append(rec)
    _save(_suppression_path(cwd), data)
    return {"ok": True, **rec}


def suppression_remove(cwd: str, suppression_id: str) -> dict:
    data = _load(_suppression_path(cwd), {"items": []})
    before = len(data.get("items", []))
    data["items"] = [x for x in data.get("items", []) if str(x.get("id")) != suppression_id]
    _save(_suppression_path(cwd), data)
    return {"ok": True, "removed": before - len(data["items"])}


def _suppression_active(item: dict) -> bool:
    try:
        exp = datetime.fromisoformat(str(item.get("expires_utc", "")))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp >= datetime.now(timezone.utc)
    except Exception:
        return False


def _is_suppressed(cwd: str, rel_path: str, sig_id: str) -> bool:
    items = _load(_suppression_path(cwd), {"items": []}).get("items", [])
    rel = rel_path.replace("\\", "/")
    for item in items:
        if not isinstance(item, dict) or not _suppression_active(item):
            continue
        s = str(item.get("signature_id", "")).strip()
        p = str(item.get("path_prefix", "")).strip()
        if s and s != sig_id:
            continue
        if p and not rel.startswith(p):
            continue
        return True
    return False


def _excluded(base: Path, target: Path, policy: dict) -> bool:
    rel = str(target.resolve().relative_to(base)).replace("\\", "/")
    if target.suffix.lower() in {x.lower() for x in policy.get("exclude_extensions", [])}:
        return True
    for pref in policy.get("exclude_paths", []):
        if rel.startswith(pref.replace("\\", "/")):
            return True
    return False


def _iter_targets(cwd: str, raw_target: str, max_files: int) -> list[Path]:
    base = Path(cwd).resolve()
    target = (base / raw_target).resolve() if not Path(raw_target).is_absolute() else Path(raw_target).resolve()
    out: list[Path] = []
    if target.is_file():
        return [target]
    if target.is_dir():
        for p in target.rglob("*"):
            if p.is_file():
                out.append(p)
                if len(out) >= max_files:
                    break
        return out
    return []


def _match_signatures(text: str, feed: dict) -> list[dict]:
    hits = []
    low = text.lower()
    for sig in feed.get("signatures", []):
        if sig.get("kind") == "contains" and str(sig.get("value", "")).lower() in low:
            hits.append({"id": sig.get("id", "unknown"), "severity": sig.get("severity", "medium")})
    return hits


def _scan_zip_bytes(blob: bytes, feed: dict, depth: int, max_depth: int, max_entries: int, prefix: str = "zip") -> list[dict]:
    findings = []
    if depth > max_depth:
        return findings
    try:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(blob), "r") as zf:
            for i, name in enumerate(zf.namelist()):
                if i >= max_entries:
                    break
                try:
                    data = zf.read(name)
                except Exception:
                    continue
                text = data.decode("utf-8", errors="ignore")
                for hit in _match_signatures(text, feed):
                    findings.append({"signature": hit["id"], "severity": hit["severity"], "evidence": f"{prefix}:{name}"})
                if name.lower().endswith(".zip"):
                    findings.extend(
                        _scan_zip_bytes(
                            data,
                            feed,
                            depth=depth + 1,
                            max_depth=max_depth,
                            max_entries=max_entries,
                            prefix=f"{prefix}:{name}",
                        )
                    )
    except Exception:
        return findings
    return findings


def _scan_zip(path: Path, feed: dict, policy: dict) -> list[dict]:
    try:
        return _scan_zip_bytes(
            path.read_bytes(),
            feed,
            depth=0,
            max_depth=int(policy.get("archive_max_depth", 2)),
            max_entries=int(policy.get("archive_max_entries", 700)),
        )
    except Exception:
        return []


def _heuristic_score(text: str, name: str) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    tokens = [
        ("frombase64string(", 35, "encoded_payload"),
        ("powershell -enc", 40, "encoded_exec"),
        ("invoke-expression", 35, "dynamic_exec"),
        ("reg add", 20, "persistence"),
        ("schtasks", 20, "scheduled_task"),
        ("quantum-virus-signature", 45, "quantum_marker"),
        ("-nop", 10, "powershell_noprofile"),
    ]
    low = text.lower()
    for needle, pts, tag in tokens:
        if needle in low:
            score += pts
            reasons.append(tag)
    if name.lower().endswith((".ps1", ".bat", ".cmd")) and "http" in low:
        score += 20
        reasons.append("script_network_dropper")
    return min(100, score), reasons


def _severity_rank(s: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(s.lower(), 1)


def _severity_from_finding(finding: dict) -> str:
    sev = "low"
    for hit in finding.get("signature_hits", []):
        if _severity_rank(hit.get("severity", "low")) > _severity_rank(sev):
            sev = hit.get("severity", "low")
    for hit in finding.get("archive_hits", []):
        if _severity_rank(hit.get("severity", "low")) > _severity_rank(sev):
            sev = hit.get("severity", "low")
    hs = int(finding.get("heuristic_score", 0))
    if hs >= 90:
        sev = "critical"
    elif hs >= 70 and _severity_rank(sev) < _severity_rank("high"):
        sev = "high"
    elif hs >= 50 and _severity_rank(sev) < _severity_rank("medium"):
        sev = "medium"
    return sev


def _recommend_actions(severity: str) -> list[str]:
    if severity == "critical":
        return ["quarantine", "block execution", "incident review"]
    if severity == "high":
        return ["quarantine", "verify backups", "security review"]
    if severity == "medium":
        return ["manual triage", "increase monitoring"]
    return ["log only"]


def _process_behavior_findings() -> list[dict]:
    suspicious_names = {"powershell.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe"}
    findings = []
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, check=False)
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line.startswith('"'):
                continue
            name = line.split('","', 1)[0].strip('"').lower()
            if name in suspicious_names:
                findings.append({"process": name, "severity": "medium", "reason": "suspicious_process_name"})
    except Exception:
        return findings
    return findings


def _smart_logic_antivirus(findings: list[dict], process_findings: list[dict], highest: str, policy: dict) -> dict:
    high_or_critical = [f for f in findings if _severity_rank(str(f.get("severity", "low"))) >= _severity_rank("high")]
    mode = str(policy.get("response_mode", "manual"))
    if high_or_critical:
        action = "quarantine_now" if mode != "manual" else "manual_containment"
        reason = "high_severity_payload_detected"
    elif process_findings:
        action = "increase_monitoring"
        reason = "suspicious_process_behavior"
    elif findings:
        action = "triage"
        reason = "medium_or_low_findings"
    else:
        action = "allow"
        reason = "clean_scan"
    confidence = 0.95 if reason == "clean_scan" else 0.85 if high_or_critical else 0.75 if findings else 0.7
    return {
        "engine": "antivirus_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "highest_severity": highest,
        "high_or_critical_count": len(high_or_critical),
        "process_findings_count": len(process_findings),
        "policy_mode": mode,
        "confidence": confidence,
    }


def scan_target(cwd: str, target: str) -> dict:
    base = Path(cwd).resolve()
    feed = threat_feed_status(cwd)
    policy = policy_status(cwd)
    files = _iter_targets(cwd, target, max_files=int(policy.get("max_files_per_scan", 5000)))
    findings = []
    skipped_large = 0

    for f in files:
        try:
            f.relative_to(base)
        except ValueError:
            continue
        if _excluded(base, f, policy):
            continue
        if f.stat().st_size > int(policy.get("max_file_mb", 8)) * 1024 * 1024:
            skipped_large += 1
            continue

        text = f.read_text(encoding="utf-8", errors="ignore") if f.suffix.lower() not in {".exe", ".dll", ".bin"} else ""
        sig_hits = _match_signatures(text, feed)
        rel = str(f.relative_to(base)).replace("\\", "/")
        sig_hits = [h for h in sig_hits if not _is_suppressed(cwd, rel, str(h.get("id", "")))]
        heur_score, heur_tags = _heuristic_score(text, f.name)
        archive_hits = _scan_zip(f, feed, policy) if f.suffix.lower() == ".zip" else []
        archive_hits = [h for h in archive_hits if not _is_suppressed(cwd, rel, str(h.get("signature", "")))]

        if sig_hits or archive_hits or heur_score >= int(policy.get("heuristic_threshold", 65)):
            item = {
                "path": str(f.relative_to(base)).replace("\\", "/"),
                "sha256": _sha256(f),
                "signature_hits": sig_hits,
                "heuristic_score": heur_score,
                "heuristic_reasons": heur_tags,
                "archive_hits": archive_hits,
            }
            item["severity"] = _severity_from_finding(item)
            item["recommended_actions"] = _recommend_actions(item["severity"])
            findings.append(item)

    process_findings = _process_behavior_findings()
    highest = "low"
    for fnd in findings:
        if _severity_rank(fnd.get("severity", "low")) > _severity_rank(highest):
            highest = fnd.get("severity", "low")
    for pf in process_findings:
        if _severity_rank(pf.get("severity", "low")) > _severity_rank(highest):
            highest = pf.get("severity", "low")

    smart_logic = apply_governance(
        cwd,
        _smart_logic_antivirus(findings, process_findings, highest, policy),
        {"target": target, "finding_count": len(findings)},
    )
    report = {
        "ok": True,
        "target": target,
        "scanned_files": len(files),
        "skipped_large_files": skipped_large,
        "finding_count": len(findings),
        "process_finding_count": len(process_findings),
        "highest_severity": highest,
        "incident_actions": _recommend_actions(highest),
        "smart_logic": smart_logic,
        "findings": findings[:500],
        "process_findings": process_findings[:200],
        "time_utc": _utc_now(),
    }
    _save(_state_root(cwd) / "last_scan.json", report)
    with _incident_path(cwd).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"time_utc": _utc_now(), "kind": "scan", "report": report}, sort_keys=True) + "\n")

    if policy.get("auto_quarantine"):
        for item in findings[:100]:
            quarantine_file(cwd, item["path"], reason="auto_quarantine")
    _auto_response(cwd, report)

    return report


def _auto_response(cwd: str, report: dict) -> None:
    mode = str(policy_status(cwd).get("response_mode", "manual"))
    if mode == "manual":
        return
    threshold = "high" if mode == "quarantine_high" else "critical"
    for item in report.get("findings", [])[:100]:
        sev = str(item.get("severity", "low"))
        if _severity_rank(sev) >= _severity_rank(threshold):
            quarantine_file(cwd, str(item.get("path", "")), reason=f"response_{mode}")


def quarantine_file(cwd: str, rel_path: str, reason: str = "manual") -> dict:
    base = Path(cwd).resolve()
    src = (base / rel_path).resolve()
    try:
        src.relative_to(base)
    except ValueError:
        return {"ok": False, "reason": "path escapes workspace"}
    if not src.exists() or not src.is_file():
        return {"ok": False, "reason": "file missing"}

    qdir = _quarantine_dir(cwd)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    qname = f"{src.name}__{stamp}"
    dst = qdir / qname
    shutil.move(str(src), str(dst))

    idx = _load(_q_index_path(cwd), {"items": []})
    rec = {
        "id": hashlib.sha1((str(dst) + stamp).encode("utf-8")).hexdigest()[:12],
        "time_utc": _utc_now(),
        "reason": reason,
        "original_rel": rel_path.replace("\\", "/"),
        "quarantine_path": str(dst),
        "sha256": _sha256(dst),
    }
    idx["items"].append(rec)
    _save(_q_index_path(cwd), idx)
    return {"ok": True, **rec}


def quarantine_list(cwd: str) -> dict:
    idx = _load(_q_index_path(cwd), {"items": []})
    return {"ok": True, "count": len(idx.get("items", [])), "items": idx.get("items", [])[-200:]}


def quarantine_restore(cwd: str, item_id: str) -> dict:
    base = Path(cwd).resolve()
    idx = _load(_q_index_path(cwd), {"items": []})
    policy = policy_status(cwd)
    items = idx.get("items", [])
    target = None
    for it in items:
        if str(it.get("id")) == item_id:
            target = it
            break
    if not target:
        return {"ok": False, "reason": "item not found"}

    src = Path(str(target.get("quarantine_path", "")))
    if not src.exists():
        return {"ok": False, "reason": "quarantine file missing"}
    if _sha256(src) != str(target.get("sha256", "")):
        return {"ok": False, "reason": "quarantine hash mismatch"}

    dst = (base / str(target.get("original_rel", ""))).resolve()
    try:
        dst.relative_to(base)
    except ValueError:
        return {"ok": False, "reason": "restore path escapes workspace"}
    if dst.exists() and not bool(policy.get("restore_overwrite", False)):
        return {"ok": False, "reason": "destination exists; set restore_overwrite=true to replace"}

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink(missing_ok=True)
    shutil.move(str(src), str(dst))
    target["restored_utc"] = _utc_now()
    _save(_q_index_path(cwd), idx)
    return {"ok": True, "restored": str(dst), "id": item_id}


def _collect_snapshot(cwd: str, target: str, policy: dict) -> dict:
    base = Path(cwd).resolve()
    files = _iter_targets(cwd, target, max_files=int(policy.get("max_files_per_scan", 5000)))
    snap = {}
    for f in files:
        try:
            rel = str(f.resolve().relative_to(base)).replace("\\", "/")
        except ValueError:
            continue
        if _excluded(base, f, policy):
            continue
        snap[rel] = {"size": f.stat().st_size, "mtime_ns": f.stat().st_mtime_ns}
    return snap


def monitor_status(cwd: str) -> dict:
    default = {"enabled": False, "last_tick_utc": "", "last_scan_path": ".", "interval_seconds": 120, "last_change_count": 0}
    st = _load(_monitor_path(cwd), default)
    for k, v in default.items():
        st.setdefault(k, v)
    _save(_monitor_path(cwd), st)
    return st


def monitor_set(cwd: str, enabled: bool, interval_seconds: int | None = None) -> dict:
    st = monitor_status(cwd)
    st["enabled"] = bool(enabled)
    if interval_seconds is not None:
        st["interval_seconds"] = max(30, min(3600, int(interval_seconds)))
    _save(_monitor_path(cwd), st)
    return st


def monitor_tick(cwd: str, target: str = ".") -> dict:
    st = monitor_status(cwd)
    if not st.get("enabled", False):
        return {"ok": False, "ran": False, "reason": "monitor disabled"}
    policy = policy_status(cwd)
    prev = _load(_snapshot_path(cwd), {})
    current = _collect_snapshot(cwd, target, policy)
    added = sorted([k for k in current.keys() if k not in prev])
    removed = sorted([k for k in prev.keys() if k not in current])
    changed = sorted([k for k in current.keys() if k in prev and current[k] != prev[k]])
    delta_targets = (added + changed)[:300]

    scan_report = {"ok": True, "finding_count": 0, "findings": [], "target": target}
    if delta_targets:
        aggregate = []
        for rel in delta_targets[:100]:
            out = scan_target(cwd, rel)
            aggregate.extend(out.get("findings", []))
        scan_report = {
            "ok": True,
            "target": target,
            "delta_scanned": len(delta_targets[:100]),
            "finding_count": len(aggregate),
            "findings": aggregate[:300],
            "highest_severity": max([f.get("severity", "low") for f in aggregate], default="low", key=_severity_rank),
        }

    _save(_snapshot_path(cwd), current)
    st["last_tick_utc"] = _utc_now()
    st["last_scan_path"] = target
    st["last_change_count"] = len(added) + len(removed) + len(changed)
    _save(_monitor_path(cwd), st)
    return {"ok": True, "ran": True, "monitor": st, "changes": {"added": added[:200], "removed": removed[:200], "changed": changed[:200]}, "report": scan_report}
