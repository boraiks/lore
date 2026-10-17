"""Safe note writing: generated header, no overwrite, no secrets, always linked."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import frontmatter, guard, mesh, vault
from .turkish import lower


class SecretRejected(Exception):
    def __init__(self, findings: list[guard.Finding]):
        self.findings = findings
        where = ", ".join(f"{f.field} line {f.line}: {f.kind}" for f in findings)
        super().__init__(f"possible secret or sensitive data found (value hidden): {where}")


class NoteExists(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"file already exists, not overwritten: {path}")


def normalize_tags(tags) -> list[str]:
    out = []
    for tag in tags:
        tag = "-".join(lower(str(tag)).lstrip("#").split())
        if tag and tag not in out:
            out.append(tag)
    return out


def clean_link(link: str) -> str:
    return link.strip().removeprefix("[[").removesuffix("]]").strip()


def jot(notes_dir: Path, area: str, title: str, body: str = "", tags=(), status: str = "active",
        type: str = "note", client: str | None = None, links=(), now: datetime | None = None,
        machine: str | None = None) -> tuple[Path, list[str]]:
    """Write a new note; returns (path, warnings). Nothing touches disk if a check fails."""
    if area not in vault.AREAS:
        raise ValueError(f"unknown area: {area} (choices: {', '.join(vault.AREAS)})")
    if status not in frontmatter.STATUSES:
        raise ValueError(f"invalid status: {status}")
    if type not in frontmatter.TYPES:
        raise ValueError(f"invalid type: {type}")
    if client is not None and client not in frontmatter.CLIENTS:
        raise ValueError(f"invalid client: {client}")
    title = " ".join(title.split())
    slug = vault.slugify(title)
    if not slug:
        raise ValueError("the title is empty or cannot become a file name")
    tags = normalize_tags(tags)
    if client and client != "manual" and f"client/{client}" not in tags:
        tags.append(f"client/{client}")  # the graph can show where a note was written
    links = [l for l in (clean_link(x) for x in links) if l]
    body = body.strip("\n")

    findings = []
    for name, text in (("title", title), ("tags", " ".join(tags)), ("links", " ".join(links)),
                       ("body", body)):
        findings += guard.scan(text, field=name)
    if findings:
        raise SecretRejected(findings)

    if area == "sessions":  # one naming scheme for session notes: date-client-topic
        slug = f"{(now or datetime.now()):%Y-%m-%d}-{client or 'manual'}-{slug}"
    path = notes_dir / area / f"{slug}.md"
    if path.exists():
        raise NoteExists(path)

    vault.seed(notes_dir, now=now, machine=machine)
    warnings = []
    if client is None:
        client = "manual"
        warnings.append("no client given, wrote 'manual' (--client claude|codex|antigravity)")
    if not links and not mesh.extract_links(body):
        links = [vault.hub(area)]
        warnings.append(f"no link given, linked to the area note: [[{vault.hub(area)}]]")
    index = mesh.LinkIndex(notes_dir)
    for link in links:
        if index.resolve(link) is None:
            warnings.append(f"link target not found: [[{link}]]")
    if links:
        body = (body + "\n\n" if body else "") + "Related: " + " ".join(f"[[{l}]]" for l in links)

    ts = vault.stamp(now)
    meta = {"title": title, "created": ts, "updated": ts, "tags": tags, "status": status,
            "type": type, "machine": machine or vault.machine_name(), "client": client}
    for name in frontmatter.missing_fields(meta):
        warnings.append(f"empty header field: {name}")

    try:
        vault.write_new(path, frontmatter.render(meta) + "\n" + body + "\n")
    except FileExistsError:
        raise NoteExists(path) from None
    return path, warnings
