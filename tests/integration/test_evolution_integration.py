"""End-to-End Integration tests for Phase 12 Continuous Autonomous Evolution & Self-Healing Swarms."""

import tempfile
from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from packages.contracts.evolution import (
    AgentProposal,
    AgentVote,
    RemediationClass,
    RemediationProposal,
    SwarmAgentIdentity,
    SwarmAgentRole,
    VoteDecision,
)
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app


@pytest.fixture
def test_client() -> Iterator[TestClient]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        auth_mgr = ControlPlaneAuthManager(secret_key="test_secret_evolution_phase12")
        mgr = ControlPlaneManager()
        # Override DB paths with temp dir
        mgr.proposal_manager.db_path = f"{tmp_dir}/proposals.db"
        mgr.proposal_manager._init_db()
        mgr.kill_switches.db_path = f"{tmp_dir}/killswitches.db"
        mgr.kill_switches._init_db()

        app = create_control_plane_app(manager=mgr, auth_manager=auth_mgr)
        with TestClient(app) as client:
            yield client


def test_swarm_and_consensus_api_flow(test_client: TestClient) -> None:
    # 1. Login as operator
    login_res = test_client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "pixel-operator-2026"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Swarm
    create_res = test_client.post(
        "/api/v1/swarms",
        json={"swarm_id": "swarm-integration", "name": "Diagnostics Swarm", "max_agents": 5},
        headers=headers,
    )
    assert create_res.status_code == 200
    assert create_res.json()["swarm_id"] == "swarm-integration"

    # 3. Register Agents
    coord = SwarmAgentIdentity(agent_id="agent-c", role=SwarmAgentRole.COORDINATOR, trust_level=1.0)
    coder = SwarmAgentIdentity(agent_id="agent-d", role=SwarmAgentRole.CODER, trust_level=0.9)
    test_client.post(
        "/api/v1/swarms/swarm-integration/agents", json=coord.model_dump(), headers=headers
    )
    test_client.post(
        "/api/v1/swarms/swarm-integration/agents", json=coder.model_dump(), headers=headers
    )

    # 4. Submit Proposal
    proposal = AgentProposal(
        proposal_id="prop-int-1",
        origin_agent_id="agent-d",
        swarm_id="swarm-integration",
        title="Cache Optimization",
        description="Clear stale memory cache",
        action_payload={"target": "memory_cache"},
    )
    prop_res = test_client.post(
        "/api/v1/swarms/swarm-integration/proposals", json=proposal.model_dump(), headers=headers
    )
    assert prop_res.status_code == 200
    assert prop_res.json()["stage"] == "ROLE_REVIEW"

    # 5. Cast Votes
    v1 = AgentVote(
        vote_id="v1",
        proposal_id="prop-int-1",
        voter_agent_id="agent-c",
        voter_role=SwarmAgentRole.COORDINATOR,
        decision=VoteDecision.APPROVE,
    )
    v2 = AgentVote(
        vote_id="v2",
        proposal_id="prop-int-1",
        voter_agent_id="agent-d",
        voter_role=SwarmAgentRole.CODER,
        decision=VoteDecision.APPROVE,
    )
    test_client.post(
        "/api/v1/swarms/swarm-integration/votes", json=v1.model_dump(), headers=headers
    )
    test_client.post(
        "/api/v1/swarms/swarm-integration/votes", json=v2.model_dump(), headers=headers
    )

    # 6. Finalize Proposal as Admin
    admin_login = test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "pixel-admin-secure-2026"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    finalize_res = test_client.post(
        "/api/v1/swarms/swarm-integration/proposals/prop-int-1/finalize",
        headers=admin_headers,
    )
    assert finalize_res.status_code == 200
    assert finalize_res.json()["is_approved"] is True
    assert finalize_res.json()["stage"] == "EXECUTED"


def test_diagnostics_and_self_healing_api_flow(test_client: TestClient) -> None:
    # Login as admin
    admin_login = test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "pixel-admin-secure-2026"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Execute auto-remediation
    remediation = RemediationProposal(
        proposal_id="rem-auto-1",
        anomaly_id="anom-1",
        hypothesis_id="hypo-1",
        remediation_class=RemediationClass.CLEAR_BOUNDED_CACHE,
        is_automatic_allowed=True,
        parameters={"cache": "query_cache"},
    )
    exec_res = test_client.post(
        "/api/v1/proposals/execute-remediation",
        json=remediation.model_dump(),
        headers=admin_headers,
    )
    assert exec_res.status_code == 200
    chg = exec_res.json()
    assert chg["state"] == "PROMOTED"
    assert chg["canary_percentage"] == 100

    # Rollback remediation
    rb_res = test_client.post(
        f"/api/v1/proposals/{chg['proposal_id']}/rollback",
        json={"reason": "Testing rollback via API"},
        headers=admin_headers,
    )
    assert rb_res.status_code == 200
    assert rb_res.json()["status"] == "rolled_back"


def test_killswitch_trip_and_reset_flow(test_client: TestClient) -> None:
    # Login as admin
    admin_login = test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "pixel-admin-secure-2026"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Trip MODEL_PROMOTION switch
    trip_res = test_client.post(
        "/api/v1/killswitches/MODEL_PROMOTION/trip",
        json={"reason": "Suspected drift in candidate models"},
        headers=admin_headers,
    )
    assert trip_res.status_code == 200
    assert trip_res.json()["is_active"] is True

    # Check status list
    list_res = test_client.get("/api/v1/killswitches", headers=admin_headers)
    assert list_res.status_code == 200
    statuses = list_res.json()
    assert statuses["MODEL_PROMOTION"]["is_active"] is True

    # Reset switch
    reset_res = test_client.post(
        "/api/v1/killswitches/MODEL_PROMOTION/reset",
        headers=admin_headers,
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["is_active"] is False
