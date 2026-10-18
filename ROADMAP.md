# Roadmap

## Done
- **Two folders:** the open code repository `lore` and the personal `lore-vault`. The vault opens directly in Obsidian; the areas (`career`, `courses`, `ideas`, `research`, `sessions`, `imports`) sit at its root, and local state lives in the hidden `.lore/` folder. `home` sets up the vault; `seed` creates missing folders, area notes and skill copies. Each area has a note named after it (`career/career.md`), so the graph shows areas by name.
- **Memory commands:** `recall` (suffix-tolerant, limited, masked search), `jot` (safe note writing with a header, secret rejection and links), `mesh` (broken links, orphan notes, outcome checks).
- **Session outcome:** when meaningful work is done, the agent writes a 3-8 line linked `## Outcome` with `seal`. The note is found by session id and updated in place.
- **Hooks (Claude Code, Codex, Antigravity):** they write nothing into the memory. They remind once when there is no outcome and the session is past the threshold, and log a content-free session record in the vault's hidden `.lore/` folder. `wire` installs them, dry run by default.
- **Areas you choose and an intro:** only `inbox` and `sessions` are fixed; other areas are chosen at setup (`area add`) or suggested by the agent when inbox notes pile up on one theme (`jot` shows the inbox's tags; the agent judges meaning, the code does not), never created without a yes; a declined area is not suggested again. `mesh` reports the inbox's size, age and tags. Search matches words, so agents search a topic with its close words. A short, skippable intro writes `me.md`, which agents read first.
- **Graph:** colour = area, `[[links]]` = topic, `#client/<name>` tag = where a note was written (optional: shown as nodes when the graph's Tags option is on). Settings Obsidian already made are filled in where blank, never overwritten.
- **Privacy:** an allow list (`allowed_roots`, the `scope` command), `private_dirs`, `seal --private`, a secret and personal-number filter, and the public repository test.
- **Skills:** `lore-memory`, `lore-check`, `lore-setup`, from one source in `skills/`; `seed` syncs both client folders.
- **One-message install, updates and Obsidian:** `INSTALL.md` lets an agent set lore up from a single pasted message. The vault gets lore's real rules and skills (with the path to the code filled in), tracked by hash so `lore.py update` refreshes untouched copies and keeps edited ones. Also an Obsidian note template and graph colours, each only if missing.

## Next
- [ ] **Health check and safe repair.** One command to check everything. Repairs only do safe, reversible things, always show a dry run first, and offer anything that touches user content as a suggestion.
- [ ] **Message count in resumed sessions.** A session opened as a continuation of another carries the old conversation in its transcript, so the reminder threshold is reached too early. The hook should count only the session's own messages.
- [ ] **Importing old chat history.** Read Claude Code, Codex and Antigravity records read-only. Dry run by default, safe to re-run with stable ids, masked excerpts written to `imports/`.
- [ ] **Skill drafts proposed by the agent.** When the agent sees recurring work, it proposes a draft for `skills/`. The draft is written only after the user approves; nothing is enabled automatically.
- [ ] **Optional: summaries by a small model.** **Warning: this adds network and model use, and notes go to the model provider; a privacy risk.** It would be off by default, and `private` notes would never be sent. Not planned for now.
