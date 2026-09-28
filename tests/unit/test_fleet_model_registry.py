"""Unit tests for FleetModelRegistry."""

import hashlib

from packages.contracts.fleet import FleetCapability, FleetModelSpec
from services.fleet.model_registry import FleetModelRegistry
from services.orchestration.pki import PKIEngine


def test_model_registration_and_distribution() -> None:
    """Verify model registration, distribution packaging, node caching, and rollback."""
    pki = PKIEngine()
    reg = FleetModelRegistry(pki_engine=pki)

    raw_data = b"model_binary_weights_v1_synthetic"
    computed_hash = hashlib.sha256(raw_data).hexdigest()

    spec = FleetModelSpec(
        model_id="whisper-tiny-v1",
        model_name="Whisper Tiny Voice",
        version="1.0.0",
        architecture="whisper",
        size_mb=75,
        ram_requirement_mb=256,
        sha256_hash=computed_hash,
        supported_capabilities=[FleetCapability.LOCAL_STT],
    )

    # 1. Register model
    reg.register_model(spec)
    assert reg.get_model("whisper-tiny-v1") is not None

    # 2. Build distribution package
    package = reg.create_distribution_package("whisper-tiny-v1", target_node_id="phone_pixel_01")
    assert package is not None
    assert package.model_spec.model_id == "whisper-tiny-v1"

    # 3. Node cache simulation
    cached = reg.verify_and_cache_model_on_node(
        package=package,
        provided_checksum=computed_hash,
    )
    assert cached is True

    # 4. Rollback test
    spec_v2 = FleetModelSpec(
        model_id="whisper-tiny-v2",
        model_name="Whisper Tiny Voice v2",
        version="2.0.0",
        architecture="whisper",
        size_mb=80,
        ram_requirement_mb=300,
        sha256_hash=hashlib.sha256(b"v2_weights").hexdigest(),
        supported_capabilities=[FleetCapability.LOCAL_STT],
    )
    reg.register_model(spec_v2)
    pkg_v2 = reg.create_distribution_package("whisper-tiny-v2", target_node_id="phone_pixel_01")
    reg.verify_and_cache_model_on_node(pkg_v2, spec_v2.sha256_hash)

    rolled_back = reg.rollback_model_on_node(
        node_id="phone_pixel_01",
        failing_model_id="whisper-tiny-v2",
        fallback_model_id="whisper-tiny-v1",
        reason="Quality regression",
    )
    assert rolled_back is True


def test_tampered_model_checksum_rejection() -> None:
    """Verify that packages with invalid checksums fail verification."""
    reg = FleetModelRegistry()
    package = reg.create_distribution_package("pixel_edge_llm_q4", target_node_id="phone_01")
    verified = reg.verify_and_cache_model_on_node(
        package, provided_checksum="invalid_tampered_hash"
    )
    assert verified is False
