import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load("release_test", "tools/check_public_release.py")
doctor = load("doctor_test", "tools/doctor.py")
setup = load("setup_test", "tools/setup_runtime.py")


class ToolGateTests(unittest.TestCase):
    def test_setup_fails_if_sitecustomize_cannot_be_written(self):
        with patch.object(setup, "VENV_DIR", Path("nonexistent-setup-test-venv")), \
             patch.object(setup.venv, "EnvBuilder"):
            with patch.object(setup.subprocess, "run") as run:
                run.return_value.returncode = 0
                with patch.object(setup, "write_sitecustomize", side_effect=OSError("denied")):
                    with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                        self.assertEqual(setup.main(), 2)
                        self.assertIn("denied", stderr.getvalue())

    def test_setup_preserves_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(setup, "VENV_DIR", Path(directory)), \
                 patch.object(setup.venv, "EnvBuilder") as builder, \
                 patch.object(setup.subprocess, "run") as run, \
                 patch.object(setup, "write_sitecustomize") as write, \
                 patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(setup.main(), 2)
                self.assertIn("不会修改", stderr.getvalue())
                builder.assert_not_called()
                run.assert_not_called()
                write.assert_not_called()

    def test_release_gate_fails_when_git_is_unavailable(self):
        with patch.object(release, "git", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "无法检查 Git"):
                release.check_paths()

    def test_release_gate_detects_machine_specific_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "INSTALL.md").write_text(
                "Local interpreter: `C:\\Users\\PrivateUser\\Python\\python.exe`\n",
                encoding="utf-8",
            )
            with patch.object(release, "ROOT", root):
                findings, _ = release.check_files()
        self.assertEqual(len(findings), 1)
        self.assertIn("machine-specific path: INSTALL.md:1", findings[0])

    def test_failed_cleanup_blocks_doctor(self):
        def fake_step(args, **kwargs):
            if args[-1] == "clean":
                return 1, "cleanup failed"
            return 0, "ok"

        with tempfile.TemporaryDirectory() as directory:
            handover = Path(directory) / "HANDOVER.md"
            handover.write_text("全量替换包 本地定制清单 升级记录表", encoding="utf-8")
            with patch.object(doctor, "ROOT", Path(directory)):
                with patch.object(doctor, "run_step", side_effect=fake_step):
                    with patch("sys.argv", ["doctor", "--quick"]), patch("sys.stdout", new_callable=io.StringIO):
                        self.assertEqual(doctor.main(), doctor.EXIT_FAIL)

    def test_environment_warning_is_reported_by_doctor(self):
        def fake_step(args, **kwargs):
            if str(args[-1]).endswith("check_env.py"):
                return 1, "missing environment"
            return 0, "ok"

        with tempfile.TemporaryDirectory() as directory:
            handover = Path(directory) / "HANDOVER.md"
            handover.write_text("全量替换包 本地定制清单 升级记录表", encoding="utf-8")
            with patch.object(doctor, "ROOT", Path(directory)):
                with patch.object(doctor, "run_step", side_effect=fake_step):
                    with patch("sys.argv", ["doctor", "--quick"]), patch("sys.stdout", new_callable=io.StringIO):
                        self.assertEqual(doctor.main(), doctor.EXIT_WARN)


if __name__ == "__main__":
    unittest.main()
