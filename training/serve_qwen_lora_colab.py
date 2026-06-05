"""
Serve the trained Qwen LoRA adapter from Colab for Streamlit demos.

Run this in Colab after mounting/copying `qwen_safety_lora`.
It starts a Gradio app with an API endpoint. Use the printed public URL as:

    LOCAL_LORA_API_URL=https://...gradio.live

The Streamlit app calls this URL through `gradio_client`.
"""

from __future__ import annotations

import argparse
import gc
import os
import re
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import gradio as gr
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


SYSTEM_PROMPT = """You are Autonomous Driving Safety Analyst, an expert autonomous-driving safety analyst and technical RAG assistant.

Answer with engineering-specific reasoning. For autonomous-driving questions, relate the answer to ISO 26262, ISO 21448 (SOTIF), and ISO 8800 when relevant. Decompose the item into functions, analyze all listed functions, state assumptions, include HARA S/E/C rationale where applicable, and give concrete engineering actions and evidence limitations.

Never output token ids, numeric arrays, debug traces, or a comma-separated
sequence of numbers. If the answer cannot be completed, return a short error
message instead of numeric output.
"""


def looks_degenerate(answer: str) -> bool:
    numbers = re.findall(r"\b\d{1,5}\b", answer)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z/-]{2,}\b", answer)
    return len(numbers) >= 80 and len(words) < 25


def load_model(base_model: str, adapter: Path):
    if not torch.cuda.is_available():
        raise RuntimeError("GPU not detected. In Colab, use Runtime > Change runtime type > GPU.")

    tokenizer = AutoTokenizer.from_pretrained(adapter, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return model, tokenizer


def build_generator(model, tokenizer, max_new_tokens: int, max_input_tokens: int):
    def generate(prompt: str) -> dict[str, str]:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        prompt_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(
            prompt_text,
            return_tensors="pt",
            truncation=True,
            max_length=max_input_tokens,
        ).to(model.device)
        try:
            with torch.inference_mode():
                output = model.generate(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    use_cache=True,
                    pad_token_id=tokenizer.eos_token_id,
                )
            generated = output[0][inputs["input_ids"].shape[-1] :]
            answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
            if looks_degenerate(answer):
                answer = (
                    "Fine-tuned LoRA generated invalid numeric/debug-style output. "
                    "Restart the Colab runtime and serve with lower limits, for example "
                    "--max-input-tokens 2048 --max-new-tokens 1800."
                )
            return {"answer": answer}
        except torch.cuda.OutOfMemoryError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return {
                "answer": (
                    "Fine-tuned LoRA endpoint ran out of GPU memory. Restart the Colab runtime "
                    "and serve with lower limits, for example: --max-input-tokens 3072 "
                    "--max-new-tokens 2500."
                )
            }

    return generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a Qwen LoRA adapter with Gradio.")
    parser.add_argument("--adapter", type=Path, default=Path("qwen_safety_lora"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=3000)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    args = parser.parse_args()

    model, tokenizer = load_model(args.base_model, args.adapter)
    generate = build_generator(model, tokenizer, args.max_new_tokens, args.max_input_tokens)

    app = gr.Interface(
        fn=generate,
        inputs=gr.Textbox(label="Prompt", lines=8),
        outputs=gr.JSON(label="Response"),
        title="Qwen Safety LoRA Endpoint",
        api_name="generate",
    )
    app.launch(share=True, debug=False)


if __name__ == "__main__":
    main()
