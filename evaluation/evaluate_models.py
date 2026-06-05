"""Run model evaluations for the Autonomous Driving Safety Analyst app.

Examples:
    python evaluation/evaluate_models.py --models local_base
    python evaluation/evaluate_models.py --models local_base local_lora --limit 2
    python evaluation/evaluate_models.py --models openai local_base local_lora --llm-judge
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from langchain_openai import ChatOpenAI

from agent.agent import (
    _retrieve_local_draft_context,
    _review_lifecycle_answer,
    build_agent,
    is_degenerate_model_answer,
    run_finetuned_lora_answer,
    run_open_source_draft_answer,
)
from config import cfg
from evaluation.rubric import evaluate_answer


MODEL_LABELS = {
    "openai": "OpenAI - advanced analysis",
    "local_base": "Local Qwen - before fine-tuning",
    "local_lora": "Local Qwen - after LoRA fine-tuning",
}
MAX_RUBRIC_SCORE = 110
DEFAULT_EXPECTED_SECTIONS = [
    "Opening Map",
    "Item Definition",
    "Functional Decomposition",
    "HARA Screening",
    "Safety Goals, Functional Safety Concept, and Technical Safety Concept",
    "ISO 26262 Part 2-9 Lifecycle Assessment",
    "ISO 21448 (SOTIF) Function Analysis",
    "ISO 8800 Function Assurance",
    "Verification and Validation Matrix",
    "Production and Operation Controls",
    "Worst-Case Scenario",
    "Final Safety Argument",
]

RUBRIC_COLUMNS = [
    ("required_sections", "Sections", 20),
    ("hara_quality", "HARA", 20),
    ("iso26262_lifecycle", "ISO 26262", 20),
    ("sotif_depth", "SOTIF", 15),
    ("iso8800_depth", "ISO 8800", 15),
    ("engineering_specificity", "Engineering", 10),
    ("hallucination_control", "Hallucination", 10),
]

RANDOM_SYSTEMS = [
    {
        "name": "blind spot monitoring system",
        "functions": "side object detection, relative velocity estimation, blind-zone occupancy, driver warning, interface output",
        "odd": "urban and highway lane changes, day/night, moderate rain",
    },
    {
        "name": "rear cross traffic alert system",
        "functions": "cross-traffic detection, object classification, TTC estimation, warning arbitration, driver HMI output",
        "odd": "parking lots and low-speed reversing, occluded vehicles and pedestrians",
    },
    {
        "name": "traffic sign recognition system",
        "functions": "sign detection, sign classification, map cross-check, confidence output, HMI speed-limit display",
        "odd": "urban, rural, and highway roads with regional sign variants",
    },
    {
        "name": "automated parking assist system",
        "functions": "slot detection, free-space estimation, obstacle detection, trajectory generation, low-speed control handoff",
        "odd": "parking lots, garages, marked and unmarked spaces, low speed",
    },
    {
        "name": "driver monitoring system",
        "functions": "gaze estimation, eyelid monitoring, distraction detection, takeover readiness assessment, HMI alerting",
        "odd": "L2/L3 highway operation with day/night cabin lighting and eyewear variation",
    },
    {
        "name": "emergency lane keeping system",
        "functions": "lane boundary detection, road-edge detection, adjacent-object detection, intervention decision, steering request output",
        "odd": "highway and rural roads with faded markings and road-edge uncertainty",
    },
    {
        "name": "sensor fusion object tracking system",
        "functions": "camera/radar/LiDAR association, track initiation, track maintenance, confidence output, stale-data rejection",
        "odd": "urban and highway operation with mixed traffic and partial occlusion",
    },
    {
        "name": "minimal-risk maneuver controller",
        "functions": "failure detection, fallback trajectory selection, hazard-light request, controlled deceleration, safe-stop confirmation",
        "odd": "L3 highway pilot fallback after perception or actuator degradation",
    },
    {
        "name": "camera-based cyclist detection system",
        "functions": "cyclist detection, posture classification, trajectory prediction, occlusion handling, AEB/planning interface output",
        "odd": "urban intersections, bike lanes, night, rain, glare, partial occlusion",
    },
    {
        "name": "radar perception system for adaptive cruise control",
        "functions": "lead-vehicle detection, range estimation, relative velocity estimation, cut-in detection, object-track confidence",
        "odd": "highways and arterial roads with moderate to dense traffic",
    },
]


def load_questions(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
    return rows


def generate_random_questions(count: int, rng: random.Random) -> list[dict[str, Any]]:
    """Generate unseen automotive assistant systems for robustness evaluation."""
    cases: list[dict[str, Any]] = []
    selected = [rng.choice(RANDOM_SYSTEMS) for _ in range(count)]
    for index, system in enumerate(selected, start=1):
        scenario = rng.choice(
            [
                "include a worst-case scenario involving low visibility and partial occlusion",
                "include a supplier ECU boundary and production/service evidence",
                "include degraded sensor performance and an ODD restriction decision",
                "include an OTA update and regression-release decision",
                "include a near-miss field incident and validation evidence",
            ]
        )
        case_id = re_safe_id(f"random_{system['name']}_{index}")
        question = (
            f"Create a complete safety lifecycle and item safety case for a {system['name']} "
            "according to ISO 26262, ISO 21448 (SOTIF), and ISO 8800. "
            f"The main functions are: {system['functions']}. "
            f"Assume the ODD is: {system['odd']}. "
            f"Also {scenario}. Make it detailed, engineering-specific, and include function-level HARA."
        )
        cases.append(
            {
                "id": case_id,
                "question": question,
                "selected_standards": ["ISO 26262", "ISO 21448 (SOTIF)", "ISO 8800"],
                "expected_sections": DEFAULT_EXPECTED_SECTIONS,
                "generated": True,
                "system_name": system["name"],
            }
        )
    return cases


def re_safe_id(value: str) -> str:
    """Convert arbitrary text to a stable file/id-safe slug."""
    import re

    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def scoped_prompt(question: str, selected_standards: list[str]) -> str:
    standards = ", ".join(selected_standards) if selected_standards else "ISO 26262, ISO 21448 (SOTIF), ISO 8800"
    return (
        f"Evaluate the request according to these selected standards only: {standards}.\n"
        "If a selected standard is not relevant, say why. If an unselected standard is useful context, mention it only as context.\n\n"
        f"User request:\n{question}"
    )


def run_model(model_key: str, prompt: str, openai_agent=None) -> str:
    if model_key == "openai":
        agent = openai_agent or build_agent()
        result = agent.invoke({"input": prompt})
        return _review_lifecycle_answer(prompt, result["output"])
    if model_key == "local_base":
        return run_open_source_draft_answer(prompt)
    if model_key == "local_lora":
        return run_finetuned_lora_answer(prompt)
    raise ValueError(f"Unknown model key: {model_key}")


def llm_judge_answer(question: str, answer: str, retrieved_context: str) -> dict[str, Any]:
    """Optional LLM-as-judge for faithfulness and hallucination risk."""
    judge = ChatOpenAI(
        model=cfg.LLM_MODEL,
        temperature=0,
        openai_api_key=cfg.OPENAI_API_KEY,
    )
    prompt = f"""
