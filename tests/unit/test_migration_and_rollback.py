"""Unit tests for MigrationEngine and atomic rollbacks."""

from services.evolution.migration_engine import MigrationEngine


def test_forward_migration_success() -> None:
    engine = MigrationEngine()
    initial_state = {"schema_version": "1.13.0", "devices": ["phone-01"]}

    def migration_fn(data: dict[str, object]) -> dict[str, object]:
        new_data = dict(data)
        new_data["schema_version"] = "1.14.0"
        new_data["readiness_level"] = "LEVEL_5"
        return new_data

    migrated, success = engine.apply_migration("1.14.0", initial_state, migration_fn)
    assert success
    assert migrated["schema_version"] == "1.14.0"
    assert migrated["readiness_level"] == "LEVEL_5"
    assert engine.current_version == "1.14.0"


def test_failed_migration_automatic_rollback() -> None:
    engine = MigrationEngine()
    initial_state = {"schema_version": "1.13.0", "intact": True}

    def failing_migration_fn(data: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("Corrupted database migration step")

    restored, success = engine.apply_migration("1.14.0", initial_state, failing_migration_fn)
    assert not success
    assert restored["schema_version"] == "1.13.0"
    assert restored["intact"] is True
    assert engine.current_version == "1.13.0"
