"""Unit tests for Emergency Kill Switches and Evolution Governor."""

import tempfile

from packages.contracts.evolution import (
    EvolutionPolicy,
    KillSwitchDomain,
)
from services.evolution.governance.governor import EvolutionGovernor
from services.evolution.governance.kill_switches import KillSwitchSystem


def test_kill_switch_system() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = f"{tmp_dir}/test_killswitches.db"
        ks = KillSwitchSystem(db_path=db_path)

        assert ks.is_tripped(KillSwitchDomain.AUTONOMOUS_REMEDIATION) is False

        # Trip switch
        status = ks.trip_switch(
            KillSwitchDomain.AUTONOMOUS_REMEDIATION,
            tripped_by="admin_user",
            reason="Unstable self-healing loops observed",
        )
        assert status.is_active is True
        assert ks.is_tripped(KillSwitchDomain.AUTONOMOUS_REMEDIATION) is True

        # Other switches remain untripped
        assert ks.is_tripped(KillSwitchDomain.MODEL_PROMOTION) is False

        # Trip global ALL_SWARMS
        ks.trip_switch(KillSwitchDomain.ALL_SWARMS, reason="Emergency system pause")
        assert ks.is_tripped(KillSwitchDomain.MODEL_PROMOTION) is True  # Global trips all

        # Reset global
        ks.reset_switch(KillSwitchDomain.ALL_SWARMS)
        assert ks.is_tripped(KillSwitchDomain.MODEL_PROMOTION) is False
        assert (
            ks.is_tripped(KillSwitchDomain.AUTONOMOUS_REMEDIATION) is True
        )  # Individual remained tripped

        # Reset individual
        ks.reset_switch(KillSwitchDomain.AUTONOMOUS_REMEDIATION)
        assert ks.is_tripped(KillSwitchDomain.AUTONOMOUS_REMEDIATION) is False


def test_evolution_governor() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = f"{tmp_dir}/test_killswitches.db"
        ks = KillSwitchSystem(db_path=db_path)
        policy = EvolutionPolicy(allow_automatic_remediation=True, max_daily_proposals=2)
        governor = EvolutionGovernor(kill_switch_system=ks, policy=policy)

        assert governor.can_execute_remediation() is True

        # Trip kill switch -> Blocks remediation
        ks.trip_switch(KillSwitchDomain.AUTONOMOUS_REMEDIATION)
        assert governor.can_execute_remediation() is False
