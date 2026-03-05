import sys
import tempfile
import shutil
import unittest
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class CoreRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_highway_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_core_status_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("core status", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Unified entity: Zero OS Unified Core", result.summary)

    def test_auto_upgrade(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("auto upgrade", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Auto-upgrade complete", result.summary)

    def test_plugin_scaffold(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("plugin scaffold sample", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Plugin scaffold created", result.summary)
        self.assertTrue((self.base / "plugins" / "sample.py").exists())

    def test_law_status_and_export(self) -> None:
        laws = self.base / "laws"
        laws.mkdir(parents=True, exist_ok=True)
        (laws / "recursion_law.txt").write_text("LAW-TEXT", encoding="utf-8")
        highway = Highway(cwd=str(self.base))

        status = highway.dispatch("law status", cwd=str(self.base))
        self.assertEqual("system", status.capability)
        self.assertIn("SHA256:", status.summary)

        exported = highway.dispatch("law export", cwd=str(self.base))
        self.assertEqual("system", exported.capability)
        self.assertEqual("LAW-TEXT", exported.summary)

    def test_cure_firewall_pressure_gate(self) -> None:
        target = self.base / "sample.txt"
        target.write_text("hello", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "cure firewall run sample.txt pressure 10", cwd=str(self.base)
        )
        self.assertEqual("system", result.capability)
        self.assertIn("activated: False", result.summary)

    def test_cure_firewall_beacon_on_survival(self) -> None:
        target = self.base / "sample2.txt"
        target.write_text("hello recursion", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "cure firewall run sample2.txt pressure 80", cwd=str(self.base)
        )
        self.assertEqual("system", result.capability)
        self.assertIn("survived: True", result.summary)
        self.assertIn("score:", result.summary)
        self.assertTrue((self.base / ".zero_os" / "beacons" / "sample2.beacon.json").exists())
        verify = highway.dispatch("cure firewall verify sample2.txt", cwd=str(self.base))
        self.assertIn("signature_valid: True", verify.summary)

    def test_mark_strict_toggle_and_status(self) -> None:
        target = self.base / "safe.txt"
        target.write_text("ok", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        on = highway.dispatch("mark strict on", cwd=str(self.base))
        self.assertIn("True", on.summary)
        show = highway.dispatch("mark strict show", cwd=str(self.base))
        self.assertIn("True", show.summary)
        status = highway.dispatch("mark status safe.txt", cwd=str(self.base))
        self.assertIn("exists: True", status.summary)

    def test_beacon_signature_tamper_detected(self) -> None:
        target = self.base / "tamper.txt"
        target.write_text("hello", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run tamper.txt pressure 80", cwd=str(self.base))
        beacon = self.base / ".zero_os" / "beacons" / "tamper.beacon.json"
        data = json.loads(beacon.read_text(encoding="utf-8"))
        data["digest"] = "deadbeef"
        beacon.write_text(json.dumps(data, indent=2), encoding="utf-8")
        verify = highway.dispatch("cure firewall verify tamper.txt", cwd=str(self.base))
        self.assertIn("signature_valid: False", verify.summary)

    def test_beacon_content_drift_detected(self) -> None:
        target = self.base / "drift.txt"
        target.write_text("initial", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run drift.txt pressure 80", cwd=str(self.base))
        target.write_text("changed", encoding="utf-8")
        verify = highway.dispatch("cure firewall verify drift.txt", cwd=str(self.base))
        self.assertIn("signature_valid: False", verify.summary)
        self.assertIn("content drift detected", verify.summary)

    def test_cure_firewall_net_beacon_and_verify(self) -> None:
        highway = Highway(cwd=str(self.base))
        run = highway.dispatch(
            "cure firewall net run https://example.com pressure 80",
            cwd=str(self.base),
        )
        self.assertIn("survived: True", run.summary)
        verify = highway.dispatch(
            "cure firewall net verify https://example.com",
            cwd=str(self.base),
        )
        self.assertIn("signature_valid: True", verify.summary)

    def test_net_strict_blocks_unverified_fetch(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("net strict on", cwd=str(self.base))
        result = highway.dispatch("fetch https://example.com", cwd=str(self.base))
        self.assertEqual("web", result.capability)
        self.assertIn("Blocked by net strict mode", result.summary)

    def test_net_policy_deny_blocks_net_run(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("net policy deny example.com", cwd=str(self.base))
        run = highway.dispatch(
            "cure firewall net run https://example.com pressure 80",
            cwd=str(self.base),
        )
        self.assertIn("survived: False", run.summary)
        self.assertIn("domain denied by policy", run.summary)

    def test_audit_status_chain(self) -> None:
        target = self.base / "audit.txt"
        target.write_text("x", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run audit.txt pressure 80", cwd=str(self.base))
        status = highway.dispatch("audit status", cwd=str(self.base))
        self.assertIn("audit entries:", status.summary)
        self.assertIn("chain_valid: True", status.summary)

    def test_code_intake_known_language(self) -> None:
        f = self.base / "m.py"
        f.write_text("import os\n\ndef x():\n    return 1\n", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("code intake m.py", cwd=str(self.base))
        self.assertIn("language_guess: python", result.summary)
        self.assertIn("report:", result.summary)

    def test_code_intake_unknown_format(self) -> None:
        f = self.base / "alien.zzz"
        f.write_text("@@@ QX-77 :: proto\nnodes=>alpha,beta\n", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("code intake alien.zzz", cwd=str(self.base))
        self.assertIn("language_guess: unknown-format", result.summary)

    def test_api_get_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("api get https://example.com", cwd=str(self.base))
        self.assertEqual("api", result.capability)
        self.assertIn("status:", result.summary)

    def test_browser_help_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("browser help", cwd=str(self.base))
        self.assertEqual("browser", result.capability)
        self.assertIn("browser open <url>", result.summary)

    def test_search_multi_has_citations(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("search multi zero os", cwd=str(self.base))
        self.assertEqual("web", result.capability)
        self.assertIn("with citations", result.summary.lower())
        self.assertIn("citation:", result.summary.lower())

    def test_os_readiness_and_missing_fix(self) -> None:
        highway = Highway(cwd=str(self.base))
        before = highway.dispatch("os readiness", cwd=str(self.base))
        self.assertIn("os_readiness_score:", before.summary)
        fix = highway.dispatch("os missing fix", cwd=str(self.base))
        self.assertIn("created_count:", fix.summary)
        after = highway.dispatch("os readiness", cwd=str(self.base))
        self.assertIn("drivers_manifest\": true", after.summary.lower())
        self.assertIn("apps_registry\": true", after.summary.lower())
        self.assertIn("services_manifest\": true", after.summary.lower())
        self.assertIn("security_policy\": true", after.summary.lower())
        self.assertIn("system_profile\": true", after.summary.lower())

    def test_os_readiness_json(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("os readiness --json", cwd=str(self.base))
        data = json.loads(result.summary)
        self.assertIn("score", data)
        self.assertIn("checks", data)
        self.assertIn("missing", data)

    def test_beginner_os_status_and_fix(self) -> None:
        highway = Highway(cwd=str(self.base))
        before = highway.dispatch("beginner os status", cwd=str(self.base))
        self.assertIn("beginner_os_score:", before.summary)
        fix = highway.dispatch("beginner os fix", cwd=str(self.base))
        self.assertIn("created_count:", fix.summary)
        after = highway.dispatch("beginner os status", cwd=str(self.base))
        self.assertIn("boot_kernel_base\": true", after.summary.lower())
        self.assertIn("process_scheduler\": true", after.summary.lower())
        self.assertIn("syscall_api\": true", after.summary.lower())
        self.assertIn("app_loader\": true", after.summary.lower())

    def test_cleanup_dry_run_and_apply(self) -> None:
        highway = Highway(cwd=str(self.base))
        junk = self.base / "notes" / "old.tmp"
        junk.parent.mkdir(parents=True, exist_ok=True)
        junk.write_text("junk", encoding="utf-8")
        # Make stale enough for default stale_days=30
        import os, time as _t
        stale = _t.time() - (40 * 86400)
        os.utime(junk, (stale, stale))

        dry = highway.dispatch("cleanup dry run", cwd=str(self.base))
        self.assertIn("\"candidate_count\":", dry.summary)
        apply = highway.dispatch("cleanup apply", cwd=str(self.base))
        self.assertIn("\"ok\": true", apply.summary.lower())

    def test_storage_smart_optimize_and_restore(self) -> None:
        highway = Highway(cwd=str(self.base))
        big = self.base / "notes" / "big.txt"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text(("zero os data\n" * 20000), encoding="utf-8")
        status_before = highway.dispatch("storage smart status", cwd=str(self.base))
        self.assertIn("\"pack_count\":", status_before.summary)
        opt = highway.dispatch("storage smart optimize min_kb=1", cwd=str(self.base))
        self.assertIn("\"ok\": true", opt.summary.lower())
        self.assertFalse(big.exists())
        restore = highway.dispatch("storage smart restore notes/big.txt", cwd=str(self.base))
        self.assertIn("\"ok\": true", restore.summary.lower())
        self.assertTrue(big.exists())

    def test_system_optimize_all(self) -> None:
        highway = Highway(cwd=str(self.base))
        big = self.base / "notes" / "bulk.txt"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text(("zero optimize\n" * 12000), encoding="utf-8")
        import os, time as _t
        stale = _t.time() - (40 * 86400)
        os.utime(big, (stale, stale))

        out = highway.dispatch("system optimize all", cwd=str(self.base))
        self.assertEqual("system", out.capability)
        self.assertIn("\"ok\": true", out.summary.lower())
        self.assertIn("\"memory\":", out.summary.lower())
        self.assertIn("\"storage\":", out.summary.lower())
        self.assertIn("\"cleanup\":", out.summary.lower())

    def test_hyperlayer_status_command(self) -> None:
        highway = Highway(cwd=str(self.base))
        out = highway.dispatch("hyperlayer status", cwd=str(self.base))
        self.assertEqual("system", out.capability)
        self.assertIn("\"zero_hyperlayer\": true", out.summary.lower())

    def test_auto_optimize_commands(self) -> None:
        highway = Highway(cwd=str(self.base))
        on = highway.dispatch("auto optimize on interval=5", cwd=str(self.base))
        self.assertIn("\"enabled\": true", on.summary.lower())
        status = highway.dispatch("auto optimize status", cwd=str(self.base))
        self.assertIn("\"interval_minutes\": 5", status.summary.lower())
        off = highway.dispatch("auto optimize off", cwd=str(self.base))
        self.assertIn("\"enabled\": false", off.summary.lower())

    def test_auto_merge_commands_and_run(self) -> None:
        highway = Highway(cwd=str(self.base))
        runtime = self.base / ".zero_os" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        inbox = runtime / "zero_ai_tasks.txt"
        inbox.write_text(
            "optimize storage status\n"
            "status optimize storage\n"
            "scan security\n",
            encoding="utf-8",
        )
        on = highway.dispatch("auto merge on threshold=0.8", cwd=str(self.base))
        self.assertIn("\"enabled\": true", on.summary.lower())
        run = highway.dispatch("auto merge run", cwd=str(self.base))
        self.assertIn("\"ran\": true", run.summary.lower())
        self.assertIn("\"merged_count\": 1", run.summary.lower())
        status = highway.dispatch("auto merge status", cwd=str(self.base))
        self.assertIn("\"threshold\": 0.8", status.summary.lower())
        off = highway.dispatch("auto merge off", cwd=str(self.base))
        self.assertIn("\"enabled\": false", off.summary.lower())

    def test_ai_files_smart_commands(self) -> None:
        highway = Highway(cwd=str(self.base))
        runtime = self.base / ".zero_os" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        outbox = runtime / "zero_ai_output.txt"
        outbox.write_text(("line\n" * 4000), encoding="utf-8")

        on = highway.dispatch("ai files smart on interval=5", cwd=str(self.base))
        self.assertIn("\"enabled\": true", on.summary.lower())
        self.assertIn("\"interval_minutes\": 5", on.summary.lower())
        status = highway.dispatch("ai files smart status", cwd=str(self.base))
        self.assertIn("\"runtime_output_kb\":", status.summary.lower())
        run = highway.dispatch("ai files smart optimize", cwd=str(self.base))
        self.assertIn("\"ok\": true", run.summary.lower())
        off = highway.dispatch("ai files smart off", cwd=str(self.base))
        self.assertIn("\"enabled\": false", off.summary.lower())

    def test_hardware_capability_map(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("hardware capability map", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        data = json.loads(result.summary)
        self.assertIn("direct_vs_indirect", data)
        self.assertIn("ready_now", data)
        self.assertIn("needs_drivers_kernel_layer_next", data)

    def test_codex_style_agent_executes_and_verifies(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "codex: create file notes/codex.txt with hello then read file notes/codex.txt",
            cwd=str(self.base),
        )
        self.assertEqual("agent", result.capability)
        self.assertIn("codex_style: enabled", result.summary)
        self.assertIn("route_options:", result.summary)
        self.assertIn("verification:", result.summary)
        self.assertTrue((self.base / "notes" / "codex.txt").exists())

    def test_codex_goal_planner_creates_and_reads_file(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "codex: create hello world file notes/goal.txt",
            cwd=str(self.base),
        )
        self.assertEqual("agent", result.capability)
        self.assertIn("create file notes/goal.txt with hello world", result.summary.lower())
        self.assertIn("read file notes/goal.txt", result.summary.lower())
        self.assertTrue((self.base / "notes" / "goal.txt").exists())

    def test_codex_suggest_route_only(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "codex: suggest route: create hello world file notes/suggest.txt",
            cwd=str(self.base),
        )
        self.assertEqual("agent", result.capability)
        self.assertIn("codex_style: suggest_only", result.summary)
        self.assertIn("route_options:", result.summary)
        self.assertFalse((self.base / "notes" / "suggest.txt").exists())

    def test_codex_option_selection_executes_selected_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "codex: option 4: search zero os",
            cwd=str(self.base),
        )
        self.assertEqual("agent", result.capability)
        self.assertIn("auto-selected: 4", result.summary)

    def test_codex_builds_long_horizon_intelligence_memory(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("codex: create hello world file notes/intel.txt", cwd=str(self.base))
        intel = self.base / ".zero_os" / "runtime" / "agent_intelligence.json"
        self.assertTrue(intel.exists())
        data = json.loads(intel.read_text(encoding="utf-8"))
        self.assertIn("history", data)
        self.assertGreaterEqual(len(data["history"]), 1)
        self.assertIn("route_stats", data)
        self.assertIn("user_profile", data)

    def test_codex_shows_proactive_suggestions(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("codex: search zero os", cwd=str(self.base))
        self.assertIn("proactive_suggestions:", result.summary)

    def test_boot_gate_blocks_below_threshold(self) -> None:
        env = dict(**__import__("os").environ)
        env["ZERO_OS_BOOT_MIN_SCORE"] = "100"
        main_py = ROOT / "src" / "main.py"
        proc = subprocess.run(
            ["python", str(main_py), "core status"],
            cwd=str(self.base),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, proc.returncode)
        self.assertIn("boot blocked", proc.stdout)

    def test_production_sandbox_policy(self) -> None:
        highway = Highway(cwd=str(self.base))
        allow = highway.dispatch("sandbox allow python", cwd=str(self.base))
        self.assertIn("python", allow.summary.lower())
        check = highway.dispatch("sandbox check python src/main.py", cwd=str(self.base))
        self.assertIn("allowed: True", check.summary)

    def test_production_update_and_rollback(self) -> None:
        highway = Highway(cwd=str(self.base))
        create = highway.dispatch("update package create v1", cwd=str(self.base))
        self.assertIn("\"version\": \"v1\"", create.summary)
        apply = highway.dispatch("update apply v1", cwd=str(self.base))
        self.assertIn("\"ok\": true", apply.summary.lower())
        rollback = highway.dispatch("update rollback", cwd=str(self.base))
        self.assertIn("\"ok\": true", rollback.summary.lower())

    def test_jobs_queue(self) -> None:
        highway = Highway(cwd=str(self.base))
        add = highway.dispatch("jobs add 9 build kernel", cwd=str(self.base))
        self.assertIn("\"priority\": 9", add.summary)
        run = highway.dispatch("jobs run one", cwd=str(self.base))
        self.assertIn("\"ok\": true", run.summary.lower())

    def test_snapshot_and_release_and_api(self) -> None:
        highway = Highway(cwd=str(self.base))
        snap = highway.dispatch("snapshot create", cwd=str(self.base))
        self.assertIn("\"id\":", snap.summary)
        rel = highway.dispatch("release init", cwd=str(self.base))
        self.assertIn("\"version\": \"0.1.0\"", rel.summary)
        token = highway.dispatch("api token create", cwd=str(self.base))
        data = json.loads(token.summary)
        verify = highway.dispatch(f"api token verify {data['token']}", cwd=str(self.base))
        self.assertIn("\"ok\": true", verify.summary.lower())

    def test_znet_private_internet_registry(self) -> None:
        highway = Highway(cwd=str(self.base))
        init = highway.dispatch("znet init zero-net", cwd=str(self.base))
        self.assertIn("\"network\": \"zero-net\"", init.summary)
        node = highway.dispatch("znet node add core https://zero.local", cwd=str(self.base))
        self.assertIn("\"core\"", node.summary)
        svc = highway.dispatch("znet service add dashboard node=core path=/ui", cwd=str(self.base))
        self.assertIn("\"dashboard\"", svc.summary)
        resolve = highway.dispatch("znet resolve dashboard", cwd=str(self.base))
        self.assertIn("\"type\": \"service\"", resolve.summary)
        self.assertIn("/ui", resolve.summary)
        topo = highway.dispatch("znet topology", cwd=str(self.base))
        self.assertIn("\"edges\"", topo.summary)

    def test_znet_cure_firewall_apply(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("znet init zero-net", cwd=str(self.base))
        highway.dispatch("znet node add core https://example.com", cwd=str(self.base))
        highway.dispatch("znet service add docs node=core path=/", cwd=str(self.base))
        cure = highway.dispatch("znet cure apply pressure 80", cwd=str(self.base))
        self.assertIn("\"all_verified\": true", cure.summary.lower())
        status = highway.dispatch("znet cure status", cwd=str(self.base))
        self.assertIn("\"verified_count\":", status.summary)

    def test_freedom_policy_modes_and_reset(self) -> None:
        highway = Highway(cwd=str(self.base))
        open_mode = highway.dispatch("freedom mode open", cwd=str(self.base))
        self.assertIn("\"ok\": true", open_mode.summary.lower())
        self.assertIn("\"mode\": \"open\"", open_mode.summary.lower())
        status = highway.dispatch("freedom status", cwd=str(self.base))
        self.assertIn("\"mode\": \"open\"", status.summary.lower())
        guarded = highway.dispatch("freedom mode guarded", cwd=str(self.base))
        self.assertIn("\"mode\": \"guarded\"", guarded.summary.lower())
        reset = highway.dispatch("freedom reset", cwd=str(self.base))
        self.assertIn("\"ok\": true", reset.summary.lower())
        self.assertIn("\"mode\": \"guarded\"", reset.summary.lower())

    def test_smart_os_core_ops(self) -> None:
        highway = Highway(cwd=str(self.base))
        p = highway.dispatch("process list", cwd=str(self.base))
        self.assertEqual("system", p.capability)
        self.assertIn("\"items\":", p.summary)
        m = highway.dispatch("memory status", cwd=str(self.base))
        self.assertEqual("system", m.capability)
        self.assertIn("\"ok\":", m.summary)
        ms = highway.dispatch("memory smart status", cwd=str(self.base))
        self.assertIn("\"pressure_level\":", ms.summary)
        mo = highway.dispatch("memory smart optimize", cwd=str(self.base))
        self.assertIn("\"actions\":", mo.summary)
        fs = highway.dispatch("filesystem status", cwd=str(self.base))
        self.assertIn("\"file_count\":", fs.summary)
        d = highway.dispatch("device status", cwd=str(self.base))
        self.assertIn("\"platform\":", d.summary)
        s = highway.dispatch("security overview", cwd=str(self.base))
        self.assertIn("\"freedom_mode\":", s.summary)

    def test_unified_shell_run_and_alias(self) -> None:
        highway = Highway(cwd=str(self.base))
        run1 = highway.dispatch("shell run python -c \"print('zero-shell')\"", cwd=str(self.base))
        self.assertEqual("system", run1.capability)
        self.assertIn("\"ok\": true", run1.summary.lower())
        self.assertIn("zero-shell", run1.summary.lower())
        run2 = highway.dispatch("terminal run python -c \"print('zero-terminal')\"", cwd=str(self.base))
        self.assertEqual("system", run2.capability)
        self.assertIn("\"ok\": true", run2.summary.lower())
        self.assertIn("zero-terminal", run2.summary.lower())

    def test_zerofs_flow(self) -> None:
        highway = Highway(cwd=str(self.base))
        f = self.base / "notes" / "zf.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("zero fs data", encoding="utf-8")
        init = highway.dispatch("zerofs init", cwd=str(self.base))
        self.assertIn("\"name\": \"ZeroFS\"", init.summary)
        put = highway.dispatch("zerofs put notes/zf.txt", cwd=str(self.base))
        self.assertIn("\"ok\": true", put.summary.lower())
        listed = highway.dispatch("zerofs list", cwd=str(self.base))
        self.assertIn("\"path_count\":", listed.summary)
        getp = highway.dispatch("zerofs get notes/zf.txt", cwd=str(self.base))
        self.assertIn("\"ok\": true", getp.summary.lower())
        deleted = highway.dispatch("zerofs delete notes/zf.txt", cwd=str(self.base))
        self.assertIn("\"ok\": true", deleted.summary.lower())


if __name__ == "__main__":
    unittest.main()
