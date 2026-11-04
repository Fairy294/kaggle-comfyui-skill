"""Offline persistence, SDK/CLI authentication and cross-platform lock checks."""

from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
import getpass
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import kaggle_auth  # noqa: E402
import kaggle_comfy  # noqa: E402
from test_toolkit import spec, workflow  # noqa: E402


TOKEN = "KGAT_" + "offline_test_" * 3


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.home_patch = patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def save(self):
        with patch.object(kaggle_auth.getpass, "getpass", return_value=TOKEN):
            return kaggle_auth.configure()

    def test_configure_saves_private_json_without_printing_token(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = self.save()
        path = self.home / ".kaggle" / "kaggle-comfyui.json"
        self.assertEqual(result, {"token_file": str(path), "saved": True})
        self.assertEqual(common.read_json(path), {"api_token": TOKEN})
        self.assertNotIn(TOKEN, json.dumps(result) + output.getvalue())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        # Replacing the token also preserves the private file mode.
        self.save()
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_new_process_loads_saved_token_without_shell_configuration(self):
        result = self.save()
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import kaggle_auth; "
            "kaggle_auth.token_path = lambda: Path(sys.argv[2]); "
            "assert kaggle_auth.load_token().startswith('KGAT_'); "
            "assert kaggle_auth.token_environment()['KAGGLE_API_TOKEN'] "
            "== kaggle_auth.load_token(); print('loaded')"
        )
        env = {k: v for k, v in os.environ.items() if k != "KAGGLE_API_TOKEN"}
        child = subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "scripts"), result["token_file"]],
            env=env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(child.stdout.strip(), "loaded")

    def test_stdin_input_and_failed_reconfiguration_preserve_existing_token(self):
        with patch.object(sys, "stdin", io.StringIO(TOKEN + "\n")):
            kaggle_auth.configure(token_stdin=True)
        for value in [
            "", " \n", "token with spaces\n",
            "YOUR_KAGGLE_API_TOKEN\n",
        ]:
            with self.subTest(value=value), patch.object(sys, "stdin", io.StringIO(value)):
                with self.assertRaises(ValueError):
                    kaggle_auth.configure(token_stdin=True)
                self.assertEqual(kaggle_auth.load_token(), TOKEN)

    def test_secure_prompt_does_not_fall_back_to_echoed_input(self):
        self.save()
        with patch.object(
            kaggle_auth.getpass, "getpass", side_effect=getpass.GetPassWarning("no tty")
        ):
            with self.assertRaisesRegex(RuntimeError, "token-stdin"):
                kaggle_auth.configure()
        self.assertEqual(kaggle_auth.load_token(), TOKEN)

    def test_missing_and_invalid_json_fail_without_disclosing_content(self):
        with self.assertRaisesRegex(ValueError, "configure"):
            kaggle_auth.load_token()
        path = kaggle_auth.token_path()
        path.parent.mkdir()
        for text in [
            '{"api_token": "' + TOKEN,
            "[]", "{}", '{"api_token": null}', '{"api_token": ""}',
            json.dumps({"api_token": TOKEN, "extra": TOKEN}),
        ]:
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError) as error:
                    kaggle_auth.load_token()
                self.assertNotIn(TOKEN, str(error.exception))

    def test_saved_token_overrides_stale_environment_and_restores_it_on_error(self):
        self.save()
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "stale"}):
            self.assertEqual(kaggle_auth.token_environment()["KAGGLE_API_TOKEN"], TOKEN)
            self.assertEqual(os.environ["KAGGLE_API_TOKEN"], "stale")
            with self.assertRaises(RuntimeError):
                with kaggle_auth.api_token_environment():
                    self.assertEqual(os.environ["KAGGLE_API_TOKEN"], TOKEN)
                    raise RuntimeError("test failure")
            self.assertEqual(os.environ["KAGGLE_API_TOKEN"], "stale")
        with patch.dict(os.environ):
            os.environ.pop("KAGGLE_API_TOKEN", None)
            with kaggle_auth.api_token_environment():
                self.assertEqual(os.environ["KAGGLE_API_TOKEN"], TOKEN)
            self.assertNotIn("KAGGLE_API_TOKEN", os.environ)

    def test_sdk_authentication_receives_persisted_token(self):
        self.save()
        seen = []

        class FakeApi:
            def authenticate(self):
                seen.append(os.environ.get("KAGGLE_API_TOKEN"))

        modules = {name: ModuleType(name) for name in [
            "kaggle", "kaggle.api", "kaggle.api.kaggle_api_extended"
        ]}
        modules["kaggle.api.kaggle_api_extended"].KaggleApi = FakeApi
        with patch.dict(sys.modules, modules):
            self.assertIsInstance(kaggle_comfy.api_client(), FakeApi)
        self.assertEqual(seen, [TOKEN])

    def test_quota_and_cli_use_same_interpreter_and_saved_token(self):
        self.save()
        result = SimpleNamespace(returncode=0, stdout='[{"resource":"GPU"}]', stderr="")
        with patch.object(kaggle_comfy.subprocess, "run", return_value=result) as run:
            self.assertEqual(kaggle_comfy.quota(), [{"resource": "GPU"}])
            self.assertEqual(run.call_args.args[0][:3], [sys.executable, "-m", "kaggle"])
            self.assertEqual(run.call_args.kwargs["env"]["KAGGLE_API_TOKEN"], TOKEN)
        result = SimpleNamespace(returncode=7, stdout=TOKEN, stderr=TOKEN)
        output = io.StringIO()
        with (
            patch.object(kaggle_comfy.subprocess, "run", return_value=result) as run,
            redirect_stdout(output), redirect_stderr(output),
        ):
            self.assertEqual(kaggle_comfy.main(["kaggle", "--", "datasets", "list"]), 7)
        self.assertEqual(run.call_args.args[0], [sys.executable, "-m", "kaggle", "datasets", "list"])
        self.assertEqual(run.call_args.kwargs["env"]["KAGGLE_API_TOKEN"], TOKEN)
        self.assertNotIn(TOKEN, output.getvalue())

    def test_missing_sdk_dependency_has_installation_error_without_token(self):
        self.save()
        original_import = __import__

        def import_without_six(name, *args, **kwargs):
            if name == "kaggle.api.kaggle_api_extended":
                raise ModuleNotFoundError("No module named 'six'", name="six")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_six):
            with self.assertRaises(RuntimeError) as error:
                kaggle_comfy.api_client()
        message = str(error.exception)
        self.assertIn("six", message)
        self.assertIn("requirements.txt", message)
        self.assertNotIn("authentication failed", message)
        self.assertNotIn(TOKEN, message)

    def test_logs_use_saved_token_and_redact_saved_output(self):
        self.save()
        job = self.home / "job"
        common.atomic_json(job / "job.json", {"kernel_ref": "example-user/example"})
        child = SimpleNamespace(communicate=lambda **kwargs: (TOKEN, None))
        with patch.object(kaggle_comfy.subprocess, "Popen", return_value=child) as popen:
            output = kaggle_comfy.logs(job)
        self.assertEqual(popen.call_args.kwargs["env"]["KAGGLE_API_TOKEN"], TOKEN)
        self.assertNotIn(TOKEN, output)
        self.assertNotIn(TOKEN, (job / "latest-remote.log").read_text(encoding="utf-8"))

    def test_offline_prepare_does_not_load_or_embed_saved_token(self):
        self.save()
        with patch.object(kaggle_auth, "load_token", side_effect=AssertionError("offline")):
            job = kaggle_comfy.prepare(spec(), workflow(), self.home / "jobs")
        for path in job.iterdir():
            self.assertNotIn(TOKEN, path.read_text(encoding="utf-8"))


