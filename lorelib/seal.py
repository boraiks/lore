"""The agent records a session's outcome: a short, linked "## Outcome" block in its session note.

The agent already knows the conversation, so no model is called. seal creates the session
note or replaces the block in place; any other text already in the note stays as it is.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config, frontmatter, guard, logbook, mesh, outcome, sessions, vault
from .jot import SecretRejected, clean_link

CLIENTS = ("claude", "codex", "antigravity", "manual")
# Where a client exposes the current session id to the agent's shell commands.
# CLAUDE_CODE_SESSION_ID is observed in Claude Code; the Codex names are not documented.
ENV_KEYS = {"claude": ("CLAUDE_CODE_SESSION_ID",), "codex": ("CODEX_THREAD_ID", "CODEX_SESSION_ID")}
MIN_LINES, MAX_LINES, LINE_CHARS = 3, 8, 300
# Antigravity app data folders (App, IDE, CLI); each keeps brain/<conversationId>/...
AG_ROOTS = tuple(Path.home() / ".gemini" / d for d in ("antigravity", "antigravity-ide",
                                                        "antigravity-cli"))
AG_RECENT_SECONDS = 15 * 60


class PrivateSession(Exception):
    pass


@dataclass
class Result:
    action: str  # created | updated
    path: Path
    session_id: str


def running_antigravity_conversation(roots=None, max_age: float = AG_RECENT_SECONDS) -> str:
    """The conversation whose transcript was written most recently, if that was within
    max_age: while the agent runs `seal`, its own transcript is the one being written.
    Two Antigravity conversations working at the same moment can make this pick the other
    one, so the hook's reminder passes --session explicitly."""
    newest, newest_mtime = "", 0.0
    for root in roots or AG_ROOTS:
        for path in Path(root).glob("brain/*/.system_generated/logs/transcript.jsonl"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest, newest_mtime = path.parent.parent.parent.name, mtime
    if newest and time.time() - newest_mtime <= max_age and sessions.SESSION_ID.match(newest):
        return newest
    return ""


def resolve_session(client: str, session_id: str | None, topic: str | None, env, now: datetime,
                    ag_roots=None) -> str:
    if session_id:
        return session_id
    for key in ENV_KEYS.get(client, ()):
        if env.get(key):
            return env[key]
    if client == "antigravity":
        running = running_antigravity_conversation(ag_roots)
        if running:
            return running
    if not topic:
        raise ValueError("no session id found: pass --session or --topic")
    # Clients without a session id: one record per client, day and topic.
    return f"{client}-{now:%Y%m%d}-{vault.slugify(topic, 40)}"


def mark_private(state_dir: Path, session_id: str) -> Path:
    return sessions.mark_private(state_dir, session_id)


def _lines(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not MIN_LINES <= len(lines) <= MAX_LINES:
        raise ValueError(f"the outcome must be {MIN_LINES}-{MAX_LINES} lines ({len(lines)} given)")
    long = [i for i, line in enumerate(lines, 1) if len(line) > LINE_CHARS]
    if long:
        raise ValueError(f"line longer than {LINE_CHARS} characters: {', '.join(map(str, long))}")
    return lines


def seal(notes_dir: Path, client: str, body: str, links, session_id: str | None = None,
         topic: str | None = None, cwd: str = "", now: datetime | None = None,
         machine: str | None = None, state_dir: Path | None = None, cfg: dict | None = None,
         env=None, log_path: Path | None = None, ag_roots=None) -> Result:
    """Write or replace the outcome block. Nothing touches disk if a check fails."""
    now = now or datetime.now()
    cfg = cfg if cfg is not None else config.load()
    state_dir = state_dir or vault.STATE_DIR
    env = os.environ if env is None else env
    if client not in CLIENTS:
        raise ValueError(f"invalid client: {client}")
    topic = " ".join((topic or "").split())
    lines = _lines(body)
    links = [l for l in (clean_link(x) for x in links) if l]
    if not links:
        raise ValueError("at least one --link is required (the area note, e.g. career/career, if nothing else fits)")

    findings = []
    for name, text in (("body", body), ("topic", topic), ("links", " ".join(links))):
        findings += guard.scan(text, field=name)
    if findings:
        raise SecretRejected(findings)

    session_id = resolve_session(client, session_id, topic, env, now, ag_roots)
    if not sessions.SESSION_ID.match(session_id):
        raise ValueError("invalid session id")
    if sessions.is_private(session_id, cwd, cfg, state_dir):
        raise PrivateSession(session_id)

    index = mesh.LinkIndex(notes_dir)
    missing = [l for l in links if index.resolve(l) is None]
    if missing:
        raise ValueError("link target not found: " + ", ".join(f"[[{l}]]" for l in missing)
                         + " (find an existing note with recall first)")
    block = outcome.render([guard.mask_home(line) for line in lines], links)

    path = sessions.find(notes_dir, session_id)
    if path is not None:
        meta, old = frontmatter.parse(vault.read(path))
        if sessions.truthy(meta.get("private", "")):
            raise PrivateSession(session_id)
        new_body = outcome.put(old, block)
        meta.update({"updated": vault.stamp(now), "status": "summarized", "summarizer": "agent"})
        if topic:
            meta["title"] = f"Session: {topic}"
        sessions.rewrite(path, meta, new_body)
        action = "updated"
    else:
        vault.seed(notes_dir, now=now, machine=machine)
        name = topic or lines[0]
        project = sessions.project_tag(cwd)
        ts = vault.stamp(now)
        meta = {"title": f"Session: {guard.clip(name, 60)}", "created": ts, "updated": ts,
                "tags": ["session", f"client/{client}"] + ([project] if project else []),
                "status": "summarized", "type": "session",
                "machine": machine or vault.machine_name(), "client": client,
                "session": session_id, "summarizer": "agent"}
        path = sessions.new_path(notes_dir, now, client, name)
        vault.write_new(path, frontmatter.render(meta) + "\n" + block + "\n")
        action = "created"
    logbook.log("seal", log_path, client=client, session=session_id[:8], result=action,
                links=len(links))
    return Result(action, path, session_id)
