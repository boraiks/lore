"""Command line: seed, recall, jot, mesh, seal, scope, wire, and the hook entry."""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime
from pathlib import Path

from . import (config, frontmatter, guard, hook, inbox, install, jot, mesh, organize, recall,
               seal, sessions, skills, vault, wire)


def _display(path: Path, notes_dir: Path) -> str:
    """Full path: the vault is a separate folder, so a vault-relative path is ambiguous."""
    return Path(path).as_posix()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lore", description="Plain-Markdown second brain.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="create missing area folders and notes (never overwrites)")

    r = sub.add_parser("recall", help="search the notes (Turkish suffix aware)")
    r.add_argument("query", nargs="+")
    r.add_argument("--limit", type=int, default=recall.DEFAULT_LIMIT,
                   help=f"max results (default {recall.DEFAULT_LIMIT}, cap {recall.MAX_LIMIT})")

    j = sub.add_parser("jot", help="write a new note (generated header, no overwrite, no secrets)")
    j.add_argument("--area", required=True, help="an existing area; see `lore.py area list`")
    j.add_argument("--title", required=True)
    j.add_argument("--tags", default="", help="comma separated")
    j.add_argument("--status", default="active", choices=frontmatter.STATUSES)
    j.add_argument("--type", default="note", choices=frontmatter.TYPES)
    j.add_argument("--client", choices=frontmatter.CLIENTS)
    j.add_argument("--link", action="append", default=[], help="related note, repeatable")
    body = j.add_mutually_exclusive_group()
    body.add_argument("--body", default="")
    body.add_argument("--body-file", help="UTF-8 file; '-' for stdin")

    sub.add_parser("mesh", help="check broken links, orphan notes and session outcomes")

    s = sub.add_parser("seal", help="record the session outcome (3-8 lines, linked)")
    s.add_argument("--client", required=True, choices=seal.CLIENTS)
    s.add_argument("--session", help="default: the client's environment variable, else --topic")
    s.add_argument("--topic", help="what the session was about; title and new note name")
    s.add_argument("--link", action="append", default=[], help="a note the session touched (1+)")
    sbody = s.add_mutually_exclusive_group()
    sbody.add_argument("--body", default="")
    sbody.add_argument("--body-file", help="UTF-8 file; '-' for stdin")
    s.add_argument("--private", action="store_true",
                   help="do not record this session: stops reminders and records, deletes nothing")

    h = sub.add_parser("hook", help="client hook entry: reads stdin JSON, quietly exits 0")
    h.add_argument("client")
    h.add_argument("event", nargs="?", default="", help="for clients that send no event name")

    w = sub.add_parser("wire", help="install the session hooks (dry run by default)")
    w.add_argument("--apply", action="store_true", help="write the changes (backs up first)")
    w.add_argument("--only", choices=list(wire.TARGETS))

    ar = sub.add_parser("area", help="list or add areas (a folder with a note of its own name)")
    ars = ar.add_subparsers(dest="area_cmd", required=True)
    ars.add_parser("list", help="areas in the vault, and suggested ones not created yet")
    ad = ars.add_parser("add", help="create an area")
    ad.add_argument("name", help="lowercase letters, digits and '-'")
    ad.add_argument("description", nargs="?", help="what goes there (default for suggested areas)")
    dc = ars.add_parser("decline", help="the user does not want this area: stop suggesting it")
    dc.add_argument("name")

    sub.add_parser("organize", help="short inventory (areas, tags, inbox) to plan a tidy-up")

    tg = sub.add_parser("tag", help="change tags across notes")
    tgs = tg.add_subparsers(dest="tag_cmd", required=True)
    tm = tgs.add_parser("merge", help="replace tags with one tag; a dry run unless --apply")
    tm.add_argument("tags", nargs="+")
    tm.add_argument("--into", required=True)
    tm.add_argument("--apply", action="store_true")

    mv = sub.add_parser("move", help="move notes into an area, keeping links; dry run unless --apply")
    mv.add_argument("notes", nargs="+", help="vault-relative or full paths")
    mv.add_argument("--to", required=True, help="an existing area")
    mv.add_argument("--apply", action="store_true")

    me = sub.add_parser("me", help="show me.md, or replace its body (secret-checked)")
    mbody = me.add_mutually_exclusive_group()
    mbody.add_argument("--body")
    mbody.add_argument("--body-file", help="UTF-8 file; '-' for stdin")
    mbody.add_argument("--skip", action="store_true",
                       help="remember that the user skipped the intro questions")

    wl = sub.add_parser("welcome", help="Obsidian's untouched Welcome.md: show, or remove on yes")
    wl.add_argument("--remove", action="store_true",
                    help="move it to the vault's .trash; only after the user said yes")

    up = sub.add_parser("update", help="pull the new code and refresh this vault's rules and skills")
    up.add_argument("--no-pull", action="store_true", help="skip git pull; only refresh the vault")

    hm = sub.add_parser("home", help="show or set the personal vault folder")
    hm.add_argument("folder", nargs="?", help="if given: saved to ~/.lore.json and set up")
    hm.add_argument("--this-folder", action="store_true",
                    help="use the folder even though another Obsidian vault is inside or above it")

    sc = sub.add_parser("scope", help="folders where the hooks act (allowed_roots)")
    scs = sc.add_subparsers(dest="scope_cmd", required=True)
    scs.add_parser("list", help="list allowed folders")
    for name, text in (("add", "add a folder to the allow list"),
                       ("remove", "remove a folder from the allow list")):
        scs.add_parser(name, help=text).add_argument("folder")
    return p


