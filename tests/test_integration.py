"""Offline job/download/mock-Comfy scenarios; no real network or credentials."""

from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa:E402
import kaggle_comfy  # noqa:E402
import kernel_runtime  # noqa:E402
from test_toolkit import spec, workflow  # noqa:E402


def fixture_download(job):
    identity = common.read_json(job / "job.json")
    task = job / "downloads" / ("task-" + identity["task_id"])
    (task / "media").mkdir(parents=True)
    data = b"technical mock image bytes"
    (task / "media/result.png").write_bytes(data)
    entry = {
        "path": "media/result.png",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    common.atomic_json(
        task / "result.json",
        {
            "task_id": identity["task_id"],
            "state": "COMPLETED",
            "workflow_sha256": identity["workflow_sha256"],
            "outputs": [entry],
        },
    )
    (task / "workflow.json").write_bytes((job / "workflow.json").read_bytes())
    common.atomic_json(
        task / "input-manifest.json",
        [
            {"kind": kind, **item}
            for kind in ["models", "inputs"]
            for item in spec()[kind]
        ],
    )
    common.atomic_json(
        task / "output-manifest.json",
        {"task_id": identity["task_id"], "outputs": [entry]},
    )
    return task


class LocalIntegrationTests(unittest.TestCase):
    def test_prepare_submit_status_and_verify_with_mock_api(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            with patch.object(
                kaggle_comfy,
                "save_remote",
                return_value={
                    "version": 1,
                    "url": "https://www.kaggle.com/code/example-user/test",
                },
            ):
                kaggle_comfy.submit(job, True, [{"resource": "GPU", "remaining": "2h"}])
            with patch.object(kaggle_comfy, "remote_status", return_value="COMPLETE"):
                self.assertEqual(kaggle_comfy.status(job)["remote_status"], "COMPLETE")
            fixture_download(job)
            result = kaggle_comfy.verify_download(job)
            self.assertTrue(result["integrity_verified"])
            self.assertFalse(result["visual_accepted"])

    def test_verify_keeps_local_file_count_after_download(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            task = fixture_download(job)
            for number in range(8):
                (task / f"diagnostic-{number}.log").write_text("test\n", encoding="utf-8")
            (task / "empty-directory").mkdir()
            (job / "downloads/unrelated.log").write_text("other task\n", encoding="utf-8")
            collected = [
                str(path.relative_to(job / "downloads"))
                for path in task.rglob("*") if path.is_file()
            ]

            downloaded = kaggle_comfy.verify_download(job, collected)
            self.assertEqual(downloaded["local_files"], 13)
            self.assertEqual(downloaded["downloaded_this_run"], 13)
            verified = kaggle_comfy.verify_download(job)
            self.assertEqual(verified["local_files"], 13)
            self.assertEqual(verified["downloaded_this_run"], 0)
            self.assertEqual(verified["artifacts"], 1)
            self.assertNotIn("downloaded_files", verified)
            self.assertEqual(
                common.read_json(job / "download-verification.json"), verified
            )

    def test_corrupted_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            task = fixture_download(job)
            (task / "media/result.png").write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                kaggle_comfy.verify_download(job)

    def test_wrong_task_and_workflow_and_input_are_rejected(self):
        for which in ["result", "workflow", "input"]:
            with self.subTest(which=which), tempfile.TemporaryDirectory() as directory:
                job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
                task = fixture_download(job)
                if which == "result":
                    d = common.read_json(task / "result.json")
                    d["task_id"] = "f" * 32
                    common.atomic_json(task / "result.json", d)
                elif which == "workflow":
                    (task / "workflow.json").write_text("{}")
                else:
                    common.atomic_json(task / "input-manifest.json", [])
                with self.assertRaises(ValueError):
                    kaggle_comfy.verify_download(job)

    def test_failed_result_is_diagnostics_not_generation_success(self):
        with tempfile.TemporaryDirectory() as directory:
            job = kaggle_comfy.prepare(spec(), workflow(), Path(directory))
            task = fixture_download(job)
            d = common.read_json(task / "result.json")
            d["state"] = "FAILED"
            common.atomic_json(task / "result.json", d)
            report = kaggle_comfy.verify_download(job)
            self.assertEqual(report["generation_state"], "FAILED")
            self.assertEqual(report["local_files"], 5)
            self.assertEqual(report["downloaded_this_run"], 0)

    def test_download_hostname_allowlist(self):
        for value in [
            "http://storage.googleapis.com/a",
            "https://example.test/a",
            "https://storage.googleapis.com.attacker.test/a",
            "https://user:pw@storage.googleapis.com/a",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                kaggle_comfy.signed_url_allowed(value)
        kaggle_comfy.signed_url_allowed(
            "https://storage.googleapis.com/example/file?signature=value"
        )

    def test_credential_like_mount_targets_and_overlapping_files_rejected(self):
        for target in ["run.py/child", "foo"]:
            s = spec()
            s["models"] = [s["models"][0], {**s["models"][0], "target": target}]
            if target == "run.py/child":
                s["models"][0]["target"] = "run.py"
            else:
                s["models"][0]["target"] = "foo"
            with self.subTest(target=target), self.assertRaises(ValueError):
                common.validate_spec(s)

    def test_transport_timeout_and_retry_guard_without_network(self):
        from contextlib import contextmanager
        from types import SimpleNamespace

        calls = []

        class Session:
            adapters = {
                "https://": SimpleNamespace(max_retries=SimpleNamespace(total=0))
            }

            def send(self, request, **kwargs):
                calls.append(kwargs)
                return "response"

        session = Session()
        http = SimpleNamespace(_session=session, _init_session=lambda: None)

        @contextmanager
        def build():
            yield SimpleNamespace(_http_client=http)

        api = SimpleNamespace(build_kaggle_client=build)
        with kaggle_comfy.bounded_client(api) as client:
            self.assertEqual(client._http_client._session.send("request"), "response")
        self.assertEqual(calls, [{"timeout": (10, 60)}])
        session.adapters = {
            "https://": SimpleNamespace(max_retries=SimpleNamespace(total=1))
        }
        with self.assertRaises(RuntimeError):
            with kaggle_comfy.bounded_client(api):
                self.fail("Retry-enabled session must not be dispatched")

    def test_runtime_strips_common_secret_environment_keys(self):
        with patch.dict(
            "os.environ",
            {
                "SOME_TOKEN": "secret",
                "AWS_ACCESS_KEY_ID": "secret",
                "KAGGLE_USERNAME": "private",
                "SAFE": "okay",
            },
            clear=True,
        ):
            env = kernel_runtime.clean_environment()
            self.assertEqual(env, {"SAFE": "okay"})

    def test_runtime_fails_before_install_when_mounted_input_missing(self):
        # Exercise the actual runner error result path with temporary directories;
        # Pure file existence errors occur before subprocess/network work.
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            with (
                patch.object(kernel_runtime, "Path", wraps=Path) as path,
                patch.object(kernel_runtime.subprocess, "Popen") as popen,
            ):

                def resolve_path(value):
                    if value == "/kaggle/working":
                        return Path(directory)
                    return Path(value)

                path.side_effect = resolve_path
                identifier = "a" * 32
                result = kernel_runtime.run(spec(), workflow(), identifier)
                popen.assert_not_called()
            d = json.loads(
                (Path(directory) / ("task-" + identifier) / "result.json").read_text()
            )
            self.assertEqual(result, 1)
            self.assertEqual(d["state"], "FAILED")
            self.assertFalse(task.exists())

    def test_both_template_specs_and_graphs_are_structurally_valid(self):
        for mode in ["image", "video", "anima-turbo", "h3-character-swap"]:
            common.validate_spec(
                common.read_json(ROOT / "assets" / (mode + ".spec.json"))
            )
            common.validate_workflow(
                common.read_json(ROOT / "assets" / (mode + ".workflow.json"))
            )


if __name__ == "__main__":
    unittest.main()
