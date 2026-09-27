"""
Unit tests for Backup Client-Side Cryptographic Engine.
"""

import pytest

from packages.contracts.ecosystem import BackupScope
from services.ecosystem.backup.crypto import BackupCryptoEngine


def test_backup_encryption_and_decryption() -> None:
    raw_data = b'{"secret_facts": ["user likes coffee", "alarm set for 7am"]}'
    passphrase = "super_secure_master_password_2026"

    envelope = BackupCryptoEngine.encrypt_payload(
        payload_bytes=raw_data,
        passphrase=passphrase,
        user_id="user_admin",
        device_id="pc_01",
        scope=BackupScope.ALL,
    )

    assert envelope.header.backup_id.startswith("bk_")
    assert envelope.header.kdf_iterations == 100_000
    assert envelope.header.scope == BackupScope.ALL

    # Decrypt with correct passphrase
    decrypted = BackupCryptoEngine.decrypt_payload(envelope, passphrase)
    assert decrypted == raw_data


def test_backup_decryption_fails_with_wrong_passphrase() -> None:
    raw_data = b'{"sensitive": "data"}'
    passphrase = "correct_password"

    envelope = BackupCryptoEngine.encrypt_payload(
        payload_bytes=raw_data,
        passphrase=passphrase,
        user_id="user_admin",
        device_id="pc_01",
    )

    with pytest.raises(ValueError, match="Failed to decrypt"):
        BackupCryptoEngine.decrypt_payload(envelope, "wrong_password")


def test_backup_fails_on_tampered_ciphertext() -> None:
    raw_data = b'{"sensitive": "data"}'
    passphrase = "correct_password"

    envelope = BackupCryptoEngine.encrypt_payload(
        payload_bytes=raw_data,
        passphrase=passphrase,
        user_id="user_admin",
        device_id="pc_01",
    )

    # Tamper with base64 ciphertext
    tampered_envelope = envelope.model_copy(
        update={"ciphertext_b64": envelope.ciphertext_b64[:-4] + "AAAA"}
    )

    with pytest.raises(ValueError, match="integrity verification failed"):
        BackupCryptoEngine.decrypt_payload(tampered_envelope, passphrase)
