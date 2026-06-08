"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models          # Download all models
    python -m models.download_models tilde-open  # Download specific model
"""

import argparse
import os
from pathlib import Path

# Model definitions — HF Hub URLs (no git submodules needed)
MODELS = {
    "tilde-open": {
        "repo": "TildeAI/TildeOpen-30b",
        "files": ["*.gguf"],
        "description": "TildeOpen-30b text generation",
    },
    "omnivoice": {
        "repo": "k2-fsa/OmniVoice",
        "files": ["*"],
        "description": "OmniVoice TTS",
    },
    "flux": {
        "repo": "black-forest-labs/FLUX.2-klein-4B",
        "files": ["*"],
        "description": "FLUX.2-klein image generation",
    },
}


def download_model(name: str, target_dir: Path) -> None:
    """Download a single model from HF Hub."""
    info = MODELS[name]
    output_dir = target_dir / name

    print(f"Downloading {info['description']} ({info['repo']})...")
    print(f"  Target: {output_dir}")

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=info["repo"],
            allow_patterns=info["files"],
            local_dir=str(output_dir),
            resume_download=True,
        )
        print(f"  ✓ Done")
    except ImportError:
        # Fallback: use huggingface-cli
        import subprocess

        subprocess.run(
            [
                "huggingface-cli",
                "download",
                info["repo"],
                "--include",
                ",".join(info["files"]),
                "--local-dir",
                str(output_dir),
            ],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser(description="Download models from HF Hub")
    parser.add_argument(
        "models",
        nargs="*",
        choices=list(MODELS.keys()),
        help="Models to download (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".local/models"),
        help="Output directory (default: .local/models)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    models_to_download = args.models if args.models else list(MODELS.keys())

    for name in models_to_download:
        download_model(name, output_dir)


if __name__ == "__main__":
    main()
