#!/usr/bin/env python3
"""Pre-download all models for EuropaLex.

Run this script before starting the app to ensure all models are cached locally.
Models are downloaded once and cached in ~/.cache/huggingface/ (HF Hub) or
.local/models/ (GGUF files via huggingface-cli).

Usage:
    python scripts/download_models.py          # download all models
    python scripts/download_models.py --skip-tts  # skip TTS model
    python scripts/download_models.py --skip-images  # skip image generation model
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def download_gguf_model(
    repo_id: str, filename: str, local_dir: Path, runtime: str = "huggingface-cli"
) -> None:
    """Download a GGUF model file using huggingface-cli."""
    target = local_dir / filename
    if target.exists():
        size_mb = target.stat().st_size / (1024 * 1024)
        logger.info("SKIP %s (already exists, %.1f MB)", target.name, size_mb)
        return

    logger.info("Downloading %s/%s -> %s", repo_id, filename, local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    import subprocess

    if runtime == "huggingface-cli":
        cmd = [
            sys.executable, "-m", "huggingface_hub", "download",
            "--repo-type", "model",
            repo_id, filename,
            "--local-dir", str(local_dir),
            "--local-dir-use-symlinks", "false",
        ]
    else:
        # llama-cpp-python style: use hf_hub_download
        from huggingface_hub import hf_hub_download

        dest = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
        )
        logger.info("Downloaded to %s", dest)
        return

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Failed to download %s:\n%s", target.name, result.stderr)
        sys.exit(1)
    logger.info("Downloaded %s", target)


def download_tts_model() -> None:
    """Download OmniVoice TTS model files from HF Hub (PyTorch safetensors).

    Uses snapshot_download to fetch all files without loading into VRAM.
    The model is loaded lazily on first use by the app.
    """
    logger.info("Downloading OmniVoice TTS model from k2-fsa/OmniVoice...")
    logger.info("This downloads PyTorch weights (~4-8 GB) to ~/.cache/huggingface/")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        logger.error(
            "huggingface_hub not installed. Run: pip install huggingface_hub"
        )
        sys.exit(1)

    snapshot_download(
        repo_id="k2-fsa/OmniVoice",
        cache_dir=str(cache_dir),
        local_dir_use_symlinks=False,
    )
    logger.info("OmniVoice TTS model downloaded and cached.")


def download_image_model() -> None:
    """Download FLUX.2-klein image generation model files from HF Hub (PyTorch safetensors).

    Uses snapshot_download to fetch all files without loading into VRAM.
    The model is loaded lazily on first use by the app.
    """
    logger.info(
        "Downloading FLUX.2-klein image model from black-forest-labs/FLUX.2-klein-4B..."
    )
    logger.info("This downloads PyTorch weights (~8 GB) to ~/.cache/huggingface/")

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id="black-forest-labs/FLUX.2-klein-4B",
    )
    logger.info("FLUX.2-klein image model downloaded and cached.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-download all EuropaLex models"
    )
    parser.add_argument(
        "--skip-tts", action="store_true", help="Skip TTS (OmniVoice) model"
    )
    parser.add_argument(
        "--skip-images", action="store_true", help="Skip image gen (FLUX) model"
    )
    args = parser.parse_args()

    config_path = Path("configs/settings.yaml")
    if not config_path.exists():
        logger.error("settings.yaml not found. Run from project root.")
        sys.exit(1)

    import yaml

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    models_dir = Path(cfg["models"]["directory"])
    models_cfg = cfg["models"]

    # 1. MiniCPM5-1B (English text generation, GGUF)
    minicpm = models_cfg.get("minicpm", {})
    if minicpm:
        download_gguf_model(
            repo_id=minicpm["repo"],
            filename=minicpm["file"],
            local_dir=models_dir / "minicpm",
            runtime="huggingface-cli",
        )

    # 2. tiny-aya-water (translation, GGUF)
    tiny_aya = models_cfg.get("tiny_aya", {})
    if tiny_aya:
        download_gguf_model(
            repo_id=tiny_aya["repo"],
            filename=tiny_aya["file"],
            local_dir=models_dir / "tiny_aya",
            runtime="huggingface-cli",
        )

    # 3. OmniVoice (TTS, PyTorch safetensors from HF Hub)
    if not args.skip_tts:
        download_tts_model()

    # 4. FLUX.2-klein (image generation, PyTorch safetensors from HF Hub)
    if not args.skip_images:
        download_image_model()

    logger.info("All models downloaded successfully.")


if __name__ == "__main__":
    main()
