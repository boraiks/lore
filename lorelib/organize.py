"""Organizing the memory on request: a short inventory the agent can judge, then the
changes the user approved, done by code so links stay intact.

lore uses no model, so it never decides that `antrenman` and `spor` belong together; the
agent proposes, the user approves. Every change has a dry run, and nothing is deleted or
overwritten: tag merges edit only the header's `tags` and `updated` lines, and moves stop
before touching anything if a destination already exists."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import frontmatter, guard, inbox, mesh, vault
from .turkish import fold, lower

INBOX_LIST_MAX = 30
TAGS_MAX = 40


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)] if value else []


def _key(tag: str) -> str:
    return fold(str(tag).strip().lstrip("#"))


def _is_hub(path: Path, vault_dir: Path) -> bool:
    parts = path.relative_to(vault_dir).parts
    return len(parts) == 2 and parts[1] == parts[0] + ".md"


def _is_root_page(path: Path, vault_dir: Path) -> bool:
    return path.parent == vault_dir and path.stem in (vault.HOME, vault.ME)


def _topic_notes(vault_dir: Path) -> list[Path]:
    """Notes whose tags are topics: not area notes, home.md or me.md."""
    return [p for p in vault.iter_notes(vault_dir)
            if not _is_hub(p, vault_dir) and not _is_root_page(p, vault_dir)]


# --- inventory -----------------------------------------------------------------------------

def inventory(vault_dir: Path) -> str:
    out = [mesh.DATA_WARNING]
    counts = []
    for area in vault.areas(vault_dir):
        n = sum(1 for p in vault.iter_notes(vault_dir / area) if p.stem != area)
        counts.append(f"{area} {n}")
    out.append("Areas (notes): " + (", ".join(counts) or "none"))
    tags = inbox.tag_summary(vault_dir, _topic_notes(vault_dir))
    more = f" (+{len(tags) - TAGS_MAX} more)" if len(tags) > TAGS_MAX else ""
    out.append(f"Tags (top {TAGS_MAX}, client tags left out): "
               + (", ".join(f"{t} {n}" for t, n in tags[:TAGS_MAX]) or "none") + more)
    notes = sorted(p for p in vault.iter_notes(vault_dir / inbox.INBOX) if p.stem != inbox.INBOX)
    out.append(f"Inbox notes ({len(notes)}):")
    for path in notes[:INBOX_LIST_MAX]:
        meta, _ = frontmatter.parse(vault.read(path))
        tags_of = ", ".join(t for t in _as_list(meta.get("tags")) if not _key(t).startswith("client/"))
        out.append(f"  {vault.rel(path, vault_dir)} \"{meta.get('title') or path.stem}\" [{tags_of}]")
    if len(notes) > INBOX_LIST_MAX:
        out.append(f"  (+{len(notes) - INBOX_LIST_MAX} more)")
    if inbox.declined(vault_dir):
        out.append("Declined areas: " + ", ".join(inbox.declined(vault_dir)))
    out.append("To apply a plan the user approved (dry run first, then --apply): "
               "python lore.py tag merge <tag>... --into <tag> | "
               "python lore.py move <note>... --to <name> | python lore.py area add <name>")
    return "\n".join(out)


# --- editing a note in place --------------------------------------------------------------

def _set_tags(head: list[str], tags: list[str]) -> list[str]:
    for i, line in enumerate(head):
        if not line.startswith("tags:"):
            continue
        cr = "\r" if line.endswith("\r") else ""
        value = line[5:].strip()
        if value.startswith("["):
            return head[:i] + [f"tags: [{', '.join(frontmatter._quote(t) for t in tags)}]{cr}"] \
                + head[i + 1:]
        end = i + 1
        if not value:
            while end < len(head) and head[end].lstrip().startswith("- "):
                end += 1
        return (head[:i] + [f"tags:{cr}"] + [f"  - {frontmatter._quote(t)}{cr}" for t in tags]
                + head[end:])
    return head


def _edit(text: str, tags: list[str] | None = None, updated: str | None = None,
          body_fn=None) -> str:
    """Change the header's tags and updated lines and/or the body; everything else stays."""
    text = text.lstrip("﻿")
    lines = text.split("\n")
    header, _ = frontmatter.split(text)
    if header is None:
        return body_fn(text) if body_fn else text
    end = len(header) + 1          # index of the closing ---
    head = lines[1:end]
    if tags is not None:
        head = _set_tags(head, tags)
    if updated is not None:
        for i, line in enumerate(head):
            if line.startswith("updated:"):
                head[i] = f"updated: {updated}" + ("\r" if line.endswith("\r") else "")
    body = "\n".join(lines[end + 1:])
    if body_fn:
        body = body_fn(body)
    return "\n".join([lines[0]] + head + [lines[end]]) + "\n" + body


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".lore-tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


# --- tag merge -----------------------------------------------------------------------------

