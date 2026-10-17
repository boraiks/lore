---
name: lore-setup
description: Set up lore - the vault folder, area READMEs, skill copies and session hooks. Use when the user asks to set up the folders or the hooks, in any language.
---
<!-- Source: skills/lore-setup/SKILL.md. `python lore.py seed` writes the copies in .claude/skills and .agents/skills; do not edit the copies. -->
# lore-setup

Rules and details are in AGENTS.md and the README.

- **Folders**: for the personal vault, `python lore.py home <folder>` (without a folder it shows the current one), then `python lore.py seed`. This creates missing area folders and READMEs and syncs the skill copies; it never touches existing notes.
- **Hooks**: always dry run first: `python lore.py wire`. Show the user which files would change. Run `python lore.py wire --apply` only if the user clearly approves. In Codex, new hooks must also be trusted with `/hooks`.
