"""The repository is public: tracked files must not carry this machine's identity.

The values are read from the machine at test time, so the test itself holds none of them.
Notes, logs and local state are outside git (.gitignore); this guards everything else.
"""

import getpass
import socket
import subprocess
import unittest
from pathlib import Path

from lorelib import vault


def _tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=vault.REPO, capture_output=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [vault.REPO / p for p in out.decode("utf-8").split("\0") if p]


def _needles():
    home = str(Path.home())
    found = {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}
    for value in (getpass.getuser(), socket.gethostname()):
        if value and len(value) >= 4:  # too short a name would match ordinary words
            found.add(value)
    return {n.lower() for n in found if n}


class PublicRepoTest(unittest.TestCase):
    def test_private_folders_are_ignored(self):
        text = (vault.REPO / ".gitignore").read_text(encoding="utf-8")
        for entry in ("/notes/", "/.lore/", ".obsidian/", ".claude/settings.local.json"):
            self.assertIn(entry, text)

    def test_tracked_files_hold_no_machine_identity(self):
        files = _tracked_files()
        if files is None:
            self.skipTest("git not available")
        needles = _needles()
        leaks = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            leaks += [path.relative_to(vault.REPO).as_posix() for n in needles if n in text]
        self.assertEqual(leaks, [], "these files hold machine-specific data")

    def test_no_tracked_notes_or_logs(self):
        files = _tracked_files()
        if files is None:
            self.skipTest("git not available")
        rel = [p.relative_to(vault.REPO).as_posix() for p in files]
        self.assertEqual([r for r in rel if r.startswith(("notes/", ".lore/"))], [])


if __name__ == "__main__":
    unittest.main()
