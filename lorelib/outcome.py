"""The agent-written "## Outcome" block inside a session note.

The block sits between two HTML comments (invisible in Obsidian's reading view) so it can
be replaced in place without touching any other text in the note.
"""

from __future__ import annotations

from dataclasses import dataclass

BEGIN = "<!-- lore:outcome -->"
END = "<!-- /lore:outcome -->"
HEADING = "## Outcome"


@dataclass
class Found:
    block: str | None  # the whole block including markers, or None
    raw: str  # everything else in the body, stripped
    malformed: bool = False


def extract(body: str) -> Found:
    b, e = body.find(BEGIN), body.find(END)
    if b == -1 and e == -1:
        return Found(None, body.strip())
    if b == -1 or e == -1 or e < b or body.count(BEGIN) > 1 or body.count(END) > 1:
        return Found(None, body.strip(), malformed=True)
    end = e + len(END)
    return Found(body[b:end], (body[:b] + body[end:]).strip())


def render(lines: list[str], links: list[str]) -> str:
    items = ["- " + line.strip().lstrip("-*• ").strip() for line in lines if line.strip()]
    out = [BEGIN, HEADING, *items]
    if links:
        out.append("Related: " + " ".join(f"[[{link}]]" for link in links))
    out.append(END)
    return "\n".join(out)


def put(body: str, block: str) -> str:
    """Body with the block replaced, or inserted on top; the rest is kept as is."""
    found = extract(body)
    if found.malformed:
        raise ValueError("outcome block markers are broken; fix the note by hand")
    return block + ("\n\n" + found.raw if found.raw else "")