def _read_body(args) -> str:
    if args.body_file is None:
        return args.body
    if args.body_file == "-":
        return sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
    return Path(args.body_file).read_text(encoding="utf-8-sig")


def _wire(args) -> int:
    changes = wire.plan(only=args.only)
    for c in changes:
        where = guard.mask_home(str(c.path))
        if c.error:
            state = f"ERROR: {c.error}"
        elif not c.changed:
            state = "up to date"
        else:
            state = "will change" if c.exists else "new file"
        print(f"[{c.client}] {where}: {state}")
        if c.changed and not c.error:
            for line in c.lines:
                print(f"  {line}")
        for hint in c.hints:
            print(f"  SUGGESTION: {hint}")
    if not args.apply:
        print("Dry run: nothing written. To apply: python lore.py wire --apply")
    else:
        backed_up = {c.path for c in changes if c.exists}
        for path in wire.apply(changes):
            note = " (the old version is kept next to it as .lore-backup-*)" if path in backed_up else ""
            print("WRITTEN:", guard.mask_home(str(path)) + note)
    if any(c.client == "codex" and c.changed for c in changes):
        print("Codex: new or changed hooks only run once trusted; approve them with /hooks in Codex.")
    return 1 if any(c.error for c in changes) else 0


def _scope(args) -> int:
    try:
        if args.scope_cmd == "list":
            print(f"Always: {vault.REPO.as_posix()} (lore repository)")
            print(f"Always: {vault.VAULT.as_posix()} (vault)")
            roots = config.load()["allowed_roots"]
            for root in roots:
                state = "" if Path(root).is_dir() else " (folder not found)"
                print(f"Allowed: {root}{state}")
            if not roots:
                print("allowed_roots is empty: hooks act only in the lore repository and the vault.")
            return 0
        if args.scope_cmd == "add":
            changed, stored = config.add_root(args.folder)
            print(f"ADDED: {stored}" if changed else f"ALREADY LISTED: {stored}")
            return 0
        if config.remove_root(args.folder):
            print(f"REMOVED: {args.folder}. Existing notes from this folder were not touched.")
            return 0
        print(f"NOT LISTED: {args.folder}")
        return 1
    except (ValueError, OSError) as e:
        print(f"ERROR: {e}; the settings file was not touched.")
        return 5


def _area(args, notes_dir: Path) -> int:
    if args.area_cmd == "add":
        try:
            path = vault.add_area(notes_dir, args.name, args.description)
        except ValueError as e:
            print(f"ERROR: {e}")
            return 5
        print("AREA CREATED:", _display(path, notes_dir))
        return 0
    if args.area_cmd == "decline":
        try:
            inbox.decline(notes_dir, args.name)
        except ValueError as e:
            print(f"ERROR: {e}")
            return 5
        print(f"DECLINED: {args.name} will not be suggested again. Nothing was created or moved.")
        return 0
    existing = vault.areas(notes_dir)
    for name in existing:
        count = sum(1 for p in vault.iter_notes(notes_dir / name) if p.stem != name)
        print(f"{name}  ({count} notes)")
    suggested = [n for n in vault.SUGGESTED_AREAS if n not in existing]
    if suggested:
        print("Suggested, not created yet: " + ", ".join(suggested)
              + "  (python lore.py area add <name>)")
    if inbox.declined(notes_dir):
        print("Declined: " + ", ".join(inbox.declined(notes_dir)))
    return 0


_DRY = "Dry run: nothing written. Show the user; only after a clear yes, add --apply."


def _tag(args, notes_dir: Path) -> int:
    try:
        changed = organize.merge_tags(notes_dir, args.tags, args.into, apply=args.apply)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 5
    word = "UPDATED" if args.apply else "WOULD UPDATE"
    for path in changed:
        print(f"{word}: {vault.rel(path, notes_dir)}")
    print(f"{len(changed)} notes; tags {', '.join(args.tags)} -> {args.into}."
          + ("" if args.apply else " " + _DRY))
    return 0


