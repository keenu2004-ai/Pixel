"""Unit tests for ModelResourceManager and hardware memory governor."""

from packages.contracts.models import (
    ModelFamily,
    ModelMetadata,
    QuantizationType,
)
from services.agent_runtime.local_llm.resource_manager import ModelResourceManager


def test_resource_manager_registration_and_integrity() -> None:
    mgr = ModelResourceManager(max_memory_mb=6000)
    meta = ModelMetadata(
        model_id="qwen-7b",
        model_name="Qwen 7B",
        family=ModelFamily.QWEN,
        quantization=QuantizationType.Q4_K_M,
        file_path="data/qwen.gguf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        memory_required_mb=3500,
    )
    mgr.register_model(meta)
    assert mgr.get_registered_model("qwen-7b") is not None
    assert mgr.verify_model_integrity(meta) is True


def test_memory_allocation_and_eviction_scheduling() -> None:
    # Set maximum memory ceiling to 6000 MB
    mgr = ModelResourceManager(max_memory_mb=6000)

    m1 = ModelMetadata(
        model_id="llm-1",
        model_name="Model 1",
        family=ModelFamily.QWEN,
        file_path="m1.gguf",
        sha256_hash="a" * 64,
        memory_required_mb=3000,
    )
    m2 = ModelMetadata(
        model_id="tts-1",
        model_name="TTS Model",
        family=ModelFamily.KOKORO_TTS,
        file_path="tts.onnx",
        sha256_hash="b" * 64,
        memory_required_mb=2000,
    )
    m3 = ModelMetadata(
        model_id="llm-2",
        model_name="Model 2 (Large)",
        family=ModelFamily.LLAMA,
        file_path="m2.gguf",
        sha256_hash="c" * 64,
        memory_required_mb=4000,
    )

    mgr.register_model(m1)
    mgr.register_model(m2)
    mgr.register_model(m3)

    # 1. Load m1 (3000MB) -> total 3000MB <= 6000MB
    can_load, err, evictions = mgr.request_load_permission("llm-1")
    assert can_load is True
    assert len(evictions) == 0
    mgr.record_model_loaded("llm-1")
    assert mgr.get_total_allocated_memory_mb() == 3000

    # 2. Load m2 (2000MB) -> total 5000MB <= 6000MB
    can_load, err, evictions = mgr.request_load_permission("tts-1")
    assert can_load is True
    assert len(evictions) == 0
    mgr.record_model_loaded("tts-1")
    assert mgr.get_total_allocated_memory_mb() == 5000

    # 3. Load m3 (4000MB) -> 5000 + 4000 = 9000MB > 6000MB.
    # Must evict m1 (oldest) to free 3000MB -> (2000 + 4000 = 6000MB)
    can_load, err, evictions = mgr.request_load_permission("llm-2")
    assert can_load is True
    assert "llm-1" in evictions

    # Unload evicted model and record new model load
    mgr.record_model_unloaded("llm-1")
    mgr.record_model_loaded("llm-2")
    assert mgr.get_total_allocated_memory_mb() == 6000
