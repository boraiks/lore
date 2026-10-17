"""Reads and writes the note header block (YAML-like frontmatter, a small subset)."""

from __future__ import annotations

import json
import re

FIELDS = ("title", "created", "updated", "tags", "status", "type", "machine", "client")
STATUSES = ("draft", "active", "done", "raw", "summarized", "archived")
TYPES = ("note", "session", "task", "research", "import")
CLIENTS = ("claude", "codex", "antigravity", "manual", "import")


def _scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    return value


def _inline_list(value: str) -> list[str]:
    inner = value.strip()[1:-1]
    return [_scalar(v) for v in inner.split(",") if v.strip()]


def split(text: str) -> tuple[list[str] | None, str]:
    """Return (header lines or None, body)."""
    text = text.lstrip("﻿")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return None, text


def parse(text: str) -> tuple[dict, str]:
    header, body = split(text)
    if header is None:
        return {}, body
    meta: dict = {}
    key = None
    for raw in header:
        line = raw.rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and key is not None:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_scalar(stripped[2:]))
            continue
        if ":" not in line or line[0] in " \t":
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = _inline_list(value)
        else:
            meta[key] = _scalar(value) if value else []
    return meta, body


_PLAIN_UNSAFE = re.compile(r"^[\s\-?:,\[\]{}#&*!|>'\"%@`]|: | #|:$|\s$|[\r\n]")
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~"}


def _quote(value: str) -> str:
    """Leave plain values (dates, simple words) bare; quote anything YAML could misread."""
    if (not value or _PLAIN_UNSAFE.search(value) or value.lower() in _YAML_WORDS
            or re.fullmatch(r"[-+.\d]+", value)):
        return json.dumps(value, ensure_ascii=False)
    return value


def render(meta: dict) -> str:
    """Known fields first in fixed order, then any extra fields as they come."""
    keys = [k for k in FIELDS if k in meta] + [k for k in meta if k not in FIELDS]
    out = ["---"]
    for key in keys:
        value = meta[key]
        if isinstance(value, (list, tuple)):
            if value:
                out.append(f"{key}:")
                out.extend(f"  - {_quote(str(v))}" for v in value)
            else:
                out.append(f"{key}: []")
        else:
            out.append(f"{key}: {_quote(str(value))}")
    out.append("---")
    return "\n".join(out) + "\n"


def missing_fields(meta: dict) -> list[str]:
    return [k for k in FIELDS if meta.get(k) in (None, "", [])]
