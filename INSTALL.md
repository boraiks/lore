# Installing lore (instructions for the AI agent)

The user opened their vault folder in an AI client and asked you to set up lore. Follow these steps in order. Speak to the user in their language.

## Ground rules
- The folder the client is open in is the user's **vault**. Never delete, move, rename or overwrite anything in it. lore only creates files that are missing.
- The code goes in a separate folder, by default `~/lore` (on Windows `%USERPROFILE%\lore`). Nothing personal ever goes there.
- Hook changes touch the user's client settings: always show the dry run and wait for a clear "yes" before applying them.
- Never print or store secrets.

## 1. Check the tools
Run `python --version` (or `python3`, or `py` on Windows; it must be 3.9 or newer) and `git --version`. If either is missing, tell the user what to install and stop; do not download installers yourself.

## 2. Get or update the code
Use full paths: some shells (PowerShell, for example) pass `~` to programs as it is.

- If `<home>/lore` already exists and is a git checkout of lore: `git -C "<home>/lore" pull`.
- Otherwise: `git clone https://github.com/boraiks/lore.git "<home>/lore"`.

Below, `LORE` stands for that folder's full path and `VAULT` for the full path of the folder the client is open in.

## 3. Set up the vault
    python LORE/lore.py home "VAULT"

This saves the vault's location to `~/.lore.json` and creates only what is missing:
- the area folders (`career/`, `courses/`, `ideas/`, `research/`, `sessions/`, `imports/`), their READMEs and `home.md`;
- `AGENTS.md` (lore's rules, with the path to the code filled in), `CLAUDE.md` and `GEMINI.md`, plus the skills in `.claude/skills/` and `.agents/skills/`. If the user already has one of these files, it is kept and lore's version is written next to it as `<file>.new`; tell the user;
- an Obsidian note template (`_templates/lore-note.md`) and graph colours (`.obsidian/graph.json`).

Notes already in the folder stay as they are. lore works with any Markdown next to them.

## 4. Run the tests
    cd LORE
    python -m unittest discover -s tests -t .

If anything fails, show the user the failing test names and stop.

## 5. Session hooks (with approval)
    python LORE/lore.py wire

Show the user which files would change and what each hook does: it reminds the agent once to record a session outcome, and logs that a session happened without any content. Only after a clear "yes":

    python LORE/lore.py wire --apply

Then tell the user:
- **Codex:** approve the new hooks with `/hooks`.
- **Antigravity:** restart the app so it reads the hook file.
- **Claude Code:** new sessions pick the hooks up.

If the user says no, skip this step. lore still works: the agent records outcomes through the rules in `AGENTS.md`.

## 6. Check it together
1. Save a test note. Write the body in the user's language and set `--client` to your client (`claude`, `codex` or `antigravity`):

       python LORE/lore.py jot --area research --title "lore install check" --tags lore --client <client> --body "lore was set up today."

2. Read it back: `python LORE/lore.py recall "install check"`.
3. Ask the user to open a **new** session in the vault folder and ask: "Do you remember the lore install check?" The new session should find the note with `recall`.

## 7. Obsidian
Tell the user:
- Open the vault folder itself in Obsidian ("Open folder as vault"); the areas sit at its root.
- To create notes by hand with lore's header, enable **Settings → Core plugins → Templates**; the template folder `_templates` is already set.
- The graph view colours notes by area.

## Updating later
When the user asks to update lore, run `python LORE/lore.py update` (`LORE` is the path named at the top of the vault's `AGENTS.md`). It:

1. pulls the new code with `git pull --ff-only`, and stops if that fails. Then show the message to the user; never run `git reset --hard`, `git checkout -- .`, `git stash` or `git clean` without their clear approval;
2. refreshes the vault's rules and skills, keeping files the user edited (the new version goes next to them as `<file>.new`; tell the user);
3. reports whether the hooks need a change. If so, show `python LORE/lore.py wire` and apply with `--apply` only after a clear "yes".

Finally run the tests (step 4) and tell the user what changed: `git -C "LORE" log --oneline -10`.
