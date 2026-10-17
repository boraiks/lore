"""Append-only operation log. Records what happened, never note content or secrets."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import guard, vault

LOG_PATH = vault.VAULT / ".lore" / "logs" / "lore.log"
MAX_BYTES = 256 * 1024


def scrub(text: str) -> str:
    """Mask the home folder (it holds the user name) and anything secret-shaped."""
    return guard.redact(guard.mask_home(text))[0]


def log(event: str, log_path: Path | None = None, /, **fields) -> None:
    """Best effort: logging must never break the caller."""
    path = log_path or LOG_PATH
    parts = [datetime.now().isoformat(timespec="seconds"), event]
    parts += [f"{k}={scrub(str(v))}" for k, v in fields.items() if v not in (None, "")]
    line = " ".join(p.replace("\n", " ") for p in parts) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_suffix(".log.1"))
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
    except OSError:
        pass
