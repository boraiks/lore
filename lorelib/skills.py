"""Keeps the client skill folders identical to the single source in skills/.

skills/<name>/SKILL.md is the only file to edit. Claude Code reads .claude/skills and
Antigravity (and Codex) read .agents/skills; both get byte-identical copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import vault

SOURCE_DIR = vault.REPO / "skills"
TARGETS = (Path(".claude") / "skills", Path(".agents") / "skills")
PREFIX = "lore-"  # only these copies are ours; other skills in the folders are left alone


@dataclass(frozen=True)
class Change:
    path: Path
    action: str  # created | updated | unchanged | stale (copy without a source; kept)


def sync(repo: Path, dry_run: bool = False) -> list[Change]:
    sources = {p.parent.name: p for p in sorted((repo / "skills").glob(f"{PREFIX}*/SKILL.md"))}
    changes = []
    for target in TARGETS:
        folder = repo / target
        for name, src in sources.items():
            dst = folder / name / "SKILL.md"
            data = src.read_bytes()
            if not dst.exists():
                action = "created"
            elif dst.read_bytes() != data:
                action = "updated"
            else:
                action = "unchanged"
            if action != "unchanged" and not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
            changes.append(Change(dst, action))
        if folder.is_dir():
            for extra in sorted(folder.glob(f"{PREFIX}*/SKILL.md")):
                if extra.parent.name not in sources:
                    changes.append(Change(extra, "stale"))
    return changes
