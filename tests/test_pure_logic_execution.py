"""Behavioral regressions for PDF sections 56, 76, 202 and 285.10."""
import unittest
from unittest.mock import patch

from zero_os.decision_engine import decide_zero_engine, zero_engine_action_is_mutating
from zero_os.subsystem_executor import execute_subsystem_adapters
from zero_os.zero_engine_adapters import ZeroEngineAdapter


class PureLogicExecutionTests(unittest.TestCase):
    def run_plane(self, decisions, authorities, *, due=None, scan_error=None):
        self.calls = []
        def scan(name):
            if name == scan_error:
                raise RuntimeError("evidence source unavailable")
            return {}
        adapters = [ZeroEngineAdapter(
            name, 60, lambda *_, name=name: scan(name), lambda *_: {},
            lambda *_, name=name: self.calls.append(name) or {"ok": True},
        ) for name in decisions]
        return execute_subsystem_adapters(
            ".", adapters,
            subsystem_state={name: {"last_run_utc": name} for name in decisions},
            decide_all=lambda *_: {"decisions": decisions, "authority": authorities},
            due_predicate=lambda name, *_: due is None or name in due,
            mutation_action_predicate=zero_engine_action_is_mutating,
        )

    @staticmethod
    def grant(action):
        return {"status": "provisional", "authority": 0.8,
                "demonstrated_scope": [f"mutation:{action}"]}

    def test_contested_mutation_never_reaches_enforcer(self):
        result = self.run_plane({"a": {"action": "backup", "confidence": 1.0}},
                                {"a": {"status": "contested", "authority": 0}})
        self.assertEqual([], self.calls)
        self.assertEqual(0, result["executed_mutation_count"])
        self.assertTrue(result["subsystem_reports"]["a"]["blocked_by_authority"])

    def test_missing_wrong_scope_and_invalid_authority_never_execute(self):
        for grant in ({}, self.grant("verify"),
                      {**self.grant("backup"), "authority": float("nan")},
                      {**self.grant("backup"), "authority": "1.0"},
                      {**self.grant("backup"), "demonstrated_scope": "mutation:backup"}):
            with self.subTest(grant=grant):
                self.run_plane({"a": {"action": "backup"}}, {"a": grant})
                self.assertEqual([], self.calls)

    def test_confident_unauthorized_candidate_cannot_beat_authorized_path(self):
        result = self.run_plane(
            {"a": {"action": "failover_apply", "confidence": 1.0},
             "b": {"action": "backup", "confidence": 0.1}},
            {"b": self.grant("backup")})
        self.assertEqual(["b"], self.calls)
        self.assertEqual("b", result["mutation_winner_subsystem"])

    def test_only_due_authorized_mutation_runs_with_one_mutation_budget(self):
        decisions = {"a": {"action": "failover_apply"},
                     "b": {"action": "backup"}, "c": {"action": "verify"}}
        grants = {name: self.grant(d["action"]) for name, d in decisions.items()}
        result = self.run_plane(decisions, grants, due={"b", "c"})
        self.assertEqual(["b"], self.calls)
        self.assertEqual(1, result["executed_mutation_count"])
        self.assertEqual(1, result["deferred_mutation_count"])

    def test_scan_failure_and_explicit_blockers_override_positive_authority(self):
        for decision, scan_error in (({"action": "backup"}, "a"),
                                     ({"action": "backup", "blockers": ["contradiction"]}, None)):
            self.run_plane({"a": decision}, {"a": self.grant("backup")}, scan_error=scan_error)
            self.assertEqual([], self.calls)

    def test_observation_continues_while_unknown_action_fails_closed(self):
        self.run_plane({"a": {"action": "observe"}, "b": {"action": "new_mutation"}}, {})
        self.assertEqual(["a"], self.calls)

    def test_real_certifier_controls_enforcement_and_preserves_hold(self):
        calls = []
        adapter = ZeroEngineAdapter(
            "candidate", 60, lambda *_: {},
            lambda *_, **kwargs: {"action": "backup", "confidence": 1.0},
            lambda *_: calls.append("backup") or {"ok": True},
        )
        evidence = [{"source": group, "independent_group": group, "supports": True,
                     "quality": 0.8, "scope": ["mutation:backup"]} for group in ("x", "y")]
        def decide(cwd, facts, context):
            return decide_zero_engine(cwd, {**facts, "authority_evidence": {"candidate": evidence}})
        with patch("zero_os.decision_engine.zero_engine_adapters", return_value=(adapter,)):
            granted = execute_subsystem_adapters(
                ".", [adapter], decide_all=decide, due_predicate=lambda *_: True,
                mutation_action_predicate=zero_engine_action_is_mutating)
            self.assertEqual(["backup"], calls)
            self.assertEqual(1, granted["executed_mutation_count"])
            evidence.append({"source": "red", "independent_group": "red", "supports": False,
                             "quality": 1.0, "scope": ["mutation:backup"]})
            denied = execute_subsystem_adapters(
                ".", [adapter], decide_all=decide, due_predicate=lambda *_: True,
                subsystem_state=granted["updated_subsystems"],
                mutation_action_predicate=zero_engine_action_is_mutating)
        self.assertEqual(["backup"], calls)
        self.assertEqual(0, denied["executed_mutation_count"])
        self.assertEqual(granted["updated_subsystems"]["candidate"]["last_run_utc"],
                         denied["updated_subsystems"]["candidate"]["last_run_utc"])
        self.assertEqual("contested", denied["updated_subsystems"]["candidate"]
                         ["last_authority_hold"]["authority"]["status"])


if __name__ == "__main__":
    unittest.main()
