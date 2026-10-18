"""Organizing the memory on request: a short inventory the agent can judge, then the
changes the user approved, done by code so links stay intact.

lore uses no model, so it never decides that `antrenman` and `spor` belong together; the
agent proposes, the user approves. Every change has a dry run, and nothing is deleted or
overwritten: tag merges edit only the header's `tags` and `updated` lines, and moves stop
before touching anything if a destination already exists."""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


# --- journal and runs ----------------------------------------------------------------------
# Every applied change is journaled in .lore/logs/organize.jsonl so `undo` can revert it.
# Only vault-relative paths and tags are recorded, never note text. `organize` starts a run;
# changes applied within RUN_HOURS of it belong to that run, and `undo` reverts a whole run.

RUN_HOURS = 2


def _journal_path(vault_dir: Path) -> Path:
    return vault_dir / ".lore" / "logs" / "organize.jsonl"


def _run_path(vault_dir: Path) -> Path:
    return vault_dir / ".lore" / "state" / "organize-run.json"


def _new_run_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)


def start_run(vault_dir: Path, now: datetime | None = None) -> str:
    now = now or datetime.now()
    run = _new_run_id(now)
    path = _run_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run": run, "at": now.isoformat(timespec="seconds")}),
                    encoding="utf-8")
    return run


