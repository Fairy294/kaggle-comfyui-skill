"""Model-specific contracts; no weights, CUDA execution or live submissions."""

from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import kaggle_comfy  # noqa: E402


def asset(name):
    return json.loads((ROOT / "assets" / name).read_text())


class ModelPresetTests(unittest.TestCase):
    def test_anima_turbo_is_split_dit_not_sdxl_checkpoint(self):
        graph = common.validate_workflow(asset("anima-turbo.workflow.json"))
        config = common.validate_spec(asset("anima-turbo.spec.json"))
        types = [node["class_type"] for node in graph.values()]
        self.assertNotIn("CheckpointLoaderSimple", types)
        self.assertIn("UNETLoader", types)
        self.assertIn("EmptyLatentImage", types)
        sampler = next(
            n["inputs"] for n in graph.values() if n["class_type"] == "KSampler"
        )
        self.assertEqual(sampler["cfg"], 1.0)
        self.assertTrue(8 <= sampler["steps"] <= 12)
        self.assertEqual(sampler["sampler_name"], "euler")
        clip = next(
            n["inputs"] for n in graph.values() if n["class_type"] == "CLIPLoader"
        )
        self.assertEqual(clip["type"], "stable_diffusion")
        self.assertEqual(clip["clip_name"], "qwen_3_06b_base.safetensors")
        self.assertEqual(len(config["models"]), 3)
        self.assertTrue(all(m["sha256"] != "0" * 64 for m in config["models"]))

    def test_h3_graph_preserves_motion_identity_costume_and_keyframe_zero(self):
        graph = common.validate_workflow(asset("h3-character-swap.workflow.json"))
        config = common.validate_spec(asset("h3-character-swap.spec.json"))
        self.assertEqual(config["runtime_profile"], "minimax-h3-t4-v1")
        nodes = {n["class_type"] for n in graph.values()}
        for required in [
            "MiniMaxH3SPUNETLoader",
            "CLIPLoaderGGUF",
            "MiniMaxH3ReferenceToVideo",
            "MiniMaxH3AddGuide",
            "H3NativeVideoSave",
        ]:
            self.assertIn(required, nodes)
        ref = graph["reference"]["inputs"]
        self.assertEqual(ref["length"], 124)
        self.assertEqual(ref["ref_videos.ref_video_0"], ["motion-parts", 0])
        self.assertEqual(ref["ref_images.ref_image_0"], ["identity", 0])
        self.assertEqual(ref["ref_images.ref_image_1"], ["costume", 0])
        self.assertEqual(graph["guide"]["inputs"]["frame_idx"], 0)
        self.assertEqual(graph["guider"]["inputs"]["conditioning"], ["guide", 0])
        self.assertEqual(graph["sample"]["inputs"]["latent_image"], ["reference", 1])
        self.assertEqual(graph["schedule"]["inputs"]["steps"], 8)
        self.assertEqual(graph["model"]["inputs"]["world_size"], 2)
        self.assertEqual(len(config["models"]), 7)
        self.assertEqual(len(config["inputs"]), 4)

    def test_profile_rejects_unpinned_h3_variants_and_single_gpu(self):
        config = asset("h3-character-swap.spec.json")
        for change in ["p100", "comfy", "plugin", "flag", "unknown_profile"]:
            value = copy.deepcopy(config)
            if change == "p100":
                value["accelerator"] = "NvidiaTeslaP100"
            elif change == "comfy":
                value["comfy"]["revision"] = "f" * 40
            elif change == "plugin":
                value["custom_nodes"][0]["revision"] = "f" * 40
            elif change == "flag":
                value["extra_comfy_args"].remove("--disable-async-offload")
            else:
                value["runtime_profile"] = "unknown"
            with self.subTest(change=change), self.assertRaises(ValueError):
                common.validate_spec(value)
        config = asset("image.spec.json")
        config["extra_comfy_args"].append("--force-fp32")
        with self.assertRaises(ValueError):
            common.validate_spec(config)

    def test_prepared_h3_embeds_owned_profile_and_native_saver(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(
                asset("h3-character-swap.spec.json"),
                asset("h3-character-swap.workflow.json"),
                Path(directory),
            )
            source = (job / "kernel.py").read_text()
            compile(source, "prepared-h3.py", "exec")
            self.assertIn("h3_compat", source)
            self.assertIn("H3NativeVideoSave", source)
            self.assertIn("H3_SAFE_FILE_COPY_V1", source)
            self.assertNotIn("叶瞬光", source)
            self.assertNotIn("riyuexingchennnn", source)

    def test_profile_patches_fail_closed_and_leave_files_unchanged(self):
        import h3_compat

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "comfy").mkdir()
            target = root / "comfy/memory_management.py"
            target.write_text("# upstream changed\n")
            with self.assertRaises((RuntimeError, FileNotFoundError)):
                h3_compat.apply(root, root / "gguf", root / "sp")
            self.assertEqual(target.read_text(), "# upstream changed\n")
        compile(h3_compat.NODE_SOURCE, "owned-h3-saver.py", "exec")
        compile(h3_compat.GPU_SMOKE_SOURCE, "gpu-smoke.py", "exec")

    def test_native_output_paths_are_returned_for_download_manifest(self):
        import kernel_runtime

        item = {
            "status": {"status_str": "success", "completed": True},
            "outputs": {
                "save": {
                    "videos": [
                        {"type": "output", "filename": "segment.mp4", "subfolder": "h3"}
                    ],
                    "images": [
                        {
                            "type": "output",
                            "filename": "000000.png",
                            "subfolder": "h3/segment-frames",
                        }
                    ],
                }
            },
        }
        self.assertEqual(
            kernel_runtime.history_outputs(item),
            ["h3/segment-frames/000000.png", "h3/segment.mp4"],
        )


if __name__ == "__main__":
    unittest.main()
