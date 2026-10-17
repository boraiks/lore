# Antigravity hooks

In Antigravity, lore works as it does in Claude Code and Codex: the hook writes nothing into the memory. When needed it reminds once, and it logs a content-free session record in the vault's `.lore/logs/`. The agent writes the session note with `seal`.

## What Antigravity expects
Sources: the official documentation (antigravity.google/docs/hooks) and the input Antigravity actually sends to hooks.

- **Location:** global `~/.gemini/config/hooks.json`, workspace `<project>/.agents/hooks.json`. lore uses the global file so that machine-specific paths never enter project repositories.
- **Format:** named hook sets at the top level. For `Stop`, the handler list sits directly under the event: `{"lore": {"Stop": [{"type": "command", "command": "...", "timeout": 10}]}}`. There is no trust step; changes are read after a restart.
- **Input:** `artifactDirectoryPath`, `conversationId`, `error`, `executionNum`, `fullyIdle`, `modelName`, `terminationReason`, `transcriptPath`, `workspacePaths`. No event name is sent, so the command carries it as an argument (`hook antigravity Stop`).
- **Output:** `{"decision": "continue", "reason": "..."}` keeps the agent going, and `reason` is added to the conversation as a system message. Any other value, `"block"` included, lets it stop.

## What lore does
- **Input reader** (`hook.read_input`): `conversationId` becomes the session, `transcriptPath` the transcript, `workspacePaths[0]` the project folder. `file://` URIs become paths. A missing or malformed field never crashes anything; the hook quietly exits 0. The operation log gets only the key names that arrived and the result, never values.
- **Scope:** if the project folder is not inside the lore repository, the vault or an `allowed_roots` folder (or there is none), the hook leaves no trace, not even a log line.
- **Transcript** (read only to count messages): `brain/<conversationId>/.system_generated/logs/transcript.jsonl`, one flat JSON object per step.
  - `USER_INPUT` is the user's request. Only the inside of `<USER_REQUEST>` is taken; the `<ADDITIONAL_METADATA>` block after it (open files and the like) belongs to the client and is dropped. In truncated rows, a tag that never closes runs to the end of the text.
  - `PLANNER_RESPONSE` is the agent's answer. Non-empty `content` counts as an answer, `tool_calls` are only counted, `thinking` is dropped.
  - Tool results, system and history messages and unknown row types are skipped.
- **Session log:** on each Stop, `.lore/logs/sessions.jsonl` gets the date, `antigravity`, the `conversationId` and the message count; no content.
- **Reminder:** when there is no outcome and the session is past the threshold, `"decision": "continue"` comes back once per session. Two guards stop loops:
  - A reminder is given only after an error-free, idle (`fullyIdle: true`) `terminationReason: "model_stop"`; the agent is never kept going while background tasks still run.
  - A marker file per session, `.lore/state/reminded/antigravity-<conversationId>`, keeps the continued turn's Stop from reminding again.
- **seal:** the reminder passes `--session <conversationId>`. Without `--session`, `seal` takes the `conversationId` of the newest Antigravity transcript written in the last 15 minutes, since the agent's own transcript is being written while it runs `seal`. If there is none, it falls back to a client+day+topic id.

## Known limits
- **Wrong conversation:** if two Antigravity conversations run at the same moment, `seal` without `--session` can pick the other one. That is why the reminder's command passes `--session` explicitly.
- **Undocumented transcript schema:** the row types were found by observation. If Antigravity changes them, the reader skips types it does not know; it does not crash, but the message count may come out low.

## Setup
    python lore.py wire --only antigravity          # dry run
    python lore.py wire --only antigravity --apply  # backs up first; leaves every set except "lore" alone