def _current_run(vault_dir: Path, now: datetime) -> str:
    try:
        data = json.loads(_run_path(vault_dir).read_text(encoding="utf-8"))
        if now - datetime.fromisoformat(data["at"]) <= timedelta(hours=RUN_HOURS):
            return str(data["run"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return _new_run_id(now)   # an apply without a recent `organize` is a run of its own


def _journal(vault_dir: Path, now: datetime, entry: dict) -> None:
    entry = {"run": _current_run(vault_dir, now), "at": now.isoformat(timespec="seconds"),
             **entry}
    path = _journal_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _rel(path: Path, vault_dir: Path) -> str:
    return vault.rel(path, vault_dir)


# --- tag merge -----------------------------------------------------------------------------

def merge_tags(vault_dir: Path, sources, into: str, apply: bool = False, keep: bool = False,
               now: datetime | None = None) -> list[Path]:
    """Replace the source tags with `into` in every note that has one (synonyms). With
    `keep`, add `into` before them and keep them (sub-topics: `antrenman` -> `spor,
    antrenman`). Returns the notes that change."""
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
    now = now or datetime.now()
    changed, records = [], []
    for path in vault.iter_notes(vault_dir):
        text = vault.read(path)
        meta, _ = frontmatter.parse(text)
        tags = _as_list(meta.get("tags"))
        if not any(_key(t) in src for t in tags):
            continue
        new: list[str] = []
        if keep:
            if _key(into) in {_key(t) for t in tags}:
                continue
            first = next(i for i, t in enumerate(tags) if _key(t) in src)
            new = tags[:first] + [into] + tags[first:]
        else:
            for tag in tags:
                tag = into if _key(tag) in src else tag
                if _key(tag) not in {_key(t) for t in new}:
                    new.append(tag)
        changed.append(path)
        if apply:
            _write(path, _edit(text, tags=new,
                               updated=vault.stamp(now) if "updated" in meta else None))
            records.append({"path": _rel(path, vault_dir), "before": tags, "after": new})
    if records:
        _journal(vault_dir, now, {"kind": "tags", "notes": records})
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


def _old_hub(src: Path, vault_dir: Path) -> str | None:
    """The area note a note in an area folder belongs to, as a link target."""
    parts = src.relative_to(vault_dir).parts
    if len(parts) > 1 and (vault_dir / parts[0] / f"{parts[0]}.md").exists():
        return vault.hub(parts[0])
    return None


def _relocate(vault_dir: Path, pairs: list[tuple[Path, Path]], hubs: dict, apply: bool,
              now: datetime) -> MovePlan:
    """Move each (src, dest); rewrite path-style links to moved notes, and in a moved note
    the link to its old area note (hubs: resolved src -> (old hub target, new hub target))."""
    plan = MovePlan(moves=list(pairs))
    moved = {src.resolve(): dest for src, dest in pairs}
    index = mesh.LinkIndex(vault_dir)
    hub_paths = {}
    for src, (old, new) in hubs.items():
        hit = index.resolve(old) if old else None
        if hit is not None and new:
            hub_paths[src] = (hit.resolve(), new)
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
            if me in hub_paths and hub_paths[me][0] == hit:
                return hub_paths[me][1]
            return None

        text = vault.read(path)
        counted = [0]

        def body_fn(body, fn=fn):
            new, n = _rewrite_links(body, fn)
            counted[0] = n
            return new

        new_text = _edit(text, body_fn=body_fn)
        if counted[0]:
            if "updated" in frontmatter.parse(text)[0]:
                new_text = _edit(new_text, updated=vault.stamp(now))
            new_texts[path] = new_text
            plan.link_updates.append((path, counted[0]))

    if apply:
        for path, text in new_texts.items():
            if path.resolve() not in moved:
                _write(path, text)
        for src, dest in pairs:
            if dest.exists():
                raise ValueError(f"{_rel(dest, vault_dir)} appeared meanwhile; stopped")
            if src in new_texts:
                _write(src, new_texts[src])
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dest)
    return plan


def move_notes(vault_dir: Path, given, area: str, apply: bool = False,
               now: datetime | None = None) -> MovePlan:
    """Move notes into an area and update path-style links to them, plus the moved notes'
    links to their old area note. All checks run before anything is written."""
    if area == "sessions":
        raise ValueError("sessions/ holds outcome records written by seal only")
    if area not in set(vault.areas(vault_dir)) | {inbox.INBOX}:
        raise ValueError(f"unknown area: {area}; create it first with `lore.py area add {area}`")
    now = now or datetime.now()
    notes = {p.resolve(): p for p in vault.iter_notes(vault_dir)}
    pairs: list[tuple[Path, Path]] = []
    hubs: dict = {}
    for item in given:
        src = _resolve_note(vault_dir, item, notes)
        dest = vault_dir / area / src.name
        if src.parent == dest.parent:
            raise ValueError(f"already in {area}: {_rel(src, vault_dir)}")
        if dest.exists() or dest in {d for _, d in pairs}:
            raise ValueError(f"{_rel(dest, vault_dir)} already exists; nothing was moved")
        pairs.append((src, dest))
        hubs[src.resolve()] = (_old_hub(src, vault_dir), vault.hub(area))
    plan = _relocate(vault_dir, pairs, hubs, apply, now)
    if apply:
        _journal(vault_dir, now, {"kind": "move", "moves": [
            {"from": _rel(src, vault_dir), "to": _rel(dest, vault_dir),
             "hub_from": hubs[src.resolve()][0], "hub_to": hubs[src.resolve()][1]}
            for src, dest in pairs]})
    return plan


# --- undo ----------------------------------------------------------------------------------

@dataclass
class UndoResult:
    run: str
    undone: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # changed since; left as they are


def _entries(vault_dir: Path) -> list[dict]:
    try:
        lines = _journal_path(vault_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def undo(vault_dir: Path, now: datetime | None = None) -> UndoResult:
    """Revert the latest organize run that was not undone yet, newest change first.
    A note changed since is skipped and reported, never overwritten."""
    now = now or datetime.now()
    entries = _entries(vault_dir)
    done = {e.get("undo") for e in entries if "undo" in e}
    batches = [e for e in entries if e.get("kind") in ("tags", "move") and e.get("run") not in done]
    if not batches:
        raise ValueError("Nothing to undo: no organize changes are recorded.")
    run = batches[-1]["run"]
    result = UndoResult(run)
    for batch in reversed([b for b in batches if b["run"] == run]):
        if batch["kind"] == "tags":
            for rec in batch.get("notes", []):
                path = vault_dir / rec["path"]
                if not path.is_file():
                    result.skipped.append(rec["path"])
                    continue
                text = vault.read(path)
                meta, _ = frontmatter.parse(text)
                if _as_list(meta.get("tags")) != rec["after"]:
                    result.skipped.append(rec["path"])
                    continue
                _write(path, _edit(text, tags=rec["before"],
                                   updated=vault.stamp(now) if "updated" in meta else None))
                result.undone.append(f"tags of {rec['path']}")
        else:
            pairs, hubs = [], {}
            for mv in batch.get("moves", []):
                src, dest = vault_dir / mv["to"], vault_dir / mv["from"]
                if not src.is_file() or dest.exists():
                    result.skipped.append(mv["to"])
                    continue
                pairs.append((src, dest))
                hubs[src.resolve()] = (mv.get("hub_to"), mv.get("hub_from"))
            if pairs:
                _relocate(vault_dir, pairs, hubs, True, now)
                result.undone.extend(f"{mv_from} back from {mv_to}" for mv_to, mv_from in
                                     ((_rel(s, vault_dir), _rel(d, vault_dir)) for s, d in pairs))
    path = _journal_path(vault_dir)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"undo": run, "at": now.isoformat(timespec="seconds")}) + "\n")
    return result
