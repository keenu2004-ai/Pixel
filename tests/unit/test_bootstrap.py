"""Unit tests for scripts/bootstrap_models.py integrity and path safety."""

import hashlib
import os
from unittest.mock import patch

import pytest

from scripts.bootstrap_models import (
    calculate_file_sha256,
    download_model,
    sanitize_model_path,
)


def calculate_file_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def test_calculate_file_sha256(tmp_path: os.PathLike[str]) -> None:
    test_file = os.path.join(tmp_path, "sample.bin")
    data = b"Hello PIXEL VAD"
    with open(test_file, "wb") as f:
        f.write(data)

    expected = calculate_file_sha256_bytes(data)
    actual = calculate_file_sha256(test_file)
    assert actual == expected


def test_sanitize_model_path_valid(tmp_path: os.PathLike[str]) -> None:
    base = os.path.abspath(tmp_path)
    res = sanitize_model_path(base, "silero_vad.onnx")
    assert res == os.path.join(base, "silero_vad.onnx")


def test_sanitize_model_path_traversal_rejected(tmp_path: os.PathLike[str]) -> None:
    base = os.path.abspath(tmp_path)
    with pytest.raises(ValueError, match="Unsafe model path traversal detected"):
        sanitize_model_path(base, "../../etc/shadow")


def test_download_model_integrity_success(tmp_path: os.PathLike[str]) -> None:
    base = os.path.abspath(tmp_path)
    fake_content = b"fake_silero_bytes"

    def mock_retrieve(url: str, filename: str) -> tuple[str, None]:
        with open(filename, "wb") as f:
            f.write(fake_content)
        return filename, None

    with patch("urllib.request.urlretrieve", side_effect=mock_retrieve):
        with patch.dict(
            "scripts.bootstrap_models.MODEL_REGISTRY",
            {
                "test-model": {
                    "url": "http://example.com/model.onnx",
                    "relative_path": "test_model.onnx",
                    "sha256": calculate_file_sha256_bytes(fake_content),
                    "description": "Test Model"
                }
            }
        ):
            success = download_model("test-model", base_dir=base)
            assert success is True
            target = os.path.join(base, "test_model.onnx")
            assert os.path.exists(target)


def test_download_model_integrity_mismatch_rejected(tmp_path: os.PathLike[str]) -> None:
    base = os.path.abspath(tmp_path)
    fake_content = b"corrupted_silero_bytes"

    def mock_retrieve(url: str, filename: str) -> tuple[str, None]:
        with open(filename, "wb") as f:
            f.write(fake_content)
        return filename, None

    with patch("urllib.request.urlretrieve", side_effect=mock_retrieve):
        with patch.dict(
            "scripts.bootstrap_models.MODEL_REGISTRY",
            {
                "test-model": {
                    "url": "http://example.com/model.onnx",
                    "relative_path": "test_model.onnx",
                    "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                    "description": "Test Model"
                }
            }
        ):
            success = download_model("test-model", base_dir=base)
            assert success is False
            target = os.path.join(base, "test_model.onnx")
            assert not os.path.exists(target)
