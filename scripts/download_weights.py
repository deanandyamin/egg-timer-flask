import argparse
from pathlib import Path
from huggingface_hub import hf_hub_download


def download_infinite_talk(base: Path):
    single_dir = base / "InfiniteTalk" / "single"
    multi_dir = base / "InfiniteTalk" / "multi"
    single_dir.mkdir(parents=True, exist_ok=True)
    multi_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading InfiniteTalk single checkpoint...")
    hf_hub_download(
        repo_id="MeiGen-AI/InfiniteTalk",
        filename="single/infinitetalk.safetensors",
        local_dir=single_dir,
        local_dir_use_symlinks=False,
    )

    print("Downloading InfiniteTalk multi checkpoint...")
    hf_hub_download(
        repo_id="MeiGen-AI/InfiniteTalk",
        filename="multi/infinitetalk.safetensors",
        local_dir=multi_dir,
        local_dir_use_symlinks=False,
    )


def download_wav2vec(base: Path):
    wav_dir = base / "chinese-wav2vec2-base"
    wav_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading Chinese wav2vec2 files...")
    for fname in [
        "chinese-wav2vec2-base-fairseq-ckpt.pt",
        "config.json",
        "preprocessor_config.json",
        "pytorch_model.bin",
    ]:
        hf_hub_download(
            repo_id="TencentGameMate/chinese-wav2vec2-base",
            filename=fname,
            local_dir=wav_dir,
            local_dir_use_symlinks=False,
        )


def download_wan(base: Path):
    wan_dir = base / "Wan2.1-I2V-14B-480P"
    wan_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading Wan 2.1 I2V 14B weights (this is very large)...")
    # Core diffusion shards and index
    for i in range(1, 8):
        fname = f"diffusion_pytorch_model-{i:05d}-of-00007.safetensors"
        hf_hub_download(
            repo_id="Wan-AI/Wan2.1-I2V-14B-480P",
            filename=fname,
            local_dir=wan_dir,
            local_dir_use_symlinks=False,
        )
    hf_hub_download(
        repo_id="Wan-AI/Wan2.1-I2V-14B-480P",
        filename="diffusion_pytorch_model.safetensors.index.json",
        local_dir=wan_dir,
        local_dir_use_symlinks=False,
    )
    # Additional required files
    for fname in [
        "Wan2.1_VAE.pth",
        "config.json",
        "models_clip_open-clip-xlm-roberta-large-vit-huge-14.pth",
        "models_t5_umt5-xxl-enc-bf16.pth",
        "google/umt5-xxl/special_tokens_map.json",
        "google/umt5-xxl/spiece.model",
        "google/umt5-xxl/tokenizer.json",
        "google/umt5-xxl/tokenizer_config.json",
        "xlm-roberta-large/sentencepiece.bpe.model",
        "xlm-roberta-large/special_tokens_map.json",
        "xlm-roberta-large/tokenizer.json",
        "xlm-roberta-large/tokenizer_config.json",
    ]:
        hf_hub_download(
            repo_id="Wan-AI/Wan2.1-I2V-14B-480P",
            filename=fname,
            local_dir=wan_dir,
            local_dir_use_symlinks=False,
        )


def main():
    parser = argparse.ArgumentParser(description="Download required weights for InfiniteTalk")
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("weights"),
        help="Base directory to place downloaded weights",
    )
    parser.add_argument(
        "--include_wan",
        action="store_true",
        help="Also download Wan 2.1 I2V 14B (VERY LARGE ~10+ GB)",
    )
    args = parser.parse_args()

    args.base.mkdir(parents=True, exist_ok=True)
    download_infinite_talk(args.base)
    download_wav2vec(args.base)
    if args.include_wan:
        download_wan(args.base)

    print("All requested weights downloaded to:", args.base.resolve())


if __name__ == "__main__":
    main()