# Model Evaluation

This folder evaluates the three app model paths:

- `openai`: OpenAI advanced model
- `local_base`: local Qwen before fine-tuning
- `local_lora`: local Qwen after LoRA fine-tuning

The evaluator is intentionally safety-case specific. It checks the failures that
matter for this project:

- missing required answer sections,
- weak or missing HARA,
- missing ISO 26262 Part 2-9 lifecycle coverage,
- shallow ISO 21448 (SOTIF) triggering-condition analysis,
- shallow ISO 8800 AI/data/model assurance,
- generic engineering recommendations,
- hallucination risk, especially unsupported exact ISO clause claims.

## Quick Run

Evaluate the two free/local paths:

```bash
python evaluation/evaluate_models.py --models local_base local_lora --limit 2
```

By default, each run also adds 2 random unseen automotive systems.
Use `--random-cases 0` if you want only the fixed benchmark questions.

Evaluate all three model paths:

```bash
python evaluation/evaluate_models.py --models openai local_base local_lora --limit 2
```

Generate random unseen automotive systems in the same run:

```bash
python evaluation/evaluate_models.py \
  --models local_base local_lora \
  --limit 2 \
  --random-cases 2
```

Use a seed when you want the random cases to be reproducible:

```bash
python evaluation/evaluate_models.py \
  --models openai local_base local_lora \
  --random-cases 2 \
  --seed 42
```

Add OpenAI LLM-as-judge hallucination and faithfulness scoring:

```bash
python evaluation/evaluate_models.py \
  --models openai local_base local_lora \
  --limit 2 \
  --llm-judge
```

## Outputs

The script writes:

```text
evaluation/results/model_eval_YYYYMMDD_HHMMSS.csv
evaluation/results/model_eval_YYYYMMDD_HHMMSS.md
evaluation/results/answers_YYYYMMDD_HHMMSS/*.md
evaluation/results/plots_YYYYMMDD_HHMMSS/*.svg
evaluation/results/generated_random_cases_YYYYMMDD_HHMMSS.jsonl
```

Use the CSV for charts and the Markdown report for presentation screenshots.
The SVG plots are generated without extra plotting dependencies.

Generated plots:

- `score_comparison.svg`: grouped percentage score by model and question.
- `rubric_heatmap.svg`: category-level rubric score heatmap, including hallucination control.

## Score Meaning

The deterministic rubric is normalized to a percentage out of 100% in the CSV
and Markdown report. The raw rubric totals 110 points:

| Category | Points |
|---|---:|
| Required sections | 20 |
| HARA quality | 20 |
| ISO 26262 lifecycle | 20 |
| ISO 21448 (SOTIF) depth | 15 |
| ISO 8800 depth | 15 |
| Engineering specificity | 10 |
| Hallucination control | 10 |

Example:

```text
Score: 93.6%
Raw score: 103/110
```

The optional LLM judge adds separate 0-10 scores for:

- faithfulness,
- hallucination risk,
- engineering quality.

These are separate from the deterministic score so you can explain both:

1. deterministic safety-schema checks,
2. LLM-as-judge semantic assessment.

## Hallucination Checks

The deterministic hallucination score flags:

- exact `clause x.y` claims not found in retrieved context,
- ISO clause-like claims not supported by retrieved context,
- over-certain compliance wording,
- missing assumptions/evidence limitations.

This is not a legal compliance validator. It is a practical guard against
polished but unsupported standards claims.