class SubmissionLockTests(unittest.TestCase):
    def test_windows_lock_uses_the_same_byte_for_acquire_and_release(self):
        calls = []
        windows_locks = SimpleNamespace(
            LK_NBLCK=1,
            LK_UNLCK=0,
            locking=lambda fd, mode, size: calls.append(
                (mode, os.lseek(fd, 0, os.SEEK_CUR), size)
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submit.lock"
            with (
                patch.object(kaggle_comfy, "os", SimpleNamespace(name="nt", SEEK_END=os.SEEK_END)),
                patch.dict(sys.modules, {"msvcrt": windows_locks}),
            ):
                with kaggle_comfy.submission_lock(path):
                    self.assertEqual(path.read_bytes(), b"\0")
        self.assertEqual(calls, [(1, 0, 1), (0, 0, 1)])

    def test_competing_process_is_blocked_and_exception_releases_lock(self):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from kaggle_comfy import submission_lock\n"
            "try:\n"
            " with submission_lock(sys.argv[2]): print('acquired')\n"
            "except OSError: print('busy')\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submit.lock"
            with self.assertRaisesRegex(RuntimeError, "release"):
                with kaggle_comfy.submission_lock(path):
                    result = subprocess.run(
                        [sys.executable, "-c", code, str(ROOT / "scripts"), str(path)],
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "busy")
                    raise RuntimeError("release")
            with kaggle_comfy.submission_lock(path):
                pass


if __name__ == "__main__":
    unittest.main()
