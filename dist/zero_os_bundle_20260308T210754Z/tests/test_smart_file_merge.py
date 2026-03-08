import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class SmartFileMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_smart_merge_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_smart_merge_into_output_file(self) -> None:
        left = self.base / "left.txt"
        right = self.base / "right.txt"
        left.write_text("alpha\nbeta\nshared\n", encoding="utf-8")
        right.write_text("shared\ngamma\ndelta\n", encoding="utf-8")

        out = self.highway.dispatch(
            "smart merge files left=left.txt right=right.txt out=merged.txt",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        merged = (self.base / "merged.txt").read_text(encoding="utf-8")
        self.assertIn("alpha", merged)
        self.assertIn("beta", merged)
        self.assertIn("gamma", merged)
        self.assertIn("delta", merged)
        self.assertEqual(1, merged.count("shared"))

    def test_smart_merge_overwrites_target_with_backup(self) -> None:
        left = self.base / "primary.txt"
        right = self.base / "secondary.txt"
        left.write_text("one\ntwo\n", encoding="utf-8")
        right.write_text("two\nthree\n", encoding="utf-8")

        out = self.highway.dispatch(
            "smart merge files left=primary.txt right=secondary.txt",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        merged = left.read_text(encoding="utf-8")
        self.assertIn("one", merged)
        self.assertIn("three", merged)
        self.assertTrue((self.base / ".zero_os" / "production" / "smart_merge" / "last_merge.json").exists())

    def test_smart_merge_json_recursively(self) -> None:
        left = self.base / "left.json"
        right = self.base / "right.json"
        left.write_text(
            json.dumps({"name": "zero", "features": ["shell"], "security": {"enabled": True}}, indent=2),
            encoding="utf-8",
        )
        right.write_text(
            json.dumps({"features": ["store"], "security": {"mode": "strict"}}, indent=2),
            encoding="utf-8",
        )

        out = self.highway.dispatch(
            "smart merge files left=left.json right=right.json out=merged.json",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("json_recursive_merge", data["strategy"])
        merged = json.loads((self.base / "merged.json").read_text(encoding="utf-8"))
        self.assertEqual("zero", merged["name"])
        self.assertEqual(["shell", "store"], merged["features"])
        self.assertTrue(merged["security"]["enabled"])
        self.assertEqual("strict", merged["security"]["mode"])

    def test_smart_merge_markdown_preserves_sections(self) -> None:
        left = self.base / "left.md"
        right = self.base / "right.md"
        left.write_text("# Zero OS\n\n## Intro\nAlpha\n", encoding="utf-8")
        right.write_text("## Intro\nAlpha\n\n## Security\nHardened\n", encoding="utf-8")

        out = self.highway.dispatch(
            "smart merge files left=left.md right=right.md out=merged.md",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("markdown_section_merge", data["strategy"])
        merged = (self.base / "merged.md").read_text(encoding="utf-8")
        self.assertEqual(1, merged.count("## Intro"))
        self.assertIn("## Security", merged)

    def test_smart_merge_code_dedupes_imports(self) -> None:
        left = self.base / "left.py"
        right = self.base / "right.py"
        left.write_text("import os\n\n\ndef alpha():\n    return 'a'\n", encoding="utf-8")
        right.write_text("import os\nimport sys\n\n\ndef beta():\n    return 'b'\n", encoding="utf-8")

        out = self.highway.dispatch(
            "smart merge files left=left.py right=right.py out=merged.py",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("code_symbol_union_merge", data["strategy"])
        merged = (self.base / "merged.py").read_text(encoding="utf-8")
        self.assertEqual(1, merged.count("import os"))
        self.assertIn("import sys", merged)
        self.assertIn("def alpha", merged)
        self.assertIn("def beta", merged)

    def test_smart_merge_policy_decides_skip_for_database_files(self) -> None:
        left = self.base / "data.sqlite"
        right = self.base / "other.sqlite"
        left.write_bytes(b"left-db")
        right.write_bytes(b"right-db")

        out = self.highway.dispatch(
            "smart merge policy decide left=data.sqlite right=other.sqlite",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("skip", data["decision"])

    def test_smart_merge_policy_replaces_sensitive_files(self) -> None:
        secure_dir = self.base / "certs"
        secure_dir.mkdir()
        left = secure_dir / "app.pem"
        right = secure_dir / "new.pem"
        left.write_text("old-cert", encoding="utf-8")
        right.write_text("new-cert", encoding="utf-8")

        out = self.highway.dispatch(
            f"smart merge files left={left} right={right} out={secure_dir / 'merged.pem'}",
            cwd=str(self.base),
        )
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("policy_replace", data["strategy"])
        self.assertEqual("new-cert", (secure_dir / "merged.pem").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
