import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from lorelib import config, logbook, seal, sessionlog, vault

NOW = datetime(2026, 10, 17, 10, 30)


class VaultCase(unittest.TestCase):
    """Gives each test an empty notes directory in a temp folder. The default log, state
    and config locations, the vault pointer and the Antigravity data folders also point into
    it, so no test touches the real vault, ~/.lore.json or ~/.gemini/."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.notes = root / "notes"
        self._saved = (logbook.LOG_PATH, vault.STATE_DIR, config.CONFIG_PATH, seal.AG_ROOTS,
                       sessionlog.LOG_PATH, vault.VAULT, vault.NOTES_DIR, vault.POINTER)
        logbook.LOG_PATH = root / "default.log"
        vault.STATE_DIR = root / "default-state"
        config.CONFIG_PATH = root / "default-config.json"
        seal.AG_ROOTS = (root / "default-gemini",)
        sessionlog.LOG_PATH = root / "default-sessions.jsonl"
        vault.VAULT = vault.NOTES_DIR = root / "default-vault"
        vault.POINTER = root / "default-pointer.json"

    def tearDown(self):
        (logbook.LOG_PATH, vault.STATE_DIR, config.CONFIG_PATH, seal.AG_ROOTS,
         sessionlog.LOG_PATH, vault.VAULT, vault.NOTES_DIR, vault.POINTER) = self._saved
        self._tmp.cleanup()

    def put(self, rel, text):
        path = self.notes / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