def _move(args, notes_dir: Path) -> int:
    try:
        plan = organize.move_notes(notes_dir, args.notes, args.to, apply=args.apply)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 5
    word = "" if args.apply else "WOULD "
    for src, dest in plan.moves:
        print(f"{word}MOVE: {vault.rel(src, notes_dir)} -> {vault.rel(dest, notes_dir)}")
    for path, n in plan.link_updates:
        print(f"{word}UPDATE LINKS: {vault.rel(path, notes_dir)} ({n})")
    if not args.apply:
        print(_DRY)
    return 0


def _intro_prompt() -> str:
    lines = ["me.md has no answers yet. Ask the user these now, one or two at a time, in their "
             "language; they may skip any or all of them:"]
    lines += [f"  {i}. {q}" for i, q in enumerate(vault.INTRO_QUESTIONS, 1)]
    lines += ["Then create only the areas they chose (python lore.py area add <name> "
              "[\"<what goes there>\"]) and write their answers under the headings of me.md "
              "(python lore.py me --body-file -). If they skip it all: python lore.py me --skip"]
    return "\n".join(lines)


def _me(args, notes_dir: Path) -> int:
    if args.skip:
        print("SKIPPED: noted in me.md; the intro will not be offered again:",
              _display(vault.skip_intro(notes_dir), notes_dir))
        return 0
    if args.body is None and args.body_file is None:
        path = notes_dir / f"{vault.ME}.md"
        if path.exists():
            print(recall.DATA_WARNING)
            print(frontmatter.parse(vault.read(path))[1].strip())
        if vault.me_is_blank(notes_dir):
            print(_intro_prompt())
        return 0
    try:
        path = vault.set_me(notes_dir, args.body if args.body is not None else _read_body(args))
    except guard.SecretRejected as e:
        print(f"REJECTED: {e}. Nothing was written; remove that line.")
        return 3
    print("WRITTEN:", _display(path, notes_dir))
    return 0


def _seal(args, notes_dir: Path) -> int:
    try:
        if args.private:
            sid = seal.resolve_session(args.client, args.session, args.topic, os.environ,
                                       datetime.now())
            seal.mark_private(vault.STATE_DIR, sid)
            existing = sessions.find(notes_dir, sid)
            print("PRIVATE: no reminders or records for this session."
                  + (f" The existing note was not deleted: {_display(existing, notes_dir)}"
                     if existing else ""))
            return 0
        result = seal.seal(notes_dir, args.client, _read_body(args), args.link, args.session,
                           args.topic, cwd=os.getcwd())
    except jot.SecretRejected as e:
        print(f"REJECTED: {e}. Nothing was written; remove that line.")
        return 3
    except seal.PrivateSession:
        print("PRIVATE: this session or folder is marked private; nothing was written.")
        return 6
    except (ValueError, OSError) as e:
        print(f"ERROR: {e}")
        return 5
    word = "CREATED" if result.action == "created" else "UPDATED"
    print(f"OUTCOME {word}: {_display(result.path, notes_dir)} (session {result.session_id})")
    return 0


def _set_up(vault_dir: Path) -> None:
    """Everything `home`, `seed` and `update` lay down; notes are never touched."""
    for path in vault.seed(vault_dir):
        print("CREATED:", path.as_posix())
    for path, action in vault.obsidian_starter(vault_dir):
        print("CREATED:" if action == "created" else "FILLED:",
              path.relative_to(vault_dir).as_posix())
    words = {"created": "CREATED", "updated": "UPDATED"}
    for change in install.install(vault_dir):
        if change.action in words:
            print(f"{words[change.action]}: {change.rel}")
        elif change.action == "kept":
            print(f"KEPT (your edits): {change.rel}; the new version is in {change.rel}.new")
    for change in skills.sync(vault.REPO):  # the repository's own copies, for working on lore
        if change.action == "stale":
            print(f"WARNING: skill copy without a source, not deleted: {change.path.as_posix()}")
    print("Existing notes untouched.")
    if vault.me_is_blank(vault_dir):
        print("NEXT: ask the intro questions; `python lore.py me` lists them.")
    if vault.obsidian_welcome(vault_dir):
        print(f"ASK: Obsidian's starter note {vault.WELCOME} is still untouched. Ask the user "
              "whether to remove it; only on yes run `python lore.py welcome --remove` "
              "(it goes to the vault's .trash).")


