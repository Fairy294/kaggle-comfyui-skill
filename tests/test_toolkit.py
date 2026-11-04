"""Offline contract and security tests: no credentials, network, GPU or paid work."""

from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import kaggle_comfy  # noqa: E402
import kernel_runtime  # noqa: E402


def spec():
    return {
        "version": 1,
        "owner": "example-user",
        "accelerator": "NvidiaTeslaT4",
        "timeout_seconds": 3600,
        "comfy": {"repo": "https://github.com/Comfy-Org/ComfyUI", "revision": "a" * 40},
        "datasets": ["example-user/private-models"],
        "parent_kernels": [],
        "models": [
            {
                "source": "/kaggle/input/private-models/model.safetensors",
                "target": "checkpoints/model.safetensors",
                "sha256": "b" * 64,
            }
        ],
        "inputs": [],
        "custom_nodes": [],
        "pip_packages": [],
        "extra_comfy_args": ["--fp32-vae"],
    }


def workflow():
    return {
        "1": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 64, "height": 64, "batch_size": 1},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "test"},
        },
    }


class ConfigurationTests(unittest.TestCase):
    def test_valid_spec_and_graph(self):
        self.assertEqual(common.validate_spec(spec())["version"], 1)
        self.assertEqual(common.validate_workflow(workflow()), workflow())

    def test_ui_export_is_not_silently_treated_as_api_workflow(self):
        with self.assertRaises(ValueError):
            common.validate_workflow({"nodes": [], "links": []})

    def test_missing_link_and_self_cycle_are_rejected(self):
        for link in [["missing", 0], ["2", 0]]:
            w = workflow()
            w["2"]["inputs"]["images"] = link
            with self.subTest(link=link), self.assertRaises(ValueError):
                common.validate_workflow(w)

    def test_multi_node_cycle_is_rejected(self):
        w = workflow()
        w["1"]["inputs"]["other"] = ["2", 0]
        with self.assertRaises(ValueError):
            common.validate_workflow(w)

    def test_node_input_unknown_or_required_field_missing(self):
        schema = {
            "EmptyLatentImage": {
                "input": {
                    "required": {
                        "width": ["INT"],
                        "height": ["INT"],
                        "batch_size": ["INT"],
                    }
                }
            },
            "SaveImage": {
                "input": {
                    "required": {"images": ["IMAGE"], "filename_prefix": ["STRING"]}
                }
            },
        }
        common.validate_schema(workflow(), schema)
        w = workflow()
        del w["2"]["inputs"]["images"]
        with self.assertRaises(ValueError):
            common.validate_schema(w, schema)
        w = workflow()
        w["1"]["class_type"] = "NotInstalled"
        with self.assertRaises(ValueError):
            common.validate_schema(w, schema)

    def test_unpinned_sources_and_external_input_paths_are_rejected(self):
        for field, value in [
            ("revision", "main"),
            ("repo", "https://user:pass@github.com/a/b"),
            ("repo", "https://github.com/a/b?token=secret"),
        ]:
            s = spec()
            s["comfy"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                common.validate_spec(s)
        for source in [
            "/etc/passwd",
            "/kaggle/input/../secret",
            "/kaggle/inputish/file",
        ]:
            s = spec()
            s["models"][0]["source"] = source
            with self.subTest(source=source), self.assertRaises(ValueError):
                common.validate_spec(s)

    def test_duplicate_targets_and_shell_args_are_rejected(self):
        s = spec()
        s["models"].append(copy.deepcopy(s["models"][0]))
        with self.assertRaises(ValueError):
            common.validate_spec(s)
        for args in [["--listen", "0.0.0.0"], ["--port", "9999"], [";rm -rf /"]]:
            s = spec()
            s["extra_comfy_args"] = args
            with self.subTest(args=args), self.assertRaises(ValueError):
                common.validate_spec(s)

    def test_unsafe_relative_paths_and_names(self):
        for path in ["../x", "/absolute", "a/../../x", "a\\..\\b", "a//b", "a/./b"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                common.safe_relative(path)

    def test_budget_uses_session_cap_plus_margin(self):
        common.require_budget([{"resource": "GPU", "remaining": "2.0h"}], 3600, 300)
        for rows in [
            [],
            [{"resource": "GPU", "remaining": "0.69h"}],
            [{"resource": "GPU", "remaining": "unknown"}],
        ]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                common.require_budget(rows, 3600, 300)

    def test_serialized_payload_has_no_credentials_or_personal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            p = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            payload = (p / "kernel.py").read_text()
            self.assertNotIn(directory, payload)
            self.assertNotRegex(payload, r"KGAT_[A-Za-z0-9]{16,}")
            compile(payload, "kernel.py", "exec")
            self.assertEqual(
                json.loads((p / "kernel-metadata.json").read_text())["is_private"], True
            )


class JobSafetyTests(unittest.TestCase):
    def test_exactly_one_submission_even_if_response_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            with patch.object(
                kaggle_comfy, "save_remote", side_effect=TimeoutError("unknown outcome")
            ) as save:
                with self.assertRaises(TimeoutError):
                    kaggle_comfy.submit(
                        job,
                        confirmed=True,
                        quota=[{"resource": "GPU", "remaining": "2h"}],
                    )
                self.assertEqual(save.call_count, 1)
            with patch.object(kaggle_comfy, "save_remote") as save:
                with self.assertRaises(ValueError):
                    kaggle_comfy.submit(
                        job,
                        confirmed=True,
                        quota=[{"resource": "GPU", "remaining": "2h"}],
                    )
                save.assert_not_called()
            self.assertEqual(
                common.read_json(job / "submission.json")["state"], "SUBMISSION_UNKNOWN"
            )

    def test_explicit_approval_and_budget_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            with self.assertRaises(ValueError):
                kaggle_comfy.submit(job, confirmed=False, quota=[])
            self.assertFalse((job / "submission.json").exists())
            with self.assertRaises(ValueError):
                kaggle_comfy.submit(
                    job,
                    confirmed=True,
                    quota=[{"resource": "GPU", "remaining": "0.1h"}],
                )
            self.assertFalse((job / "submission.json").exists())

    def test_successful_save_readback_and_hash_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            with patch.object(
                kaggle_comfy,
                "save_remote",
                return_value={
                    "version": 1,
                    "url": "https://www.kaggle.com/code/example-user/example",
                },
            ):
                state = kaggle_comfy.submit(
                    job, confirmed=True, quota=[{"resource": "GPU", "remaining": "2h"}]
                )
            self.assertEqual(state["state"], "SUBMITTED")
            other = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            (other / "kernel.py").write_text("changed")
            with self.assertRaises(ValueError):
                kaggle_comfy.submit(
                    other,
                    confirmed=True,
                    quota=[{"resource": "GPU", "remaining": "2h"}],
                )

    def test_redaction_covers_tokens_urls_and_authorization(self):
        raw = (
            "KGAT_"
            + "x" * 32
            + " https://example.test/a?signature=hidden Authorization: Bearer hidden"
        )
        clean = common.redact(raw)
        self.assertNotIn("x" * 32, clean)
        self.assertNotIn("signature=hidden", clean)
        self.assertNotIn("Bearer hidden", clean)

    def test_download_target_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "out"
            root.mkdir()
            with self.assertRaises(ValueError):
                kaggle_comfy.download_target(root, "../outside")
            try:
                (root / "link").symlink_to(Path(directory), target_is_directory=True)
            except OSError as error:
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows account lacks the symbolic-link privilege")
                raise
            with self.assertRaises(ValueError):
                kaggle_comfy.download_target(root, "link/outside")


class RuntimeTests(unittest.TestCase):
    def test_history_error_is_not_succeeded(self):
        for item in [
            {"status": {"status_str": "error", "completed": False}},
            {"status": {"status_str": "success", "completed": True}, "outputs": {}},
        ]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                kernel_runtime.history_outputs(item)

    def test_expected_history_files_only_and_valid_image_check(self):
        history = {
            "status": {"status_str": "success", "completed": True},
            "outputs": {
                "2": {
                    "images": [
                        {"filename": "a.png", "subfolder": "images", "type": "output"}
                    ]
                }
            },
        }
        self.assertEqual(kernel_runtime.history_outputs(history), ["images/a.png"])
        history["outputs"]["2"]["images"][0]["filename"] = "../bad.png"
        with self.assertRaises(ValueError):
            kernel_runtime.history_outputs(history)

    def test_runtime_no_automatic_manager_tunnel_or_hardcoded_credentials(self):
        source = (ROOT / "scripts/kernel_runtime.py").read_text()
        self.assertNotIn("ngrok", source)
        self.assertNotIn("cloudflared", source)
        self.assertIn("127.0.0.1", source)
        self.assertIn("output-manifest.json", source)

    def test_skill_and_examples_have_consistent_names(self):
        text = (ROOT / "SKILL.md").read_text()
        self.assertIn("name: kaggle-comfyui-skill", text)
        for path in (ROOT / "assets").glob("*.json"):
            data = json.loads(path.read_text())
            if path.name.endswith("workflow.json"):
                common.validate_workflow(data)


if __name__ == "__main__":
    unittest.main()
