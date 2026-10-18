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

from . import frontmatter, guard
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

# An area is a folder at the vault root holding a note of the same name (career/career.md).
# area -> (title of its area note, what goes there)
REQUIRED_AREAS = {  # lore itself needs these
    "inbox": ("Inbox", "Notes that do not belong to an area yet. When several of them share a "
                       "theme, the agent suggests a new area."),
    "sessions": ("Sessions", "Outcome records of agent sessions; written by `seal`, not by hand."),
}
SUGGESTED_AREAS = {  # offered during setup; any other name works too
    "career": ("Career", "Jobs and internships. One note per company or application: role, "
                         "date applied, status, interviews, next step. CV and interview "
                         "preparation live here too."),
    "courses": ("Courses", "Course notes. One main note per course; topic notes link to it."),
    "ideas": ("Ideas", "Project ideas. One note per idea: the problem, why it is interesting, "
                       "the first step."),
    "research": ("Research", "Day-to-day research: what was read, tried and found, with sources."),
    "personal": ("Personal", "Personal life: goals, habits, plans and reflections. No ID "
                             "numbers, addresses or passwords."),
    "work": ("Work", "Work notes: projects, meetings, decisions and follow-ups."),
}
HOME = "home"
ME = "me"
_AREA_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_ME_BODY = """What agents should know about the user, in the user's own words. Agents read this at the start of a session, so keep it short. Never put ID numbers, addresses, passwords or other identifiers here.

## What I use this memory for

## What I am working on

## How I like answers

## Language for notes

Home: [[home]]"""


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
    """Create the home note, me.md and the required areas if missing. Never overwrites."""
    files = {
        notes_dir / f"{HOME}.md": _seed_note(
            "Home", ["home"],
            "Home of your second brain. Every area note links here; `lore.py area list` shows "
            "the areas. Never write personal data, passwords, keys, tokens, ID or financial "
            "numbers in notes.", now, machine),
        notes_dir / f"{ME}.md": _seed_note("About me", ["me"], _ME_BODY, now, machine),
    }
    for area, (title, desc) in REQUIRED_AREAS.items():
        files[notes_dir / area / f"{area}.md"] = _seed_note(
            title, ["area", area], f"{desc}\n\nHome: [[{HOME}]]", now, machine)
    return _create_missing(files)


def areas(vault_dir: Path) -> list[str]:
    """Folders at the vault root that hold a note of their own name."""
    if not vault_dir.is_dir():
        return []
    return sorted(p.name for p in vault_dir.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_"))
                  and (p / f"{p.name}.md").is_file())


def add_area(vault_dir: Path, name: str, description: str | None = None,
             now: datetime | None = None, machine: str | None = None) -> Path:
    """Create <name>/<name>.md. An existing folder is adopted; its files stay as they are."""
    if not _AREA_NAME.match(name or ""):
        raise ValueError(f"invalid area name: {name!r} (lowercase letters, digits and '-', "
                         "at most 40 characters)")
    path = vault_dir / name / f"{name}.md"
    if path.exists():
        raise ValueError(f"area already exists: {name}")
    known = {**REQUIRED_AREAS, **SUGGESTED_AREAS}
    words = name.replace("-", " ")
    title, default = known.get(name, (words.title(), f"Notes about {words}."))
    desc = " ".join((description or default).split())
    if guard.scan(desc):
        raise ValueError("the description looks like it holds a secret or a personal number "
                         "(value hidden); nothing was created")
    write_new(path, _seed_note(title, ["area", name], f"{desc}\n\nHome: [[{HOME}]]", now, machine))
    return path


