"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models                  # Download all models
    python -m models.download_models minicpm tiny_aya  # Download specific models

Models:
    minicpm         — MiniCPM5-1B Q8_0 (llama-cpp-python)
    tiny_aya        — tiny-aya-water Q4_K_M (llama-cpp-python)
    omnivoice       — OmniVoice Q8_0 TTS (omnivoice.cpp, requires base + tokenizer)
    flux            — FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)
"""

import argparse
import concurrent.futures
from pathlib import Path


# Model definitions — HF Hub repos with exact GGUF filenames
MODELS = {
    "minicpm": {
        "repo": "Abiray/MiniCPM5-1B-GGUF",
        "files": ["minicpm5-1b-Q8_0.gguf"],
        "description": "MiniCPM5-1B Q8_0 text gen (llama-cpp-python)",
    },
    "tiny_aya": {
        "repo": "CohereLabs/tiny-aya-water-GGUF",
        "files": ["tiny-aya-water-q4_k_m.gguf"],
        "description": "tiny-aya-water q4_k_m translation (llama-cpp-python)",
    },
    "omnivoice": {
        "repo": "Serveurperso/OmniVoice-GGUF",
        "files": ["omnivoice-base-Q8_0.gguf", "omnivoice-tokenizer-Q8_0.gguf"],
        "description": "OmniVoice Q8_0 TTS (base + tokenizer, omnivoice.cpp)",
    },
    "flux": {
        "repo": "unsloth/FLUX.2-klein-4B-GGUF",
        "files": ["flux-2-klein-4b-Q4_K_M.gguf"],
        "description": "FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)",
    },
}


def download_model(name: str, target_dir: Path) -> None:
    """Download a single model from HF Hub using Python API."""
    info = MODELS[name]
    output_dir = target_dir / name

    print(f"Downloading {info['description']} ({info['repo']})...")
    print(f"  Target: {output_dir}")
    for f in info["files"]:
        print(f"  📦 {f}")
    print()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=info["repo"],
        allow_patterns=info["files"],
        local_dir=str(output_dir),
        resume_download=True,
    )
    print(f"  ✓ Done — {output_dir}\n")


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

    print(f"Starting {len(models_to_download)} download(s) with 4 parallel workers...\n")

    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(download_model, name, output_dir): name
            for name in models_to_download
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as e:
                errors.append((name, str(e)))
                print(f"  ✗ {name} failed: {e}\n")

    if errors:
        print(f"\n{len(errors)} model(s) failed to download.")
        raise SystemExit(1)
    else:
        print(f"All {len(models_to_download)} model(s) downloaded successfully.")


if __name__ == "__main__":
    main()
