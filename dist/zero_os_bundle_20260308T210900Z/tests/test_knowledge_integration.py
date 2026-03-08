import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.knowledge_integration import integrate_knowledge


class KnowledgeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_knowledge_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_integrates_and_stores_unified_model(self) -> None:
        out = integrate_knowledge(str(self.base), "  optimize   storage status ", "human")
        self.assertTrue(out["ok"])
        self.assertEqual("optimize storage status", out["normalized"])
        self.assertIn("unified_model", out)
        model = self.base / ".zero_os" / "runtime" / "knowledge_model.json"
        self.assertTrue(model.exists())

    def test_channel_adds_source(self) -> None:
        out = integrate_knowledge(str(self.base), "api: status", "system_api")
        sources = out["sources"]
        self.assertTrue(any(s.get("source") == "external_system" for s in sources))


if __name__ == "__main__":
    unittest.main()

