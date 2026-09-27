"""
Client-Side Zero-Knowledge Encryption Engine for PIXEL Backups.

Uses standard cryptographic primitives:
- Key Derivation: PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salt.
- Authenticated Encryption: AES-256-GCM with 96-bit (12-byte) random nonce and 128-bit authentication tag.
- Integrity: SHA-256 checksum across the raw ciphertext blob.
- Storage/Envelope: Pure ciphertext and salt/nonce metadata; zero plaintext or key exposure to the server.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from packages.contracts.ecosystem import (
    BackupHeader,
    BackupScope,
    EncryptedBackupEnvelope,
)


class BackupCryptoEngine:
    """Handles client-side encryption and decryption of backup snapshots."""

    KDF_ITERATIONS = 100_000
    KEY_LENGTH_BYTES = 32  # 256-bit key for AES-256
    SALT_LENGTH_BYTES = 16
    NONCE_LENGTH_BYTES = 12

    @classmethod
    def derive_key(cls, passphrase: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
        """Derive a 256-bit cryptographic key from a user passphrase using PBKDF2-HMAC-SHA256."""
        return hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=passphrase.encode("utf-8"),
            salt=salt,
            iterations=iterations,
            dklen=cls.KEY_LENGTH_BYTES,
        )

    @classmethod
    def encrypt_payload(
        cls,
        payload_bytes: bytes,
        passphrase: str,
        user_id: str,
        device_id: str,
        scope: BackupScope = BackupScope.ALL,
        revision: int = 1,
        backup_id: str | None = None,
    ) -> EncryptedBackupEnvelope:
        """Encrypt uncompressed/compressed JSON bytes into a Zero-Knowledge backup envelope."""
        b_id = backup_id or f"bk_{uuid.uuid4().hex[:16]}"
        salt = os.urandom(cls.SALT_LENGTH_BYTES)
        nonce = os.urandom(cls.NONCE_LENGTH_BYTES)

        # 1. Derive AES-256 key
        key = cls.derive_key(passphrase, salt, cls.KDF_ITERATIONS)

        # 2. AES-256-GCM authenticated encryption
        aesgcm = AESGCM(key)
        # Additional authenticated data (AAD) binds envelope header metadata
        aad = f"{b_id}:{user_id}:{device_id}:{scope.value}:{revision}".encode()
        encrypted_data = aesgcm.encrypt(nonce, payload_bytes, aad)

        # In cryptography AESGCM, the 16-byte auth tag is appended to the ciphertext
        ciphertext = encrypted_data[:-16]
        auth_tag = encrypted_data[-16:]

        # 3. Calculate SHA-256 checksum of raw ciphertext
        ciphertext_sha256 = hashlib.sha256(ciphertext).hexdigest()

        # 4. Build unencrypted header metadata
        header = BackupHeader(
            format_version="1.0.0",
            backup_id=b_id,
            user_id=user_id,
            device_id=device_id,
            timestamp=datetime.now(UTC),
            revision=revision,
            scope=scope,
            kdf_salt=salt.hex(),
            kdf_iterations=cls.KDF_ITERATIONS,
            nonce=nonce.hex(),
            auth_tag=auth_tag.hex(),
            ciphertext_sha256=ciphertext_sha256,
        )

        ciphertext_b64 = base64.b64encode(encrypted_data).decode("utf-8")
        return EncryptedBackupEnvelope(header=header, ciphertext_b64=ciphertext_b64)

    @classmethod
    def decrypt_payload(cls, envelope: EncryptedBackupEnvelope, passphrase: str) -> bytes:
        """
        Decrypt and verify the authenticity and integrity of a backup envelope.
        Raises ValueError or cryptography.exceptions.InvalidTag on tamper or wrong key.
        """
        header = envelope.header
        salt = bytes.fromhex(header.kdf_salt)
        nonce = bytes.fromhex(header.nonce)
        encrypted_data = base64.b64decode(envelope.ciphertext_b64.encode("utf-8"))

        # Verify integrity of ciphertext before decryption
        raw_ciphertext = encrypted_data[:-16]
        raw_tag = encrypted_data[-16:]
        calculated_sha = hashlib.sha256(raw_ciphertext).hexdigest()

        if calculated_sha != header.ciphertext_sha256:
            raise ValueError(
                f"Backup ciphertext integrity verification failed! Expected {header.ciphertext_sha256}, got {calculated_sha}"
            )
        if raw_tag.hex() != header.auth_tag:
            raise ValueError("Authentication tag mismatch in backup envelope")

        # Derive key
        key = cls.derive_key(passphrase, salt, header.kdf_iterations)

        # Authenticate & Decrypt
        aesgcm = AESGCM(key)
        aad = f"{header.backup_id}:{header.user_id}:{header.device_id}:{header.scope.value}:{header.revision}".encode()

        try:
            decrypted_bytes = aesgcm.decrypt(nonce, encrypted_data, aad)
            return decrypted_bytes
        except Exception as ex:
            raise ValueError(
                f"Failed to decrypt backup envelope: wrong passphrase or corrupted payload ({ex})"
            ) from ex
