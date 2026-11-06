"""What we know, kept where it belongs.

Knowledge: a project or topic's main note carries a `## Knowledge` section that grows one
line at a time, each line ending with a link to the session note it came from. Lines are
only added or struck through as outdated, never deleted; every change is journaled, so
`lore.py undo` reverts it with the rest of the latest run.

Index: every area note holds a lore-managed list of the notes in its folder, newest first,
so an area never looks empty in Obsidian and its node links to everything in it. Only the
block between the markers is rewritten; recall ignores it."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import frontmatter, guard, mesh, organize, vault
from .turkish import fold

HEADING = "## Knowledge"
INDEX_BEGIN = "<!-- lore:index -->"
INDEX_END = "<!-- /lore:index -->"
INDEX_HEADING = "## Notes"
INDEX_MAX = 50
DESC_CHARS = 110

_INDEX_BLOCK = re.compile(re.escape(INDEX_BEGIN) + r".*?" + re.escape(INDEX_END), re.S)
_SOURCE = re.compile(r"\s*\(\[\[[^\]]*\]\]\)\s*$")
_LINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")


def strip_index(body: str) -> str:
    return _INDEX_BLOCK.sub("", body)


# --- finding notes -------------------------------------------------------------------------

def _resolve(vault_dir: Path, target: str, what: str) -> Path:
    path = Path(target)
    if path.is_absolute():
        hit = path if path.is_file() else None
    else:
        hit = mesh.LinkIndex(vault_dir).resolve(str(target).replace("\\", "/").removesuffix(".md"))
    if hit is None:
        raise ValueError(f"{what} not found: {target} (find the note with recall first)")
    return hit


def _knowledge_target(vault_dir: Path, target: str) -> Path:
    path = _resolve(vault_dir, target, "note")
    parts = path.relative_to(vault_dir).parts
    if parts[0] == "sessions":
        raise ValueError("knowledge goes into a project or topic note, not a session note")
    if len(parts) == 1 and path.stem in (vault.HOME, vault.ME):
        raise ValueError("knowledge does not go into home.md or me.md")
    return path


# --- knowledge lines -----------------------------------------------------------------------

def _norm(line: str) -> str:
    line = _SOURCE.sub("", line.strip().lstrip("-").strip()).replace("~~", "")
    return fold(" ".join(line.split()))


def _section(lines: list[str]) -> tuple[int | None, int]:
    """(index of the heading or None, index where the section ends)."""
    start = next((i for i, l in enumerate(lines) if l.strip() == HEADING), None)
    if start is None:
        return None, len(lines)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("## ") or s.startswith("Related: [[") or s.startswith("Home: [[") \
                or s.startswith("<!-- lore:"):
            end = i
            break
    return start, end


def _insert(body: str, line: str) -> str:
    lines = body.split("\n")
    start, end = _section(lines)
    if start is None:
        at = next((i for i, l in enumerate(lines)
                   if l.strip().startswith(("Related: [[", "Home: [[", "<!-- lore:"))), len(lines))
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        block = ["", HEADING, line, ""]
        lines[at:at] = block
        return "\n".join(lines)
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, line)
    return "\n".join(lines)


def add(vault_dir: Path, target: str, fact: str, source: str,
        now: datetime | None = None) -> bool:
    """Add one sourced line to the note's Knowledge section. False if it is already there."""
    now = now or datetime.now()
    fact = " ".join(str(fact).split()).lstrip("- ").strip()
    if not fact:
        raise ValueError("the line is empty")
    findings = guard.scan(fact, field="knowledge")
    if findings:
        raise guard.SecretRejected(findings)
    path = _knowledge_target(vault_dir, target)
    src = _resolve(vault_dir, source, "source note")
    link = vault.rel(src, vault_dir)[:-3]
    text = vault.read(path)
    meta, body = frontmatter.parse(text)
    lines = body.split("\n")
    start, end = _section(lines)
    if start is not None and any(_norm(l) == _norm(fact) for l in lines[start + 1:end]):
        return False
    line = f"- {fact} ([[{link}]])"
    organize._write(path, organize._edit(
        text, updated=vault.stamp(now) if "updated" in meta else None,
        body_fn=lambda b: _insert(b, line)))
    organize._journal(vault_dir, now, {"kind": "know", "path": vault.rel(path, vault_dir),
                                       "added": line})
    return True


