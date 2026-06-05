"""
Colab-ready Qwen LoRA fine-tuning script.

Use this after generating `training/generated/qwen_sft.jsonl` locally with:

    python training/generate_sft_dataset.py --overwrite

Upload that JSONL file to Colab, then run this script. It trains a LoRA adapter
for style/structure/tool-grounded safety reasoning. It does not replace RAG.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# This fine-tuning path is PyTorch-only. Colab preinstalls TensorFlow, and some
# transformers imports may try to load it unless explicitly disabled.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def _bf16_supported() -> bool:
    return torch.cuda.is_available() and torch.cuda.is_bf16_supported()


def _format_chat(example, tokenizer) -> dict[str, str]:
    return {
        "text": tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
    }


def _tokenize(example, tokenizer, max_seq_length: int) -> dict[str, list[int]]:
    return tokenizer(
        example["text"],
        truncation=True,
        max_length=max_seq_length,
        padding=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune Qwen with LoRA on project SFT examples.")
    parser.add_argument("--data", type=Path, default=Path("qwen_sft.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("qwen_safety_lora"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("GPU not detected. In Colab, use Runtime > Change runtime type > GPU.")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if _bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    lora_config = LoraConfig(
        r=16,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = load_dataset("json", data_files=str(args.data), split="train")
    dataset = dataset.map(lambda row: _format_chat(row, tokenizer), remove_columns=dataset.column_names)
    dataset = dataset.map(
        lambda row: _tokenize(row, tokenizer, args.max_seq_length),
        remove_columns=dataset.column_names,
    )

    trainer = Trainer(
        model=model,
        train_dataset=dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            fp16=not _bf16_supported(),
            bf16=_bf16_supported(),
            logging_steps=1,
            optim="paged_adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=str(args.output),
            save_strategy="epoch",
            report_to="none",
        ),
    )

    trainer.train()
    model.save_pretrained(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    print(f"Saved LoRA adapter to {args.output}")


if __name__ == "__main__":
    main()
