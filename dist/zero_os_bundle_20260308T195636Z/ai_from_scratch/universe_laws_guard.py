from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LawCheck:
    passed: bool
    law1_awareness: bool
    law2_pressure: bool
    law3_balance: bool
    reason: str


def check_universe_laws(text: str) -> LawCheck:
    t = text.lower()

    awareness_terms = ("aware", "awareness", "self", "conscious")
    pressure_terms = ("pressure", "contradiction", "threat", "decision", "stress")
    balance_terms = ("balance", "harmony", "stability", "triad", "clarity")

    l1 = any(k in t for k in awareness_terms)
    l2 = any(k in t for k in pressure_terms)
    l3 = any(k in t for k in balance_terms)

    passed = l1 and l2 and l3
    if passed:
        reason = "pass: 1-2-3 universe law cycle present"
    else:
        missing = []
        if not l1:
            missing.append("law1_awareness")
        if not l2:
            missing.append("law2_pressure")
        if not l3:
            missing.append("law3_balance")
        reason = "fail: missing " + ", ".join(missing)

    return LawCheck(
        passed=passed,
        law1_awareness=l1,
        law2_pressure=l2,
        law3_balance=l3,
        reason=reason,
    )