def _welcome(args, notes_dir: Path) -> int:
    if not args.remove:
        path = vault.obsidian_welcome(notes_dir)
        print(f"{vault.WELCOME} is Obsidian's untouched starter note; remove it only after "
              "the user says yes: python lore.py welcome --remove" if path else
              f"No untouched {vault.WELCOME} from Obsidian here.")
        return 0
    try:
        dest = vault.remove_welcome(notes_dir)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 5
    print("MOVED:", vault.WELCOME, "->", _display(dest, notes_dir))
    return 0


def _home(args) -> int:
    if not args.folder:
        path, source = vault.locate()
        print(f"Vault: {path.as_posix()} ({source})")
        print("The folder exists." if path.is_dir() else
              "The folder does not exist yet. To set it up: python lore.py home <folder>")
        return 0
    others = vault.nested_vaults(Path(args.folder))
    if others and not args.this_folder:
        print("STOP: another Obsidian vault is inside or above this folder, so it may be the "
              "wrong one. Nothing was set up.")
        for other in others:
            print("  ", other.as_posix())
        print("Ask the user which folder is their vault and run `python lore.py home <it>`; "
              "to use this folder anyway, add --this-folder.")
        return 7
    path = vault.set_home(Path(args.folder))
    print(f"VAULT: {path.as_posix()} (saved to ~/.lore.json)")
    _set_up(path)
    print("Open this folder as a vault in Obsidian, and in your AI client.")
    if vault.locate()[1] == "LORE_HOME":
        print("WARNING: LORE_HOME is set and takes precedence; this setting applies once it is unset.")
    return 0


def _update(args) -> int:
    if not args.no_pull:
        ok, output = install.pull()
        if output:
            print(output)
        if not ok:
            print("ERROR: git pull did not complete, so nothing else was done. "
                  "Local changes were not touched.")
            return 5
    _set_up(vault.NOTES_DIR)
    pending = [c for c in wire.plan() if c.installed and (c.changed or c.error)]
    if pending:
        print("Hooks: changes are waiting (" + ", ".join(c.client for c in pending) + "). "
              "Review with `python lore.py wire`, then apply with `--apply`.")
    else:
        print("Hooks: nothing to do.")
    return 0


def main(argv=None, notes_dir: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "hook":
        stdin = sys.stdin
        if hasattr(stdin, "buffer"):  # clients send UTF-8 whatever the console code page is
            stdin = io.TextIOWrapper(stdin.buffer, encoding="utf-8", errors="replace")
        return hook.run(args.client, stdin, event=args.event)
    if args.cmd == "scope":
        return _scope(args)
    if args.cmd == "home":
        return _home(args)
    if args.cmd == "update":
        return _update(args)
    if args.cmd == "wire":
        return _wire(args)
    real_vault = notes_dir is None
    notes_dir = notes_dir or vault.NOTES_DIR

    if args.cmd == "seed":
        if real_vault:
            _set_up(notes_dir)
            return 0
        created = vault.seed(notes_dir)  # a test vault: areas only
        for path in created:
            print("CREATED:", _display(path, notes_dir))
        print(f"{len(created)} files created; existing files untouched.")
        return 0

    if args.cmd == "recall":
        hits = recall.recall(notes_dir, " ".join(args.query), args.limit)
        print(recall.format_hits(hits, " ".join(args.query), args.limit))
        return 0

    if args.cmd == "jot":
        try:
            path, warnings = jot.jot(
                notes_dir, args.area, args.title, _read_body(args),
                tags=args.tags.split(","), status=args.status, type=args.type,
                client=args.client, links=args.link)
        except jot.SecretRejected as e:
            print(f"REJECTED: {e}. Nothing was written; remove or mask the value.")
            return 3
        except jot.NoteExists as e:
            print(f"EXISTS: {_display(e.path, notes_dir)} was not overwritten. Pick another title "
                  "or edit the existing note with the user's approval.")
            return 4
        except (ValueError, OSError) as e:
            print(f"ERROR: {e}")
            return 5
        print("WRITTEN:", _display(path, notes_dir))
        for w in warnings:
            print("WARNING:", w)
        if args.area == inbox.INBOX:
            line = inbox.summary_line(notes_dir)
            if line:
                print(line)
        return 0

    if args.cmd == "mesh":
        report = mesh.check(notes_dir, config.load()["remind_min_messages"])
        print(mesh.format_report(report))
        return 1 if report.failed else 0

    if args.cmd == "seal":
        return _seal(args, notes_dir)

    if args.cmd == "area":
        return _area(args, notes_dir)

    if args.cmd == "me":
        return _me(args, notes_dir)

    if args.cmd == "welcome":
        return _welcome(args, notes_dir)

    if args.cmd == "organize":
        print(organize.inventory(notes_dir))
        return 0

    if args.cmd == "tag":
        return _tag(args, notes_dir)

    if args.cmd == "move":
        return _move(args, notes_dir)

    return 2
