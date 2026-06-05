"""Evaluate OpenAI video + standards retrieval answers.

This is a separate demo/evaluation track for the paid version selling point:
OpenAI can combine the video transcript DB with ISO standards reasoning.

Example:
    python evaluation/evaluate_video_standard.py --limit 2
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agent.agent import build_agent, search_iso_standards, search_video_evidence
from evaluation.rubric import detect_hallucination_flags


MAX_SCORE = 100

CRITERIA = [
    ("video_evidence", "Video Evidence", 20),
    ("video_grounding", "Video Grounding", 15),
    ("standards_integration", "Standards", 20),
    ("failure_classification", "Classification", 15),
    ("engineering_actions", "Engineering", 15),
    ("evidence_limits", "Limits", 10),
    ("hallucination_control", "Hallucination", 5),
]

VIDEO_STANDARD_CASES = [
    {
        "id": "video_failure_plus_standards",
        "question": (
            "Find relevant video evidence about an autonomous-driving perception "
            "failure, edge case, or unsafe behavior. Then analyze the observed "
            "behavior using ISO 26262, ISO 21448 (SOTIF), and ISO 8800."
        ),
    },
    {
        "id": "video_pedestrian_edge_case",
        "question": (
            "Use the video transcript database to find evidence about a pedestrian "
            "or vulnerable-road-user perception edge case. Then explain the safety "
            "issue using ISO 26262, ISO 21448 (SOTIF), and ISO 8800."
        ),
    },
    {
        "id": "video_weather_visibility_case",
        "question": (
            "Find video evidence related to bad weather, low visibility, occlusion, "
            "or sensor/perception limitations in autonomous driving. Connect the "
            "case to ISO 26262 malfunction risk, SOTIF triggering conditions, and "
            "ISO 8800 data/model assurance."
        ),
    },
]


@dataclass
class VideoStandardScore:
    video_evidence: int
    video_grounding: int
    standards_integration: int
    failure_classification: int
    engineering_actions: int
    evidence_limits: int
    hallucination_control: int
    total: int
    missing_items: list[str]
    hallucination_flags: list[str]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def svg_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def score_video_standard_answer(answer: str, retrieved_context: str) -> VideoStandardScore:
    text = normalize(answer)
    missing: list[str] = []

    video_terms = (
        "video evidence",
        "video",
        "title",
        "channel",
        "timestamp",
        "transcript",
    )
    video_hits = sum(term in text for term in video_terms)
    video_evidence = min(20, video_hits * 4)
    if video_evidence < 12:
        missing.append("clear video evidence with title/channel/timestamp or transcript basis")

    grounding_checks = {
        "observed behavior": "observed behavior" in text or "observed issue" in text,
        "retrieved/cited evidence": "retrieved" in text or "evidence" in text,
        "not overclaimed": "limitation" in text or "not inspect" in text or "transcript" in text,
    }
    video_grounding = round(15 * sum(grounding_checks.values()) / len(grounding_checks))
    missing.extend(label for label, ok in grounding_checks.items() if not ok)

    standards_checks = {
        "ISO 26262": "iso 26262" in text,
        "ISO 21448/SOTIF": "sotif" in text or "iso 21448" in text,
        "ISO 8800": "iso 8800" in text,
        "practical standards connection": "safety goal" in text
        or "triggering condition" in text
        or "data" in text
        or "robustness" in text,
    }
    standards_integration = round(20 * sum(standards_checks.values()) / len(standards_checks))
    missing.extend(label for label, ok in standards_checks.items() if not ok)

    classification_checks = {
        "malfunction": "malfunction" in text or "fault" in text,
        "SOTIF limitation": "limitation" in text or "triggering condition" in text,
        "AI/data/model": "data" in text or "model" in text or "uncertainty" in text,
        "mixed or separated risk": "mixed" in text or "primary" in text or "separate" in text,
    }
    failure_classification = round(15 * sum(classification_checks.values()) / len(classification_checks))
    missing.extend(label for label, ok in classification_checks.items() if not ok)

    engineering_checks = {
        "recommended actions": "recommended" in text or "engineering action" in text,
        "validation/testing": "validation" in text or "test" in text,
        "ODD/fallback/monitoring": "odd" in text or "fallback" in text or "monitoring" in text,
        "measurable evidence": "evidence" in text or "acceptance criterion" in text or "metric" in text,
    }
    engineering_actions = round(15 * sum(engineering_checks.values()) / len(engineering_checks))
    missing.extend(label for label, ok in engineering_checks.items() if not ok)

    limits_checks = {
        "evidence limitations": "evidence and limitations" in text or "limitations" in text,
        "assumptions": "assumption" in text or "unknown" in text,
    }
    evidence_limits = round(10 * sum(limits_checks.values()) / len(limits_checks))
    missing.extend(label for label, ok in limits_checks.items() if not ok)

    flags = detect_hallucination_flags(answer, retrieved_context)
    hallucination_control = max(0, 5 - len(flags))

    total = (
        video_evidence
        + video_grounding
        + standards_integration
        + failure_classification
        + engineering_actions
        + evidence_limits
        + hallucination_control
    )

    return VideoStandardScore(
        video_evidence=video_evidence,
        video_grounding=video_grounding,
        standards_integration=standards_integration,
        failure_classification=failure_classification,
        engineering_actions=engineering_actions,
        evidence_limits=evidence_limits,
        hallucination_control=hallucination_control,
        total=total,
        missing_items=missing,
        hallucination_flags=flags,
    )


def build_prompt(question: str) -> str:
    return f"""
