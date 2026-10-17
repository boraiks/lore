# AGENTS.md: lore source code

This repository is the source of lore, a plain-Markdown second brain for AI clients. Personal notes never live here; they are in each user's vault folder.

## Memory rules
The rules agents follow inside a vault (search before reading, write notes with `jot`, record outcomes with `seal`, never write secrets, never delete or move notes) are in `vault/AGENTS.md`. `lore.py home` and `lore.py update` install that file into the vault with the path to this code filled in. Follow the same rules when you use the memory from here, running commands as `python lore.py <command>`.

## Working on lore
- Python standard library only; no network calls, no model calls, no new dependencies.
- Write or update tests first, then the code. Run `python -m unittest discover -s tests -t .` before every commit. `tests/test_public_repo.py` must pass: no machine paths, user names or personal data in tracked files.
- Never edit generated copies. Skills come from `skills/<name>/SKILL.md`; the vault rules from `vault/AGENTS.md`. `{{LORE}}` in those sources stands for the path to this code. `python lore.py seed` refreshes this repository's own copies in `.claude/skills/` and `.agents/skills/`.
- Do not edit skill or rule files unless the user says so; show a suggestion instead. These are `skills/`, `vault/`, `.claude/skills/`, `.agents/skills/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and the clients' hook settings.
- Updates must never rewrite or delete user notes. Anything that has to change existing notes is a separate command that shows a dry run first.
- Never run commands that discard work (`git checkout -- .`, `git reset --hard`, `git clean`, `git stash`) without the user's clear approval.
- Commit messages: a short summary line and a 1-4 line description of why.
