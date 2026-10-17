"""Vault layout: where notes live, the area list, file naming, and the skeleton.

The code (this repository) and the personal vault are separate folders. The vault is the
folder opened in Obsidian: areas sit at its root, local logs/state/settings in its hidden
.lore/ folder. Where the vault is: LORE_HOME, else ~/.lore.json {"home": ...}, else a
lore-vault folder next to the repository.
"""

from __future__ import annotations

import json
import os
import re
import socket
from datetime import datetime
from pathlib import Path

from . import frontmatter
from .turkish import fold

REPO = Path(__file__).resolve().parent.parent
POINTER = Path.home() / ".lore.json"
DEFAULT_VAULT = REPO.parent / "lore-vault"


def locate() -> tuple[Path, str]:
    """(vault folder, where that came from)."""
    env = os.environ.get("LORE_HOME", "").strip()
    if env:
        return Path(env).expanduser(), "LORE_HOME"
    try:
        home = json.loads(POINTER.read_text(encoding="utf-8-sig")).get("home")
        if isinstance(home, str) and home.strip():
            return Path(home).expanduser(), str(POINTER)
    except (OSError, ValueError, AttributeError):
        pass
    return DEFAULT_VAULT, "default (lore-vault next to the repository)"


def set_home(folder: Path) -> Path:
    """Remember the vault folder in ~/.lore.json; other keys in that file are kept."""
    try:
        data = json.loads(POINTER.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["home"] = Path(folder).expanduser().resolve().as_posix()
    tmp = POINTER.with_name(POINTER.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, POINTER)
    return Path(data["home"])


VAULT = locate()[0]
NOTES_DIR = VAULT  # notes live at the vault root
STATE_DIR = VAULT / ".lore" / "state"  # reminder and private markers

# area -> (title of its area note, what goes there)
AREAS = {
    "career": ("Career", "Jobs and internships. One note per company or application: role, "
                         "date applied, status, interviews, next step. CV and interview "
                         "preparation live here too."),
    "courses": ("Courses", "Course notes. One main note per course; topic notes link to it."),
    "ideas": ("Ideas", "Project ideas. One note per idea: the problem, why it is interesting, "
                       "the first step."),
    "research": ("Research", "Day-to-day research: what was read, tried and found, with sources."),
    "sessions": ("Sessions", "Outcome records of agent sessions; written by `seal`, not by hand."),
    "imports": ("Imports", "Notes brought over from old chat history. Kept apart so they do not "
                           "clutter the graph; do not write here by hand."),
}
HOME = "home"


def hub(area: str) -> str:
    """Link target of an area's own note, <area>/<area>.md: the graph shows it by the area's
    name, and every note in the area can link to it."""
    return f"{area}/{area}"


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
    return slug[:max_len].rstrip("-")


def machine_name() -> str:
    """Computer name only; never the user name or a path."""
    return socket.gethostname() or "unknown"


def stamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%dT%H:%M")


def rel(path: Path, notes_dir: Path) -> str:
    return path.relative_to(notes_dir).as_posix()


# Agent instruction files at the vault root (installed by lore); instructions, not notes.
AGENT_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")


def _is_note_file(parts: tuple[str, ...]) -> bool:
    """Hidden folders (.lore, .obsidian, .trash) and folders starting with "_" (templates)
    hold no notes; neither do the agent pointer files at the root."""
    if any(part.startswith((".", "_")) for part in parts):
        return False
    return not (len(parts) == 1 and parts[0].lower() in {f.lower() for f in AGENT_FILES})


def iter_files(notes_dir: Path):
    """All note files and attachments in the vault."""
    if not notes_dir.is_dir():
        return []
    return sorted(
        p for p in notes_dir.rglob("*")
        if p.is_file() and _is_note_file(p.relative_to(notes_dir).parts)
    )


def iter_notes(notes_dir: Path):
    return [p for p in iter_files(notes_dir) if p.suffix.lower() == ".md"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def write_new(path: Path, text: str) -> None:
    """Create a file; raises FileExistsError instead of overwriting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _seed_note(title: str, tags: list[str], body: str, now, machine) -> str:
    ts = stamp(now)
    meta = {"title": title, "created": ts, "updated": ts, "tags": tags, "status": "active",
            "type": "note", "machine": machine or machine_name(), "client": "manual"}
    return frontmatter.render(meta) + "\n" + body + "\n"


def seed(notes_dir: Path, now: datetime | None = None, machine: str | None = None) -> list[Path]:
    """Create missing area folders, area notes and the home note. Never overwrites."""
    files = {notes_dir / f"{HOME}.md": _seed_note(
        "Home", ["home"],
        "Home of your second brain. Never write personal data, passwords, keys, tokens, ID or "
        "financial numbers here.\n\n"
        + "\n".join(f"- [[{hub(a)}|{t}]]: {d.split('.')[0]}." for a, (t, d) in AREAS.items()),
        now, machine)}
    for area, (title, desc) in AREAS.items():
        files[notes_dir / area / f"{area}.md"] = _seed_note(
            title, ["area", area], f"{desc}\n\nHome: [[{HOME}]]", now, machine)
    return _create_missing(files)


def _create_missing(files: dict) -> list[Path]:
    created = []
    for path, text in files.items():
        try:
            write_new(path, text)
            created.append(path)
        except FileExistsError:
            pass
    return created


# Obsidian graph colours per area (RGB as Obsidian stores it: one integer).
_GRAPH_COLORS = {"career": 0xE8A33D, "courses": 0x4C9AFF, "ideas": 0xB37FEB,
                 "research": 0x36B37E, "sessions": 0x8993A4, "imports": 0x6B778C}
_TEMPLATE = """---
title: "{{title}}"
created: {{date}}T{{time}}
updated: {{date}}T{{time}}
tags: []
status: active
type: note
machine: ""
client: manual
---

Related: [[home]]
"""


def obsidian_starter(vault_dir: Path) -> list[Path]:
    """A note template with lore's header and graph colours per area. Each file is created
    only if missing: Obsidian's own settings are never changed."""
    obsidian = vault_dir / ".obsidian"
    groups = [{"query": f"path:{area}", "color": {"a": 1, "rgb": rgb}}
              for area, rgb in _GRAPH_COLORS.items()]
    return _create_missing({
        vault_dir / "_templates" / "lore-note.md": _TEMPLATE,
        obsidian / "templates.json": json.dumps(
            {"folder": "_templates", "dateFormat": "YYYY-MM-DD", "timeFormat": "HH:mm"},
            indent=2) + "\n",
        obsidian / "graph.json": json.dumps({"showTags": True, "colorGroups": groups},
                                            indent=2) + "\n",
    })
