import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.model_evolution import apply_evolution, evaluate_evolution_need


class ModelEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_evo_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_evolution_triggers_on_high_rejection(self) -> None:
        d = evaluate_evolution_need(0.7, 0.2, 0.2)
        self.assertTrue(d["trigger"])
        self.assertEqual("model_replacement", d["method"])

    def test_evolution_applies_parameter_tuning(self) -> None:
        state = {"model_generation": 1, "profile": "strict", "mode": "stability"}
        d = evaluate_evolution_need(0.2, 0.7, 0.1)
        out = apply_evolution(str(self.base), d, state)
        self.assertEqual("adaptive", state["profile"])
        self.assertTrue(out["action"]["triggered"])


if __name__ == "__main__":
    unittest.main()
