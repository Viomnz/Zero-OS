from __future__ import annotations


def score_from_checks(checks: dict[str, bool], issues: list[str] | None = None) -> dict:
    total = len(checks)
    passed = sum(1 for ok in checks.values() if ok)
    score = 100.0 if total == 0 else round((passed / total) * 100, 2)
    issue_list = list(issues or [])
    perfect = score == 100.0 and len(issue_list) == 0
    failed_checks = [name for name, ok in checks.items() if not ok]
    root_issues = {
        "failed_checks": failed_checks,
        "issue_sources": issue_list,
    } if score <= 99 else {}
    return {
        "score": score,
        "passed": passed,
        "total": total,
        "issues": issue_list,
        "perfect": perfect,
        "root_issues": root_issues,
    }
