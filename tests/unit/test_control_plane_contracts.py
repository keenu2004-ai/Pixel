"""Unit tests for Phase 10 Control Plane contracts and models."""

from datetime import UTC, datetime

from packages.contracts.autonomous import TaskLifecycleState
from packages.contracts.control_plane import (
    ControlPlaneEventType,
    ControlPlaneStreamEvent,
    ConversationSessionView,
    LoginRequest,
    LoginResponse,
    ServiceHealthStatus,
    SystemOverview,
    TaskActionRequest,
    TaskActionResponse,
    UserIdentity,
    UserRole,
)
from packages.contracts.events import VoiceState


def test_user_role_hierarchy() -> None:
    assert UserRole.READ_ONLY.value == "READ_ONLY"
    assert UserRole.OPERATOR.value == "OPERATOR"
    assert UserRole.ADMIN.value == "ADMIN"
    assert UserRole.SYSTEM.value == "SYSTEM"


def test_user_identity_contract() -> None:
    now = datetime.now(UTC)
    user = UserIdentity(
        user_id="usr_001",
        username="test_admin",
        role=UserRole.ADMIN,
        created_at=now,
    )
    assert user.user_id == "usr_001"
    assert user.username == "test_admin"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True


def test_login_request_response() -> None:
    req = LoginRequest(username="admin", password="secure-password")
    assert req.username == "admin"
    assert req.password == "secure-password"

    user = UserIdentity(user_id="u1", username="admin", role=UserRole.ADMIN)
    res = LoginResponse(access_token="tok_xyz", user=user)
    assert res.token_type == "Bearer"
    assert res.access_token == "tok_xyz"
    assert res.user.username == "admin"


def test_system_overview_contract() -> None:
    service = ServiceHealthStatus(
        service_name="L1_VoiceGateway",
        is_healthy=True,
        latency_ms=1.5,
        details={"active_sessions": 2},
    )
    overview = SystemOverview(
        runtime_version="1.0.0",
        environment="production",
        is_online=True,
        active_devices_count=3,
        active_tasks_count=1,
        active_sessions_count=2,
        services=[service],
    )
    assert overview.is_online is True
    assert len(overview.services) == 1
    assert overview.services[0].latency_ms == 1.5


def test_conversation_session_view() -> None:
    view = ConversationSessionView(
        session_id="sess_123",
        user_id="usr_001",
        device_id="desktop_01",
        voice_state=VoiceState.LISTENING,
        current_transcript="Hey Pixel",
        turn_count=1,
    )
    assert view.session_id == "sess_123"
    assert view.voice_state == VoiceState.LISTENING
    assert view.turn_count == 1


def test_task_action_request_response() -> None:
    req = TaskActionRequest(action="PAUSE", reason="Operator requested")
    assert req.action == "PAUSE"

    res = TaskActionResponse(
        success=True,
        task_id="task_001",
        action="PAUSE",
        new_state=TaskLifecycleState.PAUSED,
        message="Task paused successfully",
    )
    assert res.success is True
    assert res.new_state == TaskLifecycleState.PAUSED


def test_control_plane_stream_event() -> None:
    event = ControlPlaneStreamEvent(
        event_type=ControlPlaneEventType.CONVERSATION_UPDATE,
        payload={"session_id": "sess_123", "state": "SPEAKING"},
    )
    assert event.event_type == ControlPlaneEventType.CONVERSATION_UPDATE
    assert event.payload["session_id"] == "sess_123"
    assert isinstance(event.event_id, str)
    assert len(event.event_id) > 0
