"""
Zero-Knowledge Encrypted Backups REST API Router.

Enables creating client-encrypted snapshots, listing backup envelopes, and restoring.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.ecosystem import (
    BackupMetadataView,
    BackupRestoreRequest,
    BackupRestoreResult,
    BackupScope,
)
from services.control_plane.dependencies import get_control_plane_manager, require_role
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/backups", tags=["Zero-Knowledge Backups"])


class CreateBackupRequest(BaseModel):
    passphrase: str
    scope: BackupScope = BackupScope.ALL


@router.get("", response_model=list[BackupMetadataView])
async def list_backups(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> list[BackupMetadataView]:
    """List available encrypted backup envelopes without exposing plaintext."""
    return manager.backup_manager.list_backups()


@router.post("/create")
async def create_backup(
    req: CreateBackupRequest,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Create a client-side encrypted backup envelope of active memory and device topology."""
    try:
        envelope = await manager.backup_manager.create_backup(
            passphrase=req.passphrase,
            user_id=user.username,
            scope=req.scope,
        )
        return {
            "success": True,
            "backup_id": envelope.header.backup_id,
            "scope": envelope.header.scope.value,
            "timestamp": envelope.header.timestamp.isoformat(),
            "ciphertext_sha256": envelope.header.ciphertext_sha256,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post("/restore", response_model=BackupRestoreResult)
async def restore_backup(
    req: BackupRestoreRequest,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> BackupRestoreResult:
    """Decrypt and restore a backup snapshot."""
    return await manager.backup_manager.restore_backup(req)


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Permanently delete an encrypted backup envelope."""
    deleted = manager.backup_manager.delete_backup(backup_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Backup '{backup_id}' not found")
    return {"backup_id": backup_id, "deleted": True}
