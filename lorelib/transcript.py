"""Reads Claude Code, Codex and Antigravity JSONL transcripts into user prompts and the
last answer.

Only plain conversation text is kept: thinking, tool calls, tool output, system and
developer messages, and text the client injects (reminders, environment context) are dropped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .guard import clip

PROMPT_KEEP_CHARS = 2000  # per prompt, before the excerpt trims further
ANSWER_KEEP_CHARS = 6000

_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_INJECTED_PREFIXES = ("<command-", "<local-command-", "<environment_context", "<user_instructions",
                      "<permissions", "<turn_aborted", "<user_shell_command", "# AGENTS.md",
                      "Caveat: The messages below")
# Starts the lore Stop-hook reminder. Clients store that reminder as a user turn, so it is
# dropped here: it is not something the user asked.
REMINDER_TAG = "[lore-reminder]"
_CODEX_TOOL_ITEMS = ("function_call", "custom_tool_call", "local_shell_call", "web_search_call")
# Antigravity wraps what the user typed; the metadata block after it (open files, cursor)
# is the client's, not the user's. Long rows are cut (truncated_fields), so a block may
# open and never close: then it runs to the end of the text.
_AG_REQUEST = re.compile(r"<USER_REQUEST>(.*?)(?:</USER_REQUEST>|\Z)", re.S)
_AG_BLOCKS = re.compile(r"<(ADDITIONAL_METADATA|USER_SETTINGS_CHANGE)>.*?(?:</\1>|\Z)", re.S)


@dataclass
class Conversation:
    session_id: str = ""
    title: str = ""
    started: str = ""
    ended: str = ""
    cwd: str = ""
    prompts: list[str] = field(default_factory=list)
    answers: int = 0
    tools: int = 0
    last_answer: str = ""

    @property
    def messages(self) -> int:
        """User prompts + agent messages + tool calls: the size measure for reminders."""
        return len(self.prompts) + self.answers + self.tools


def _texts(content, kinds: tuple[str, ...]) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") in kinds and isinstance(b.get("text"), str)]


def _clean_prompt(text: str) -> str:
    text = _REMINDER.sub("", text).strip()
    if not text or text.startswith(_INJECTED_PREFIXES) or REMINDER_TAG in text[:300]:
        return ""
    return clip(text, PROMPT_KEEP_CHARS)


def _add(conv: Conversation, role: str, texts: list[str], ts: str) -> None:
    if role == "user":
        for t in texts:
            t = _clean_prompt(t)
            if t:
                conv.prompts.append(t)
                conv.started = conv.started or ts
                conv.ended = ts or conv.ended
    elif role == "assistant":
        text = "\n".join(t.strip() for t in texts if t.strip())
        if text:
            conv.answers += 1
            conv.last_answer = clip(text, ANSWER_KEEP_CHARS)
            conv.ended = ts or conv.ended


def _claude_row(conv: Conversation, row: dict) -> None:
    kind = row.get("type")
    if kind == "custom-title" and isinstance(row.get("customTitle"), str):
        conv.title = row["customTitle"]
        return
    if kind not in ("user", "assistant") or row.get("isMeta") or row.get("isSidechain"):
        return
    conv.session_id = conv.session_id or str(row.get("sessionId") or "")
    conv.cwd = conv.cwd or str(row.get("cwd") or "")
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    content = msg.get("content")
    if kind == "assistant" and isinstance(content, list):
        conv.tools += sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_use")
    _add(conv, kind, _texts(content, ("text",)), str(row.get("timestamp") or ""))


def _codex_row(conv: Conversation, row: dict) -> None:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if row.get("type") == "session_meta":
        conv.session_id = conv.session_id or str(payload.get("id") or "")
        conv.cwd = conv.cwd or str(payload.get("cwd") or "")
        return
    if row.get("type") != "response_item":
        return
    if payload.get("type") in _CODEX_TOOL_ITEMS:
        conv.tools += 1
        return
    if payload.get("type") != "message":
        return
    role = payload.get("role")
    if role in ("user", "assistant"):
        _add(conv, role, _texts(payload.get("content"), ("input_text", "output_text", "text")),
             str(row.get("timestamp") or ""))


def _ag_request(content) -> str:
    if not isinstance(content, str):
        return ""
    m = _AG_REQUEST.search(content)
    return _AG_BLOCKS.sub("", m.group(1) if m else content).strip()


def _antigravity_row(conv: Conversation, row: dict) -> None:
    """USER_INPUT is the user, PLANNER_RESPONSE the agent; every other step type (tool
    results, system and history messages, types added later) is skipped."""
    kind, ts = row.get("type"), str(row.get("created_at") or "")
    if kind == "USER_INPUT":
        _add(conv, "user", [_ag_request(row.get("content"))], ts)
    elif kind == "PLANNER_RESPONSE":
        calls = row.get("tool_calls")
        if isinstance(calls, list):
            conv.tools += len(calls)
        content = row.get("content")
        _add(conv, "assistant", [content] if isinstance(content, str) else [], ts)


def _is_antigravity(row: dict) -> bool:
    kind = row.get("type")
    return "step_index" in row and isinstance(kind, str) and kind.isupper()


def read(path: Path) -> Conversation:
    """Stream the file line by line; unreadable lines are skipped."""
    path = Path(path)
    conv = Conversation()
    antigravity = False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if "payload" in row:
                _codex_row(conv, row)
            elif _is_antigravity(row):
                antigravity = True
                _antigravity_row(conv, row)
            else:
                _claude_row(conv, row)
    # Antigravity rows carry no id; the file lives in brain/<conversationId>/.system_generated/logs/
    if antigravity and not conv.session_id and path.parent.parent.name == ".system_generated":
        conv.session_id = path.parent.parent.parent.name
    return conv
