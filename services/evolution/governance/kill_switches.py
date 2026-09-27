"""PIXEL — Emergency Kill Switch System.

Provides tamper-resistant, persistent emergency kill switches for all autonomous evolution domains:
ALL_SWARMS, AUTONOMOUS_REMEDIATION, MODEL_PROMOTION, CODE_PROMOTION, MEMORY_REPLICATION, TRAINING_PIPELINE.
"""

import sqlite3
from datetime import UTC, datetime

from packages.contracts.evolution import KillSwitchDomain, KillSwitchStatus


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class KillSwitchSystem:
    """Manages persistent emergency shutdown state across evolution subsystems."""

    def __init__(self, db_path: str = "pixel_killswitches.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kill_switches (
                        domain TEXT PRIMARY KEY,
                        is_active INTEGER NOT NULL,
                        tripped_at TEXT,
                        tripped_by TEXT,
                        reason TEXT
                    )
                    """
                )
                # Initialize all domains as inactive (is_active=0)
                for domain in KillSwitchDomain:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO kill_switches (domain, is_active, tripped_at, tripped_by, reason)
                        VALUES (?, 0, NULL, NULL, NULL)
                        """,
                        (domain.value,),
                    )
        finally:
            conn.close()

    def trip_switch(
        self,
        domain: KillSwitchDomain,
        tripped_by: str = "admin",
        reason: str = "Emergency intervention",
    ) -> KillSwitchStatus:
        """Trips a kill switch to immediately halt operations in that domain."""
        now = _utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE kill_switches
                    SET is_active = 1, tripped_at = ?, tripped_by = ?, reason = ?
                    WHERE domain = ?
                    """,
                    (now, tripped_by, reason, domain.value),
                )
        finally:
            conn.close()

        return KillSwitchStatus(
            domain=domain,
            is_active=True,
            tripped_at=now,
            tripped_by=tripped_by,
            reason=reason,
        )

    def reset_switch(
        self,
        domain: KillSwitchDomain,
        reset_by: str = "admin",
    ) -> KillSwitchStatus:
        """Resets a kill switch back to inactive state."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE kill_switches
                    SET is_active = 0, tripped_at = NULL, tripped_by = NULL, reason = NULL
                    WHERE domain = ?
                    """,
                    (domain.value,),
                )
        finally:
            conn.close()

        return KillSwitchStatus(
            domain=domain,
            is_active=False,
        )

    def is_tripped(self, domain: KillSwitchDomain) -> bool:
        """Checks if a domain's kill switch is active (or global ALL_SWARMS is active)."""
        conn = self._get_connection()
        try:
            # Check domain-specific switch
            row = conn.execute(
                "SELECT is_active FROM kill_switches WHERE domain = ?",
                (domain.value,),
            ).fetchone()
            if row and row["is_active"] == 1:
                return True

            # Check global ALL_SWARMS switch
            if domain != KillSwitchDomain.ALL_SWARMS:
                global_row = conn.execute(
                    "SELECT is_active FROM kill_switches WHERE domain = ?",
                    (KillSwitchDomain.ALL_SWARMS.value,),
                ).fetchone()
                if global_row and global_row["is_active"] == 1:
                    return True

            return False
        finally:
            conn.close()

    def get_status(self, domain: KillSwitchDomain) -> KillSwitchStatus:
        """Retrieves status of a specific kill switch domain."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM kill_switches WHERE domain = ?",
                (domain.value,),
            ).fetchone()
            if not row:
                return KillSwitchStatus(domain=domain, is_active=False)
            return KillSwitchStatus(
                domain=KillSwitchDomain(row["domain"]),
                is_active=bool(row["is_active"]),
                tripped_at=row["tripped_at"],
                tripped_by=row["tripped_by"],
                reason=row["reason"],
            )
        finally:
            conn.close()

    def list_all_statuses(self) -> dict[str, KillSwitchStatus]:
        """Lists all kill switch statuses."""
        return {d.value: self.get_status(d) for d in KillSwitchDomain}

    def close(self) -> None:
        """Explicitly closes resources if necessary."""
        pass