def outdate(vault_dir: Path, target: str, fragment: str, now: datetime | None = None) -> str:
    """Strike through the one Knowledge line containing `fragment`; it stays readable."""
    now = now or datetime.now()
    path = _knowledge_target(vault_dir, target)
    text = vault.read(path)
    meta, body = frontmatter.parse(text)
    lines = body.split("\n")
    start, end = _section(lines)
    key = fold(" ".join(fragment.split()))
    hits = [i for i in range(start + 1, end) if start is not None and key and key in _norm(lines[i])
            and "~~" not in lines[i]] if start is not None else []
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} knowledge lines match; give a fragment that fits exactly one")
    old = lines[hits[0]]
    m = _SOURCE.search(old)
    content = old.strip().lstrip("-").strip()
    source = ""
    if m:
        source, content = m.group(0).strip(), _SOURCE.sub("", content)
    new = f"- ~~{content}~~ (outdated {now:%Y-%m-%d})" + (f" {source}" if source else "")
    organize._write(path, organize._edit(
        text, updated=vault.stamp(now) if "updated" in meta else None,
        body_fn=lambda b: b.replace(old, new, 1)))
    organize._journal(vault_dir, now, {"kind": "know", "path": vault.rel(path, vault_dir),
                                       "before": old, "after": new})
    return new


def revert(vault_dir: Path, rec: dict, now: datetime) -> bool:
    """Undo one journaled knowledge change; False if the note changed since."""
    path = vault_dir / rec["path"]
    if not path.is_file():
        return False
    text = vault.read(path)
    meta, body = frontmatter.parse(text)
    lines = body.split("\n")
    if "added" in rec:
        if rec["added"] not in lines:
            return False
        lines.remove(rec["added"])
        start, end = _section(lines)
        if start is not None and not any(l.strip() for l in lines[start + 1:end]):
            del lines[start:end]          # the section was only that line: take it out too
            while start < len(lines) and start > 0 and not lines[start].strip() \
                    and not lines[start - 1].strip():
                del lines[start]
        new_body = "\n".join(lines)
    else:
        if rec["after"] not in lines:
            return False
        new_body = body.replace(rec["after"], rec["before"], 1)
    organize._write(path, organize._edit(
        text, updated=vault.stamp(now) if "updated" in meta else None,
        body_fn=lambda b: new_body))
    return True


# --- area index ----------------------------------------------------------------------------

def _describe(body: str) -> str:
    for line in strip_index(body).split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "Related:", "Home:", "<!--", "|", "---", "```")):
            continue
        s = _LINK.sub(lambda m: m.group(2) or m.group(1).split("/")[-1], s).lstrip("-*> ").strip()
        return guard.clip(s, DESC_CHARS)
    return ""


def _index_block(vault_dir: Path, area: str) -> str:
    rows = []
    for path in vault.iter_notes(vault_dir / area):
        if path.parent == vault_dir / area and path.stem == area:
            continue
        meta, body = frontmatter.parse(vault.read(path))
        title = str(meta.get("title") or path.stem).replace("|", "-").replace("]", ")")
        rows.append((str(meta.get("updated") or ""), vault.rel(path, vault_dir)[:-3], title,
                     _describe(body)))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    items = [f"- [[{rel}|{title}]]" + (f": {desc}" if desc else "")
             for _, rel, title, desc in rows[:INDEX_MAX]]
    if len(rows) > INDEX_MAX:
        items.append(f"- ... and {len(rows) - INDEX_MAX} more")
    return "\n".join([INDEX_BEGIN, INDEX_HEADING, *(items or ["- (no notes yet)"]), INDEX_END])


def refresh_index(vault_dir: Path, area: str) -> bool:
    """Rewrite the area note's index block; True if it changed. The note's own text and its
    `updated` field stay as they are: the list is generated, not written by anyone."""
    hub = vault_dir / area / f"{area}.md"
    if not hub.is_file():
        return False
    text = vault.read(hub)
    block = _index_block(vault_dir, area)

    def put(body: str) -> str:
        if _INDEX_BLOCK.search(body):
            return _INDEX_BLOCK.sub(lambda _: block, body, count=1)
        lines = body.rstrip("\n").split("\n")
        at = next((i for i in range(len(lines) - 1, -1, -1)
                   if lines[i].strip().startswith("Home: [[")), len(lines))
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        insert = ["", block]
        if at < len(lines) and lines[at].strip():
            insert.append("")
        lines[at:at] = insert
        return "\n".join(lines) + "\n"

    new = organize._edit(text, body_fn=put)
    if new == text.lstrip("﻿"):
        return False
    organize._write(hub, new)
    return True


def refresh_all(vault_dir: Path) -> list[str]:
    areas = sorted(set(vault.areas(vault_dir)) | set(vault.REQUIRED_AREAS))
    return [a for a in areas if refresh_index(vault_dir, a)]
