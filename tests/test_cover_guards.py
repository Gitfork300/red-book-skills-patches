import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qr = load("check_qr_test", ROOT / "cover-image-rules" / "helpers" / "check_qr.py")
unique = load("check_unique_test", ROOT / "cover-image-rules" / "helpers" / "check_cover_unique.py")


class CoverGuardTests(unittest.TestCase):
    def test_legacy_qr_whitelist_moves_out_of_skill_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy" / "qr_whitelist.json"
            target = root / "workspace" / ".state" / "covers" / "qr_whitelist.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text('{"abc": {"date": "1106"}}', encoding="utf-8")
            with patch.object(qr, "LEGACY_WHITELIST", legacy), patch.object(qr, "WHITELIST", target):
                qr.migrate_legacy_whitelist()
            self.assertEqual(target.read_text(encoding="utf-8"), '{"abc": {"date": "1106"}}')
            self.assertFalse(legacy.exists())

    def test_qr_whitelist_migration_refuses_conflicting_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy.json"
            target = root / "workspace" / "whitelist.json"
            legacy.write_text('{"old": true}', encoding="utf-8")
            target.parent.mkdir(parents=True)
            target.write_text('{"new": true}', encoding="utf-8")
            with patch.object(qr, "LEGACY_WHITELIST", legacy), patch.object(qr, "WHITELIST", target):
                with self.assertRaisesRegex(ValueError, "不一致"):
                    qr.migrate_legacy_whitelist()
            self.assertTrue(legacy.exists())
            self.assertTrue(target.exists())

    def test_qr_rejects_empty_and_unreadable_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(qr, "WHITELIST", root / "whitelist.json"):
                with patch("sys.argv", ["check_qr", "--dir", directory]):
                    self.assertEqual(qr.main(), 3)
                with patch("sys.argv", ["check_qr", "--file", str(root / "missing.png")]):
                    self.assertEqual(qr.main(), 3)

    def test_qr_rejects_corrupt_whitelist(self):
        with tempfile.TemporaryDirectory() as directory:
            whitelist = Path(directory) / "whitelist.json"
            whitelist.write_text("{", encoding="utf-8")
            with patch.object(qr, "WHITELIST", whitelist), patch("sys.argv", ["check_qr", "--dir", directory]):
                self.assertEqual(qr.main(), 3)

    def test_qr_accepts_valid_blank_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "sample_cover.png"
            Image.new("RGB", (200, 200), "white").save(image)
            with patch.object(qr, "WHITELIST", root / "whitelist.json"):
                with patch("sys.argv", ["check_qr", "--file", str(image)]):
                    self.assertEqual(qr.main(), 0)

    def test_qr_rejects_encoded_qr_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "qr.png"
            encoded = qr.cv2.QRCodeEncoder_create().encode("https://example.com")
            encoded = qr.cv2.copyMakeBorder(encoded, 4, 4, 4, 4, qr.cv2.BORDER_CONSTANT, value=255)
            encoded = qr.cv2.resize(encoded, None, fx=10, fy=10, interpolation=qr.cv2.INTER_NEAREST)
            self.assertTrue(qr.cv2.imwrite(str(image), encoded))
            with patch.object(qr, "WHITELIST", root / "whitelist.json"):
                with patch("sys.argv", ["check_qr", "--file", str(image)]):
                    self.assertEqual(qr.main(), 1)

    def test_unique_rejects_missing_image_and_finds_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = str(root / "missing")
            with patch("sys.argv", ["check_unique", "--files", missing]):
                self.assertEqual(unique.main(), 2)
            first, second = root / "a", root / "b"
            for path in (first, second):
                Image.new("RGB", (32, 32), "white").save(str(path) + "_cover.png")
            with patch("sys.argv", ["check_unique", "--files", str(first), str(second)]):
                self.assertEqual(unique.main(), 1)


if __name__ == "__main__":
    unittest.main()
