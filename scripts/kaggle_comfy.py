#!/usr/bin/env python3
"""Portable Kaggle ComfyUI batch CLI. Mutations require explicit confirmation."""

from pathlib import Path
from urllib.parse import urlsplit
from contextlib import contextmanager
import argparse
import datetime
import fcntl
import json
import os
import subprocess
import sys
import urllib.request
import uuid

from common import (
    atomic_json,
    read_json,
    redact,
    require_budget,
    safe_relative,
    sha256,
    validate_spec,
    validate_workflow,
)

HERE = Path(__file__).resolve().parent
TERMINAL = {"COMPLETE", "COMPLETED", "ERROR", "CANCELLED", "CANCELED"}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def quota(binary="kaggle"):
    result = subprocess.run(
        [binary, "-W", "quota", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode:
        raise RuntimeError(redact(result.stderr or result.stdout)[-1500:])
    # CLI update warnings may precede the JSON array; never read credentials files.
    text = result.stdout
    for offset, char in enumerate(text):
        if char == "[":
            try:
                rows, _ = json.JSONDecoder().raw_decode(text[offset:])
            except ValueError:
                continue
            if isinstance(rows, list) and all(isinstance(x, dict) for x in rows):
                return rows
    raise ValueError("Quota CLI returned no valid JSON resource list")


def prepare(spec, workflow, root):
    validate_spec(spec)
    validate_workflow(workflow)
    task_id = uuid.uuid4().hex
    job = Path(root).resolve() / task_id
    job.mkdir(parents=True, exist_ok=False)
    slug = "comfy-" + task_id[:20]
    reference = spec["owner"] + "/" + slug
    common_source = (HERE / "common.py").read_text()
    runtime_source = (HERE / "kernel_runtime.py").read_text()
    source = (
        "# Generated standalone private ComfyUI batch job\n"
        "import json, sys, types\n"
        '_helpers = types.ModuleType("common")\n'
        'sys.modules["common"] = _helpers\n'
        "exec(" + repr(common_source) + ", _helpers.__dict__)\n"
        "exec(" + repr(runtime_source) + ", globals())\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(run(json.loads("
        + repr(json.dumps(spec))
        + "), json.loads("
        + repr(json.dumps(workflow))
        + "), "
        + repr(task_id)
        + "))\n"
    )
    compile(source, "kernel.py", "exec")
    (job / "kernel.py").write_text(source)
    atomic_json(job / "spec.json", spec)
    atomic_json(job / "workflow.json", workflow)
    atomic_json(
        job / "kernel-metadata.json",
        {
            "id": reference,
            "title": slug.replace("-", " "),
            "code_file": "kernel.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": True,
            "dataset_sources": spec["datasets"],
            "kernel_sources": spec["parent_kernels"],
        },
    )
    atomic_json(
        job / "job.json",
        {
            "task_id": task_id,
            "kernel_ref": reference,
            "state": "PREPARED",
            "created_at": utcnow(),
            "source_sha256": sha256(job / "kernel.py"),
            "spec_sha256": sha256(job / "spec.json"),
            "workflow_sha256": sha256(job / "workflow.json"),
        },
    )
    return job


def api_client():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        raise RuntimeError(
            "Install optional pinned kaggle dependency in a local venv; do not copy credentials into the Skill"
        ) from None
    api = KaggleApi()
    api.authenticate()
    return api


@contextmanager
def bounded_client(api):
    """Pin SDK requests to a bounded, no-transport-retry requests session.

    The pinned SDK exposes no public request-timeout knob. Isolate this small
    compatibility adapter and fail closed if its transport layout changes.
    """
    with api.build_kaggle_client() as client:
        http = getattr(client, "_http_client", None)
        if http is None or not callable(getattr(http, "_init_session", None)):
            raise RuntimeError(
                "Kaggle SDK transport changed; refuse unbounded API call"
            )
        http._init_session()
        session = http._session
        if session is None or not callable(getattr(session, "send", None)):
            raise RuntimeError("Kaggle SDK has no bounded session adapter")
        for adapter in session.adapters.values():
            if getattr(adapter.max_retries, "total", None) not in {0, False}:
                raise RuntimeError(
                    "Kaggle SDK has transport retries enabled; refuse write ambiguity"
                )
        original = session.send

        def bounded_send(request, **kwargs):
            kwargs.setdefault("timeout", (10, 60))
            return original(request, **kwargs)

        session.send = bounded_send
        try:
            yield client
        finally:
            session.send = original


def save_remote(spec, identity, source):
    from kagglesdk.kernels.types.kernels_api_service import (
        ApiSaveKernelRequest,
        KernelExecutionType,
    )

    api = api_client()
    request = ApiSaveKernelRequest()
    request.slug = identity["kernel_ref"]
    request.new_title = identity["kernel_ref"].split("/")[1].replace("-", " ")
    request.text = source
    request.language = "python"
    request.kernel_type = "script"
    request.is_private = True
    request.enable_gpu = True
    request.enable_tpu = False
    request.enable_internet = True
    request.machine_shape = spec["accelerator"]
    request.session_timeout_seconds = spec["timeout_seconds"]
    request.dataset_data_sources = spec["datasets"]
    request.kernel_data_sources = spec["parent_kernels"]
    request.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
    # One bounded request, no transport retry; unknown outcomes keep the marker.
    with bounded_client(api) as client:
        response = client.kernels.kernels_api_client.save_kernel(request)
    result = json.loads(response.to_json())
    if result.get("error") or not result.get("versionNumber") or not result.get("url"):
        raise RuntimeError(
            "Unconfirmed save response; inspect unique kernel reference before retrying"
        )
    return {
        "version": result["versionNumber"],
        "url": result["url"],
        "kernel_id": result.get("kernelId"),
    }


def submit(job, confirmed=False, quota=None):
    if not confirmed:
        raise ValueError("Remote GPU execution requires --confirm-remote-execution")
    job = Path(job)
    with (job / ".submit.lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (job / "submission.json").exists():
            raise ValueError(
                "Submission marker exists; reconcile unique remote reference, never blindly retry"
            )
        spec = validate_spec(read_json(job / "spec.json"))
        validate_workflow(read_json(job / "workflow.json"))
        identity = read_json(job / "job.json")
        for name, field in [
            ("kernel.py", "source_sha256"),
            ("spec.json", "spec_sha256"),
            ("workflow.json", "workflow_sha256"),
        ]:
            if sha256(job / name) != identity[field]:
                raise ValueError("Prepared job was changed; prepare a new job instead")
        require_budget(
            quota if quota is not None else globals()["quota"](),
            spec["timeout_seconds"],
        )
        state = {**identity, "state": "SUBMITTING", "submitted_at": utcnow()}
        # Atomic x marker persists even if the API response is lost or times out.
        with (job / "submission.json").open("x") as handle:
            json.dump(state, handle, indent=2)
        try:
            response = save_remote(spec, identity, (job / "kernel.py").read_text())
        except Exception as error:
            state.update(
                state="SUBMISSION_UNKNOWN",
                error_type=type(error).__name__,
                error=redact(str(error))[:1500],
            )
            atomic_json(job / "submission.json", state)
            raise
        state.update(state="SUBMITTED", **response)
        atomic_json(job / "submission.json", state)
        return state


def remote_status(reference):
    from kagglesdk.kernels.types.kernels_api_service import (
        ApiGetKernelSessionStatusRequest,
    )

    request = ApiGetKernelSessionStatusRequest()
    request.user_name, request.kernel_slug = reference.split("/")
    with bounded_client(api_client()) as client:
        response = client.kernels.kernels_api_client.get_kernel_session_status(request)
    return str(response.status).split(".")[-1].upper()


def status(job):
    job = Path(job)
    identity = read_json(job / "job.json")
    remote = remote_status(identity["kernel_ref"])
    result = {
        "task_id": identity["task_id"],
        "kernel_ref": identity["kernel_ref"],
        "remote_status": remote,
        "checked_at": utcnow(),
        "note": "Remote COMPLETE alone does not prove generation or visual acceptance",
    }
    atomic_json(job / "status.json", result)
    return result


def logs(job, seconds=20):
    if not 1 <= seconds <= 60:
        raise ValueError("Log capture window must be1..60seconds")
    job = Path(job)
    ref = read_json(job / "job.json")["kernel_ref"]
    # SDK streams may remain open; bound the child process independently.
    code = (
        "from kaggle.api.kaggle_api_extended import KaggleApi\n"
        "a=KaggleApi();a.authenticate()\n"
        "for row in a.kernels_logs_stream(" + repr(ref) + "):\n"
        ' print(row.get("data",""),flush=True)\n'
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        stdout, _ = child.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, _ = child.communicate(timeout=10)
    stdout = redact(stdout or "")[-200000:]
    (job / "latest-remote.log").write_text(stdout)
    # No inferred sampling percentage: only actual emitted facts.
    return stdout


def download_target(root, relative):
    relative = safe_relative(relative)
    root = Path(root).resolve()
    target = root / relative
    if not target.resolve().is_relative_to(root):
        raise ValueError("Output path escapes download directory")
    if any(
        part.is_symlink() for part in [target, *target.parents] if part != root.parent
    ):
        raise ValueError("Download path contains a symlink")
    return target


def signed_url_allowed(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    allowed = (
        "storage.googleapis.com",
        "googleusercontent.com",
        "kaggleusercontent.com",
        "kaggle.com",
    )
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or not any(host == item or host.endswith("." + item) for item in allowed)
    ):
        raise ValueError("Unexpected output download host")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        signed_url_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(job):
    from kagglesdk.kernels.types.kernels_api_service import (
        ApiListKernelSessionOutputRequest,
    )

    job = Path(job)
    remote = status(job)
    if remote["remote_status"] not in TERMINAL:
        raise ValueError("Download only after remote session is terminal")
    identity = read_json(job / "job.json")
    prefix = "task-" + identity["task_id"] + "/"
    root = job / "downloads"
    root.mkdir(exist_ok=True)
    api = api_client()
    collected = []
    cursor = None
    total = 0
    # Explicit bounds: max5000artifacts /30GiB; narrow job if larger.
    with bounded_client(api) as client:
        for _ in range(100):
            request = ApiListKernelSessionOutputRequest()
            request.user_name, request.kernel_slug = identity["kernel_ref"].split("/")
            request.page_size = 100
            if cursor:
                request.page_token = cursor
            response = client.kernels.kernels_api_client.list_kernel_session_output(
                request
            )
            for entry in response.files or []:
                name = entry.file_name
                if not name.startswith(prefix):
                    continue
                if len(collected) >= 5000:
                    raise ValueError("Artifact count exceeds5000limit")
                target = download_target(root, name)
                if target.exists():
                    raise ValueError(
                        "Download already exists; use a fresh job export directory after manual review"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                signed_url_allowed(entry.url)
                temporary = target.with_name(
                    target.name + ".partial-" + uuid.uuid4().hex
                )
                try:
                    opener = urllib.request.build_opener(SafeRedirect())
                    with (
                        opener.open(entry.url, timeout=60) as response_stream,
                        temporary.open("xb") as output,
                    ):
                        file_bytes = 0
                        while True:
                            block = response_stream.read(1024 * 1024)
                            if not block:
                                break
                            file_bytes += len(block)
                            total += len(block)
                            if file_bytes > 10 * 1024**3 or total > 30 * 1024**3:
                                raise ValueError(
                                    "Artifact download exceeds byte budget"
                                )
                            output.write(block)
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                collected.append(name)
            cursor = response.next_page_token
            if not cursor:
                break
        else:
            raise ValueError("Artifact pagination exceeded100pages")
    return verify_download(job, collected)


def verify_download(job, collected=None):
    job = Path(job)
    identity = read_json(job / "job.json")
    root = job / "downloads"
    task = root / ("task-" + identity["task_id"])
    result = read_json(task / "result.json")
    if result.get("task_id") != identity["task_id"]:
        raise ValueError("Downloaded result task identity mismatch")
    if result.get("state") != "COMPLETED":
        report = {
            "task_id": identity["task_id"],
            "generation_state": result.get("state"),
            "diagnostics_downloaded": True,
            "visual_accepted": False,
        }
        atomic_json(job / "download-verification.json", report)
        return report
    expected_workflow = sha256(job / "workflow.json")
    if (
        result.get("workflow_sha256") != expected_workflow
        or sha256(task / "workflow.json") != expected_workflow
    ):
        raise ValueError("Downloaded workflow hash mismatch")
    spec = validate_spec(read_json(job / "spec.json"))
    expected_inputs = [
        {"kind": kind, **item} for kind in ["models", "inputs"] for item in spec[kind]
    ]
    if read_json(task / "input-manifest.json") != expected_inputs:
        raise ValueError("Downloaded mounted-input provenance mismatch")
    outputs = read_json(task / "output-manifest.json")
    if outputs.get("task_id") != identity["task_id"] or not outputs.get("outputs"):
        raise ValueError("Missing output artifact identity/manifest")
    for item in outputs["outputs"]:
        path = download_target(task, item["path"])
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("Artifact size or SHA256 mismatch")
    report = {
        "task_id": identity["task_id"],
        "generation_state": "COMPLETED",
        "integrity_verified": True,
        "artifacts": len(outputs["outputs"]),
        "downloaded_files": len(collected) if collected is not None else None,
        "visual_accepted": False,
        "note": "Inspect images/video frames and seams before delivery; no added labels",
    }
    atomic_json(job / "download-verification.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("quota")
    p = commands.add_parser("validate")
    p.add_argument("--spec", required=True)
    p.add_argument("--workflow", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--spec", required=True)
    p.add_argument("--workflow", required=True)
    p.add_argument("--jobs-dir", default="jobs")
    p = commands.add_parser("submit")
    p.add_argument("--job", required=True)
    p.add_argument("--confirm-remote-execution", action="store_true")
    for name in ["status", "download", "verify"]:
        p = commands.add_parser(name)
        p.add_argument("--job", required=True)
    p = commands.add_parser("logs")
    p.add_argument("--job", required=True)
    p.add_argument("--seconds", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        if args.command == "quota":
            output = quota()
        elif args.command in {"validate", "prepare"}:
            config = validate_spec(read_json(args.spec))
            graph = validate_workflow(read_json(args.workflow))
            output = (
                {"valid": True, "local_only": True}
                if args.command == "validate"
                else {"job": str(prepare(config, graph, Path(args.jobs_dir)))}
            )
        elif args.command == "submit":
            output = submit(Path(args.job), args.confirm_remote_execution)
        elif args.command == "status":
            output = status(args.job)
        elif args.command == "download":
            output = download(args.job)
        elif args.command == "verify":
            output = verify_download(args.job)
        else:
            print(logs(args.job, args.seconds))
            return 0
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "error_type": type(error).__name__,
                    "error": redact(str(error))[:2000],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
