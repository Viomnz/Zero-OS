import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.core_rule_layer import (
    ensure_core_rules,
    load_core_rules,
    verify_core_rules,
)
from ai_from_scratch.internal_zero_reasoner import reasoner_attempt_core_rule_modify


class CoreRuleLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_core_rules_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_ensure_and_verify(self) -> None:
        out = ensure_core_rules(str(self.base))
        self.assertTrue(out["ok"])
        v = verify_core_rules(str(self.base))
        self.assertTrue(v["ok"])

    def test_detects_tamper(self) -> None:
        ensure_core_rules(str(self.base))
        p = self.base / "laws" / "core_rules.json"
        data = load_core_rules(str(self.base))
        data["version"] = 99
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        v = verify_core_rules(str(self.base))
        self.assertFalse(v["ok"])

    def test_reasoner_cannot_modify_core_rules(self) -> None:
        ensure_core_rules(str(self.base))
        out = reasoner_attempt_core_rule_modify(str(self.base), {"version": 2})
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
