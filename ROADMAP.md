# Roadmap

## Done
- **Two folders:** the open code repository `lore` and the personal `lore-vault`. The vault opens directly in Obsidian; the areas (`career`, `courses`, `ideas`, `research`, `sessions`, `imports`) sit at its root, and local state lives in the hidden `.lore/` folder. `home` sets up the vault; `seed` creates missing folders, READMEs and skill copies.
- **Memory commands:** `recall` (suffix-tolerant, limited, masked search), `jot` (safe note writing with a header, secret rejection and links), `mesh` (broken links, orphan notes, outcome checks).
- **Session outcome:** when meaningful work is done, the agent writes a 3-8 line linked `## Outcome` with `seal`. The note is found by session id and updated in place.
- **Hooks (Claude Code, Codex, Antigravity):** they write nothing into the memory. They remind once when there is no outcome and the session is past the threshold, and log a content-free session record in the vault's hidden `.lore/` folder. `wire` installs them, dry run by default.
- **Privacy:** an allow list (`allowed_roots`, the `scope` command), `private_dirs`, `seal --private`, a secret and personal-number filter, and the public repository test.
- **Skills:** `lore-memory`, `lore-check`, `lore-setup`, from one source in `skills/`; `seed` syncs both client folders.

## Next
- [ ] **Health check and safe repair.** One command to check everything. Repairs only do safe, reversible things, always show a dry run first, and offer anything that touches user content as a suggestion.
- [ ] **Message count in resumed sessions.** A session opened as a continuation of another carries the old conversation in its transcript, so the reminder threshold is reached too early. The hook should count only the session's own messages.
- [ ] **Importing old chat history.** Read Claude Code, Codex and Antigravity records read-only. Dry run by default, safe to re-run with stable ids, masked excerpts written to `imports/`.
- [ ] **Skill drafts proposed by the agent.** When the agent sees recurring work, it proposes a draft for `skills/`. The draft is written only after the user approves; nothing is enabled automatically.
- [ ] **Optional: summaries by a small model.** **Warning: this adds network and model use, and notes go to the model provider; a privacy risk.** It would be off by default, and `private` notes would never be sent. Not planned for now.
