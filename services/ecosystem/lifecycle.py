"""
Persistent Plugin Lifecycle Manager and Emergency Revocation Engine.

Governs state transitions, persistent SQLite registration, emergency revocation ledger,
permission diffing, privilege escalation prevention, atomic updates, and safe rollback.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

from packages.contracts.ecosystem import (
    PluginCapability,
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginLifecycleState,
    PluginManifest,
)
from services.ecosystem.sandbox.base import BaseSandboxDriver
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver

logger = logging.getLogger(__name__)


class PluginLifecycleManager:
    """Authoritative manager for plugin lifecycle, permissions, and revocation."""

    def __init__(
        self,
        db_path: str = ":memory:",
        sandbox_driver: BaseSandboxDriver | None = None,
        base_plugins_dir: str | None = None,
    ):
        self.db_path = db_path
        self.sandbox = sandbox_driver or SubprocessSandboxDriver()
        self.base_plugins_dir = base_plugins_dir or os.path.join(os.getcwd(), "data", "plugins")
        os.makedirs(self.base_plugins_dir, exist_ok=True)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plugins (
                    plugin_id TEXT PRIMARYKEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    code_dir TEXT NOT NULL,
                    granted_capabilities_json TEXT NOT NULL,
                    previous_manifest_json TEXT,
                    previous_code_dir TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plugin_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revocation_ledger (
                    plugin_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    revoked_by TEXT NOT NULL,
                    revoked_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def is_revoked(self, plugin_id: str) -> bool:
        """Check if plugin exists in emergency revocation ledger."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM revocation_ledger WHERE plugin_id = ?", (plugin_id,)
            )
            return cursor.fetchone() is not None

    def register_discovered_plugin(
        self, manifest: PluginManifest, code_dir: str
    ) -> PluginLifecycleState:
        """Register a newly discovered plugin manifest in DISCOVERED state."""
        if self.is_revoked(manifest.plugin_id):
            raise ValueError(f"Plugin '{manifest.plugin_id}' is permanently revoked.")

        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO plugins (
                    plugin_id, name, version, publisher, manifest_json,
                    state, code_dir, granted_capabilities_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    publisher = excluded.publisher,
                    manifest_json = excluded.manifest_json,
                    code_dir = excluded.code_dir,
                    updated_at = excluded.updated_at
            """,
                (
                    manifest.plugin_id,
                    manifest.name,
                    manifest.version,
                    manifest.publisher,
                    manifest.model_dump_json(),
                    PluginLifecycleState.DISCOVERED.value,
                    code_dir,
                    json.dumps([]),
                    now,
                    now,
                ),
            )
            conn.commit()
        return PluginLifecycleState.DISCOVERED

    def approve_and_install(
        self,
        plugin_id: str,
        granted_capabilities: list[PluginCapability],
        actor: str = "admin",
        auto_enable: bool = True,
    ) -> PluginLifecycleState:
        """Approve permissions and transition plugin to INSTALLED (or ENABLED)."""
        if self.is_revoked(plugin_id):
            raise ValueError(f"Cannot install revoked plugin '{plugin_id}'")

        plugin = self.get_plugin(plugin_id)
        if not plugin:
            raise KeyError(f"Plugin '{plugin_id}' not found")

        manifest = plugin["manifest"]
        # Validate that granted capabilities are declared in manifest
        declared_set = set(manifest.capabilities)
        for cap in granted_capabilities:
            if cap not in declared_set:
                raise ValueError(
                    f"Cannot grant undeclared capability '{cap.value}' to plugin '{plugin_id}'"
                )

        target_state = (
            PluginLifecycleState.ENABLED if auto_enable else PluginLifecycleState.INSTALLED
        )
        now = datetime.now(UTC).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE plugins
                SET state = ?, granted_capabilities_json = ?, updated_at = ?
                WHERE plugin_id = ?
            """,
                (
                    target_state.value,
                    json.dumps([c.value for c in granted_capabilities]),
                    now,
                    plugin_id,
                ),
            )
            conn.commit()

        return target_state

    def enable_plugin(self, plugin_id: str) -> PluginLifecycleState:
        """Enable an installed plugin."""
        if self.is_revoked(plugin_id):
            raise ValueError(f"Cannot enable revoked plugin '{plugin_id}'")
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        if plugin["state"] == PluginLifecycleState.REVOKED:
            raise ValueError(f"Plugin '{plugin_id}' is revoked")

        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE plugins SET state = ?, updated_at = ? WHERE plugin_id = ?",
                (PluginLifecycleState.ENABLED.value, now, plugin_id),
            )
            conn.commit()
        return PluginLifecycleState.ENABLED

    def disable_plugin(self, plugin_id: str) -> PluginLifecycleState:
        """Disable an active plugin without uninstallation."""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            raise KeyError(f"Plugin '{plugin_id}' not found")

        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE plugins SET state = ?, updated_at = ? WHERE plugin_id = ?",
                (PluginLifecycleState.DISABLED.value, now, plugin_id),
            )
            conn.commit()
        return PluginLifecycleState.DISABLED

    async def emergency_revoke(
        self, plugin_id: str, reason: str, revoked_by: str = "admin"
    ) -> None:
        """Permanently revoke a plugin, terminate running instances, and record in ledger."""
        now = datetime.now(UTC).isoformat()
        await self.sandbox.terminate_all()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO revocation_ledger (plugin_id, reason, revoked_by, revoked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    reason = excluded.reason,
                    revoked_by = excluded.revoked_by,
                    revoked_at = excluded.revoked_at
            """,
                (plugin_id, reason, revoked_by, now),
            )
            conn.execute(
                """
                UPDATE plugins
                SET state = ?, granted_capabilities_json = '[]', updated_at = ?
                WHERE plugin_id = ?
            """,
                (PluginLifecycleState.REVOKED.value, now, plugin_id),
            )
            conn.commit()

        logger.warning(f"Plugin '{plugin_id}' permanently REVOKED by {revoked_by}: {reason}")

    def update_plugin(
        self,
        plugin_id: str,
        new_manifest: PluginManifest,
        new_code_dir: str,
        actor: str = "admin",
    ) -> tuple[PluginLifecycleState, list[PluginCapability]]:
        """
        Update a plugin with permission expansion detection.
        If new capabilities are required, transitions to APPROVED/PENDING rather than auto-granting.
        """
        if self.is_revoked(plugin_id):
            raise ValueError(f"Cannot update revoked plugin '{plugin_id}'")

        current = self.get_plugin(plugin_id)
        if not current:
            raise KeyError(f"Plugin '{plugin_id}' not found")

        old_manifest: PluginManifest = current["manifest"]
        current_granted: list[PluginCapability] = current["granted_capabilities"]

        # Detect permission expansion
        new_requested = set(new_manifest.capabilities)
        old_requested = set(old_manifest.capabilities)
        expanded_capabilities = list(new_requested - old_requested)

        now = datetime.now(UTC).isoformat()
        # Retain only previously granted capabilities that are still in new manifest
        retained_granted = [c for c in current_granted if c in new_requested]

        # If permissions expanded, disable until explicit re-approval
        next_state = PluginLifecycleState.INSTALLED if expanded_capabilities else current["state"]

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE plugins
                SET name = ?, version = ?, publisher = ?, manifest_json = ?,
                    code_dir = ?, state = ?, granted_capabilities_json = ?,
                    previous_manifest_json = ?, previous_code_dir = ?, updated_at = ?
                WHERE plugin_id = ?
            """,
                (
                    new_manifest.name,
                    new_manifest.version,
                    new_manifest.publisher,
                    new_manifest.model_dump_json(),
                    new_code_dir,
                    next_state.value,
                    json.dumps([c.value for c in retained_granted]),
                    old_manifest.model_dump_json(),
                    current["code_dir"],
                    now,
                    plugin_id,
                ),
            )
            conn.commit()

        return next_state, expanded_capabilities

    def rollback_plugin(self, plugin_id: str) -> PluginLifecycleState:
        """Roll back to the previous version and manifest."""
        current = self.get_plugin(plugin_id)
        if not current:
            raise KeyError(f"Plugin '{plugin_id}' not found")

        prev_manifest = current["previous_manifest"]
        prev_code_dir = current["previous_code_dir"]

        if not prev_manifest or not prev_code_dir:
            raise ValueError(f"No previous rollback state available for plugin '{plugin_id}'")

        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE plugins
                SET name = ?, version = ?, publisher = ?, manifest_json = ?,
                    code_dir = ?, state = ?,
                    previous_manifest_json = NULL, previous_code_dir = NULL, updated_at = ?
                WHERE plugin_id = ?
            """,
                (
                    prev_manifest.name,
                    prev_manifest.version,
                    prev_manifest.publisher,
                    prev_manifest.model_dump_json(),
                    prev_code_dir,
                    PluginLifecycleState.ENABLED.value,
                    now,
                    plugin_id,
                ),
            )
            conn.commit()

        return PluginLifecycleState.ENABLED

    def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        """Retrieve plugin metadata and parsed manifest."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM plugins WHERE plugin_id = ?", (plugin_id,))
            row = cursor.fetchone()
            if not row:
                return None

            manifest = PluginManifest.model_validate_json(row["manifest_json"])
            prev_manifest = None
            if row["previous_manifest_json"]:
                prev_manifest = PluginManifest.model_validate_json(row["previous_manifest_json"])

            granted_raw = json.loads(row["granted_capabilities_json"])
            granted_caps = [PluginCapability(c) for c in granted_raw]

            return {
                "plugin_id": row["plugin_id"],
                "name": row["name"],
                "version": row["version"],
                "publisher": row["publisher"],
                "manifest": manifest,
                "state": PluginLifecycleState(row["state"]),
                "code_dir": row["code_dir"],
                "granted_capabilities": granted_caps,
                "previous_manifest": prev_manifest,
                "previous_code_dir": row["previous_code_dir"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all registered plugins."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT plugin_id FROM plugins ORDER BY created_at ASC")
            rows = cursor.fetchall()
            return [self.get_plugin(r["plugin_id"]) for r in rows if r]  # type: ignore

    async def execute_plugin_action(self, request: PluginExecutionRequest) -> PluginExecutionResult:
        """Verify lifecycle state and execute action through the sandbox driver."""
        if self.is_revoked(request.plugin_id):
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                action=request.action,
                success=False,
                error=f"Plugin '{request.plugin_id}' is permanently REVOKED",
                request_id=request.request_id,
            )

        plugin = self.get_plugin(request.plugin_id)
        if not plugin:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                action=request.action,
                success=False,
                error=f"Plugin '{request.plugin_id}' not found",
                request_id=request.request_id,
            )

        if plugin["state"] != PluginLifecycleState.ENABLED:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                action=request.action,
                success=False,
                error=f"Plugin '{request.plugin_id}' is not in ENABLED state (current: {plugin['state'].value})",
                request_id=request.request_id,
            )

        manifest: PluginManifest = plugin["manifest"]
        code_dir: str = plugin["code_dir"]
        granted: list[PluginCapability] = plugin["granted_capabilities"]

        return await self.sandbox.execute(
            manifest=manifest,
            plugin_code_dir=code_dir,
            request=request,
            granted_capabilities=granted,
        )

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
