"""Local, persistent API Token configuration; never embedded in remote jobs."""

from contextlib import contextmanager
from pathlib import Path
import getpass
import json
import os
import sys
import warnings

from common import atomic_json


def token_path():
    return Path.home() / ".kaggle" / "kaggle-comfyui.json"


def validate_token(token):
    if (
        not isinstance(token, str)
        or not token
        or len(token) > 16384
        or any(character.isspace() or not character.isprintable() for character in token)
        or token == "YOUR_KAGGLE_API_TOKEN"
    ):
        raise ValueError("Expected a nonempty API Token without whitespace")
    return token


def configure(token_stdin=False):
    if token_stdin:
        token = sys.stdin.readline().strip()
    else:
        # Never fall back to echoed input when no secure terminal is available.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                token = getpass.getpass("Kaggle API Token: ").strip()
        except getpass.GetPassWarning:
            raise RuntimeError(
                "A secure terminal is unavailable; use configure --token-stdin"
            ) from None
    token = validate_token(token)
    path = token_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # atomic_json uses a private temporary file (0600 on POSIX) then replaces it.
    atomic_json(path, {"api_token": token})
    return {"token_file": str(path), "saved": True}


def load_token():
    path = token_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(
            "API Token is not configured; run python scripts/kaggle_comfy.py configure"
        ) from None
    except (ValueError, UnicodeError):
        raise ValueError("Invalid API Token JSON; run configure again") from None
    if not isinstance(config, dict) or set(config) != {"api_token"}:
        raise ValueError("API Token JSON requires exactly the api_token field")
    return validate_token(config["api_token"])


def token_environment():
    """Supply the persisted token to a child without changing the host shell."""
    return {**os.environ, "KAGGLE_API_TOKEN": load_token()}


@contextmanager
def api_token_environment():
    """The official SDK reads KAGGLE_API_TOKEN during authentication."""
    token = load_token()
    previous = os.environ.get("KAGGLE_API_TOKEN")
    os.environ["KAGGLE_API_TOKEN"] = token
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("KAGGLE_API_TOKEN", None)
        else:
            os.environ["KAGGLE_API_TOKEN"] = previous
