"""Model Download and Integrity Bootstrap Script for PIXEL.

Downloads verified open-source local model weights to data/models/ with atomic writes
and cryptographic SHA-256 checksum verification.
This script must be executed manually and is NEVER executed automatically during tests or CI.
"""

import argparse
import hashlib
import logging
import os
import shutil
import sys
import tempfile
import urllib.request
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pixel.bootstrap")

# Canonical project models directory
DEFAULT_MODELS_DIR = os.path.abspath("data/models")

# Registered local models catalog with authoritative SHA-256 hashes
MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "silero-vad": {
        "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        "relative_path": "silero_vad.onnx",
        "sha256": "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
        "description": "Silero VAD v5 ONNX (~2.2MB, Lightweight CPU Voice Activity Detection)",
    }
}


def calculate_file_sha256(file_path: str) -> str:
    """Computes the SHA-256 hexadecimal hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest().lower()


def sanitize_model_path(base_dir: str, relative_path: str) -> str:
    """Validates that destination path stays strictly inside the canonical base directory."""
    abs_base = os.path.abspath(base_dir)
    target_path = os.path.abspath(os.path.join(abs_base, relative_path))
    if not target_path.startswith(abs_base + os.sep) and target_path != abs_base:
        raise ValueError(
            f"Unsafe model path traversal detected: '{relative_path}' resolves outside '{abs_base}'"
        )
    return target_path


def download_model(model_key: str, force: bool = False, base_dir: str = DEFAULT_MODELS_DIR) -> bool:
    """Downloads a designated model artifact using atomic file writes and SHA-256 verification."""
    if model_key not in MODEL_REGISTRY:
        logger.error(f"Unknown model key: '{model_key}'. Available: {list(MODEL_REGISTRY.keys())}")
        return False

    spec = MODEL_REGISTRY[model_key]
    try:
        dest_path = sanitize_model_path(base_dir, spec["relative_path"])
    except ValueError as err:
        logger.error(f"Security validation error for '{model_key}': {err}")
        return False

    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)

    expected_sha256 = spec["sha256"]

    if os.path.exists(dest_path) and not force:
        if expected_sha256:
            actual_hash = calculate_file_sha256(dest_path)
            if actual_hash == expected_sha256.lower():
                logger.info(f"Model '{model_key}' already exists and verified at '{dest_path}'.")
                return True
            logger.warning(f"Existing model '{model_key}' checksum mismatch. Redownloading...")
        else:
            logger.info(f"Model '{model_key}' already exists at '{dest_path}'.")
            return True

    logger.info(f"Downloading {spec['description']} from {spec['url']}...")

    # Atomic download via temporary file in target directory
    temp_fd, temp_path = tempfile.mkstemp(prefix="pixel_dl_", dir=dest_dir)
    os.close(temp_fd)

    try:
        urllib.request.urlretrieve(spec["url"], temp_path)

        # Integrity verification
        if expected_sha256:
            actual_sha256 = calculate_file_sha256(temp_path)
            if actual_sha256 != expected_sha256.lower():
                logger.error(
                    f"Integrity check failed for '{model_key}'!\n"
                    f"Expected: {expected_sha256}\n"
                    f"Actual  : {actual_sha256}"
                )
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            logger.info(f"SHA-256 integrity verified for '{model_key}'.")

        # Atomic move to final destination
        shutil.move(temp_path, dest_path)
        file_size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        logger.info(
            f"Successfully installed '{model_key}' ({file_size_mb:.2f} MB) at '{dest_path}'."
        )
        return True

    except Exception as err:
        logger.error(f"Download error for '{model_key}': {err}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="PIXEL Model Weights Bootstrap Utility")
    parser.add_argument(
        "--model",
        default="all",
        choices=["all", "silero-vad"],
        help="Target model to download (default: all)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force redownload even if model already exists"
    )
    parser.add_argument(
        "--models-dir",
        default=DEFAULT_MODELS_DIR,
        help=f"Target directory for model weights (default: {DEFAULT_MODELS_DIR})",
    )

    args = parser.parse_args()

    targets = list(MODEL_REGISTRY.keys()) if args.model == "all" else [args.model]
    success_all = True

    for target in targets:
        success = download_model(target, force=args.force, base_dir=args.models_dir)
        if not success:
            success_all = False

    return 0 if success_all else 1


if __name__ == "__main__":
    sys.exit(main())
