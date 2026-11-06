from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class GroupRulesTests(unittest.TestCase):
    def test_quickref_covers_publish_patches_and_group_safeguards(self):
        text = (ROOT / "topics" / "QUICKREF.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text), 6000)
        for item in (
            "writing-facts-only", "safe-wording-guard", "cover-image-rules",
            "timeliness-window", "organizer-qualification-guard",
            "publish-preflight-guard", "publish-interval-guard",
            "publish-loop-guard", "源闸门", "Z 纪律", "23:45–00:15",
            "topics/14-group-rules.md",
        ):
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_group_rules_are_distributed_without_daily_results(self):
        text = (ROOT / "topics" / "14-group-rules.md").read_text(encoding="utf-8")
        for group in ("A", "B", "C", "E", "F", "G", "H", "Y", "W", "Z"):
            with self.subTest(group=group):
                self.assertIn(f"| {group} |", text)
        for rule in ("22", "28", "A→B→C→G→H", "无源", "6–14", "23:45–00:15"):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)
        self.assertIn("不提交到 Skill", text)
        self.assertIn("不能把规则存在视为执行器已经安装", text)


if __name__ == "__main__":
    unittest.main()
