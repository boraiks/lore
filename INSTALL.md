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

If it prints `STOP` (another Obsidian vault is inside or above this folder, which happens when a vault is created in Obsidian inside an existing folder), nothing was set up: show the user the folders it lists, ask which one is their vault, and run `home` with that folder (add `--this-folder` only if they choose the one you are in). If the vault turns out to be a folder inside the one you are in and nothing else is next to it, tell the user that future sessions must be opened in the inner folder, and offer to make it flat instead: once Obsidian is closed and the user said yes, move the inner folder's contents up one level and run `home` on the outer folder.

This saves the vault's location to `~/.lore.json` and creates only what is missing:
- `home.md`, `me.md` (about the user, filled in the next step), and the two areas lore needs: `inbox/` (notes without an area yet) and `sessions/` (session outcomes);
- `AGENTS.md` (lore's rules, with the path to the code filled in), `CLAUDE.md` and `GEMINI.md`, plus the skills in `.claude/skills/` and `.agents/skills/`. If the user already has one of these files, it is kept and lore's version is written next to it as `<file>.new`; tell the user;
- an Obsidian note template (`_templates/lore-note.md`) and starter settings: graph colours per area, and the agent files and template hidden from the file list, graph and search. If Obsidian already made its settings files, lore fills in only the keys that are missing or empty (`FILLED:` in the output); anything the user set stays.

Notes already in the folder stay as they are. lore works with any Markdown next to them.

If the output has an `ASK:` line about `Welcome.md` (the note Obsidian puts in a new vault, still unchanged), ask the user whether to remove it. Ask even if they told you to keep every note: it is Obsidian's sample note, not theirs, and the choice is theirs to make. Only on a clear yes run `python LORE/lore.py welcome --remove`; it moves the note to the vault's `.trash`, where Obsidian can restore it. The `NEXT:` line leads to step 4.

## 4. Get to know the user (do not skip this step)
Do this now, before the tests and the hooks, even if the user's message did not mention it. Do not leave it for the end or present it as optional: the user may skip any question, you may not skip asking.

Run `python LORE/lore.py me`; while `me.md` is blank it lists these questions. Ask them one or two at a time, in the user's language, and say they can skip any of them:

1. What will you use this memory for? Offer the suggested areas from `python LORE/lore.py area list` (jobs and internships, courses, project ideas, research, personal, work) and accept any other area they name.
2. What are you working on these days?
3. How do you like answers: short or detailed, and in which language?
4. In which language should notes be written?

Then:
- Create only the areas they chose: `python LORE/lore.py area add <name>` (a suggested one), or `python LORE/lore.py area add <name> "<what goes there>"` (their own; lowercase letters, digits and `-`).
- Write their answers in their own words into `me.md` under its headings: `python LORE/lore.py me --body-file -`. Never ask for or write ID numbers, addresses, phone numbers, passwords or similar.

If the user skips all of it, run `python LORE/lore.py me --skip` so no later session asks again, and create no areas; `inbox` is enough to start with, and you will suggest areas later as notes pile up.

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

If your client refuses to run `wire` (some safety checks block commands that touch client settings, even a dry run), ask the user to approve the command or to run it in a terminal; never edit those settings files by hand.

If the user says no, skip this step. lore still works: the agent records outcomes through the rules in `AGENTS.md`.

## 7. Check it together
1. Save a test note. Write the body in the user's language and set `--client` to your client (`claude`, `codex` or `antigravity`):

       python LORE/lore.py jot --area inbox --title "lore install check" --tags lore --client <client> --body "lore was set up today."

2. Read it back: `python LORE/lore.py recall "install check"`.
3. Ask the user to open a **new** session in the vault folder and ask: "Do you remember the lore install check?" The new session should find the note with `recall`, and should already know what is in `me.md`.

Then tell the user, as a line of its own: "From now on, open your AI client in VAULT. Sessions opened in other folders are not remembered."

## 8. Obsidian
Tell the user:
- Open the vault folder itself in Obsidian ("Open folder as vault"); the areas sit at its root.
- If `home` printed `NOTE: a graph tab is open`, ask the user to close the graph tab in Obsidian, run `python LORE/lore.py seed` again, and reopen the graph with Ctrl+G; otherwise Obsidian overwrites the colours on its next start.
- Nothing needs setting by hand: the graph colours notes by area, and lore's agent files and template are hidden from the file list, graph and search.
- To create notes by hand with lore's header, use the **Templates** core plugin (on by default in new vaults); its folder `_templates` is already set.
- Only if `lore.py home` printed neither `CREATED:` nor `FILLED:` for `.obsidian/app.json`, the user already has their own Excluded files list; suggest adding `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `_templates/` to it (**Settings → Files and links → Excluded files**).

## Updating later
When the user asks to update lore, run `python LORE/lore.py update` (`LORE` is the path named at the top of the vault's `AGENTS.md`). It:

1. pulls the new code with `git pull --ff-only`, and stops if that fails. Then show the message to the user; never run `git reset --hard`, `git checkout -- .`, `git stash` or `git clean` without their clear approval;
2. refreshes the vault's rules and skills, keeping files the user edited (the new version goes next to them as `<file>.new`; tell the user);
3. reports whether the hooks need a change. If so, show `python LORE/lore.py wire` and apply with `--apply` only after a clear "yes".

Finally run the tests (step 5) and tell the user what changed: `git -C "LORE" log --oneline -10`.