This is a paid-tier demo of video + standards RAG.

User request:
{question}

Your answer must include:
1. Video evidence with title, channel, and timestamp if retrieved metadata provides it
2. Observed behavior from the retrieved transcript evidence
3. Failure classification: ISO 26262 malfunction, ISO 21448 (SOTIF) limitation,
   ISO 8800 AI/data/model risk, or mixed
4. ISO 26262 interpretation
5. ISO 21448 (SOTIF) interpretation
6. ISO 8800 interpretation
7. Recommended engineering actions
8. Evidence and limitations

Use retrieved video and standards evidence. Do not invent exact ISO clause
numbers if the retrieved evidence does not provide them.
""".strip()


def build_retrieved_context(question: str) -> str:
    """Collect the same evidence families being evaluated."""
    video = search_video_evidence(question)
    standards = search_iso_standards(question)
    return f"## Video Retrieval Context\n{video}\n\n## Standards Retrieval Context\n{standards}"


def write_score_chart(results: list[dict[str, Any]], path: Path) -> None:
    width, height = 920, 420
    left, top, chart_h = 86, 70, 260
    bar_w = 70
    gap = 58
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#05070a"/>',
        '<text x="28" y="36" fill="#ffffff" font-size="22" font-family="Arial" font-weight="700">OpenAI Video + Standards RAG Score</text>',
    ]
    for tick in range(0, 101, 20):
        y = top + chart_h - (tick / 100) * chart_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-30}" y2="{y:.1f}" stroke="#29313d"/>')
        parts.append(f'<text x="42" y="{y+5:.1f}" fill="#aeb7c8" font-size="12" font-family="Arial">{tick}%</text>')
    start_x = left + 52
    for i, row in enumerate(results):
        value = float(row["score_percent"])
        bar_h = (value / 100) * chart_h
        x = start_x + i * (bar_w + gap)
        y = top + chart_h - bar_h
        parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" rx="6" fill="#7fffe1" opacity="0.92"/>')
        parts.append(f'<text x="{x+bar_w/2}" y="{y-8:.1f}" fill="#ffffff" font-size="13" font-family="Arial" font-weight="700" text-anchor="middle">{value:.1f}%</text>')
        label = row["case_id"][:22] + ("..." if len(row["case_id"]) > 22 else "")
        parts.append(f'<text x="{x+bar_w/2}" y="{top+chart_h+34}" fill="#cfd6e6" font-size="12" font-family="Arial" text-anchor="middle">{svg_text(label)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_criteria_heatmap(results: list[dict[str, Any]], path: Path) -> None:
    cell_w, cell_h = 128, 36
    left, top = 230, 76
    width = left + cell_w * len(CRITERIA) + 30
    height = top + cell_h * len(results) + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#05070a"/>',
        '<text x="28" y="36" fill="#ffffff" font-size="22" font-family="Arial" font-weight="700">Video + Standards Rubric Heatmap</text>',
    ]
    for ci, (_, label, _) in enumerate(CRITERIA):
        x = left + ci * cell_w
        parts.append(f'<text x="{x+cell_w/2}" y="{top-18}" fill="#cfd6e6" font-size="12" font-family="Arial" text-anchor="middle">{svg_text(label)}</text>')
    for ri, row in enumerate(results):
        y = top + ri * cell_h
        label = row["case_id"][:28] + ("..." if len(row["case_id"]) > 28 else "")
        parts.append(f'<text x="24" y="{y+23}" fill="#dce3f2" font-size="12" font-family="Arial">{svg_text(label)}</text>')
        for ci, (key, _, max_value) in enumerate(CRITERIA):
            value = float(row[key])
            pct = max(0.0, min(1.0, value / max_value))
            red = int(255 * (1 - pct))
            green = int(170 + 70 * pct)
            blue = int(120 + 90 * pct)
            x = left + ci * cell_w
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-5}" height="{cell_h-5}" rx="5" fill="rgb({red},{green},{blue})" opacity="0.92"/>')
            parts.append(f'<text x="{x+(cell_w-5)/2}" y="{y+22}" fill="#061018" font-size="12" font-family="Arial" font-weight="700" text-anchor="middle">{int(value)}/{max_value}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_markdown_report(results: list[dict[str, Any]], path: Path, plot_paths: list[Path]) -> None:
    lines = ["# OpenAI Video + Standards Evaluation", ""]
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("This evaluates the paid-tier capability: combining video transcript evidence with ISO standards reasoning.")
    lines.append("")
    for plot in plot_paths:
        rel = plot.relative_to(path.parent)
        title = plot.stem.replace("_", " ").title()
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"![{title}]({rel.as_posix()})")
        lines.append("")
    lines.append("| Case | Score | Video Evidence | Standards | Classification | Engineering | Hallucination |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in results:
        lines.append(
            f"| {row['case_id']} | {row['score_percent']}% | {row['video_evidence']}/20 | "
            f"{row['standards_integration']}/20 | {row['failure_classification']}/15 | "
            f"{row['engineering_actions']}/15 | {row['hallucination_control']}/5 |"
        )
    lines.append("")
    for row in results:
        lines.append(f"## {row['case_id']}")
        lines.append("")
        lines.append(f"- Score: {row['score_percent']}%")
        lines.append(f"- Missing items: {row['missing_items'] or 'None'}")
        lines.append(f"- Hallucination flags: {row['hallucination_flags'] or 'None'}")
        lines.append(f"- Answer: `{row['answer_path']}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OpenAI video + standards RAG answers.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "evaluation" / "results")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    answers_dir = args.output_dir / f"video_standard_answers_{timestamp}"
    plot_dir = args.output_dir / f"video_standard_plots_{timestamp}"
    answers_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    cases = VIDEO_STANDARD_CASES[: args.limit] if args.limit else VIDEO_STANDARD_CASES
    agent = build_agent()
    results: list[dict[str, Any]] = []

    for case in cases:
        print(f"Evaluating OpenAI video + standards RAG: {case['id']}...")
        prompt = build_prompt(case["question"])
        retrieved_context = build_retrieved_context(case["question"])
        try:
            answer = agent.invoke({"input": prompt})["output"]
            error = ""
        except Exception as exc:
            answer = ""
            error = f"{type(exc).__name__}: {exc}"

        answer_path = answers_dir / f"{case['id']}__openai_video_standard.md"
        answer_path.write_text(answer or error, encoding="utf-8")
        score = score_video_standard_answer(answer, retrieved_context)
        row = {
            "case_id": case["id"],
            "question": case["question"],
            "answer_path": str(answer_path.relative_to(PROJECT_DIR)),
            "error": error,
            **asdict(score),
        }
        row["score_percent"] = round((row["total"] / MAX_SCORE) * 100, 1)
        results.append(row)

    csv_path = args.output_dir / f"video_standard_eval_{timestamp}.csv"
    fieldnames = [
        "case_id",
        "score_percent",
        "total",
        "video_evidence",
        "video_grounding",
        "standards_integration",
        "failure_classification",
        "engineering_actions",
        "evidence_limits",
        "hallucination_control",
        "missing_items",
        "hallucination_flags",
        "answer_path",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            output = row.copy()
            output["missing_items"] = json.dumps(output["missing_items"], ensure_ascii=False)
            output["hallucination_flags"] = json.dumps(output["hallucination_flags"], ensure_ascii=False)
            writer.writerow({field: output.get(field, "") for field in fieldnames})

    score_path = plot_dir / "video_standard_score.svg"
    heatmap_path = plot_dir / "video_standard_heatmap.svg"
    write_score_chart(results, score_path)
    write_criteria_heatmap(results, heatmap_path)
    md_path = args.output_dir / f"video_standard_eval_{timestamp}.md"
    write_markdown_report(results, md_path, [score_path, heatmap_path])

    print(f"Saved CSV: {csv_path}")
    print(f"Saved report: {md_path}")
    print(f"Saved answers: {answers_dir}")
    print(f"Saved plots: {score_path}, {heatmap_path}")


if __name__ == "__main__":
    main()
