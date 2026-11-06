import importlib.util
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
PATHS_FILE = ROOT / "tools" / "runtime_paths.py"
INTERVAL = ROOT / "publish-interval-guard" / "helpers" / "publish_interval.py"
spec = importlib.util.spec_from_file_location("runtime_paths_test", PATHS_FILE)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)


class StateMigrationTests(unittest.TestCase):
    def test_state_initialization_includes_cover_whitelist_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = [root / name for name in ("publish", "covers", "cache", "pycache", "tmp")]
            names = ("PUBLISH_DIR", "COVERS_DIR", "CACHE_DIR", "PYCACHE_DIR", "TMP_DIR")
            with patch.multiple(paths, **{name: str(target) for name, target in zip(names, targets)}):
                paths.ensure_dirs()
            self.assertTrue(all(target.is_dir() for target in targets))

    def test_migration_preserves_source_and_never_overwrites_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "old.json"
            target = root / "state" / "new.json"
            source.write_text("[1]", encoding="utf-8")
            paths._migrate_file(str(source), str(target))
            self.assertEqual(source.read_text(encoding="utf-8"), "[1]")
            self.assertEqual(target.read_text(encoding="utf-8"), "[1]")
            source.write_text("[2]", encoding="utf-8")
            self.assertIn("skip", paths._migrate_file(str(source), str(target)))
            self.assertEqual(target.read_text(encoding="utf-8"), "[1]")

    def test_copy_failure_does_not_leave_partial_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "old.json", root / "new.json"
            source.write_text("[1]", encoding="utf-8")
            with patch.object(paths.shutil, "copyfileobj", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    paths._migrate_file(str(source), str(target))
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".migrate-*")), [])
            self.assertTrue(source.exists())

    def test_concurrent_migration_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "old.json", root / "new.json"
            source.write_text("[1]", encoding="utf-8")
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(
                    lambda _: paths._migrate_file(str(source), str(target)), range(2)
                ))
            self.assertEqual(sum("copied" in result for result in results), 1)
            self.assertEqual(sum("skip" in result for result in results), 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "[1]")
            self.assertEqual(source.read_text(encoding="utf-8"), "[1]")


class IntervalGuardTests(unittest.TestCase):
    def run_guard(self, directory, *args, extra_env=None):
        env = os.environ.copy()
        env["XHS_INTERVAL_STATE_DIR"] = str(directory)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(INTERVAL), *args],
            env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def test_corrupt_log_blocks_reservation_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "publish_log.json"
            log.write_text("invalid json", encoding="utf-8")
            result = self.run_guard(directory, "reserve", "--title", "test")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("无法读取发布台账", result.stderr)
            self.assertEqual(log.read_text(encoding="utf-8"), "invalid json")

    def test_reservation_prevents_duplicate_and_uses_demo_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.run_guard(directory, "reserve", "--title", "test")
            self.assertEqual(first.returncode, 0, first.stderr)
            second = self.run_guard(directory, "reserve", "--title", "test")
            self.assertEqual(second.returncode, 3, second.stdout + second.stderr)
            log = json.loads((Path(directory) / "publish_log.json").read_text(encoding="utf-8"))
            self.assertEqual(len(log), 1)
            self.assertGreaterEqual(log[0]["next_gap"], 360)
            self.assertLessEqual(log[0]["next_gap"], 840)

    def test_concurrent_reservations_cannot_both_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env["XHS_INTERVAL_STATE_DIR"] = directory
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            command = [sys.executable, str(INTERVAL), "reserve", "--title", "test"]
            processes = [
                subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)
            ]
            for process in processes:
                process.communicate(timeout=30)
            self.assertEqual(sorted(process.returncode for process in processes), [0, 3])
            log = json.loads((Path(directory) / "publish_log.json").read_text(encoding="utf-8"))
            self.assertEqual(len(log), 1)

    def test_explicit_lock_path_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = os.environ.copy()
            env.pop("XHS_INTERVAL_STATE_DIR", None)
            env["XHS_INTERVAL_LOG"] = str(root / "ledger" / "log.json")
            env["XHS_GUARD_LOCK"] = str(root / "locks" / "custom.lock")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, str(INTERVAL), "check"],
                env=env, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "locks" / "custom.lock").is_file())


if __name__ == "__main__":
    unittest.main()
