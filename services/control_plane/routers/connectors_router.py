"""
Enterprise Connectors and Outbound Webhooks REST API Router.

Enables configuring Slack, Discord, Home Assistant, Matrix connectors, testing delivery, and inspecting audit logs.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.ecosystem import (
    ConnectorConfig,
    WebhookDeliveryRecord,
)
from services.control_plane.dependencies import get_control_plane_manager, require_role
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/connectors", tags=["Connectors & Webhooks"])


@router.get("", response_model=list[ConnectorConfig])
async def list_connectors(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> list[ConnectorConfig]:
    """List all registered outbound connectors."""
    return manager.connector_registry.list_connectors()


@router.post("", response_model=ConnectorConfig)
async def register_connector(
    config: ConnectorConfig,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> ConnectorConfig:
    """Register or update an outbound connector configuration."""
    manager.connector_registry.register_connector(config)
    return config


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Delete a connector configuration."""
    deleted = manager.connector_registry.delete_connector(connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_id}' not found")
    return {"connector_id": connector_id, "deleted": True}


@router.get("/deliveries", response_model=list[WebhookDeliveryRecord])
async def list_deliveries(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    limit: int = Query(50, ge=1, le=200),
) -> list[WebhookDeliveryRecord]:
    """Retrieve recent outbound webhook deliveries and audit status."""
    return manager.connector_registry.list_deliveries(limit=limit)


@router.post("/test")
async def test_connector_dispatch(
    connector_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> WebhookDeliveryRecord:
    """Trigger a test event dispatch to a specific connector."""
    cfg = manager.connector_registry.get_connector(connector_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_id}' not found")

    connector = manager.connector_registry.create_connector_instance(cfg)
    test_event = AutonomousEvent(
        event_id=f"test_evt_{connector_id}",
        correlation_id=f"corr_{connector_id}",
        event_type="TEST_HEALTH_PING",
        source="control_plane_admin",
        payload={"message": "PIXEL Outbound Webhook Test ping", "tested_by": user.username},
    )
    record = await connector.deliver(test_event)
    manager.connector_registry.record_delivery(record)
    return record
