"""Inbox themes: notice when notes about one theme pile up in inbox, so the agent can
suggest an area. Nothing here creates or moves anything; the user decides.

A theme is a tag shared by THRESHOLD or more inbox notes that no area covers yet. Client
tags, generic tags, nested tags and themes the user declined are left out."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import frontmatter, vault
from .turkish import fold

INBOX = "inbox"
THRESHOLD = 3
GENERIC = frozenset({"lore", "note", "notes", "not", "notlar", "todo", "misc", "genel", "inbox",
                     "area", "home", "me", "session", "sessions", "draft", "idea", "fikir"})


@dataclass
class Theme:
    name: str            # a valid area name, built from the tag
    count: int
    notes: list[Path] = field(default_factory=list)


@dataclass
class Report:
    count: int = 0
    oldest_days: int | None = None
    themes: list[Theme] = field(default_factory=list)


def _declined_path(vault_dir: Path) -> Path:
    return vault_dir / ".lore" / "state" / "declined-areas.json"


def declined(vault_dir: Path) -> list[str]:
    try:
        data = json.loads(_declined_path(vault_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(n) for n in data] if isinstance(data, list) else []


def decline(vault_dir: Path, name: str) -> Path:
    """Remember that the user does not want this area, so it is not suggested again."""
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


def _area_name(tag: str) -> str | None:
    if "/" in tag:
        return None
    name = vault.slugify(tag, 40)
    return name if vault.valid_area_name(name) and name not in GENERIC else None


def themes(vault_dir: Path, tags=None) -> list[Theme]:
    """Themes at or past the threshold, largest first. With `tags`, only those tags."""
    skip = set(vault.areas(vault_dir)) | set(vault.REQUIRED_AREAS) | set(declined(vault_dir))
    only = None if tags is None else {_area_name(fold(t)) for t in tags}
    found: dict[str, Theme] = {}
    for path in _inbox_notes(vault_dir):
        meta, _ = frontmatter.parse(vault.read(path))
        names = {_area_name(fold(str(t))) for t in (meta.get("tags") or [])}
        for name in names - {None}:
            if name in skip or (only is not None and name not in only):
                continue
            theme = found.setdefault(name, Theme(name, 0))
            theme.count += 1
            theme.notes.append(path)
    return sorted((t for t in found.values() if t.count >= THRESHOLD),
                  key=lambda t: (-t.count, t.name))


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
    return Report(len(notes), max(0, ((now or datetime.now()) - oldest).days), themes(vault_dir))


def suggestion(theme: Theme) -> str:
    return (f"SUGGEST: {theme.count} inbox notes share the theme \"{theme.name}\" and no area "
            f"covers it. Ask the user in one sentence whether to create a `{theme.name}` area. "
            f"On yes: python lore.py area add {theme.name} \"<what goes there>\" (moving the notes "
            f"is a separate question). On no: python lore.py area decline {theme.name}")
