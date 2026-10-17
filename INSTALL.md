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
- `home.md`, `me.md` (about the user, filled in the next step), and the two areas lore needs: `inbox/` (notes without an area yet) and `sessions/` (session outcomes);
- `AGENTS.md` (lore's rules, with the path to the code filled in), `CLAUDE.md` and `GEMINI.md`, plus the skills in `.claude/skills/` and `.agents/skills/`. If the user already has one of these files, it is kept and lore's version is written next to it as `<file>.new`; tell the user;
- an Obsidian note template (`_templates/lore-note.md`) and starter settings (graph colours and tags, the agent files hidden from the graph).

Notes already in the folder stay as they are. lore works with any Markdown next to them.

## 4. Get to know the user (short, every question can be skipped)
Ask these one or two at a time, in the user's language, and say they can skip any of them:

1. What will you use this memory for? Offer the suggested areas from `python LORE/lore.py area list` (jobs and internships, courses, project ideas, research, personal, work) and accept any other area they name.
2. What are you working on these days?
3. How do you like answers: short or detailed, and in which language?
4. In which language should notes be written?

Then:
- Create only the areas they chose: `python LORE/lore.py area add <name>` (a suggested one), or `python LORE/lore.py area add <name> "<what goes there>"` (their own; lowercase letters, digits and `-`).
- Write their answers in their own words into `me.md` under its headings: `python LORE/lore.py me --body-file -`. Never ask for or write ID numbers, addresses, phone numbers, passwords or similar.

If the user skips all of it, create no areas; `inbox` is enough to start with, and you will suggest areas later as notes pile up.

## 5. Run the tests
    cd LORE
    python -m unittest discover -s tests -t .

If anything fails, show the user the failing test names and stop.

## 6. Session hooks (with approval)
    python LORE/lore.py wire

Show the user which files would change and what each hook does: it reminds the agent once to record a session outcome, and logs that a session happened without any content. Only after a clear "yes":

    python LORE/lore.py wire --apply

Then tell the user:
- **Codex:** approve the new hooks with `/hooks`.
- **Antigravity:** restart the app so it reads the hook file.
- **Claude Code:** new sessions pick the hooks up.

If the user says no, skip this step. lore still works: the agent records outcomes through the rules in `AGENTS.md`.

## 7. Check it together
1. Save a test note. Write the body in the user's language and set `--client` to your client (`claude`, `codex` or `antigravity`):

       python LORE/lore.py jot --area inbox --title "lore install check" --tags lore --client <client> --body "lore was set up today."

2. Read it back: `python LORE/lore.py recall "install check"`.
3. Ask the user to open a **new** session in the vault folder and ask: "Do you remember the lore install check?" The new session should find the note with `recall`, and should already know what is in `me.md`.

## 8. Obsidian
Tell the user:
- Open the vault folder itself in Obsidian ("Open folder as vault"); the areas sit at its root.
- To create notes by hand with lore's header, enable **Settings → Core plugins → Templates**; the template folder `_templates` is already set.
- The graph view colours notes by area, and shows `#client/...` tags (where a note was written) as their own nodes; turn Tags off in the graph settings for a pure topic view.
- If `lore.py home` did not report creating `.obsidian/app.json` (the folder was already an Obsidian vault), ask the user to do two things once: **Settings → Files and links → Excluded files** → add `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `_templates/`; and in **Graph view → Filters**, turn **Tags** on.

## Updating later
When the user asks to update lore, run `python LORE/lore.py update` (`LORE` is the path named at the top of the vault's `AGENTS.md`). It:

1. pulls the new code with `git pull --ff-only`, and stops if that fails. Then show the message to the user; never run `git reset --hard`, `git checkout -- .`, `git stash` or `git clean` without their clear approval;
2. refreshes the vault's rules and skills, keeping files the user edited (the new version goes next to them as `<file>.new`; tell the user);
3. reports whether the hooks need a change. If so, show `python LORE/lore.py wire` and apply with `--apply` only after a clear "yes".

Finally run the tests (step 5) and tell the user what changed: `git -C "LORE" log --oneline -10`.
