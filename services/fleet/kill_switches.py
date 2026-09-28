"""PIXEL — Phase 17 Fleet Emergency Kill Switches.

Provides instantaneous, zero-latency shutdown domains for edge execution,
model distribution, autonomous delegation, and cross-device sync.
"""

from packages.contracts.fleet import FleetKillSwitchDomain


class FleetKillSwitchManager:
    """Manages fleet-wide emergency kill switches."""

    def __init__(self) -> None:
        self._active_kill_switches: set[FleetKillSwitchDomain] = set()

    def activate_kill_switch(self, domain: FleetKillSwitchDomain, reason: str = "") -> None:
        """Engages a fleet kill switch domain immediately."""
        self._active_kill_switches.add(domain)

    def deactivate_kill_switch(self, domain: FleetKillSwitchDomain) -> None:
        """Disengages a fleet kill switch domain."""
        self._active_kill_switches.discard(domain)

    def is_blocked(self, domain: FleetKillSwitchDomain) -> bool:
        """Checks if a specific fleet domain is actively blocked by kill switch."""
        if FleetKillSwitchDomain.ALL_EDGE_EXECUTION in self._active_kill_switches:
            return True
        return domain in self._active_kill_switches

    def list_active_kill_switches(self) -> list[str]:
        """Lists currently engaged kill switch domains."""
        return [k.value for k in self._active_kill_switches]
