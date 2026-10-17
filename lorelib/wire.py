"""Installs the session-end hooks into the user's client configs.

Machine-specific paths (python, lore.py) are generated here and written only to the
user's own config files, never to the repository. Default is a dry run.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import vault

MARKER = "lore.py"
_OURS = re.compile(r'lore\.py"?\s+hook\s')
TARGETS = {"claude": Path(".claude") / "settings.json", "codex": Path(".codex") / "hooks.json",
           "antigravity": Path(".gemini") / "config" / "hooks.json"}
# event -> timeout in seconds; Codex caps SessionEnd at 3. Antigravity has no SessionEnd.
EVENTS = {"claude": {"Stop": 10, "SessionEnd": 10}, "codex": {"Stop": 10, "SessionEnd": 3},
          "antigravity": {"Stop": 10}}
# Antigravity's file holds named hook sets; lore owns exactly this one.
AG_SET = "lore"


@dataclass
class Change:
    client: str
    path: Path
    command: str = ""
    changed: bool = False
    exists: bool = False
    error: str = ""
    text: str = ""
    lines: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)  # suggestions only; never applied


def command(python: Path, lore: Path, client: str) -> str:
    def q(p: Path) -> str:
        s = Path(p).as_posix()
        return f'"{s}"' if " " in s else s
    # Antigravity sends no event name, so the command carries it.
    event = " Stop" if client == "antigravity" else ""
    return f"{q(python)} {q(lore)} hook {client}{event}"


def _merge_antigravity(data: dict, cmd: str) -> list[str]:
    """Antigravity: {"<set>": {"Stop": [handler, ...]}}; Stop takes a flat handler list.
    Only the "lore" set is replaced; every other set stays as it is."""
    timeout = EVENTS["antigravity"]["Stop"]
    data[AG_SET] = {"Stop": [{"type": "command", "command": cmd, "timeout": timeout}]}
    return [f"{AG_SET}.Stop -> {cmd} (timeout {timeout} sn)"]


def _merge(data: dict, client: str, cmd: str) -> list[str]:
    """Drop earlier lore entries, keep everything else, append the current one."""
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("'hooks' is not an object")
    lines = []
    for event, timeout in EVENTS[client].items():
        groups = hooks.get(event) or []
        if not isinstance(groups, list):
            raise ValueError(f"'hooks.{event}' is not a list")
        kept = []
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(inner, list):
                kept.append(group)
                continue
            rest = [h for h in inner
                    if not (isinstance(h, dict) and _OURS.search(str(h.get("command", ""))))]
            if rest:
                kept.append(dict(group, hooks=rest))
        kept.append({"hooks": [{"type": "command", "command": cmd, "timeout": timeout}]})
        hooks[event] = kept
        lines.append(f"{event} -> {cmd} (timeout {timeout} sn)")
    return lines


def plan(home: Path | None = None, python: Path | None = None, lore: Path | None = None,
         only: str | None = None) -> list[Change]:
    home = home or Path.home()
    python = python or Path(sys.executable)
    lore = lore or vault.REPO / "lore.py"
    changes = []
    for client, rel in TARGETS.items():
        if only and client != only:
            continue
        path = home / rel
        change = Change(client, path, command(python, lore, client), exists=path.is_file())
        changes.append(change)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig")) if change.exists else {}
            if not isinstance(data, dict):
                raise ValueError("the root is not a JSON object")
            new = copy.deepcopy(data)
            if client == "antigravity":
                change.lines = _merge_antigravity(new, change.command)
            else:
                change.lines = _merge(new, client, change.command)
        except (ValueError, OSError) as e:
            change.error = f"{e}; the file was not touched"
            continue
        change.changed = new != data
        change.text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    return changes


def apply(changes) -> list[Path]:
    """Write planned changes, backing up any existing file first."""
    written = []
    for c in changes:
        if c.error or not c.changed:
            continue
        c.path.parent.mkdir(parents=True, exist_ok=True)
        if c.exists:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(c.path, c.path.with_name(f"{c.path.name}.lore-backup-{stamp}"))
        tmp = c.path.with_name(c.path.name + ".lore-tmp")
        tmp.write_text(c.text, encoding="utf-8", newline="\n")
        os.replace(tmp, c.path)
        written.append(c.path)
    return written
