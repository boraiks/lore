"""Inbox summary: how many notes wait in inbox, how old they are, and which tags they carry.

lore uses no model, so it cannot tell that `antrenman` and `spor` are one theme. It only
shows the tags; the agent reads the meaning and may suggest an area, and the user decides.
Nothing here creates or moves anything."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import frontmatter, vault
from .turkish import fold

INBOX = "inbox"
MIN_NOTES = 3       # below this, jot prints no summary: nothing has piled up yet
MAX_TAGS = 12       # keeps the summary line short


@dataclass
class Report:
    count: int = 0
    oldest_days: int | None = None
    tags: list[tuple[str, int]] = field(default_factory=list)


def _declined_path(vault_dir: Path) -> Path:
    return vault_dir / ".lore" / "state" / "declined-areas.json"


def declined(vault_dir: Path) -> list[str]:
    try:
        data = json.loads(_declined_path(vault_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(n) for n in data] if isinstance(data, list) else []


def decline(vault_dir: Path, name: str) -> Path:
    """Remember that the user does not want this area, so agents stop suggesting it."""
    if not vault.valid_area_name(name):
        raise ValueError(f"invalid area name: {name!r} (lowercase letters, digits and '-')")
    names = declined(vault_dir)
    if name not in names:
        names.append(name)
    path = _declined_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(sorted(names), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _inbox_notes(vault_dir: Path) -> list[Path]:
    folder = vault_dir / INBOX
    if not folder.is_dir():
        return []
    return sorted(p for p in vault.iter_notes(folder) if p.stem != INBOX)


def tag_summary(vault_dir: Path, notes: list[Path] | None = None) -> list[tuple[str, int]]:
    """(tag, notes carrying it), largest first. Spellings that differ only in Turkish letters
    count together; client tags are left out."""
    counts: dict[str, list] = {}
    for path in _inbox_notes(vault_dir) if notes is None else notes:
        meta, _ = frontmatter.parse(vault.read(path))
        seen = set()
        tags = meta.get("tags") or []
        for tag in tags if isinstance(tags, list) else [tags]:
            tag = str(tag).strip()
            key = fold(tag)
            if not tag or key.startswith("client/") or key in seen:
                continue
            seen.add(key)
            counts.setdefault(key, [tag, 0])[1] += 1
    return [(tag, n) for key, (tag, n) in sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0]))]


def summary_line(vault_dir: Path) -> str | None:
    """One line for the agent after a note goes to inbox, once a few notes have piled up."""
    notes = _inbox_notes(vault_dir)
    if len(notes) < MIN_NOTES:
        return None
    tags = tag_summary(vault_dir, notes)
    shown = ", ".join(f"{t} {n}" for t, n in tags[:MAX_TAGS]) or "none"
    more = f" (+{len(tags) - MAX_TAGS} more)" if len(tags) > MAX_TAGS else ""
    no = declined(vault_dir)
    return (f"INBOX: {len(notes)} notes; tags: {shown}{more}"
            + (f"; declined areas: {', '.join(no)}" if no else ""))


def _created(path: Path) -> datetime:
    meta, _ = frontmatter.parse(vault.read(path))
    try:
        return datetime.strptime(str(meta.get("created", ""))[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return datetime.fromtimestamp(path.stat().st_mtime)


def report(vault_dir: Path, now: datetime | None = None) -> Report:
    notes = _inbox_notes(vault_dir)
    if not notes:
        return Report()
    oldest = min(_created(p) for p in notes)
    return Report(len(notes), max(0, ((now or datetime.now()) - oldest).days),
                  tag_summary(vault_dir, notes))
