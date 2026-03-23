"""Tests for the Fernet credential store."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.credential_store import CredentialStore


@pytest.fixture()
def tmp_store(tmp_path: Path) -> CredentialStore:
    return CredentialStore(base_dir=tmp_path)


class TestCredentialStore:
    def test_save_and_load(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("alice@example.com", "s3cret!")
        username, password = tmp_store.load()
        assert username == "alice@example.com"
        assert password == "s3cret!"

    def test_exists_false_initially(self, tmp_store: CredentialStore) -> None:
        assert tmp_store.exists() is False

    def test_exists_true_after_save(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("bob", "pw")
        assert tmp_store.exists() is True

    def test_delete(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("bob", "pw")
        tmp_store.delete()
        assert tmp_store.exists() is False

    def test_load_without_save_raises(self, tmp_store: CredentialStore) -> None:
        with pytest.raises(FileNotFoundError):
            tmp_store.load()

    def test_overwrite_credentials(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("old_user", "old_pw")
        tmp_store.save("new_user", "new_pw")
        username, password = tmp_store.load()
        assert username == "new_user"
        assert password == "new_pw"

    def test_tampered_cred_file(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("user", "pw")
        cred_file = tmp_store._cred_path
        cred_file.write_bytes(b"corrupted-data")
        with pytest.raises(Exception):
            tmp_store.load()

    def test_unicode_credentials(self, tmp_store: CredentialStore) -> None:
        tmp_store.save("用户@公司.cn", "密码!@#$%^&*()")
        username, password = tmp_store.load()
        assert username == "用户@公司.cn"
        assert password == "密码!@#$%^&*()"