def set_me(vault_dir: Path, body: str, now: datetime | None = None) -> Path:
    """Replace the body of me.md, keeping its header; refused if it holds a secret."""
    findings = guard.scan(body, field="me")
    if findings:
        raise guard.SecretRejected(findings)
    path = vault_dir / f"{ME}.md"
    if path.exists():
        meta, _ = frontmatter.parse(read(path))
    else:
        meta, _ = frontmatter.parse(_seed_note("About me", ["me"], "", now, None))
    meta["updated"] = stamp(now)
    body = body.strip("\n")
    if f"[[{HOME}]]" not in body:
        body += f"\n\nHome: [[{HOME}]]"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(frontmatter.render(meta) + "\n" + body + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


# Asked once, at setup or in the first session after it, while me.md has no answers.
INTRO_QUESTIONS = (
    "What will you use this memory for? (suggested areas: jobs and internships, courses, "
    "project ideas, research, personal, work; any other area is fine)",
    "What are you working on these days?",
    "How do you like answers: short or detailed, and in which language?",
    "In which language should notes be written?",
)
_SKIPPED = "_The user skipped the intro on {date}. Do not ask again unless they bring it up._"


def _me_lines(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if line.strip()}


def me_is_blank(vault_dir: Path) -> bool:
    """True while me.md holds nothing beyond the template: the intro has not happened yet."""
    path = vault_dir / f"{ME}.md"
    if not path.exists():
        return True
    _, body = frontmatter.parse(read(path))
    return not (_me_lines(body) - _me_lines(_ME_BODY))


def skip_intro(vault_dir: Path, now: datetime | None = None) -> Path:
    """Remember that the user skipped the intro, so agents stop offering it."""
    date = (now or datetime.now()).strftime("%Y-%m-%d")
    return set_me(vault_dir, _ME_BODY.replace(f"\n\nHome: [[{HOME}]]", "")
                  + "\n\n" + _SKIPPED.format(date=date), now)


# The note Obsidian puts in every vault it creates. Recognised only while it is unchanged.
WELCOME = "Welcome.md"
_WELCOME_START = "This is your new *vault*."
_WELCOME_END = "delete this note and make the vault your own."


def obsidian_welcome(vault_dir: Path) -> Path | None:
    path = vault_dir / WELCOME
    if not path.is_file():
        return None
    text = read(path).strip()
    if (text.startswith(_WELCOME_START) and text.endswith(_WELCOME_END)
            and len(text.splitlines()) <= 7):
        return path
    return None


def remove_welcome(vault_dir: Path) -> Path:
    """Move Obsidian's untouched Welcome note to the vault's .trash (Obsidian's own bin).
    Call only after the user said yes. An edited Welcome.md is a note and is refused."""
    path = obsidian_welcome(vault_dir)
    if path is None:
        raise ValueError(f"no untouched {WELCOME} from Obsidian here; nothing was moved")
    dest = vault_dir / ".trash" / WELCOME
    n = 1
    while dest.exists():
        n += 1
        dest = vault_dir / ".trash" / f"Welcome {n}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(path, dest)
    return dest


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
                 "research": 0x36B37E, "personal": 0xE5607A, "work": 0xF2C94C,
                 "sessions": 0x8993A4, "inbox": 0xC1C7D0}
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


def _fill_json(path: Path, wanted: dict) -> str | None:
    """Create the settings file, or fill keys that are missing or empty in it.
    A key the user set to something is kept; a file that is not valid JSON is left alone."""
    if not path.exists():
        write_new(path, json.dumps(wanted, indent=2) + "\n")
        return "created"
    try:
        data = json.loads(read(path) or "{}")
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    blank = {k: v for k, v in wanted.items() if data.get(k) in (None, "", [], {})}
    if not blank:
        return None
    data.update(blank)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return "filled"


def obsidian_starter(vault_dir: Path) -> list[tuple[Path, str]]:
    """A note template with lore's header, graph colours per area, and the agent files
    excluded from the graph. A vault made in Obsidian already holds blank settings files,
    so missing or empty keys are filled in; anything the user set stays as it is.
    Returns (path, "created" | "filled")."""
    obsidian = vault_dir / ".obsidian"
    groups = [{"query": f"path:{area}", "color": {"a": 1, "rgb": rgb}}
              for area, rgb in _GRAPH_COLORS.items()]
    changes = [(p, "created") for p in _create_missing(
        {vault_dir / "_templates" / "lore-note.md": _TEMPLATE})]
    for path, wanted in (
        (obsidian / "templates.json",
         {"folder": "_templates", "dateFormat": "YYYY-MM-DD", "timeFormat": "HH:mm"}),
        (obsidian / "graph.json", {"colorGroups": groups}),
        # "Excluded files": the agent files and the template are not notes, so keep them out
        # of the graph, search and quick switcher.
        (obsidian / "app.json", {"userIgnoreFilters": [*AGENT_FILES, "_templates/"]}),
    ):
        action = _fill_json(path, wanted)
        if action:
            changes.append((path, action))
    return changes
