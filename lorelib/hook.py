"""Session hook entry for Claude Code, Codex and Antigravity. Always exits 0.

The hook writes no notes: the agent records the outcome itself with `seal`.
The hook only
  - notes that the session exists in .lore/logs/sessions.jsonl (time, client, session id,
    message count; no content), and
  - on Stop, once per session, reminds the agent when there is no outcome yet and the
    session is past the size threshold. Claude Code and Codex continue on
    {"decision": "block"}, Antigravity on {"decision": "continue"}.
Otherwise it prints nothing (Codex rejects plain text from Stop hooks). Outside the allow
list (lore repo + allowed_roots) it leaves no trace at all, not even a log line.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import config, frontmatter, logbook, outcome, sessionlog, sessions, transcript, vault
from .transcript import REMINDER_TAG

CLIENTS = ("claude", "codex", "antigravity")
MAX_INPUT = 1_000_000
LORE_PY = vault.REPO / "lore.py"
_SESSION_ID = sessions.SESSION_ID


@dataclass
class HookInput:
    """One client's stdin, in the same shape for every client. Missing fields are empty."""
    session: str = ""
    transcript: str = ""
    cwd: str = ""
    event: str = ""
    continuing: bool = False  # this turn already exists because a Stop hook asked for it
    idle: bool = True  # Antigravity: false while background tasks still run
    termination: str = ""
    error: str = ""


def _local_path(value) -> str:
    """A filesystem path from a plain path or a file:// URI; anything else is empty."""
    if not isinstance(value, str) or not value.strip():
        return ""
    value = value.strip()
    if value.lower().startswith("file:"):
        path = unquote(urlparse(value).path)
        if re.match(r"^/[A-Za-z]:", path):  # file:///C:/x -> C:/x
            path = path[1:]
        return str(Path(path))
    return value


def read_input(client: str, data: dict, event: str = "") -> HookInput:
    if client == "antigravity":
        spaces = data.get("workspacePaths")
        first = spaces[0] if isinstance(spaces, list) and spaces else ""
        return HookInput(
            session=str(data.get("conversationId") or ""),
            transcript=_local_path(data.get("transcriptPath")),
            cwd=_local_path(first),
            event=event or "Stop",  # Antigravity sends no event name; lore registers Stop only
            idle=data.get("fullyIdle") is not False,
            termination=str(data.get("terminationReason") or ""),
            error=str(data.get("error") or ""))
    return HookInput(
        session=str(data.get("session_id") or ""),
        transcript=_local_path(data.get("transcript_path")),
        cwd=data["cwd"] if isinstance(data.get("cwd"), str) else "",
        event=str(data.get("hook_event_name") or event or ""),
        continuing=data.get("stop_hook_active") is True)


def reminder_text(client: str, session_id: str) -> str:
    cmd = (f"python {LORE_PY.as_posix()} seal --client {client} --session {session_id} "
           f'--topic "<topic>" --link <area/note> --body-file -')
    return (f"{REMINDER_TAG} This session has no outcome record yet (this reminder is shown "
            "once; nothing else was written to memory). If meaningful work is done, before your "
            "final answer write 3-8 lines: what was done, what was decided and why, what is "
            "still open, the next concrete step. First use recall to find the notes the session "
            "touched and link them with --link (or the area note, e.g. career/career). Write the lines in the "
            f"user's language. Command: {cmd} . If this was small talk, if the user does not "
            "want it recorded, or if the session is private, write nothing and finish normally. "
            "Do not copy the raw chat, your reasoning, tool output, secrets or personal data.")


def reminder_output(client: str, session_id: str) -> str:
    """Claude Code and Codex continue on "block"; Antigravity continues on "continue" and
    reads "block" as permission to stop."""
    decision = "continue" if client == "antigravity" else "block"
    return json.dumps({"decision": decision, "reason": reminder_text(client, session_id)})


def _should_remind(client: str, hin: HookInput, messages: int, has_outcome: bool, state_dir,
                   cfg) -> bool:
    """Loop guard, in order: only a plain Stop; never a turn a Stop hook started
    (stop_hook_active); for Antigravity only a normal, idle, error-free model stop; and at
    most once per session (the marker file)."""
    if hin.event != "Stop" or hin.continuing:
        return False
    if client == "antigravity" and (not hin.idle or hin.termination != "model_stop" or hin.error):
        return False
    if has_outcome or messages < cfg["remind_min_messages"]:
        return False
    marker = state_dir / "reminded" / f"{client}-{hin.session}"
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        marker.touch(exist_ok=False)  # already reminded, or a concurrent Stop won
    except FileExistsError:
        return False
    return True


def run(client: str, stdin, log_path: Path | None = None, notes_dir: Path | None = None,
        state_dir: Path | None = None, cfg: dict | None = None, event: str = "",
        session_log: Path | None = None) -> int:
    keys = None  # Antigravity: log the key names that arrived, never their values

    def log(result, **kw):
        if keys is not None:
            kw = {"keys": keys, **{k: v for k, v in kw.items() if k == "error"}}
        logbook.log("hook", log_path, client=client, result=result, **kw)

    try:
        if client not in CLIENTS:
            log("unknown-client")
            return 0
        try:
            data = json.loads(stdin.read(MAX_INPUT))
        except ValueError:
            data = None
        if not isinstance(data, dict):
            log("bad-input")
            return 0
        if client == "antigravity":
            keys = sorted(data)
        hin = read_input(client, data, event)
        cfg = cfg if cfg is not None else config.load()
        if not config.in_scope(hin.cwd, cfg):
            return 0  # outside the lore repo, vault and allowed_roots: no trace, not even a log line
        if notes_dir is None and not vault.NOTES_DIR.is_dir():
            return 0  # no vault set up yet (`lore.py home`): nothing to remind about or log into
        event, session, path = hin.event, hin.session, hin.transcript
        if not _SESSION_ID.match(session):
            log("bad-session", event=event)
            return 0
        if not path or not Path(path).is_file():
            log("no-transcript", event=event, session=session[:8])
            return 0
        state_dir = state_dir or vault.STATE_DIR
        note = sessions.find(notes_dir or vault.NOTES_DIR, session)
        meta, body = frontmatter.parse(vault.read(note)) if note else ({}, "")
        if sessions.is_private(session, hin.cwd, cfg, state_dir, meta):
            return 0  # private: no session record, no reminder
        # The transcript is read only to count messages; none of its text is kept.
        messages = transcript.read(Path(path)).messages
        sessionlog.record(client, session, messages, event, path=session_log)
        log("recorded", event=event, session=session[:8])
        has_outcome = outcome.extract(body).block is not None
        if _should_remind(client, hin, messages, has_outcome, state_dir, cfg):
            print(reminder_output(client, session))
            log("reminded", event=event, session=session[:8])
    except Exception as e:  # noqa: BLE001 - the hook must never fail the client
        log("error", error=f"{type(e).__name__}: {e}")
    return 0
