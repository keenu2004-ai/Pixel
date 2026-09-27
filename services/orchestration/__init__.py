"""Multi-Device Orchestration & Satellite Topology Service.

Provides cryptographic device pairing, canonical device & presence registries,
multi-satellite audio coordination & wake arbitration, and cross-device handoff.
"""

from services.orchestration.arbitration import WakeArbiter
from services.orchestration.handoff import HandoffManager
from services.orchestration.mock_nodes import (
    MockAndroidNode,
    MockDeviceNode,
    MockPCNode,
    MockSatelliteNode,
)
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager

__all__ = [
    "PKIEngine",
    "DeviceRegistry",
    "PresenceManager",
    "WakeArbiter",
    "HandoffManager",
    "MockDeviceNode",
    "MockPCNode",
    "MockAndroidNode",
    "MockSatelliteNode",
]
