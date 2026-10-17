"""Optional local settings in the vault's .lore/config.json (machine-specific, never in git)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import vault

CONFIG_PATH = vault.VAULT / ".lore" / "config.json"
DEFAULTS = {
    # user prompts + agent messages + tool calls; below this a session counts as small talk
    "remind_min_messages": 10,
    # sessions whose working folder is inside one of these are never recorded
    "private_dirs": [],
    # hooks act only inside the lore repository, the vault and these folders
    "allowed_roots": [],
}


def _str_list(value) -> list[str]:
    return [d for d in value if isinstance(d, str) and d.strip()] if isinstance(value, list) else []


def load(path: Path | None = None) -> dict:
    """Defaults overlaid with valid values from the file; a broken file means defaults."""
    cfg = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    try:
        data = json.loads((path or CONFIG_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    n = data.get("remind_min_messages")
    if isinstance(n, int) and not isinstance(n, bool) and n >= 1:
        cfg["remind_min_messages"] = n
    for key in ("private_dirs", "allowed_roots"):
        if isinstance(data.get(key), list):
            cfg[key] = _str_list(data[key])
    return cfg


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(p))).rstrip("\\/")


def _inside(cwd: str, dirs) -> bool:
    if not cwd:
        return False
    here = _norm(cwd)
    for d in dirs:
        base = _norm(d)
        if here == base or here.startswith(base + os.sep):
            return True
    return False


def in_private_dir(cwd: str, cfg: dict) -> bool:
    return _inside(cwd, cfg.get("private_dirs", []))


def in_scope(cwd: str, cfg: dict) -> bool:
    """Allow list for hooks: the lore repository, the vault and allowed_roots. An unknown
    working folder is out of scope."""
    return _inside(cwd, [str(vault.REPO), str(vault.VAULT), *cfg.get("allowed_roots", [])])


# --- editing allowed_roots (the scope command) ---

def _read_file(path: Path) -> dict:
    """The stored settings as they are; refuses to go on with a broken file."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))  # ValueError if broken
    if not isinstance(data, dict):
        raise ValueError("the root is not a JSON object")
    return data


def _write_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")
    os.replace(tmp, path)


def add_root(folder: str, path: Path | None = None) -> tuple[bool, str]:
    """(changed, stored form). Other settings in the file are kept as they are."""
    path = path or CONFIG_PATH
    target = Path(folder).expanduser().resolve()
    if not target.is_dir():
        raise ValueError(f"no such folder: {folder}")
    stored = target.as_posix()
    data = _read_file(path)
    roots = _str_list(data.get("allowed_roots", []))
    if any(_norm(r) == _norm(stored) for r in roots):
        return False, stored
    data["allowed_roots"] = roots + [stored]
    _write_file(path, data)
    return True, stored


def remove_root(folder: str, path: Path | None = None) -> bool:
    path = path or CONFIG_PATH
    data = _read_file(path)
    roots = _str_list(data.get("allowed_roots", []))
    kept = [r for r in roots if _norm(r) != _norm(folder)]
    if len(kept) == len(roots):
        return False
    data["allowed_roots"] = kept
    _write_file(path, data)
    return True
