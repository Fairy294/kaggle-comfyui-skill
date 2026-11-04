"""Standalone Kaggle batch runtime; embedded by prepare, never exposes a tunnel."""

from pathlib import Path
import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from common import (
    atomic_json,
    redact,
    safe_relative,
    sha256,
    validate_schema,
    validate_spec,
    validate_workflow,
)

BASE = "http://127.0.0.1:8188"
MEDIA = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".mp4",
    ".webm",
    ".mkv",
    ".wav",
    ".flac",
}


def history_outputs(item):
    status = item.get("status", {})
    if status.get("status_str") != "success" or status.get("completed") is not True:
        raise ValueError("ComfyUI history did not confirm successful completion")
    paths = set()
    for node in item.get("outputs", {}).values():
        for records in node.values():
            if not isinstance(records, list):
                continue
            for entry in records:
                if (
                    not isinstance(entry, dict)
                    or entry.get("type") != "output"
                    or not entry.get("filename")
                ):
                    continue
                folder = entry.get("subfolder", "")
                name = entry["filename"]
                safe_relative(name)
                if "/" in name:
                    raise ValueError("Output filename must be a basename")
                paths.add(safe_relative((folder + "/" if folder else "") + name))
    if not paths:
        raise ValueError("Workflow finished without persisted output files")
    return sorted(paths)


def request_json(path, body=None):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read(32 * 1024 * 1024))
    except urllib.error.HTTPError as error:
        detail = error.read(16 * 1024).decode(errors="replace")
        raise ValueError("ComfyUI rejected request: " + redact(detail)) from None


def clean_environment():
    return {
        key: value
        for key, value in os.environ.items()
        if not any(
            word in key.upper()
            for word in ["TOKEN", "PASSWORD", "SECRET", "KEY", "CREDENTIAL"]
        )
        and not key.upper().startswith(("KAGGLE_", "AWS_", "AZURE_"))
    }


