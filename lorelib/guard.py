"""Detects secrets and sensitive numbers. Findings never carry the matched value."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    line: int
    kind: str
    field: str = "text"


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _luhn(s: str) -> bool:
    d = _digits(s)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _tckn(s: str) -> bool:
    d = [int(c) for c in s]
    if d[0] == 0:
        return False
    tenth = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    return d[9] == tenth and d[10] == sum(d[:10]) % 10


def _iban(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    if not 15 <= len(s) <= 34:
        return False
    moved = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def _looks_secret(value: str) -> bool:
    return len(value) >= 6 and bool(re.search(r"[0-9!@#$%^&*_+=\-]", value))


# (kind, pattern, validator, group holding the sensitive value)
_RULES = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), None, 0),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), None, 0),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"), None, 0),
    ("api-key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"), None, 0),
    ("api-key", re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"), None, 0),
    ("api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), None, 0),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), None, 0),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), None, 0),
    ("bearer-token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9\-._~+/]{20,}=*)"), None, 1),
    ("url-credentials", re.compile(r"(?i)\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:([^\s/@]+)@"), None, 1),
    ("password", re.compile(
        r"(?i)(?<![\w])(?:pass(?:word|wd)?|parola(?:m)?|şifre(?:m)?|sifre(?:m)?|secret|"
        r"token|api[_-]?key|access[_-]?key|client[_-]?secret)\s*[:=]\s*[\"']?([^\s\"']{4,})"),
     _looks_secret, 1),
    ("iban", re.compile(r"(?i)\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b"), _iban, 0),
    ("card-number", re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)"), _luhn, 0),
    ("national-id", re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"), _tckn, 0),
    ("phone", re.compile(r"(?<![\d+])(?:\+90[ -]?|0)?5\d{2}[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}(?!\d)"), None, 0),
]


def _spans(line: str):
    for kind, pattern, check, group in _RULES:
        for m in pattern.finditer(line):
            value = m.group(group)
            if check is None or check(value):
                yield kind, m.start(group), m.end(group)


def scan(text: str, field: str = "text") -> list[Finding]:
    found = []
    for no, line in enumerate(text.splitlines(), 1):
        kinds = []
        for kind, _, _ in _spans(line):
            if kind not in kinds:
                kinds.append(kind)
        found.extend(Finding(no, kind, field) for kind in kinds)
    return found


def _home_variants(home: str) -> list[str]:
    forward = home.replace("\\", "/")
    out = {home, forward, home.replace("\\", "\\\\")}
    if re.match(r"^[A-Za-z]:/", forward):  # Git Bash style: /c/Users/name
        out.add("/" + forward[0].lower() + forward[2:])
    return sorted(out, key=len, reverse=True)


def mask_home(text: str, home: str | None = None) -> str:
    """Replace the home folder path (it contains the user name) with ~."""
    for variant in _home_variants(home or str(Path.home())):
        text = re.sub(re.escape(variant), "~", text, flags=re.I)
    return text


def clip(text: str, limit: int) -> str:
    """Shorten at a whitespace boundary so no token (a key, a number) is cut in half,
    which would let a partial secret slip past the patterns."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = max(cut.rfind(" "), cut.rfind("\n"), cut.rfind("\t"))
    return (cut[:space] if space > 0 else "").rstrip() + "…"


def redact(text: str) -> tuple[str, int]:
    """Replace sensitive values with a placeholder; returns (text, number replaced)."""
    out, count = [], 0
    for line in text.split("\n"):
        merged = []  # overlapping matches collapse into one hidden span
        for kind, start, end in sorted(_spans(line), key=lambda s: (s[1], -s[2])):
            if merged and start < merged[-1][2]:
                merged[-1][2] = max(merged[-1][2], end)
            else:
                merged.append([kind, start, end])
        pieces, pos = [], 0
        for kind, start, end in merged:
            pieces.append(line[pos:start] + f"[REDACTED:{kind}]")
            pos = end
        pieces.append(line[pos:])
        out.append("".join(pieces))
        count += len(merged)
    return "\n".join(out), count
