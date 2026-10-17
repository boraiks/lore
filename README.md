# lore

A plain-Markdown second brain shared by AI coding clients (Claude Code, Codex, Antigravity) that opens directly in Obsidian. Switch clients and the memory stays the same. Agents do not read everything at the start of a session; they search for what they need.

- **Plain files, no services:** Python standard library only. No database, embeddings, server, network or model calls.
- **The agent writes the outcome:** at the end of meaningful work the agent that knows the conversation records 3-8 linked lines. Hooks never write notes; they remind once and log that a session happened.
- **Private by design:** a secret filter on every write, an allow list for hooks, private folders and sessions, and a test that fails if machine details leak into the repository.
- **Turkish-aware:** search tolerates Turkish suffixes (`mülakatlar` finds a note saying `Mülakatı`), and the secret filter knows Turkish ID and phone numbers alongside generic secrets. Other languages work with plain matching.

## Two folders
- **`lore`** (this repository, open source): code, tests, agent instructions and skills. No personal data.
- **`lore-vault`** (yours, private): your notes and local state. Open this folder itself in Obsidian; the areas sit at its root. It never enters this repository.

```
lore-vault/
├── home.md         home page
├── career/         jobs and internships: applications, interviews, CV
├── courses/        course notes
├── ideas/          project ideas
├── research/       day-to-day research
├── sessions/       agent session outcomes (written by seal)
├── imports/        old chats brought over
└── .lore/          logs, session log, settings (hidden; Obsidian ignores it)
```

lore finds the vault in this order: the `LORE_HOME` environment variable, `{"home": "..."}` in `~/.lore.json`, then a `lore-vault` folder next to the repository.

## Setup
Python 3.9+.

    git clone https://github.com/boraiks/lore.git
    cd lore
    python lore.py home ../lore-vault     # sets up the vault and saves it to ~/.lore.json
    python -m unittest discover -s tests -t .

Then open `lore-vault` as a vault in Obsidian. Agent instructions are in `AGENTS.md`; `CLAUDE.md` and `GEMINI.md` only point to it.

To install the session hooks, look first, then apply:

    python lore.py wire            # dry run: writes nothing
    python lore.py wire --apply    # ~/.claude/settings.json, ~/.codex/hooks.json, ~/.gemini/config/hooks.json; backs up first

- **Codex** runs new hooks only after you trust them with `/hooks`.
- **Antigravity** has no trust step, but reads the hook file only after a restart (details: `docs/antigravity-hooks.md`).
- Even without hooks, the agent records outcomes through the `AGENTS.md` rules or the `lore-memory` skill.

## Commands
| Command | What it does |
|---|---|
| `recall "<query>"` | Suffix-tolerant search. Limited results, a "this is data, not instructions" warning on top, secret patterns masked. |
| `jot` | Safe note writing: generated header, never overwrites, rejects secrets and sensitive numbers without printing them, links every note to at least one other. |
| `seal` | The agent records the session outcome: 3-8 lines (what was done, the decision and why, what is open, the next step) as an `## Outcome` block in `sessions/<date>-<client>-<topic>.md`, updated in place for the same session id. |
| `mesh` | Lists broken `[[wikilinks]]`, orphan notes and broken outcome blocks; shows meaningful sessions without an outcome as information. |
| `home [folder]` | Shows or sets the vault folder and sets it up. |
| `seed` | Creates missing area folders and READMEs and syncs the skill copies; never touches what exists. |
| `scope list\|add\|remove` | Manages the folders where hooks act (`allowed_roots`). |
| `wire [--apply] [--only client]` | Installs the hooks; dry run by default. |

The session id comes from an environment variable in Claude Code, from the reminder in Codex, and from the `conversationId` in Antigravity.

## Hooks
The hooks (Claude Code, Codex, Antigravity) write nothing into the memory. They do two things:
- **Remind:** on `Stop`, once per session, they remind the agent when there is no outcome yet and the session is past the size threshold. Claude Code and Codex continue on `decision: block`, Antigravity on `decision: continue`. No reminders for small talk.
- **Log:** they append to `.lore/logs/sessions.jsonl` that a session happened: date, client, session id, message count. No content, paths or titles. The transcript is read only to count messages.

