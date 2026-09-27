"""Unit tests for GoalDriftDetector and scope enforcement."""

from packages.contracts.autonomous import GoalContract
from services.autonomous.drift_detector import GoalDriftDetector


def test_drift_detector_aligned_plan() -> None:
    detector = GoalDriftDetector()
    goal = GoalContract(
        objective="Run automated regression tests",
        allowed_targets=["tests/unit/*", "tests/integration/*"],
        prohibited_actions=["delete", "drop_table", "force_push"],
    )

    report = detector.evaluate_drift(
        goal=goal,
        active_plan=[{"description": "Execute unit test runner"}],
        proposed_tools=["run_tests"],
        proposed_targets=["tests/unit/test_app.py"],
        current_objective="Run automated regression tests",
    )

    assert not report.is_drifted
    assert report.divergence_score < 0.5
    assert len(report.unauthorized_targets) == 0
    assert len(report.unauthorized_tools) == 0


def test_drift_detector_unauthorized_target() -> None:
    detector = GoalDriftDetector()
    goal = GoalContract(
        objective="Analyze project dependencies",
        allowed_targets=["pyproject.toml", "requirements.txt"],
        prohibited_actions=["delete"],
    )

    report = detector.evaluate_drift(
        goal=goal,
        active_plan=[{"description": "Inspect sensitive files"}],
        proposed_tools=["read_file"],
        proposed_targets=["/etc/shadow", "C:/Windows/System32/config/SAM"],
        current_objective="Analyze project dependencies",
    )

    assert report.is_drifted
    assert len(report.unauthorized_targets) == 2
    assert "not in allowed targets" in report.reason


def test_drift_detector_prohibited_action() -> None:
    detector = GoalDriftDetector()
    goal = GoalContract(
        objective="Clean temporary test cache",
        allowed_targets=["/tmp/test_cache/*"],
        prohibited_actions=["drop_table", "delete_database"],
    )

    report = detector.evaluate_drift(
        goal=goal,
        active_plan=[{"description": "drop_table for users table"}],
        proposed_tools=["drop_table_tool"],
        proposed_targets=["/tmp/test_cache/temp.txt"],
        current_objective="Clean temporary test cache",
    )

    assert report.is_drifted
    assert len(report.unauthorized_tools) > 0
    assert "matches prohibited action" in report.reason
