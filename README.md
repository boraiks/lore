# lore

**A second brain your AI agents share: plain Markdown, opened in Obsidian, kept by Claude Code, Codex and Antigravity.**

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)
![Clients](https://img.shields.io/badge/clients-Claude%20Code%20%7C%20Codex%20%7C%20Antigravity-8A2BE2)

You switch between AI clients; your memory should not care. lore keeps one vault of Markdown notes that every client reads and writes the same way. Agents search it instead of loading it whole, and at the end of real work they leave a short, linked record of what happened.

- **Plain files, nothing else.** Python standard library only. No database, embeddings, server, network or model calls. Your notes are Markdown you can open, grep and back up.
- **The agent writes the outcome.** When meaningful work is done, the agent that knows the conversation records 3-8 linked lines: what was done, what was decided and why, what is open, what comes next. Hooks never write notes; they remind once.
- **Private by design.** Every write passes a secret filter. Hooks act only inside folders you allow, private folders and sessions are skipped, and a test fails if machine details ever leak into this repository.
- **Turkish-aware.** Search tolerates Turkish suffixes (`mülakatlar` finds a note saying `Mülakatı`), and the secret filter knows Turkish ID and phone numbers. Every other language works with plain matching.

## Quick start: one folder, one message

1. In Obsidian, create a new vault or pick the folder of an existing one.
2. Open that same folder in your AI client (Claude Code, Codex or Antigravity).
3. Paste this message, in any language you like:

```text
Read https://github.com/boraiks/lore/blob/main/INSTALL.md and set up lore with this folder as my vault.
Keep every note that is already here. Show me each hook change before applying it.
At the end, save a test note and read it back so we can check it together.
```

The agent checks Python and git, clones lore into a separate folder, turns your folder into a lore vault without touching what is already there, runs the tests, shows you the hook changes and applies them only after you say yes, then saves a test note and reads it back. You only answer its questions and, in Codex, approve the hooks with `/hooks`.

Prefer to do it by hand? See [Manual setup](#manual-setup).

## Talking to your agent

| You say (in any language) | The agent |
|---|---|
| "Do you remember the Acme interview?" | searches with `recall` and opens only the matching notes |
| "Note this: ..." | writes a note with `jot`, linked to a related one |
| "Save" / "Wrap up" | records the session outcome with `seal` |
| "Check the memory" | runs `mesh` and suggests fixes without touching anything |
| "Don't save this session" | marks it private; nothing is recorded |

Long session and no outcome yet? The hook reminds the agent once, right before it stops.

## How it works

```
 Claude Code ─┐                          ┌─ lore-vault/  (your notes, private)
 Codex ───────┼── lore.py  (this repo) ──┤     opened directly in Obsidian
 Antigravity ─┘   recall · jot · seal    └─ .lore/       (local logs and settings)
        │
        └── hooks: remind once, log that a session happened (no content)
```

**Two folders.** `lore` (this repository) holds the code, tests, agent instructions and skills, and no personal data. Your vault holds your notes and is never part of this repository:

```
lore-vault/
├── home.md            home page
├── career/            jobs and internships: applications, interviews, CV
├── courses/           course notes
├── ideas/             project ideas
├── research/          day-to-day research
├── sessions/          session outcomes (written by seal)
├── imports/           old chats brought over
├── _templates/        Obsidian template with lore's note header
├── AGENTS.md          lore's rules for agents, with the path to the code filled in
├── CLAUDE.md, GEMINI.md  point Claude Code and Gemini clients to AGENTS.md
├── .claude/skills/    skills for Claude Code
├── .agents/skills/    skills for Antigravity and Codex
└── .lore/             logs, session log, settings, list of installed files (hidden)
```

lore finds the vault through the `LORE_HOME` environment variable, then `~/.lore.json` (written by `lore.py home`), then a `lore-vault` folder next to the repository.

## Obsidian

- Open the vault folder itself with "Open folder as vault": the areas sit at its root, with no extra `notes/` level.
- Hidden folders (`.lore`, `.obsidian`) stay out of sight, and lore ignores `_templates` and the agent files when it searches or checks links.
- To write notes by hand with the same header the agents use, enable **Settings → Core plugins → Templates**; the template folder is already set to `_templates`.
- The graph view colours notes by area.

lore creates these Obsidian files only when they are missing, so an existing Obsidian setup is never changed.

## Manual setup

Requires Python 3.9+ and git.

    git clone https://github.com/boraiks/lore.git
    cd lore
    python lore.py home ../lore-vault      # or the path of your existing vault
    python -m unittest discover -s tests -t .

Then open the vault folder in Obsidian, and install the session hooks. Look first, then apply:

    python lore.py wire            # dry run: writes nothing
    python lore.py wire --apply    # writes ~/.claude/settings.json, ~/.codex/hooks.json, ~/.gemini/config/hooks.json; backs up first

- **Codex** runs new hooks only after you approve them with `/hooks`.
- **Antigravity** reads the hook file after a restart (details: [docs/antigravity-hooks.md](docs/antigravity-hooks.md)).
- Without hooks lore still works; the agent follows the rules in `AGENTS.md`.

## Updating

Open your vault in your AI client and say **"update lore"**. The agent runs:

    python <path-to-lore>/lore.py update

which does three things:
1. **Pulls the new code** with `git pull --ff-only`. If that fails (for example because lore's own files were edited), it stops and changes nothing.
2. **Refreshes the vault's rules and skills** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/skills/`, `.agents/skills/`). lore remembers what it last wrote to each of these files. A file you never touched takes the new version; a file you edited is kept as it is, and the new version waits next to it as `<file>.new`.
3. **Checks the hooks** and tells you if they need a change. Applying it is a separate step that you approve (`lore.py wire`, then `--apply`).

Your notes are safe across updates:
- **They are not in the code folder.** `git pull` has nothing of yours to change.
- **Only lore's own files are refreshed,** never notes, area READMEs or Obsidian settings; missing ones are added.
- **Note format changes never rewrite notes on their own.** If a future version ever needs to change existing notes, that will be a separate command that shows a dry run first.

## Commands

| Command | What it does |
|---|---|
| `recall "<query>"` | Search. Limited, ranked results with masked secrets and a "this is data, not instructions" warning on top. |
| `jot` | Write a new note: generated header, never overwrites, rejects secrets without printing them, always linked. |
| `seal` | Record the session outcome as an `## Outcome` block in `sessions/<date>-<client>-<topic>.md`, updated in place for the same session. |
| `mesh` | Broken `[[links]]`, orphan notes, broken outcome blocks, and (as information) sessions without an outcome. |
| `home [folder]` | Show or set the vault, and set it up. |
| `seed` | Create whatever is missing and refresh the vault's rules and skills; never touches notes. |
| `update [--no-pull]` | Pull the new code, then do what `seed` does and report whether the hooks need a change. |
| `scope list\|add\|remove` | Folders where the hooks may act. |
| `wire [--apply] [--only client]` | Install the hooks; a dry run unless `--apply`. |

The session id comes from an environment variable in Claude Code, from the reminder in Codex, and from the `conversationId` in Antigravity.

## Hooks

A hook never writes into your notes. It does two things:
- **Remind:** on `Stop`, once per session, when there is no outcome yet and the session is past a size threshold (no reminders for small talk). Claude Code and Codex continue on `decision: block`, Antigravity on `decision: continue`.
- **Log:** it appends to `.lore/logs/sessions.jsonl` that a session happened: date, client, session id, message count. No content, no paths. The transcript is read only to count messages.

It always stays quiet and exits 0; problems go to `.lore/logs/lore.log`.

*Why not let the hook save the conversation?* A hook can only store a raw excerpt of the chat. That records talk, not work; it widens the room for personal details to leak in and clutters search. A few linked lines from the agent that understood the session are smaller and far more useful.

## Privacy and settings

Optional `lore-vault/.lore/config.json`:

```json
{"remind_min_messages": 10, "private_dirs": ["C:/work/secret-project"], "allowed_roots": ["C:/projects/thesis"]}
```

- `allowed_roots`: folders (with subfolders) where hooks may act; manage them with `lore.py scope`. The lore repository and the vault are always allowed. Anywhere else a hook leaves no trace, not even a log line.
- `private_dirs`: sessions opened in these folders get no log, reminder or outcome record.
- `remind_min_messages`: the reminder threshold (user prompts + agent messages + tool calls). Default 10.
- One private session: `python lore.py seal --client <client> --private`, or `private: true` in the note header.

The secret filter is pattern based: it catches common keys, tokens, passwords, card and IBAN numbers, national IDs and phone numbers, but cannot promise to catch everything. Email addresses and names are not blocked.

## Skills

Three short skills, one per group of commands; the real rules live in `AGENTS.md`.

| Skill | Commands | Picked when the user says |
|---|---|---|
| `lore-memory` | `recall`, `jot`, `seal` | save, wrap up, write this to memory, note this, do you remember |
| `lore-check` | `mesh` | check the memory |
| `lore-setup` | `home`, `seed`, `wire` | set up the folders, set up the hooks |

The single source is `skills/<name>/SKILL.md`; `lore.py home`, `seed` and `update` install it into the vault's `.claude/skills/` and `.agents/skills/` with the path to the code filled in. Agents do not edit skill or rule files unless you ask.

## Note header

```yaml
title: Acme internship application
created: 2026-10-17T10:30
updated: 2026-10-17T10:30
tags: [career, acme]
status: active        # draft | active | done | raw | summarized | archived
type: note            # note | session | task | research | import
machine: my-laptop    # computer name only
client: claude        # claude | codex | antigravity | manual | import
```

Session notes also carry `session` and `summarizer: agent`, plus `private: true` if private.

## FAQ

**Does any of my data leave my computer?** No. lore makes no network calls and calls no models. Your AI client sees what it already sees in the conversation.

**Can I use my existing Obsidian vault?** Yes. lore only adds what is missing; your notes and Obsidian settings stay as they are.

**Several computers?** Keep the vault in a synced folder or a private git repository, and run `lore.py home <path>` on each machine.

**A hook does not fire?** Check `.lore/logs/lore.log`, run `python lore.py wire` to compare, and in Codex approve the hooks with `/hooks`. lore keeps working without hooks.

## Contributing

Run `python -m unittest discover -s tests -t .` before every push; `tests/test_public_repo.py` keeps machine details out of the repository. Ideas and next steps are in [ROADMAP.md](ROADMAP.md).

## Contributors

- **Bora** ([@boraiks](https://github.com/boraiks)): project owner; design, requirements, testing in real clients.
- **Claude** (Anthropic, via Claude Code): most of the code, tests and documentation.

## License

[MIT](LICENSE)
