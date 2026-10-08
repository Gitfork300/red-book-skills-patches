"""Regression tests for batch-preflight note input validation."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location


PATCH_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(
    PATCH_ROOT, "publish-preflight-guard", "helpers", "batch_preflight.py"
)
SPEC = spec_from_file_location("batch_preflight", SCRIPT)
PREFLIGHT = module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class PreflightInputTests(unittest.TestCase):
    def test_missing_field_file_raises_instead_of_returning_empty_text(self):
        with self.assertRaisesRegex(FileNotFoundError, "content_file 不存在"):
            PREFLIGHT.field(
                {"key": "note-1", "content_file": "not-here.txt"},
                "content",
            )

    def test_missing_required_field_is_reported(self):
        with self.assertRaisesRegex(ValueError, "缺少 title 或 title_file"):
            PREFLIGHT.field({"key": "note-1"}, "title")

    def test_empty_inline_field_is_reported(self):
        with self.assertRaisesRegex(ValueError, "缺少 content 或 content_file"):
            PREFLIGHT.field({"key": "note-1", "content": " \n "}, "content")

    def test_missing_source_file_fails_instead_of_becoming_empty_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_path = os.path.join(temp_dir, "notes.json")
            with open(notes_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "batch": "input-test",
                        "notes": [
                            {
                                "key": "note-1",
                                "title_file": "missing-title.txt",
                                "content": "正文",
                            }
                        ],
                    },
                    handle,
                )

            result = subprocess.run(
                [sys.executable, SCRIPT, "--notes", notes_path],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("稿件输入无效", result.stderr)
        self.assertIn("title_file 不存在", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_required_title_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_path = os.path.join(temp_dir, "notes.json")
            with open(notes_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "batch": "input-test",
                        "notes": [{"key": "note-1", "content": "正文"}],
                    },
                    handle,
                )

            result = subprocess.run(
                [sys.executable, SCRIPT, "--notes", notes_path],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("缺少 title 或 title_file", result.stderr)


if __name__ == "__main__":
    unittest.main()
