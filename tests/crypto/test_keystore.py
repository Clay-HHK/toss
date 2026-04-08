"""Tests for toss.crypto.keystore backends."""

from pathlib import Path

import pytest

from toss.crypto.keypair import KeyPair
from toss.crypto.keystore import (
    ENV_VAR_NAME,
    EnvKeyStore,
    FileKeyStore,
    KeyStoreError,
    auto_detect_keystore,
)


def test_file_keystore_save_load(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "default.seed")
    assert store.load() is None
    assert not store.exists()

    kp = KeyPair.generate()
    store.save(kp)
    assert store.exists()
    restored = store.load()
    assert restored is not None
    assert restored.seed == kp.seed


def test_file_keystore_file_is_0600(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "default.seed")
    store.save(KeyPair.generate())
    mode = (tmp_path / "default.seed").stat().st_mode & 0o777
    assert mode == 0o600


def test_file_keystore_delete(tmp_path: Path) -> None:
    store = FileKeyStore(tmp_path / "x.seed")
    store.save(KeyPair.generate())
    assert store.exists()
    store.delete()
    assert not store.exists()
    # delete is idempotent
    store.delete()


def test_file_keystore_rejects_malformed(tmp_path: Path) -> None:
    path = tmp_path / "bad.seed"
    path.write_text("not-base64-garbage-????")
    store = FileKeyStore(path)
    with pytest.raises(KeyStoreError, match="malformed"):
        store.load()


def test_env_keystore_reads_var(monkeypatch: pytest.MonkeyPatch) -> None:
    kp = KeyPair.generate()
    monkeypatch.setenv(ENV_VAR_NAME, kp.seed_b64())
    store = EnvKeyStore()
    loaded = store.load()
    assert loaded is not None
    assert loaded.seed == kp.seed
    assert store.exists()


def test_env_keystore_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    store = EnvKeyStore()
    assert store.load() is None
    assert not store.exists()


def test_env_keystore_save_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    store = EnvKeyStore()
    store.save(KeyPair.generate())  # should not raise
    assert not store.exists()


def test_env_keystore_rejects_bad_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR_NAME, "not!valid!base64!!")
    with pytest.raises(KeyStoreError, match="valid seed"):
        EnvKeyStore().load()


def test_auto_detect_prefers_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    kp = KeyPair.generate()
    monkeypatch.setenv(ENV_VAR_NAME, kp.seed_b64())
    store = auto_detect_keystore(tmp_path)
    assert isinstance(store, EnvKeyStore)


def test_auto_detect_falls_back_to_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    store = auto_detect_keystore(tmp_path, profile="work")
    assert isinstance(store, FileKeyStore)
    assert store.path == tmp_path / "keys" / "work.seed"
