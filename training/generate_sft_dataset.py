"""
Generate supervised fine-tuning data for the local Qwen draft model.

The goal is not to teach the model the standards from memory. The goal is to
teach response behavior:
- use retrieved evidence,
- follow the project's safety-case / HARA / lifecycle structure,
- reason separately across ISO 26262, ISO 21448 (SOTIF), and ISO 8800,
- produce engineer-friendly tables and rationale.

Output format is JSONL with ChatML-style messages, suitable for Unsloth/TRL SFT.
Generated files can contain retrieved standards text, so they are ignored by git.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from openai import OpenAI

from agent.agent import _build_local_system_prompt, _retrieve_local_draft_context
from config import cfg


TEACHER_SYSTEM_PROMPT = """You are generating ideal supervised fine-tuning answers for a local autonomous-driving safety RAG model.

Write the answer as the model should answer at inference time.
Use the retrieved context as evidence, but do not quote long copyrighted passages.
Do not claim the retrieved context is complete.
Be detailed, engineering-specific, structured, and practical.

Important behavior to demonstrate:
- Decompose the item into functions when relevant.
- If HARA is requested, evaluate every listed function or explicitly screen it out.
- Always reason Severity, Exposure, and Controllability before ASIL/QM.
- Separate ISO 26262 malfunction risk, ISO 21448 (SOTIF) performance/ODD risk, and ISO 8800 AI/data/model risk.
- For lifecycle answers, include ISO 26262 Parts 2-9, SOTIF activities, ISO 8800 activities, V&V, production/operation, residual risk, evidence and limitations.
- Include rationale, assumptions, and realistic engineering examples.
- Prefer tables where they improve readability.
"""


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {record.get("id", "") for record in read_jsonl(path)}


def build_teacher_user_prompt(prompt: str, context: str) -> str:
    return f"""User question:
{prompt}

Retrieved local evidence:
{context}

Write the ideal answer now. The answer should be suitable as a high-quality example for training the local model.
"""


def call_teacher(client: OpenAI, model: str, prompt: str, context: str) -> str:
    response = client.chat.completions.create(
        model=model,
        temperature=0.25,
        messages=[
            {"role": "system", "content": TEACHER_SYSTEM_PROMPT},
            {"role": "user", "content": build_teacher_user_prompt(prompt, context)},
        ],
    )
    return response.choices[0].message.content.strip()


def make_training_record(seed: dict, context: str, answer: str) -> dict:
    # The assistant is trained on the local-mode runtime prompt plus retrieved
    # context, matching the way the Streamlit app calls Qwen.
    user_content = f"""User question:
{seed["prompt"]}

Retrieved context:
{context}

Draft the answer now.
"""
    return {
        "id": seed["id"],
        "category": seed.get("category", "unknown"),
        "messages": [
            {"role": "system", "content": _build_local_system_prompt()},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": answer},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SFT JSONL data for Qwen LoRA.")
    parser.add_argument("--seeds", type=Path, default=PROJECT_DIR / "training" / "seed_prompts.jsonl")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "training" / "generated" / "qwen_sft.jsonl")
    parser.add_argument("--teacher-model", default=cfg.LLM_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="Optional max examples to generate.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Pause between teacher calls.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not cfg.OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is required for teacher-data generation.")

    if args.overwrite and args.out.exists():
        args.out.unlink()

    seeds = read_jsonl(args.seeds)
    if args.limit:
        seeds = seeds[: args.limit]

    done_ids = load_done_ids(args.out)
    client = OpenAI(api_key=cfg.OPENAI_API_KEY)

    for index, seed in enumerate(seeds, start=1):
        if seed["id"] in done_ids:
            print(f"[skip] {seed['id']} already generated")
            continue

        print(f"[{index}/{len(seeds)}] retrieving context for {seed['id']}")
        context = _retrieve_local_draft_context(seed["prompt"])

        print(f"[{index}/{len(seeds)}] calling teacher model for {seed['id']}")
        answer = call_teacher(client, args.teacher_model, seed["prompt"], context)

        record = make_training_record(seed, context, answer)
        append_jsonl(args.out, record)
        print(f"[write] {args.out} <- {seed['id']}")
        time.sleep(args.sleep)

    print(f"Done. Output: {args.out}")


if __name__ == "__main__":
    main()
