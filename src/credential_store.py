"""Fernet-encrypted credential storage for guangdada.net login.

Files are kept under ``~/.openclaw/`` by default (override with
``GDD_CREDENTIAL_DIR`` env-var).  The symmetric key and the encrypted
payload live in separate files so that compromising one does not
immediately reveal the other.

    ~/.openclaw/guangdada.key              – Fernet key  (mode 0600)
    ~/.openclaw/guangdada.credentials.enc  – encrypted JSON blob
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _default_credential_dir() -> Path:
    override = os.environ.get("GDD_CREDENTIAL_DIR")
    if override:
        return Path(override)
    return Path.home() / ".openclaw"


_KEY_FILENAME = "guangdada.key"
_CRED_FILENAME = "guangdada.credentials.enc"


class CredentialStore:
    """Manage encrypted guangdada login credentials."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._dir = base_dir or _default_credential_dir()
        self._key_path = self._dir / _KEY_FILENAME
        self._cred_path = self._dir / _CRED_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, username: str, password: str) -> None:
        """Encrypt and persist *username* / *password*."""
        self._dir.mkdir(parents=True, exist_ok=True)

        if not self._key_path.exists():
            key = Fernet.generate_key()
            self._key_path.write_bytes(key)
            self._chmod_600(self._key_path)
        else:
            key = self._key_path.read_bytes()

        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        cipher = Fernet(key)
        self._cred_path.write_bytes(cipher.encrypt(payload))
        self._chmod_600(self._cred_path)

    def load(self) -> tuple[str, str]:
        """Return ``(username, password)`` after decryption.

        Raises ``FileNotFoundError`` when credentials have not been saved
        yet, and ``cryptography.fernet.InvalidToken`` if the key doesn't
        match.
        """
        if not self._key_path.exists():
            raise FileNotFoundError(f"密钥文件不存在: {self._key_path}")
        if not self._cred_path.exists():
            raise FileNotFoundError(f"凭据文件不存在: {self._cred_path}")

        key = self._key_path.read_bytes()
        cipher = Fernet(key)
        try:
            raw = cipher.decrypt(self._cred_path.read_bytes())
        except InvalidToken:
            raise InvalidToken("凭据解密失败，密钥可能已更换。请重新执行 login。")
        data = json.loads(raw)
        return data["username"], data["password"]

    def delete(self) -> None:
        """Remove key and credential files."""
        for p in (self._cred_path, self._key_path):
            if p.exists():
                p.unlink()

    def exists(self) -> bool:
        return self._key_path.exists() and self._cred_path.exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chmod_600(path: Path) -> None:
        """Best-effort ``chmod 600``; silently ignored on Windows."""
        if sys.platform != "win32":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
