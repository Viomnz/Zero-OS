from __future__ import annotations


def synthesize_result(run: dict) -> dict:
    lines = []
    if not run.get("results"):
        return {"summary": "No action was taken.", "ok": False}
    for item in run["results"]:
        kind = item.get("kind", "step")
        if not item.get("ok", False):
            lines.append(f"{kind}: failed")
            continue
        result = item.get("result", {})
        if kind == "web_verify":
            lines.append(f"web verification: verified={result.get('verified', False)}")
        elif kind == "web_fetch":
            lines.append(f"web fetch: status={result.get('status', 0)}")
        elif kind == "store_status":
            lines.append(f"native store: ok={result.get('ok', False)}")
        elif kind == "recover":
            lines.append(f"recovery: ok={result.get('ok', False)}")
        elif kind == "self_repair":
            lines.append(f"self repair: ok={result.get('ok', False)}")
        elif kind == "browser_open":
            lines.append(f"browser open: opened={result.get('opened', False)}")
        elif kind == "browser_status":
            lines.append(f"browser session: tabs={len(result.get('tabs', []))}")
        elif kind == "browser_dom_inspect":
            lines.append(f"browser dom: selectors={len(result.get('page', {}).get('selectors', []))}")
        elif kind == "browser_action":
            lines.append(f"browser action: {'ok' if item.get('ok', False) else 'approval required'}")
        elif kind == "api_request":
            lines.append(f"api request: status={result.get('status', 0)}")
        elif kind == "api_workflow":
            lines.append(f"api workflow: ok={result.get('ok', False)}")
        elif kind == "github_connect":
            lines.append(f"github connect: ok={result.get('ok', False)}")
        elif kind == "github_issues":
            lines.append(f"github issues: count={len(result.get('issues', []))}")
        elif kind == "cloud_target_set":
            lines.append(f"cloud target: ok={result.get('ok', False)}")
        elif kind == "cloud_deploy":
            lines.append(f"cloud deploy: ok={result.get('ok', False)}")
        elif kind == "autonomy_gate":
            lines.append(f"autonomy gate: {result.get('decision', 'unknown')}")
        elif kind == "highway_dispatch":
            lines.append(f"highway: {result.get('capability', 'unknown')}")
        else:
            lines.append(f"{kind}: ok")
    return {"ok": run.get("ok", False), "summary": "\n".join(lines)}