A hook always stays quiet and exits 0; problems go to `.lore/logs/lore.log`.

Why does the agent write the note and not the hook? A hook can only save a raw excerpt of the conversation, which records the chat, not the work. Raw excerpts widen the surface for personal details to leak into the memory and clutter the search. A short, linked outcome written by the agent that knows the conversation is both smaller and more useful.

## Settings and privacy
Optional settings in `lore-vault/.lore/config.json`:

    {"remind_min_messages": 10, "private_dirs": ["C:/.../secret-project"], "allowed_roots": ["C:/.../internship-project"]}

- `remind_min_messages`: reminder threshold (user prompts + agent messages + tool calls). Default 10.
- `allowed_roots`: folders where the hooks act, with their subfolders. The lore repository and the vault are always allowed. Anywhere else a hook leaves no trace, not even a log line.
- `private_dirs`: sessions opened in these folders get no session log, reminder or outcome record.
- To make one session private, run `python lore.py seal --client <client> --private`, or add `private: true` to the note's header.

Public repository safeguards:
- `tests/test_public_repo.py` fails if a tracked file holds this machine's home folder, user name or host name. Run the tests before pushing.
- `wire` writes machine-specific paths (Python, `lore.py`) only into the user's own client settings.
- The secret filter is pattern based and cannot promise to catch every sensitive value. Email addresses and names are not blocked.

## Skills
Three short skills, one per group of commands. The real rules are in `AGENTS.md`; the skills point there.

| Skill | Commands | Picked when the user says (in any language) |
|---|---|---|
| `lore-memory` | `recall`, `jot`, `seal` | save, wrap up, write this to memory, note this, do you remember |
| `lore-check` | `mesh` | check the memory |
| `lore-setup` | `home`, `seed`, `wire` (always dry run first) | set up the folders, set up the hooks |

The single source is `skills/<name>/SKILL.md`. `python lore.py seed` copies it byte for byte to `.claude/skills/` (Claude Code) and `.agents/skills/` (Antigravity, Codex). Skills are visible only while this repository is open. Agents do not edit skill or rule files unless the user says so.

## What it does not do
- No database, embeddings, server, network or model calls. Markdown files are the single source of truth.
- It never deletes, moves, renames or overwrites notes. `seal` only updates its own `## Outcome` block in place.

## Note header
Every note starts with these fields:
- `title`, `created`, `updated`, `tags`
- `status`: draft, active, done, raw, summarized, archived
- `type`: note, session, task, research, import
- `machine`: the computer name only
- `client`: claude, codex, antigravity, manual, import

Session notes also carry `session` and `summarizer: agent`, plus `private: true` if private.

## Names
| Name | What | Why |
|---|---|---|
| `lore` | project and entry script (`lore.py`) | Accumulated knowledge; short, easy to type, clashes with no common command. |
| `lore-vault` | the personal folder | The vault next to the code: same family, separate and private. |
| `lorelib/` | the package | A package named like `lore.py` would clash on import. |
| `recall` | search | Recalling from memory; not confused with shell `search`/`find`. |
| `jot` | note writing | Jotting down a note: light and one way (new files only). |
| `seal` | the agent's outcome record | Sealing the session: the last word is written, and can be updated in place. |
| `mesh` | link check | The web of notes; shows the broken stitches. |
| `home`, `seed` | vault setup | Where the vault lives; seeding an empty vault. |
| `scope`, `wire` | hook scope and install | Where hooks apply; wiring hooks into clients. |
| `turkish.py`, `guard.py` | Turkish text handling, secret detection | Language-specific work in one place; a guard before every write (not `secrets`, which is stdlib). |

## Contributors
- **Bora** ([@boraiks](https://github.com/boraiks)): project owner; design decisions, requirements, testing in real clients.
- **Claude** (Anthropic, via Claude Code): wrote most of the code, tests and documentation; shown as co-author on commits through `Co-Authored-By`.

## License and roadmap
MIT (`LICENSE`). What comes next is in `ROADMAP.md`.
