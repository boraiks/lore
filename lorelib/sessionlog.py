"""Session records outside the vault: that a session happened, never what was said.

One JSON line per hook call in .lore/logs/sessions.jsonl (gitignored):
time, client, session id, message count, event. No prompts, answers, paths or titles.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import vault

LOG_PATH = vault.VAULT / ".lore" / "logs" / "sessions.jsonl"
MAX_BYTES = 1024 * 1024


def record(client: str, session: str, messages: int, event: str, path: Path | None = None,
           now: datetime | None = None) -> None:
    """Best effort, like the operation log: a failure here must never reach the client."""
    path = path or LOG_PATH
    line = json.dumps({"time": (now or datetime.now()).isoformat(timespec="seconds"),
                       "client": client, "session": session, "messages": int(messages),
                       "event": event}, ensure_ascii=False) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_name(path.name + ".1"))
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
    except OSError:
        pass


def read(path: Path | None = None) -> dict:
    """(client, session) -> {client, session, first, last, messages}; the rotated file too."""
    path = path or LOG_PATH
    out: dict = {}
    for part in (path.with_name(path.name + ".1"), path):
        try:
            lines = part.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
                key = (str(row["client"]), str(row["session"]))
                time, messages = str(row["time"]), int(row["messages"])
            except (ValueError, KeyError, TypeError):
                continue
            rec = out.setdefault(key, {"client": key[0], "session": key[1], "first": time,
                                       "last": time, "messages": 0})
            rec["first"], rec["last"] = min(rec["first"], time), max(rec["last"], time)
            rec["messages"] = max(rec["messages"], messages)
    return out
