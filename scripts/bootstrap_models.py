"""Model Download and Integrity Bootstrap Script for PIXEL.

Downloads verified open-source local model weights to data/models/.
This script must be executed manually and is NEVER executed automatically during tests or CI.
"""

import argparse
import hashlib
import logging
import os
import sys
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pixel.bootstrap")

# Registered local models catalog
MODEL_REGISTRY = {
    "silero-vad": {
        "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        "destination": "data/models/silero_vad.onnx",
        "sha256": None,  # Will verify size/sha if provided
        "description": "Silero VAD v5 ONNX (~2MB, Lightweight CPU Voice Activity Detection)"
    }
}


def download_model(model_key: str, force: bool = False) -> bool:
    """Downloads a designated model artifact with progress reporting."""
    if model_key not in MODEL_REGISTRY:
        logger.error(f"Unknown model key: '{model_key}'. Available: {list(MODEL_REGISTRY.keys())}")
        return False

    spec = MODEL_REGISTRY[model_key]
    dest_path = spec["destination"]
    dest_dir = os.path.dirname(dest_path)

    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    if os.path.exists(dest_path) and not force:
        logger.info(f"Model '{model_key}' already exists at '{dest_path}'. Use --force to redownload.")
        return True

    logger.info(f"Downloading {spec['description']} from {spec['url']}...")

    try:
        urllib.request.urlretrieve(spec["url"], dest_path)
        file_size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        logger.info(f"Successfully downloaded '{model_key}' ({file_size_mb:.2f} MB) to '{dest_path}'.")

        if spec["sha256"]:
            sha256 = hashlib.sha256()
            with open(dest_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            actual = sha256.hexdigest().lower()
            if actual != spec["sha256"].lower():
                logger.error(f"Checksum verification failed for '{model_key}'! Deleting corrupted file.")
                os.remove(dest_path)
                return False
            logger.info("SHA-256 verification passed.")

        return True
    except Exception as err:
        logger.error(f"Failed to download model '{model_key}': {err}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="PIXEL Model Weights Bootstrap Utility")
    parser.add_argument(
        "--model",
        default="all",
        choices=["all", "silero-vad"],
        help="Target model to download (default: all)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force redownload even if model already exists"
    )

    args = parser.parse_args()

    targets = list(MODEL_REGISTRY.keys()) if args.model == "all" else [args.model]
    success_all = True

    for target in targets:
        success = download_model(target, force=args.force)
        if not success:
            success_all = False

    return 0 if success_all else 1


if __name__ == "__main__":
    sys.exit(main())
