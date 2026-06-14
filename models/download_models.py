"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models                  # Download all models
    python -m models.download_models minicpm tiny_aya flux  # Download specific models

Models:
    minicpm         — MiniCPM5-1B Q8_0 (llama-cpp-python)
    tiny_aya        — tiny-aya-water Q4_K_M (llama-cpp-python)
    flux            — FLUX.2-klein 4B image gen (diffusers)

Note: OmniVoice TTS is loaded at runtime via
    omnivoice.OmniVoice.from_pretrained("k2-fsa/OmniVoice")
and cached in ~/.cache/huggingface/ — no manual download needed.
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
    "flux": {
        "repo": "black-forest-labs/FLUX.2-klein-4B",
        "files": None,  # Download all files — safetensors weights + configs (~10–12 GB)
        "description": "FLUX.2-klein 4B image gen (diffusers)",
    },
}


def download_model(name: str, target_dir: Path) -> None:
    """Download a single model from HF Hub using Python API."""
    info = MODELS[name]
    output_dir = target_dir / name

    print(f"Downloading {info['description']} ({info['repo']})...")
    print(f"  Target: {output_dir}")
    if info["files"]:
        for f in info["files"]:
            print(f"  📦 {f}")
    else:
        print(f"  📦 All files ({info['description']} is ~10–12 GB)")
    print()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=info["repo"],
        allow_patterns=info["files"] or ["*"],  # None → download all
        local_dir=str(output_dir),
        resume_download=True,
    )
    print(f"  ✓ Done — {output_dir}\n")


def download_all(output_dir: Path | str = ".local/models") -> None:
    """Download all models from HF Hub. Convenience wrapper around download_model."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    errors = []
    for name in MODELS:
        try:
            download_model(name, output_dir)
        except Exception as e:
            errors.append((name, str(e)))
            print(f"  ✗ {name} failed: {e}\n")

    if errors:
        raise RuntimeError(f"{len(errors)} model(s) failed to download: {[n for n, _ in errors]}")


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
