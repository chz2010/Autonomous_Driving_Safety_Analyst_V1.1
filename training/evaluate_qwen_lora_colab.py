"""
Evaluate the trained Qwen LoRA adapter in Colab.

Upload or copy `qwen_safety_lora` into the Colab working directory, then run:

    python evaluate_qwen_lora_colab.py \
      --adapter qwen_safety_lora \
      --prompt "Give me the whole safety lifecycle for an AEB pedestrian system..."

This script is for quality checking before app integration.
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
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


DEFAULT_SYSTEM_PROMPT = """You are Autonomous Driving Safety Analyst, an expert autonomous-driving safety analyst and technical RAG assistant.

Answer with engineering-specific reasoning. For autonomous-driving questions, relate the answer to ISO 26262, ISO 21448 (SOTIF), and ISO 8800 when relevant. Decompose the item into functions, analyze all listed functions, state assumptions, include HARA S/E/C rationale where applicable, and give concrete engineering actions and evidence limitations.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a Qwen LoRA adapter.")
    parser.add_argument("--adapter", type=Path, default=Path("qwen_safety_lora"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=1400)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-p", type=float, default=0.9)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("GPU not detected. In Colab, use Runtime > Change runtime type > GPU.")

    tokenizer = AutoTokenizer.from_pretrained(args.adapter, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, args.adapter)
    model.eval()

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": args.prompt},
    ]
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            max_new_tokens=args.max_new_tokens,
            do_sample=args.temperature > 0,
            temperature=args.temperature,
            top_p=args.top_p,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output[0][inputs["input_ids"].shape[-1] :]
    print(tokenizer.decode(generated, skip_special_tokens=True).strip())


if __name__ == "__main__":
    main()