def run(spec, workflow, task_id):
    output = Path("/kaggle/working") / ("task-" + task_id)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + spec["timeout_seconds"] - 60
    process = None
    server_log = None
    phase = "VALIDATING_INPUTS"

    def emit(event, **fields):
        record = {
            "task_id": task_id,
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": event,
            "phase": phase,
            "elapsed_seconds": round(time.monotonic() - started, 1),
            **fields,
        }
        line = redact(json.dumps(record, ensure_ascii=False))
        with (output / "telemetry.jsonl").open("a") as handle:
            handle.write(line + "\n")
        print("KAGGLE_COMFY " + line, flush=True)
        atomic_json(output / "progress.json", json.loads(line))

    def remaining(cap):
        budget = min(cap, deadline - time.monotonic())
        if budget <= 0:
            raise TimeoutError("Reserved session budget reached; no automatic retry")
        return budget

    def command(args, cwd=None, cap=900):
        emit("command_started", program=args[0])
        with (output / "bootstrap.log").open("a") as log:
            child = subprocess.Popen(
                args,
                cwd=cwd,
                env=clean_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            end = time.monotonic() + remaining(cap)
            try:
                while child.poll() is None:
                    wait = min(20, end - time.monotonic())
                    if wait <= 0:
                        raise TimeoutError("Command exceeded bounded time")
                    try:
                        child.wait(timeout=wait)
                    except subprocess.TimeoutExpired:
                        emit("heartbeat", command=args[0])
                if child.returncode:
                    raise RuntimeError(
                        "Command failed; inspect bootstrap.log: " + args[0]
                    )
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)

    def clone_pinned(config, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        command(["git", "init", str(target)])
        command(["git", "-C", str(target), "remote", "add", "origin", config["repo"]])
        command(
            [
                "git",
                "-C",
                str(target),
                "fetch",
                "--depth",
                "1",
                "origin",
                config["revision"],
            ]
        )
        command(["git", "-C", str(target), "checkout", "--detach", "FETCH_HEAD"])
        actual = subprocess.check_output(
            ["git", "-C", str(target), "rev-parse", "HEAD"], text=True, timeout=10
        ).strip()
        if actual != config["revision"]:
            raise ValueError("Repository commit mismatch")

    try:
        validate_spec(spec)
        validate_workflow(workflow)
        if not uuid.UUID(task_id).hex == task_id:
            raise ValueError("Invalid task identity")
        atomic_json(output / "workflow.json", workflow)
        atomic_json(output / "run-spec.json", spec)
        sources = []
        for kind in ["models", "inputs"]:
            for item in spec[kind]:
                source = Path(item["source"]).resolve(strict=True)
                if not source.is_relative_to("/kaggle/input") or not source.is_file():
                    raise ValueError("Mounted source must resolve inside /kaggle/input")
                if sha256(source) != item["sha256"]:
                    raise ValueError("Mounted file SHA256 mismatch: " + item["target"])
                sources.append({"kind": kind, **item})
        atomic_json(output / "input-manifest.json", sources)
        phase = "PROBING_GPU"
        command(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total",
                "--format=csv,noheader",
            ],
            cap=30,
        )
        workspace = Path("/kaggle/temp") / ("comfy-" + task_id)
        phase = "INSTALLING_COMFYUI"
        clone_pinned(spec["comfy"], workspace)
        command(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(workspace / "requirements.txt"),
            ],
            cap=1500,
        )
        node_paths = []
        for index, config in enumerate(spec["custom_nodes"]):
            target = workspace / "custom_nodes" / ("reviewed_node_" + str(index))
            clone_pinned(config, target)
            node_paths.append(target)
            requirements = target / "requirements.txt"
            if requirements.exists():
                command(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "-r",
                        str(requirements),
                    ],
                    cap=900,
                )
        if spec["pip_packages"]:
            command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    *spec["pip_packages"],
                ],
                cap=900,
            )
        if spec.get("runtime_profile") == "minimax-h3-t4-v1":
            phase = "APPLYING_H3_COMPATIBILITY"
            import h3_compat

            report = h3_compat.apply(workspace, node_paths[0], node_paths[1])
            atomic_json(output / "h3-compatibility.json", report)
            phase = "VALIDATING_H3_GPU_COPY"
            for device in range(2):
                command(
                    [
                        sys.executable,
                        str(workspace / "h3_gpu_copy_smoke.py"),
                        str(device),
                    ],
                    cwd=workspace,
                    cap=180,
                )
        for entry in sources:
            base = workspace / ("models" if entry["kind"] == "models" else "input")
            target = base / entry["target"]
            if not target.resolve().is_relative_to(base.resolve()) or target.exists():
                raise ValueError(
                    "Mounted destination already exists or escapes its directory"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(entry["source"])
        media_root = output / "media"
        media_root.mkdir()
        phase = "STARTING_COMFYUI"
        server_log = (output / "comfy.log").open("w")
        server_env = clean_environment()
        if spec.get("runtime_profile") == "minimax-h3-t4-v1":
            worker_logs = output / "sp-worker-logs"
            worker_logs.mkdir()
            server_env.update(
                MINIMAX_SP_LOGDIR=str(worker_logs),
                MINIMAX_SP_COLLECTIVE_TIMEOUT="3600",
                MINIMAX_SP_STARTUP_TIMEOUT="900",
                PYTHONFAULTHANDLER="1",
            )
        process = subprocess.Popen(
            [
                sys.executable,
                str(workspace / "main.py"),
                "--listen",
                "127.0.0.1",
                "--port",
                "8188",
                "--disable-auto-launch",
                "--output-directory",
                str(media_root),
                *spec["extra_comfy_args"],
            ],
            cwd=workspace,
            env=server_env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            start_new_session=spec.get("runtime_profile") == "minimax-h3-t4-v1",
        )
        ready_end = time.monotonic() + remaining(300)
        while True:
            if process.poll() is not None:
                raise RuntimeError("ComfyUI exited during startup; inspect comfy.log")
            try:
                schema = request_json("/object_info")
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if time.monotonic() >= ready_end:
                    raise TimeoutError("ComfyUI did not become ready") from None
                time.sleep(2)
        validate_schema(workflow, schema)
        atomic_json(
            output / "object-info.json",
            {
                name: schema[name]
                for name in {x["class_type"] for x in workflow.values()}
            },
        )
        phase = "SUBMITTING_WORKFLOW"
        # /prompt is a non-idempotent write: submit it ONCE, never retry on timeout.
        response = request_json("/prompt", {"prompt": workflow, "client_id": task_id})
        if response.get("node_errors") or not response.get("prompt_id"):
            raise ValueError(
                "ComfyUI prompt validation failed: " + redact(json.dumps(response))
            )
        prompt_id = response["prompt_id"]
        if not isinstance(prompt_id, str) or not all(
            x.isalnum() or x in "-_" for x in prompt_id
        ):
            raise ValueError("Invalid prompt identity")
        atomic_json(
            output / "prompt.json", {"task_id": task_id, "prompt_id": prompt_id}
        )
        phase = "GENERATING"
        emit(
            "workflow_queued", prompt_id=prompt_id, note="Not proof sampling has begun"
        )
        while True:
            remaining(20)
            if process.poll() is not None:
                raise RuntimeError("ComfyUI process terminated during inference")
            if spec.get("runtime_profile") == "minimax-h3-t4-v1" and list(
                (output / "sp-worker-logs").glob("rank*-failed.json")
            ):
                raise RuntimeError(
                    "H3 worker exited; see sp-worker-logs before any retry"
                )
            history = request_json("/history/" + prompt_id)
            if prompt_id in history:
                item = history[prompt_id]
                break
            emit(
                "heartbeat",
                prompt_id=prompt_id,
                note="Process/history polling is not a sampling-step percentage",
            )
            time.sleep(min(15, remaining(15)))
        atomic_json(output / "history.json", item)
        expected = history_outputs(item)
        phase = "VALIDATING_OUTPUTS"
        manifest = []
        for name in expected:
            path = (media_root / name).resolve(strict=True)
            if (
                not path.is_relative_to(media_root.resolve())
                or path.suffix.lower() not in MEDIA
                or not path.is_file()
            ):
                raise ValueError("Unexpected or unsafe output artifact")
            if path.stat().st_size == 0:
                raise ValueError("Empty output artifact")
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                from PIL import Image

                with Image.open(path) as image:
                    image.verify()
            elif shutil.which("ffmpeg"):
                command(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-xerror",
                        "-i",
                        str(path),
                        "-f",
                        "null",
                        "-",
                    ],
                    cap=180,
                )
            else:
                raise RuntimeError("ffmpeg missing; cannot validate audio/video decode")
            manifest.append(
                {
                    "path": "media/" + name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
        atomic_json(
            output / "output-manifest.json", {"task_id": task_id, "outputs": manifest}
        )
        phase = "COMPLETED"
        atomic_json(
            output / "result.json",
            {
                "task_id": task_id,
                "state": "COMPLETED",
                "prompt_id": prompt_id,
                "workflow_sha256": sha256(output / "workflow.json"),
                "outputs": manifest,
                "technical_decode_pass": True,
                "visual_accepted": False,
            },
        )
        emit("completed", outputs=len(manifest), visual_accepted=False)
        return 0
    except Exception as error:
        atomic_json(
            output / "result.json",
            {
                "task_id": task_id,
                "state": "FAILED",
                "phase": phase,
                "error_type": type(error).__name__,
                "error": redact(str(error))[:2000],
                "visual_accepted": False,
            },
        )
        emit("failed", error_type=type(error).__name__, error=redact(str(error))[:2000])
        return 1
    finally:
        if process is not None:
            if spec.get("runtime_profile") == "minimax-h3-t4-v1":
                # The SP worker shares this isolated process group; do not leave
                # a second GPU process running after parent failure/timeout.
                for sig in [signal.SIGTERM, signal.SIGKILL]:
                    try:
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        break
                    if sig == signal.SIGTERM:
                        time.sleep(1)
                process.wait(timeout=10)
            elif process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        if server_log is not None:
            server_log.close()
