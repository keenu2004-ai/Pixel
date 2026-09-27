"""
Persistent Storage Engine for Zero-Knowledge Encrypted Backups.

Stores only opaque encrypted envelopes; possesses zero plaintext access and zero key material.
"""

from __future__ import annotations

import sqlite3

from packages.contracts.ecosystem import (
    BackupHeader,
    BackupMetadataView,
    EncryptedBackupEnvelope,
)


class ZeroKnowledgeBackupStorage:
    """Stores encrypted backup blobs in SQLite without plaintext access."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if self.db_path != ":memory:":
            import os

            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backup_envelopes (
                    backup_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    header_json TEXT NOT NULL,
                    ciphertext_b64 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def store_envelope(self, envelope: EncryptedBackupEnvelope) -> None:
        """Store an encrypted backup envelope."""
        header = envelope.header
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO backup_envelopes (
                    backup_id, user_id, device_id, scope, revision,
                    header_json, ciphertext_b64, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(backup_id) DO UPDATE SET
                    revision = excluded.revision,
                    header_json = excluded.header_json,
                    ciphertext_b64 = excluded.ciphertext_b64,
                    created_at = excluded.created_at
            """,
                (
                    header.backup_id,
                    header.user_id,
                    header.device_id,
                    header.scope.value,
                    header.revision,
                    header.model_dump_json(),
                    envelope.ciphertext_b64,
                    header.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def get_envelope(self, backup_id: str) -> EncryptedBackupEnvelope | None:
        """Fetch an encrypted backup envelope by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT header_json, ciphertext_b64 FROM backup_envelopes WHERE backup_id = ?",
                (backup_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            header = BackupHeader.model_validate_json(row["header_json"])
            return EncryptedBackupEnvelope(header=header, ciphertext_b64=row["ciphertext_b64"])

    def list_envelopes(self, user_id: str | None = None) -> list[BackupMetadataView]:
        """List safe metadata for all stored backup envelopes."""
        with self._get_connection() as conn:
            if user_id:
                cursor = conn.execute(
                    "SELECT header_json, length(ciphertext_b64) as size_bytes FROM backup_envelopes WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT header_json, length(ciphertext_b64) as size_bytes FROM backup_envelopes ORDER BY created_at DESC"
                )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                header = BackupHeader.model_validate_json(row["header_json"])
                results.append(
                    BackupMetadataView(
                        backup_id=header.backup_id,
                        user_id=header.user_id,
                        device_id=header.device_id,
                        timestamp=header.timestamp,
                        revision=header.revision,
                        scope=header.scope,
                        size_bytes=row["size_bytes"],
                        ciphertext_sha256=header.ciphertext_sha256,
                    )
                )
            return results

    def delete_envelope(self, backup_id: str) -> bool:
        """Permanently delete an encrypted backup envelope."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM backup_envelopes WHERE backup_id = ?", (backup_id,))
            conn.commit()
            return cursor.rowcount > 0

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
