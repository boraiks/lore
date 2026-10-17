---
name: lore-setup
description: Set up or update lore - the vault folder, rules, skills and session hooks. Use when the user asks to set up the folders or the hooks, or to update lore, in any language.
---
<!-- Source: skills/lore-setup/SKILL.md in the lore code. `lore.py update` refreshes this copy; edits here block its updates. -->
# lore-setup

Rules and details are in AGENTS.md and the README.

- **Folders**: for the personal vault, `python ./lore.py home <folder>` (without a folder it shows the current one). It creates missing area folders, READMEs, rules and skills; it never touches existing notes.
- **Update**: `python ./lore.py update`. It pulls the new code and refreshes this vault's rules and skills, keeping files the user edited. If `git pull` fails, show the message and stop; never discard local changes. If it reports hook changes, handle them as below.
- **Hooks**: always dry run first: `python ./lore.py wire`. Show the user which files would change. Run `python ./lore.py wire --apply` only if the user clearly approves. In Codex, new hooks must also be trusted with `/hooks`.