You are evaluating an autonomous-driving safety standards answer.

Return strict JSON only with these keys:
- faithfulness_score: integer 0-10
- hallucination_risk_score: integer 0-10 where 10 means low hallucination risk
- engineering_quality_score: integer 0-10
- unsupported_claims: list of short strings
- comments: short string

Penalize invented exact ISO clause numbers, unsupported standard requirements,
overconfident ASIL ratings without assumptions, and claims not supported by the
retrieved context.

Question:
{question}

Retrieved context:
{retrieved_context[:12000]}

Answer:
{answer[:16000]}
"""
    response = judge.invoke([("human", prompt)])
    content = getattr(response, "content", "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "faithfulness_score": None,
            "hallucination_risk_score": None,
            "engineering_quality_score": None,
            "unsupported_claims": [],
            "comments": f"Judge returned non-JSON: {content[:300]}",
        }


def svg_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def model_color(model_key: str) -> str:
    colors = {
        "openai": "#ffffff",
        "local_base": "#9fb7ff",
        "local_lora": "#7fffe1",
    }
    return colors.get(model_key, "#d8dee9")


def write_score_chart(results: list[dict[str, Any]], path: Path) -> None:
    """Write grouped score-percent bar chart as SVG."""
    question_ids = list(dict.fromkeys(row["question_id"] for row in results))
    models = list(dict.fromkeys(row["model_key"] for row in results))
    width = max(920, 180 + 180 * len(question_ids))
    height = 430
    left, top, chart_h = 90, 70, 260
    group_w = (width - left - 40) / max(1, len(question_ids))
    bar_w = min(34, (group_w - 28) / max(1, len(models)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#05070a"/>',
        '<text x="28" y="34" fill="#ffffff" font-size="22" font-family="Arial" font-weight="700">Model Score Comparison</text>',
    ]
    for tick in range(0, 101, 20):
        y = top + chart_h - (tick / 100) * chart_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-30}" y2="{y:.1f}" stroke="#29313d" stroke-width="1"/>')
        parts.append(f'<text x="42" y="{y+5:.1f}" fill="#aeb7c8" font-size="12" font-family="Arial">{tick}%</text>')
    lookup = {(row["question_id"], row["model_key"]): row for row in results}
    for qi, question_id in enumerate(question_ids):
        gx = left + qi * group_w + 18
        for mi, model in enumerate(models):
            row = lookup.get((question_id, model))
            if not row:
                continue
            value = float(row["score_percent"])
            bar_h = (value / 100) * chart_h
            x = gx + mi * (bar_w + 8)
            y = top + chart_h - bar_h
            color = model_color(model)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" fill="{color}" opacity="0.9"/>')
            parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y-6:.1f}" fill="#ffffff" font-size="11" font-family="Arial" text-anchor="middle">{value:.1f}</text>')
        label = question_id[:24] + ("..." if len(question_id) > 24 else "")
        parts.append(f'<text x="{gx:.1f}" y="{top+chart_h+34}" fill="#cfd6e6" font-size="12" font-family="Arial">{svg_text(label)}</text>')
    legend_x = width - 360
    for index, model in enumerate(models):
        y = 28 + index * 22
        parts.append(f'<rect x="{legend_x}" y="{y-12}" width="14" height="14" rx="3" fill="{model_color(model)}"/>')
        parts.append(f'<text x="{legend_x+22}" y="{y}" fill="#dce3f2" font-size="12" font-family="Arial">{svg_text(MODEL_LABELS[model])}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_rubric_heatmap(results: list[dict[str, Any]], path: Path) -> None:
    """Write category-level heatmap as SVG."""
    rows = results
    cell_w, cell_h = 116, 32
    left, top = 250, 72
    width = left + cell_w * len(RUBRIC_COLUMNS) + 30
    height = top + cell_h * len(rows) + 70
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#05070a"/>',
        '<text x="28" y="34" fill="#ffffff" font-size="22" font-family="Arial" font-weight="700">Rubric Category Heatmap</text>',
    ]
    for ci, (_, label, _) in enumerate(RUBRIC_COLUMNS):
        x = left + ci * cell_w
        parts.append(f'<text x="{x+cell_w/2}" y="{top-18}" fill="#cfd6e6" font-size="12" font-family="Arial" text-anchor="middle">{svg_text(label)}</text>')
    for ri, row in enumerate(rows):
        y = top + ri * cell_h
        label = f"{row['question_id']} | {row['model_key']}"
        label = label[:34] + ("..." if len(label) > 34 else "")
        parts.append(f'<text x="24" y="{y+21}" fill="#dce3f2" font-size="12" font-family="Arial">{svg_text(label)}</text>')
        for ci, (key, _, max_value) in enumerate(RUBRIC_COLUMNS):
            value = float(row[key])
            pct = max(0.0, min(1.0, value / max_value))
            red = int(255 * (1 - pct))
            green = int(170 + 70 * pct)
            blue = int(120 + 90 * pct)
            color = f"rgb({red},{green},{blue})"
            x = left + ci * cell_w
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-5}" height="{cell_h-5}" rx="5" fill="{color}" opacity="0.9"/>')
            parts.append(f'<text x="{x+(cell_w-5)/2}" y="{y+19}" fill="#061018" font-size="12" font-family="Arial" font-weight="700" text-anchor="middle">{int(value)}/{max_value}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_plots(results: list[dict[str, Any]], output_dir: Path, timestamp: str) -> list[Path]:
    plot_dir = output_dir / f"plots_{timestamp}"
    plot_dir.mkdir(parents=True, exist_ok=True)
    score_path = plot_dir / "score_comparison.svg"
    heatmap_path = plot_dir / "rubric_heatmap.svg"
    write_score_chart(results, score_path)
    write_rubric_heatmap(results, heatmap_path)
    return [score_path, heatmap_path]



def write_markdown_report(results: list[dict[str, Any]], path: Path, plot_paths: list[Path] | None = None) -> None:
    lines = ["# Model Evaluation Report", ""]
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    if plot_paths:
        lines.append("## Plots")
        lines.append("")
        for plot_path in plot_paths:
            relative = plot_path.relative_to(path.parent)
            title = plot_path.stem.replace("_", " ").title()
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"![{title}]({relative.as_posix()})")
            lines.append("")
    lines.append("| Question ID | Model | Score | Raw | Hallucination | HARA | ISO 26262 | SOTIF | ISO 8800 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in results:
        lines.append(
            "| {question_id} | {model_label} | {score_percent}% | {raw_total}/{max_score} | {hallucination_control} | "
            "{hara_quality} | {iso26262_lifecycle} | {sotif_depth} | {iso8800_depth} |".format(**row)
        )
    lines.append("")

    for row in results:
        lines.append(f"## {row['question_id']} - {row['model_label']}")
        lines.append("")
        lines.append(f"- Score: {row['score_percent']}%")
        lines.append(f"- Raw score: {row['raw_total']}/{row['max_score']}")
        lines.append(f"- Missing items: {row['missing_items'] or 'None'}")
        lines.append(f"- Hallucination flags: {row['hallucination_flags'] or 'None'}")
        if row.get("judge_comments"):
            lines.append(f"- Judge comments: {row['judge_comments']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OpenAI/base Qwen/LoRA Qwen answers.")
    parser.add_argument("--questions", type=Path, default=PROJECT_DIR / "evaluation" / "test_questions.jsonl")
    parser.add_argument("--models", nargs="+", choices=MODEL_LABELS, default=["local_base", "local_lora"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--random-cases",
        type=int,
        default=2,
        help="Generate N random unseen automotive systems. Use 0 to disable.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for generated cases.")
    parser.add_argument("--no-plots", action="store_true", help="Skip SVG plot generation.")
    parser.add_argument("--llm-judge", action="store_true", help="Use OpenAI as a faithfulness/hallucination judge.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "evaluation" / "results")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    answers_dir = args.output_dir / f"answers_{timestamp}"
    answers_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(args.questions, args.limit)
    if args.random_cases:
        rng = random.Random(args.seed)
        random_questions = generate_random_questions(args.random_cases, rng)
        questions.extend(random_questions)
        generated_path = args.output_dir / f"generated_random_cases_{timestamp}.jsonl"
        with generated_path.open("w", encoding="utf-8") as file:
            for row in random_questions:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Saved generated random cases: {generated_path}")
    openai_agent = build_agent() if "openai" in args.models else None
    results: list[dict[str, Any]] = []

    for question_row in questions:
        question_id = question_row["id"]
        prompt = scoped_prompt(question_row["question"], question_row.get("selected_standards", []))
        expected_sections = question_row.get("expected_sections", [])
        retrieved_context = _retrieve_local_draft_context(prompt)

        for model_key in args.models:
            print(f"Evaluating {question_id} with {MODEL_LABELS[model_key]}...")
            try:
                answer = run_model(model_key, prompt, openai_agent=openai_agent)
                error = ""
                if is_degenerate_model_answer(answer):
                    error = (
                        "InvalidGeneration: model returned a numeric/debug-style output "
                        "instead of a safety analysis."
                    )
                    answer = ""
            except Exception as exc:
                answer = ""
                error = f"{type(exc).__name__}: {exc}"

            answer_path = answers_dir / f"{question_id}__{model_key}.md"
            answer_path.write_text(answer or error, encoding="utf-8")

            rubric = evaluate_answer(answer, retrieved_context, expected_sections)
            row = {
                "question_id": question_id,
                "model_key": model_key,
                "model_label": MODEL_LABELS[model_key],
                "answer_path": str(answer_path.relative_to(PROJECT_DIR)),
                "error": error,
                **rubric.to_dict(),
            }
            row["raw_total"] = row.pop("total")
            row["max_score"] = MAX_RUBRIC_SCORE
            row["score_percent"] = round((row["raw_total"] / MAX_RUBRIC_SCORE) * 100, 1)

            if args.llm_judge and answer and not error:
                judge = llm_judge_answer(prompt, answer, retrieved_context)
                row.update(
                    {
                        "judge_faithfulness": judge.get("faithfulness_score"),
                        "judge_hallucination_risk": judge.get("hallucination_risk_score"),
                        "judge_engineering_quality": judge.get("engineering_quality_score"),
                        "judge_unsupported_claims": judge.get("unsupported_claims", []),
                        "judge_comments": judge.get("comments", ""),
                    }
                )
            else:
                row.update(
                    {
                        "judge_faithfulness": "",
                        "judge_hallucination_risk": "",
                        "judge_engineering_quality": "",
                        "judge_unsupported_claims": [],
                        "judge_comments": "",
                    }
                )

            results.append(row)

    csv_path = args.output_dir / f"model_eval_{timestamp}.csv"
    fieldnames = [
        "question_id",
        "model_key",
        "model_label",
        "score_percent",
        "raw_total",
        "max_score",
        "required_sections",
        "hara_quality",
        "iso26262_lifecycle",
        "sotif_depth",
        "iso8800_depth",
        "engineering_specificity",
        "hallucination_control",
        "missing_items",
        "hallucination_flags",
        "judge_faithfulness",
        "judge_hallucination_risk",
        "judge_engineering_quality",
        "judge_unsupported_claims",
        "judge_comments",
        "answer_path",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            csv_row = row.copy()
            for key in ("missing_items", "hallucination_flags", "judge_unsupported_claims"):
                csv_row[key] = json.dumps(csv_row.get(key, []), ensure_ascii=False)
            writer.writerow({field: csv_row.get(field, "") for field in fieldnames})

    plot_paths = [] if args.no_plots else write_plots(results, args.output_dir, timestamp)
    md_path = args.output_dir / f"model_eval_{timestamp}.md"
    write_markdown_report(results, md_path, plot_paths=plot_paths)
    print(f"Saved CSV: {csv_path}")
    print(f"Saved report: {md_path}")
    print(f"Saved answers: {answers_dir}")
    if plot_paths:
        print("Saved plots:")
        for plot_path in plot_paths:
            print(f"  {plot_path}")


if __name__ == "__main__":
    main()
