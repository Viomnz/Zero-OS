from __future__ import annotations

from zero_os.global_runtime_network import node_register, network_status, runtime_release_propagate
from zero_os.runtime_protocol_v1 import maximize_security as rp_maximize_security, security_grade as rp_security_grade
from zero_os.universal_runtime_ecosystem import adapters_status, runtime_install, runtime_status
from zero_os.app_store_production_ops import compliance_set, compliance_status, slo_set, telemetry_status


def ecosystem_status(cwd: str) -> dict:
    return {
        "ok": True,
        "runtime_protocol": rp_security_grade(cwd),
        "universal_runtime": runtime_status(cwd),
        "adapters": adapters_status(cwd),
        "runtime_network": network_status(cwd),
        "store_compliance": compliance_status(cwd),
        "store_telemetry": telemetry_status(cwd),
    }


def ecosystem_grade(cwd: str) -> dict:
    st = ecosystem_status(cwd)
    rp = st["runtime_protocol"]
    ur = st["universal_runtime"].get("runtime", {})
    ad = st["adapters"].get("adapters", {})
    rn = st["runtime_network"]
    comp = st["store_compliance"].get("compliance", {})
    tele = st["store_telemetry"].get("telemetry", {})
    slo = tele.get("slo", {})

    checks = {
        "runtime_protocol_a_or_better": rp.get("grade_score", 0) >= 80,
        "runtime_installed": bool(ur.get("installed", False)),
        "adapter_coverage_5": len(ad) >= 5,
        "network_online": rn.get("registry", {}).get("global") == "online",
        "network_has_nodes": int(rn.get("node_total", 0)) >= 1,
        "ios_policy_restricted": comp.get("ios_external_store_allowed", True) is False,
        "slo_strong": float(slo.get("availability", 0.0)) >= 99.9 and int(slo.get("p95_install_sec", 9999)) <= 120,
    }
    weights = {
        "runtime_protocol_a_or_better": 30,
        "runtime_installed": 15,
        "adapter_coverage_5": 10,
        "network_online": 10,
        "network_has_nodes": 10,
        "ios_policy_restricted": 10,
        "slo_strong": 15,
    }
    score = sum(weights[k] for k, ok in checks.items() if ok)
    tier = "A+" if score >= 95 else "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 65 else "D"
    gaps = [k for k, ok in checks.items() if not ok]
    return {"ok": True, "ecosystem_score": score, "ecosystem_tier": tier, "checks": checks, "gaps": gaps, "status": st}


def ecosystem_maximize(cwd: str) -> dict:
    rp = rp_maximize_security(cwd)
    runtime_install(cwd, "1.0.0")
    runtime_release_propagate(cwd, "1.0.0-secure")
    node_register(cwd, "linux", "desktop", "jit-native")
    compliance_set(cwd, False)
    slo_set(cwd, 99.95, 90)
    grade = ecosystem_grade(cwd)
    return {"ok": True, "runtime_protocol": rp, "grade": grade}
