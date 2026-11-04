"""Civitai author Chaika graph contracts; offline, no GPU or account access."""
from pathlib import Path
import copy
import json
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common


def asset(name):
    return json.loads((ROOT / "assets" / name).read_text(encoding="utf-8"))


class AuthorWorkflowTests(unittest.TestCase):
    def test_original_parameters_and_resolution(self):
        graph = common.validate_workflow(asset("anima-chaika-original.api.json"))
        self.assertEqual(len(graph), 10)
        self.assertEqual(graph["1"]["class_type"], "PreviewImage")
        sample = graph["19"]["inputs"]
        self.assertEqual(sample["seed"], 758641017238633)
        self.assertEqual(sample["steps"], 8)
        self.assertEqual(sample["cfg"], 1.0)
        self.assertEqual(sample["sampler_name"], "euler")
        self.assertEqual(sample["scheduler"], "simple")
        self.assertEqual(graph["45"]["inputs"]["device"], "default")
        self.assertEqual(graph["54"]["inputs"], {
            "aspect_ratio": "3:4 (Portrait Standard)", "megapixels": 1.2, "multiple": 16
        })
        scale = math.sqrt(1.2 * 1024 * 1024 / 12)
        self.assertEqual((round(3 * scale / 16) * 16, round(4 * scale / 16) * 16), (976, 1296))
        self.assertIn("chaika trabant", graph["11"]["inputs"]["text"])

    def test_batch_changes_only_preview_to_save(self):
        expected = copy.deepcopy(asset("anima-chaika-original.api.json"))
        expected["1"]["class_type"] = "SaveImage"
        expected["1"]["inputs"]["filename_prefix"] = "anima/chaika"
        expected["1"]["_meta"]["title"] = "Save Image (batch persistence only)"
        self.assertEqual(common.validate_workflow(asset("anima-turbo.workflow.json")), expected)

    def test_ui_and_provenance_preserve_original_identity(self):
        ui = asset("anima-chaika-original.ui.json")
        provenance = asset("anima-chaika-source.json")
        self.assertEqual(provenance["image_id"], 140742450)
        self.assertEqual(provenance["model_version_id"], 3263843)
        self.assertEqual(len(ui["nodes"]), 10)
        self.assertEqual(next(n for n in ui["nodes"] if n["id"] == 19)["widgets_values"][0], 758641017238633)
        self.assertIn("comfy_extras/nodes_resolution.py", provenance["resolution_selector_source"])


if __name__ == "__main__":
    unittest.main()
