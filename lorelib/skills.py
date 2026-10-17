"""Keeps the repository's own client skill folders in line with the single source in skills/.

skills/<name>/SKILL.md is the only file to edit. Claude Code reads .claude/skills and
Antigravity (and Codex) read .agents/skills. Sources say `{{LORE}}` where the path to the
lore code goes: here it becomes "." (the repository itself); in a vault, `install` fills
in the full path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import vault

SOURCE_DIR = vault.REPO / "skills"
TARGETS = (Path(".claude") / "skills", Path(".agents") / "skills")
PREFIX = "lore-"  # only these copies are ours; other skills in the folders are left alone
PLACEHOLDER = "{{LORE}}"


def render(text: str, lore: str) -> str:
    return text.replace(PLACEHOLDER, lore)


def sources(repo: Path) -> dict[str, Path]:
    return {p.parent.name: p for p in sorted((repo / "skills").glob(f"{PREFIX}*/SKILL.md"))}


@dataclass(frozen=True)
class Change:
    path: Path
    action: str  # created | updated | unchanged | stale (copy without a source; kept)


def sync(repo: Path, dry_run: bool = False, lore: str = ".") -> list[Change]:
    srcs = sources(repo)
    changes = []
    for target in TARGETS:
        folder = repo / target
        for name, src in srcs.items():
            dst = folder / name / "SKILL.md"
            data = render(src.read_bytes().decode("utf-8"), lore).encode("utf-8")
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
                if extra.parent.name not in srcs:
                    changes.append(Change(extra, "stale"))
    return changes
