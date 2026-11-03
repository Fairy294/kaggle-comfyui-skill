"""Shared validation and local file helpers; Python standard library only."""

from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
import hashlib
import json
import math
import os
import re
import tempfile


SPEC_KEYS = {
    "version",
    "owner",
    "accelerator",
    "timeout_seconds",
    "comfy",
    "datasets",
    "parent_kernels",
    "models",
    "inputs",
    "custom_nodes",
    "pip_packages",
    "extra_comfy_args",
}
SAFE_FLAGS = {
    "--lowvram",
    "--normalvram",
    "--cpu-vae",
    "--fp32-vae",
    "--fp16-vae",
    "--use-pytorch-cross-attention",
    "--disable-smart-memory",
    "--disable-pinned-memory",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Expected a nonempty POSIX relative path")
    parts = value.split("/")
    if (
        any(part in {"", ".", ".."} for part in parts)
        or PurePosixPath(value).is_absolute()
    ):
        raise ValueError("Unsafe relative path")
    return value


def validate_repo(data):
    if not isinstance(data, dict) or set(data) != {"repo", "revision"}:
        raise ValueError("Repository requires exactly repo and revision")
    url = urlsplit(data["repo"])
    if (
        url.scheme != "https"
        or url.netloc != "github.com"
        or url.query
        or url.fragment
        or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url.path)
    ):
        raise ValueError(
            "Use a credential-free https://github.com/owner/repository URL"
        )
    if not re.fullmatch(r"[a-f0-9]{40}", data["revision"]):
        raise ValueError("Pin the repository to a full lowercase 40-character commit")


def validate_spec(data):
    if not isinstance(data, dict) or set(data) != SPEC_KEYS or data["version"] != 1:
        raise ValueError("Run spec requires the documented version1 fields only")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,50}", data["owner"]):
        raise ValueError("Invalid Kaggle owner")
    if data["accelerator"] not in {"NvidiaTeslaT4", "NvidiaTeslaP100"}:
        raise ValueError("This CUDA toolkit supports T4/P100 only, not TPU")
    if (
        type(data["timeout_seconds"]) is not int
        or not 300 <= data["timeout_seconds"] <= 43200
    ):
        raise ValueError(
            "Session timeout must be an integer between300 and43200seconds"
        )
    validate_repo(data["comfy"])
    for field in ["datasets", "parent_kernels"]:
        items = data[field]
        if (
            not isinstance(items, list)
            or len(items) > 20
            or len(set(items)) != len(items)
        ):
            raise ValueError("Data sources must be a bounded unique list")
        if any(
            not isinstance(item, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", item)
            for item in items
        ):
            raise ValueError("Expected owner/slug data source")
    for field in ["models", "inputs"]:
        if not isinstance(data[field], list) or len(data[field]) > 100:
            raise ValueError("Too many mounted files")
        targets = set()
        for item in data[field]:
            if not isinstance(item, dict) or set(item) != {
                "source",
                "target",
                "sha256",
            }:
                raise ValueError("Mounted file requires source,target,sha256")
            src = item["source"]
            if not isinstance(src, str) or not src.startswith("/kaggle/input/"):
                raise ValueError(
                    "Files must come from explicitly mounted Kaggle inputs"
                )
            safe_relative(src.removeprefix("/kaggle/input/"))
            target = safe_relative(item["target"])
            if any(
                target == existing
                or target.startswith(existing + "/")
                or existing.startswith(target + "/")
                for existing in targets
            ):
                raise ValueError("Duplicate or overlapping file target")
            targets.add(target)
            if not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
                raise ValueError("Each mounted file needs its expected SHA256")
    if not isinstance(data["custom_nodes"], list) or len(data["custom_nodes"]) > 20:
        raise ValueError("Custom nodes must be a bounded list")
    node_repos = set()
    for item in data["custom_nodes"]:
        validate_repo(item)
        if item["repo"] in node_repos:
            raise ValueError("Duplicate custom node repository")
        node_repos.add(item["repo"])
    if not isinstance(data["pip_packages"], list) or len(data["pip_packages"]) > 40:
        raise ValueError("Too many extra packages")
    for package in data["pip_packages"]:
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*", package
        ):
            raise ValueError(
                "Extra packages must use exact name==version, no URLs/options"
            )
    if (
        not isinstance(data["extra_comfy_args"], list)
        or any(x not in SAFE_FLAGS for x in data["extra_comfy_args"])
        or len(set(data["extra_comfy_args"])) != len(data["extra_comfy_args"])
    ):
        raise ValueError(
            "Unsupported ComfyUI flag; listen/port/output paths are managed"
        )
    return data


def validate_workflow(data):
    if not isinstance(data, dict) or not 1 <= len(data) <= 500:
        raise ValueError("Expected ComfyUI API-format node mapping, max500nodes")
    edges = {}
    for node_id, node in data.items():
        if (
            not isinstance(node_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_:.\-]{1,100}", node_id)
            or not isinstance(node, dict)
            or set(node) - {"class_type", "inputs", "_meta"}
            or not isinstance(node.get("class_type"), str)
            or not node["class_type"]
            or not isinstance(node.get("inputs"), dict)
        ):
            raise ValueError("Use Export(API), not the UI nodes/links format")
        edges[node_id] = []
        for key, value in node["inputs"].items():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and type(value[1]) is int
            ):
                if value[0] not in data or value[1] < 0:
                    raise ValueError(
                        "Workflow references an absent node or invalid output"
                    )
                edges[node_id].append(value[0])
            if key == "filename_prefix" and isinstance(value, str):
                safe_relative(value)
    visited, active = set(), set()

    def visit(node_id):
        if node_id in active:
            raise ValueError("Workflow contains a cycle")
        if node_id in visited:
            return
        active.add(node_id)
        for upstream in edges[node_id]:
            visit(upstream)
        active.remove(node_id)
        visited.add(node_id)

    for node_id in edges:
        visit(node_id)
    if len(json.dumps(data)) > 2_000_000:
        raise ValueError("Workflow JSON too large")
    return data


def validate_schema(workflow, schema):
    for node in workflow.values():
        name = node["class_type"]
        if name not in schema:
            raise ValueError("Required node is not installed: " + name)
        missing = set(schema[name].get("input", {}).get("required", {})) - set(
            node["inputs"]
        )
        if missing:
            raise ValueError(
                "Missing required inputs on " + name + ": " + ",".join(sorted(missing))
            )
    # Full value/type/selector validation is performed by ComfyUI /prompt itself.


def require_budget(rows, timeout_seconds, margin_seconds=300):
    gpu = next((row for row in rows if row.get("resource") == "GPU"), None)
    if gpu is None or not re.fullmatch(r"\d+(?:\.\d+)?h", str(gpu.get("remaining"))):
        raise ValueError("Cannot determine live GPU quota; refusing execution")
    hours = float(gpu["remaining"][:-1])
    if not math.isfinite(hours) or hours * 3600 < timeout_seconds + margin_seconds:
        raise ValueError(
            "GPU quota is below the requested session cap plus safety margin"
        )


def redact(text):
    text = re.sub(
        r"\b(?:KGAT_|KGRT_|ghp_|gho_|hf_)[A-Za-z0-9_]+", "[REDACTED]", str(text)
    )
    text = re.sub(r"(https?://[^\s?\"<>]+)\?[^\s\"<>]+", r"\1?[REDACTED]", text)
    text = re.sub(r"(?im)(authorization\s*[:=]\s*)[^\r\n]+", r"\1[REDACTED]", text)
    return text
