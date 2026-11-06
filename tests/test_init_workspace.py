"""New workspace bootstrap must not overwrite existing memory."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InitWorkspaceTests(unittest.TestCase):
    def test_new_workspace_and_existing_memory_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            command = [sys.executable, str(ROOT / "tools" / "init_workspace.py"),
                       "--workspace", str(workspace)]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            memory = workspace / ".workbuddy" / "memory"
            main = (memory / "MEMORY.md").read_text(encoding="utf-8")
            self.assertIn("topics/03-publish-rhythm.md", main)
            self.assertTrue((workspace / "xhs_publish").is_dir())
            self.assertEqual(len(list((memory / "topics").glob("*.md"))), 15)
            self.assertTrue((memory / "topics" / "14-group-rules.md").is_file())
            self.assertIn("topics/14-group-rules.md", main)
            env = os.environ.copy()
            env["XHS_WORKSPACE"] = str(workspace)
            checked = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "check_doc_layers.py")],
                capture_output=True, text=True, encoding="utf-8", env=env,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
            self.assertEqual((memory / "MEMORY.md").read_text(encoding="utf-8"), main)


if __name__ == "__main__":
    unittest.main()