def merge_tags(vault_dir: Path, sources, into: str, apply: bool = False,
               now: datetime | None = None) -> list[Path]:
    """Replace the source tags with `into` in every note that has one. Returns those notes."""
    into = "-".join(lower(str(into)).lstrip("#").split())
    if not into or "/" in into:
        raise ValueError("the target tag must be one plain word (no '/', not empty)")
    if guard.scan(into):
        raise ValueError("the target tag looks like a secret or a personal number (value hidden)")
    src = {_key(s) for s in sources if str(s).strip()} - {_key(into)}
    if not src:
        raise ValueError("nothing to merge: give tags other than the target")
    if any(k.startswith("client/") for k in src):
        raise ValueError("client tags record where a note was written; they are not merged")
    changed = []
    for path in vault.iter_notes(vault_dir):
        text = vault.read(path)
        meta, _ = frontmatter.parse(text)
        tags = _as_list(meta.get("tags"))
        if not any(_key(t) in src for t in tags):
            continue
        new: list[str] = []
        for tag in tags:
            tag = into if _key(tag) in src else tag
            if _key(tag) not in {_key(t) for t in new}:
                new.append(tag)
        changed.append(path)
        if apply:
            _write(path, _edit(text, tags=new,
                               updated=vault.stamp(now) if "updated" in meta else None))
    return changed


# --- move ----------------------------------------------------------------------------------

@dataclass
class MovePlan:
    moves: list[tuple[Path, Path]] = field(default_factory=list)
    link_updates: list[tuple[Path, int]] = field(default_factory=list)


def _rewrite_links(body: str, fn) -> tuple[str, int]:
    """Apply fn(target) -> new target or None to each wikilink outside code."""
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        raw = m.group(1)
        new = fn(mesh._clean_target(raw))
        if new is None:
            return m.group(0)
        cut = min([i for i in (raw.find("|"), raw.find("#")) if i >= 0], default=len(raw))
        count += 1
        return ("!" if m.group(0).startswith("!") else "") + f"[[{new}{raw[cut:]}]]"

    out, in_fence = [], False
    for line in body.split("\n"):
        if mesh._FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        parts, last = [], 0
        for code in mesh._INLINE_CODE.finditer(line):
            parts.append(mesh._LINK.sub(repl, line[last:code.start()]))
            parts.append(code.group(0))
            last = code.end()
        parts.append(mesh._LINK.sub(repl, line[last:]))
        out.append("".join(parts))
    return "\n".join(out), count


def _resolve_note(vault_dir: Path, given, notes: dict[Path, Path]) -> Path:
    path = Path(given)
    if not path.is_absolute():
        path = vault_dir / path
    if not path.name.lower().endswith(".md"):
        path = path.with_name(path.name + ".md")
    found = notes.get(path.resolve())
    if found is None:
        raise ValueError(f"not a note in the vault: {given}")
    if _is_hub(found, vault_dir) or _is_root_page(found, vault_dir):
        raise ValueError(f"area notes, home.md and me.md stay where they are: {given}")
    if found.relative_to(vault_dir).parts[0] == "sessions":
        raise ValueError(f"session notes stay in sessions/: {given}")
    return found


def _no_md(path: Path, vault_dir: Path) -> str:
    rel = vault.rel(path, vault_dir)
    return rel[:-3] if rel.lower().endswith(".md") else rel


def move_notes(vault_dir: Path, given, area: str, apply: bool = False,
               now: datetime | None = None) -> MovePlan:
    """Move notes into an area and update path-style links to them, plus the moved notes'
    links to their old area note. All checks run before anything is written."""
    if area == "sessions":
        raise ValueError("sessions/ holds outcome records written by seal only")
    if area not in set(vault.areas(vault_dir)) | {inbox.INBOX}:
        raise ValueError(f"unknown area: {area}; create it first with `lore.py area add {area}`")
    notes = {p.resolve(): p for p in vault.iter_notes(vault_dir)}
    plan = MovePlan()
    dests: set[Path] = set()
    moved: dict[Path, Path] = {}       # resolved source -> destination
    old_hub: dict[Path, Path] = {}     # resolved source -> resolved old area note
    for item in given:
        src = _resolve_note(vault_dir, item, notes)
        dest = vault_dir / area / src.name
        if src.parent == dest.parent:
            raise ValueError(f"already in {area}: {vault.rel(src, vault_dir)}")
        if dest.exists() or dest in dests:
            raise ValueError(f"{vault.rel(dest, vault_dir)} already exists; nothing was moved")
        dests.add(dest)
        plan.moves.append((src, dest))
        moved[src.resolve()] = dest
        first = src.relative_to(vault_dir).parts[0]
        hub = vault_dir / first / f"{first}.md"
        if len(src.relative_to(vault_dir).parts) > 1 and hub.exists():
            old_hub[src.resolve()] = hub.resolve()

    index = mesh.LinkIndex(vault_dir)
    new_texts: dict[Path, str] = {}
    for path in vault.iter_notes(vault_dir):
        me = path.resolve()

        def fn(target, me=me):
            hit = index.resolve(target)
            if hit is None:
                return None
            hit = hit.resolve()
            if hit in moved and "/" in target:
                return _no_md(moved[hit], vault_dir)
            if me in moved and old_hub.get(me) == hit:
                return vault.hub(area)
            return None

        text = vault.read(path)
        body_count = [0]

        def body_fn(body, fn=fn):
            new, n = _rewrite_links(body, fn)
            body_count[0] = n
            return new

        new_text = _edit(text, body_fn=body_fn)
        if body_count[0]:
            meta, _ = frontmatter.parse(text)
            if "updated" in meta:
                new_text = _edit(new_text, updated=vault.stamp(now))
            new_texts[path] = new_text
            plan.link_updates.append((path, body_count[0]))

    if apply:
        for path, text in new_texts.items():
            if path.resolve() not in moved:
                _write(path, text)
        for src, dest in plan.moves:
            if dest.exists():
                raise ValueError(f"{vault.rel(dest, vault_dir)} appeared meanwhile; stopped")
            if src in new_texts:
                _write(src, new_texts[src])
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dest)
    return plan
