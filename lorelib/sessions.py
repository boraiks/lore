"""Session notes: lookup by session id, file naming, and the private markers."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from . import config, frontmatter, vault

SESSION_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEAD_CHARS = 4096


def truthy(value) -> bool:
    return str(value).strip().lower() in ("true", "yes", "1", "evet")


def find(notes_dir: Path, session_id: str) -> Path | None:
    """The note whose header names this session, whatever its file name is."""
    folder = notes_dir / "sessions"
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob("*.md")):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                head = f.read(_HEAD_CHARS)
        except OSError:
            continue
        meta, _ = frontmatter.parse(head)
        if meta.get("session") == session_id:
            return path
    return None


def new_path(notes_dir: Path, when: datetime, client: str, topic: str) -> Path:
    """sessions/<date>-<client>-<topic>.md; a numeric suffix if that name is taken."""
    stem = f"{when:%Y-%m-%d}-{client}-{vault.slugify(topic, 40) or 'session'}"
    path = notes_dir / "sessions" / f"{stem}.md"
    n = 2
    while path.exists():
        path = notes_dir / "sessions" / f"{stem}-{n}.md"
        n += 1
    return path


def project_tag(cwd: str) -> str:
    """Folder name of the working directory; nothing for the home folder or a drive root."""
    if not cwd:
        return ""
    p = Path(cwd)
    try:
        if p.resolve() == Path.home().resolve():
            return ""
    except OSError:
        pass
    return vault.slugify(p.name)


def rewrite(path: Path, meta: dict, body: str) -> None:
    """Replace a note in one step (temp file + rename), so a crash leaves no half file."""
    tmp = path.with_suffix(".md.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(frontmatter.render(meta) + "\n" + body + "\n")
    os.replace(tmp, path)


def _marker(state_dir: Path, session_id: str) -> Path:
    return state_dir / "private" / session_id


def mark_private(state_dir: Path, session_id: str) -> Path:
    if not SESSION_ID.match(session_id):
        raise ValueError("invalid session id")
    path = _marker(state_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def is_private(session_id: str, cwd: str, cfg: dict, state_dir: Path, meta: dict | None = None) -> bool:
    """Marked by the agent (seal --private), by folder (config), or in the note header."""
    if SESSION_ID.match(session_id or "") and _marker(state_dir, session_id).exists():
        return True
    if config.in_private_dir(cwd, cfg):
        return True
    return bool(meta) and truthy(meta.get("private", ""))
