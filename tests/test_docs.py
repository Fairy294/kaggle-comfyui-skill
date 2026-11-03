"""Keep the Chinese repository homepage aligned with the bundled assets."""

from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_release  # noqa: E402


class ReadmeTests(unittest.TestCase):
    def test_chinese_homepage_is_public_and_explains_actual_templates(self):
        self.assertTrue(
            (ROOT / "README.md").is_file(), "Missing user-facing Chinese README"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("README.md", check_release.TOP)
        self.assertIn("中文说明", readme)
        for filename in [
            "image.workflow.json",
            "image.spec.json",
            "video.workflow.json",
            "video.spec.json",
        ]:
            self.assertIn(filename, readme)
        self.assertIn("H3 专项工作流已包含", readme)
        self.assertIn("尚未完成新的 Kaggle GPU 端到端实跑", readme)
        self.assertIn("--confirm-remote-execution", readme)
        self.assertIn("不是开箱即用", readme)

    def test_readme_local_links_exist_and_do_not_escape_repository(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", readme):
            if target.startswith(("https://", "http://", "#")):
                continue
            target = target.split("#", 1)[0]
            path = (ROOT / target).resolve()
            with self.subTest(target=target):
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertTrue(path.is_file())

    def test_workflow_inventory_and_documented_sample_sizes_match_assets(self):
        actual = sorted(path.name for path in (ROOT / "assets").glob("*.workflow.json"))
        self.assertEqual(
            actual,
            [
                "anima-turbo.workflow.json",
                "h3-character-swap.workflow.json",
                "image.workflow.json",
                "video.workflow.json",
            ],
        )
        image = json.loads((ROOT / "assets/image.workflow.json").read_text())
        video = json.loads((ROOT / "assets/video.workflow.json").read_text())
        image_size = next(
            n["inputs"] for n in image.values() if n["class_type"] == "EmptyLatentImage"
        )
        video_size = next(
            n["inputs"]
            for n in video.values()
            if n["class_type"] == "EmptyHunyuanLatentVideo"
        )
        readme = (ROOT / "README.md").read_text()
        self.assertIn(f"{image_size['width']}×{image_size['height']}", readme)
        self.assertIn(f"{video_size['width']}×{video_size['height']}", readme)
        self.assertIn(f"{video_size['length']} 帧", readme)


if __name__ == "__main__":
    unittest.main()
