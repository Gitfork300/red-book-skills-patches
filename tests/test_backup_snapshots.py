import importlib.util
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("backup_snapshots_test", ROOT / "tools" / "backup_snapshots.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupCollectionTests(unittest.TestCase):
    def test_credentials_excluded_from_both_overlapping_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in (
                "runtime/config/accounts.json", "runtime/config/cookies.json",
                "runtime/session/token", "runtime/profiles/default/data",
                "runtime/config/export.cookie", "runtime/.git/config", ".git/config",
                "runtime/tmp/sensitive.txt", "runtime/scripts/xhs_publish_fail.png",
                "runtime/scripts/tool.py", "cover-image-rules/state/qr_whitelist.json",
                "publish-loop-guard/state/inflight.json",
                "publish-loop-guard/state/README.md",
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test", encoding="utf-8")
            for path, rule in ((root, backup.RULES["patches"]),
                               (root / "runtime", backup.RULES["body"])):
                names = {rel for _, rel in backup.collect(str(path), rule)}
                if path == root:
                    self.assertIn("publish-loop-guard/state/README.md", names)
                    self.assertNotIn("publish-loop-guard/state/inflight.json", names)
                    self.assertNotIn("cover-image-rules/state/qr_whitelist.json", names)
                    self.assertEqual(len(names), 2)
                else:
                    self.assertEqual(len(names), 1)
                    self.assertTrue(any(name.endswith("scripts/tool.py") for name in names))

    def test_business_state_backup_copies_and_verifies_only_present_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = root / "publish_log.json"
            whitelist = root / "qr_whitelist.json"
            ledger.write_text('{"entries": []}', encoding="utf-8")
            whitelist.write_text('{"abc": {"date": "1106"}}', encoding="utf-8")
            destination = root / "backup"

            snapshot = Path(backup.backup_business_state(
                str(destination),
                [("publish_log.json", str(ledger)), ("qr_whitelist.json", str(whitelist))],
            ))

            self.assertEqual((snapshot / "publish_log.json").read_bytes(), ledger.read_bytes())
            self.assertEqual((snapshot / "qr_whitelist.json").read_bytes(), whitelist.read_bytes())
            manifest = json.loads((snapshot / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"]["publish_log.json"]["sha256"], backup.sha256_file(str(ledger)))
            self.assertEqual(manifest["missing_optional_files"], [])
            self.assertEqual(ledger.read_text(encoding="utf-8"), '{"entries": []}')

    def test_business_state_backup_reports_missing_optional_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = root / "publish_log.json"
            ledger.write_text("{}", encoding="utf-8")
            snapshot = Path(backup.backup_business_state(
                str(root / "backup"),
                [("publish_log.json", str(ledger)), ("qr_whitelist.json", str(root / "missing.json"))],
            ))
            manifest = json.loads((snapshot / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["missing_optional_files"], ["qr_whitelist.json"])


if __name__ == "__main__":
    unittest.main()
