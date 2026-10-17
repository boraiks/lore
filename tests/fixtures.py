"""Builders for small fake Claude Code and Codex transcripts."""

import json


def claude_transcript(path, prompts, answers, title=None, extra=(), tools=0):
    """tools: number of tool_use rows added after each prompt."""
    rows = []
    for i, (p, a) in enumerate(zip(prompts, answers)):
        ts = f"2026-10-17T08:{i:02d}:00.000Z"
        rows.append({"type": "user", "sessionId": "abc", "timestamp": ts, "cwd": "/x",
                     "message": {"role": "user", "content": p}})
        for _ in range(tools):
            rows.append({"type": "assistant", "sessionId": "abc", "timestamp": ts,
                         "message": {"role": "assistant", "content": [
                             {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}})
        rows.append({"type": "assistant", "sessionId": "abc", "timestamp": ts,
                     "message": {"role": "assistant",
                                 "content": [{"type": "thinking", "thinking": "gizli düşünce"},
                                             {"type": "text", "text": a}]}})
    if title:
        rows.append({"type": "custom-title", "customTitle": title, "sessionId": "abc"})
    rows.extend(extra)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    return path


def codex_transcript(path, prompts, answers):
    rows = [{"type": "session_meta", "timestamp": "2026-10-17T08:00:00Z",
             "payload": {"id": "019a-codex", "cwd": "/x"}},
            {"type": "response_item", "timestamp": "2026-10-17T08:00:00Z",
             "payload": {"type": "message", "role": "developer",
                         "content": [{"type": "input_text", "text": "sistem talimatı"}]}},
            {"type": "response_item", "timestamp": "2026-10-17T08:00:00Z",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text",
                                      "text": "<environment_context>\n  <cwd>/x</cwd>\n</environment_context>"}]}}]
    for i, (p, a) in enumerate(zip(prompts, answers)):
        ts = f"2026-10-17T08:{i + 1:02d}:00Z"
        rows.append({"type": "response_item", "timestamp": ts,
                     "payload": {"type": "message", "role": "user",
                                 "content": [{"type": "input_text", "text": p}]}})
        rows.append({"type": "response_item", "timestamp": ts,
                     "payload": {"type": "function_call", "name": "shell", "arguments": "{}"}})
        rows.append({"type": "response_item", "timestamp": ts,
                     "payload": {"type": "message", "role": "assistant",
                                 "content": [{"type": "output_text", "text": a}]}})
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    return path


def antigravity_transcript(path, prompts, answers, tools=1, extra=()):
    """Rows shaped like Antigravity's transcript.jsonl: one flat object per step."""
    rows, step = [], 0

    def row(kind, source, **kw):
        nonlocal step
        step += 1
        rows.append(dict({"type": kind, "source": source, "status": "DONE", "step_index": step,
                          "created_at": f"2026-10-17T08:{step % 60:02d}:00Z"}, **kw))

    row("CONVERSATION_HISTORY", "SYSTEM", content="önceki konuşmalar")
    for p, a in zip(prompts, answers):
        row("USER_INPUT", "USER_EXPLICIT",
            content=f"<USER_REQUEST>\n{p}\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\n"
                    "Açık dosya: C:/gizli/yol.txt\n</ADDITIONAL_METADATA>")
        for _ in range(tools):
            row("PLANNER_RESPONSE", "MODEL", content="", thinking="gizli düşünce",
                tool_calls=[{"name": "view_file", "args": {"path": "x"}}])
            row("VIEW_FILE", "MODEL", content="dosya içeriği")
        row("PLANNER_RESPONSE", "MODEL", content=a, thinking="gizli düşünce", tool_calls=[])
    for e in extra:
        rows.append(e)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)
                              for e in rows) + "\n", encoding="utf-8")
    return path
