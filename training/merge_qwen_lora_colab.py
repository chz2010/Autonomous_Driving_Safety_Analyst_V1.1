"""
Merge the trained Qwen LoRA adapter into the base Qwen Hugging Face model.

Run in Colab after training or after copying `qwen_safety_lora` from Drive:

    python merge_qwen_lora_colab.py \
      --adapter qwen_safety_lora \
      --output qwen_safety_merged

The merged output is large. For Qwen2.5-7B it can be around 15 GB before
Ollama quantization. Save it to Drive before the Colab runtime is deleted.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def disable_torchao_dispatch() -> None:
    """
    Colab may include an old torchao package. PEFT sees it and tries the torchao
    LoRA dispatcher, then fails on version compatibility. This merge path does
    not need torchao, so force PEFT to use the normal PyTorch LoRA modules.
    """
    try:
        import peft.import_utils as peft_import_utils

        peft_import_utils.is_torchao_available = lambda: False
    except Exception:
        pass

    try:
        import peft.tuners.lora.torchao as peft_lora_torchao

        peft_lora_torchao.is_torchao_available = lambda: False
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Qwen LoRA adapter into the base model.")
    parser.add_argument("--adapter", type=Path, default=Path("qwen_safety_lora"))
    parser.add_argument("--output", type=Path, default=Path("qwen_safety_merged"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-shard-size", default="4GB")
    parser.add_argument("--offload-dir", type=Path, default=Path("/content/qwen_merge_offload"))
    args = parser.parse_args()

    if not args.adapter.exists():
        raise FileNotFoundError(
            f"LoRA adapter folder not found: {args.adapter}\n"
            "If you saved it to Google Drive, use a full path such as:\n"
            "  --adapter /content/drive/MyDrive/qwen_safety_lora\n"
            "Or copy it into /content first:\n"
            "  !cp -r /content/drive/MyDrive/qwen_safety_lora /content/qwen_safety_lora"
        )
    if not (args.adapter / "adapter_config.json").exists():
        raise FileNotFoundError(
            f"{args.adapter} exists, but adapter_config.json was not found. "
            "Point --adapter to the actual qwen_safety_lora folder."
        )

    args.offload_dir.mkdir(parents=True, exist_ok=True)

    disable_torchao_dispatch()

    tokenizer = AutoTokenizer.from_pretrained(args.adapter, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=torch.float16,
        device_map="auto",
        offload_folder=str(args.offload_dir),
        offload_state_dict=True,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(
        model,
        args.adapter,
        device_map="auto",
        offload_folder=str(args.offload_dir),
        offload_state_dict=True,
    )
    model = model.merge_and_unload()

    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(
        args.output,
        safe_serialization=True,
        max_shard_size=args.max_shard_size,
    )
    tokenizer.save_pretrained(args.output)

    modelfile = args.output / "Modelfile"
    modelfile.write_text(
        "\n".join(
            [
                "FROM .",
                "PARAMETER temperature 0.2",
                "PARAMETER num_ctx 16384",
                "PARAMETER num_predict 4000",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Merged model saved to: {args.output}")
    print(f"Ollama Modelfile saved to: {modelfile}")


if __name__ == "__main__":
    main()
