"""Installs lore's agent-facing files into a vault and keeps them current on update.

The code stays in its own folder (a git clone, updated with `git pull`). Only the files an
AI client reads from the folder it is opened in are copied into the vault: AGENTS.md,
CLAUDE.md, GEMINI.md and the skills. Notes are never part of this set.

Each copy's SHA-256 is recorded in the vault's .lore/installed.json. On the next install a
file that still matches its record is replaced by the new version; a file that differs (the
user edited it, or it was theirs to begin with) is kept, and the new version is written next
to it as <file>.new.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import skills, vault

MANIFEST = Path(".lore") / "installed.json"
CLIENT_FILE = "# {name}\n\nThe instructions for agents in this vault are in AGENTS.md.\n\n@AGENTS.md\n"
# Text the earliest lore versions wrote into vault pointer files; such files are lore's own.
_OLD_POINTER = "Written by `lore.py home`; this file is an instruction, not a note."

render = skills.render


@dataclass(frozen=True)
class Change:
    rel: str
    action: str  # created | updated | unchanged | kept (user's version kept; see .new)


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")  # bytes as they are: no newline translation


def sources(lore: Path | None = None) -> dict[str, str]:
    """Vault-relative path -> content, read from this repository, with `lore` (default:
    this repository's own location) filled in as the path to the code."""
    repo = vault.REPO
    lore_path = Path(lore or repo).as_posix()
    out = {"AGENTS.md": render(_read(repo / "vault" / "AGENTS.md"), lore_path),
           "CLAUDE.md": CLIENT_FILE.format(name="CLAUDE.md"),
           "GEMINI.md": CLIENT_FILE.format(name="GEMINI.md")}
    for name, src in skills.sources(repo).items():
        text = render(_read(src), lore_path)
        for target in skills.TARGETS:
            out[(target / name / "SKILL.md").as_posix()] = text
    return out


_lore_sources = sources  # install() takes a `sources` argument of the same name


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".lore-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _load_manifest(vault_dir: Path) -> dict:
    try:
        data = json.loads((vault_dir / MANIFEST).read_text(encoding="utf-8"))
        return data.get("files", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def install(vault_dir: Path, lore: Path | None = None, dry_run: bool = False,
            sources: dict[str, str] | None = None) -> list[Change]:
    srcs = sources if sources is not None else _lore_sources(lore)
    recorded = _load_manifest(vault_dir)
    files = dict(recorded)
    changes = []
    for rel, text in srcs.items():
        path, new = vault_dir / rel, text.encode("utf-8")
        if not path.exists():
            action = "created"
        else:
            current = path.read_bytes()
            if current == new:
                action = "unchanged"
            elif recorded.get(rel) == _digest(current) or (
                    rel not in recorded and _OLD_POINTER in current.decode("utf-8", "replace")):
                action = "updated"  # still exactly what lore wrote last time
            else:
                action = "kept"
        if not dry_run:
            if action in ("created", "updated"):
                _write(path, new)
            if action == "kept":
                _write(path.with_name(path.name + ".new"), new)
            else:
                files[rel] = _digest(new)
        changes.append(Change(rel, action))
    if not dry_run:
        _write(vault_dir / MANIFEST, (json.dumps({"files": files}, indent=2) + "\n").encode("utf-8"))
    return changes


def pull(repo: Path | None = None) -> tuple[bool, str]:
    """Fast-forward the code to the latest version; never merges, resets or discards."""
    try:
        done = subprocess.run(["git", "-C", str(repo or vault.REPO), "pull", "--ff-only"],
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"git pull could not run: {e}"
    return done.returncode == 0, (done.stdout + done.stderr).strip()
