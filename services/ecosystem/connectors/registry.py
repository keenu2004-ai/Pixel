"""
Persistent Connector Registry and Delivery Audit Ledger.

Manages connector configurations, lifecycle states, and records delivery telemetry.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from packages.contracts.ecosystem import (
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
    WebhookDeliveryRecord,
)
from services.ecosystem.connectors.base import BaseConnector
from services.ecosystem.connectors.discord import DiscordConnector
from services.ecosystem.connectors.home_assistant import HomeAssistantConnector
from services.ecosystem.connectors.matrix import MatrixConnector
from services.ecosystem.connectors.slack import SlackConnector


class ConnectorRegistry:
    """Manages connector configurations and execution instances."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._instances: dict[str, BaseConnector] = {}
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
                CREATE TABLE IF NOT EXISTS connectors (
                    connector_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    connector_type TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status_code INTEGER,
                    success INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    attempt INTEGER NOT NULL,
                    error_message TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def create_connector_instance(self, config: ConnectorConfig) -> BaseConnector:
        """Instantiate driver class based on connector type."""
        if config.connector_type == ConnectorType.SLACK:
            return SlackConnector(config)
        elif config.connector_type == ConnectorType.DISCORD:
            return DiscordConnector(config)
        elif config.connector_type == ConnectorType.HOME_ASSISTANT:
            return HomeAssistantConnector(config)
        elif config.connector_type == ConnectorType.MATRIX:
            return MatrixConnector(config)
        else:
            return SlackConnector(config)  # Default fallback

    def register_connector(self, config: ConnectorConfig) -> None:
        """Register or update a connector configuration."""
        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO connectors (
                    connector_id, name, connector_type, target_url, config_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(connector_id) DO UPDATE SET
                    name = excluded.name,
                    connector_type = excluded.connector_type,
                    target_url = excluded.target_url,
                    config_json = excluded.config_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """,
                (
                    config.connector_id,
                    config.name,
                    config.connector_type.value,
                    config.target_url,
                    config.model_dump_json(),
                    config.status.value,
                    config.created_at.isoformat(),
                    now,
                ),
            )
            conn.commit()

        # Update cache
        self._instances[config.connector_id] = self.create_connector_instance(config)

    def get_connector(self, connector_id: str) -> ConnectorConfig | None:
        """Fetch connector config by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT config_json FROM connectors WHERE connector_id = ?", (connector_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ConnectorConfig.model_validate_json(row["config_json"])

    def list_connectors(self) -> list[ConnectorConfig]:
        """List all registered connectors."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT config_json FROM connectors ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [ConnectorConfig.model_validate_json(r["config_json"]) for r in rows]

    def delete_connector(self, connector_id: str) -> bool:
        """Delete a connector configuration."""
        self._instances.pop(connector_id, None)
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM connectors WHERE connector_id = ?", (connector_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_active_instances(self) -> list[BaseConnector]:
        """Get all active connector execution instances."""
        configs = self.list_connectors()
        active = []
        for cfg in configs:
            if cfg.status == ConnectorStatus.ACTIVE:
                if cfg.connector_id not in self._instances:
                    self._instances[cfg.connector_id] = self.create_connector_instance(cfg)
                active.append(self._instances[cfg.connector_id])
        return active

    def record_delivery(self, record: WebhookDeliveryRecord) -> None:
        """Store delivery telemetry into the audit ledger."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO webhook_deliveries (
                    delivery_id, connector_id, event_id, event_type,
                    status_code, success, latency_ms, attempt, error_message, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.delivery_id,
                    record.connector_id,
                    record.event_id,
                    record.event_type,
                    record.status_code,
                    1 if record.success else 0,
                    record.latency_ms,
                    record.attempt,
                    record.error_message,
                    record.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def list_deliveries(self, limit: int = 50) -> list[WebhookDeliveryRecord]:
        """Retrieve recent webhook deliveries."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM webhook_deliveries ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append(
                    WebhookDeliveryRecord(
                        delivery_id=r["delivery_id"],
                        connector_id=r["connector_id"],
                        event_id=r["event_id"],
                        event_type=r["event_type"],
                        status_code=r["status_code"],
                        success=bool(r["success"]),
                        latency_ms=r["latency_ms"],
                        attempt=r["attempt"],
                        error_message=r["error_message"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                    )
                )
            return results

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
