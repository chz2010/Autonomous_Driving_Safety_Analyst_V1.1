"""Evaluation rubric for Autonomous Driving Safety Analyst model outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


ISO26262_PARTS = [f"part {number}" for number in range(2, 10)]
GENERIC_PHRASES = (
    "improve robustness",
    "ensure data quality",
    "perform testing",
    "validate the model",
    "monitor performance",
    "add redundancy",
)


@dataclass
class RubricResult:
    required_sections: int
    hara_quality: int
    iso26262_lifecycle: int
    sotif_depth: int
    iso8800_depth: int
    engineering_specificity: int
    hallucination_control: int
    total: int
    missing_items: list[str]
    hallucination_flags: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def section_present(answer: str, label: str) -> bool:
    text = normalize(answer)
    label_text = normalize(label)
    if label_text in text:
        return True
    aliases = {
        "iso 26262 part 2-9 lifecycle assessment": ("part 2", "part 9"),
        "iso 21448 (sotif) function analysis": ("sotif", "triggering condition"),
        "iso 8800 function assurance": ("iso 8800", "data", "robustness"),
        "verification and validation matrix": ("verification", "validation"),
        "production and operation controls": ("production", "operation"),
    }
    terms = aliases.get(label_text)
    return bool(terms and all(term in text for term in terms))


def score_required_sections(answer: str, expected_sections: list[str]) -> tuple[int, list[str]]:
    missing = [section for section in expected_sections if not section_present(answer, section)]
    if not expected_sections:
        return 20, []
    score = round(20 * (len(expected_sections) - len(missing)) / len(expected_sections))
    return max(0, min(20, score)), missing


def score_hara(answer: str) -> tuple[int, list[str]]:
    text = normalize(answer)
    missing: list[str] = []
    score = 0
    if "hara" in text:
        score += 4
    else:
        missing.append("HARA section")
    if "|" in answer and "asil" in text:
        score += 4
    else:
        missing.append("HARA markdown table with ASIL/QM")
    if re.search(r"\bS[0-3]\b", answer) and re.search(r"\bE[0-4]\b", answer) and re.search(r"\bC[0-3]\b", answer):
        score += 4
    else:
        missing.append("S/E/C ratings")
    if "rationale" in text or "because" in text:
        score += 4
    else:
        missing.append("S/E/C rationale")
    if "qm" in text or re.search(r"\basil\s+[abcd]\b", text):
        score += 4
    else:
        missing.append("ASIL/QM outcome")
    return score, missing


def score_iso26262_lifecycle(answer: str) -> tuple[int, list[str]]:
    text = normalize(answer)
    missing = [part.title() for part in ISO26262_PARTS if part not in text]
    score = round(20 * (len(ISO26262_PARTS) - len(missing)) / len(ISO26262_PARTS))
    lifecycle_terms = ("system", "hardware", "software", "production", "operation", "supporting", "dependent")
    if not all(term in text for term in ("system", "hardware", "software")):
        score = min(score, 12)
        missing.append("system/hardware/software specificity")
    if not any(term in text for term in lifecycle_terms):
        score = min(score, 8)
    return max(0, min(20, score)), missing


def score_sotif(answer: str) -> tuple[int, list[str]]:
    text = normalize(answer)
    checks = {
        "ISO 21448/SOTIF mention": "sotif" in text or "21448" in text,
        "triggering conditions": "triggering condition" in text,
        "ODD boundary/assumption": "odd" in text or "operational design domain" in text,
        "performance limitation": "performance limitation" in text or "intended function" in text,
        "residual risk/mitigation": "residual risk" in text or "mitigation" in text,
    }
    missing = [label for label, ok in checks.items() if not ok]
    return round(15 * sum(checks.values()) / len(checks)), missing


def score_iso8800(answer: str) -> tuple[int, list[str]]:
    text = normalize(answer)
    checks = {
        "ISO 8800 mention": "iso 8800" in text,
        "data requirement or dataset gap": "data" in text or "dataset" in text,
        "robustness/uncertainty": "robustness" in text or "uncertainty" in text,
        "OOD/distribution shift": "ood" in text or "distribution" in text,
        "release gate/monitoring/change control": (
            "release" in text or "monitoring" in text or "change control" in text
        ),
    }
    missing = [label for label, ok in checks.items() if not ok]
    return round(15 * sum(checks.values()) / len(checks)), missing


def score_engineering_specificity(answer: str) -> tuple[int, list[str]]:
    text = normalize(answer)
    score = 10
    missing: list[str] = []
    if len(answer) < 2500:
        score -= 3
        missing.append("answer may be too short")
    if not any(term in text for term in ("acceptance criterion", "evidence", "test case", "diagnostic", "calibration")):
        score -= 3
        missing.append("measurable evidence/test/diagnostic detail")
    if not any(term in text for term in ("safe state", "degraded", "fallback", "driver", "hmi")):
        score -= 2
        missing.append("safe-state/degraded-mode detail")
    generic_hits = [phrase for phrase in GENERIC_PHRASES if phrase in text]
    if generic_hits and not any(term in text for term in ("for example", "criterion", "within", "ms", "%")):
        score -= 2
        missing.append(f"generic wording: {', '.join(generic_hits[:3])}")
    return max(0, score), missing


def detect_hallucination_flags(answer: str, retrieved_context: str) -> list[str]:
    """Detect unsupported exact claims that commonly appear in standards answers."""
    answer_text = normalize(answer)
    context_text = normalize(retrieved_context)
    flags: list[str] = []

    clause_refs = sorted(set(re.findall(r"\b(?:clause|section)\s+\d+(?:\.\d+){1,3}\b", answer_text)))
    for ref in clause_refs:
        if ref not in context_text:
            flags.append(f"unsupported exact {ref}")

    iso_clause_refs = sorted(
        set(re.findall(r"\biso\s*(?:26262|21448|8800)[^\n.;:]{0,80}?\b\d+(?:\.\d+){1,3}\b", answer_text))
    )
    for ref in iso_clause_refs:
        number = re.search(r"\d+(?:\.\d+){1,3}", ref)
        if number and number.group(0) not in context_text:
            flags.append(f"unsupported ISO clause-like claim: {ref}")

    if "must comply with" in answer_text and not any(term in answer_text for term in ("assumption", "if", "depending")):
        flags.append("over-certain compliance wording")

    if "exact clause" in answer_text and "exact clause" not in context_text:
        flags.append("claims exact clause basis without retrieved support")

    if not any(term in answer_text for term in ("limitation", "assumption", "retrieved", "evidence")):
        flags.append("no evidence/assumption limitation stated")

    return flags


def score_hallucination_control(answer: str, retrieved_context: str) -> tuple[int, list[str]]:
    flags = detect_hallucination_flags(answer, retrieved_context)
    score = max(0, 10 - 2 * len(flags))
    return score, flags


def evaluate_answer(
    answer: str,
    retrieved_context: str,
    expected_sections: list[str],
) -> RubricResult:
    required_score, missing_sections = score_required_sections(answer, expected_sections)
    hara_score, hara_missing = score_hara(answer)
    iso_score, iso_missing = score_iso26262_lifecycle(answer)
    sotif_score, sotif_missing = score_sotif(answer)
    iso8800_score, iso8800_missing = score_iso8800(answer)
    eng_score, eng_missing = score_engineering_specificity(answer)
    hallucination_score, hallucination_flags = score_hallucination_control(answer, retrieved_context)

    total = (
        required_score
        + hara_score
        + iso_score
        + sotif_score
        + iso8800_score
        + eng_score
        + hallucination_score
    )
    missing_items = (
        missing_sections
        + hara_missing
        + iso_missing
        + sotif_missing
        + iso8800_missing
        + eng_missing
    )
    return RubricResult(
        required_sections=required_score,
        hara_quality=hara_score,
        iso26262_lifecycle=iso_score,
        sotif_depth=sotif_score,
        iso8800_depth=iso8800_score,
        engineering_specificity=eng_score,
        hallucination_control=hallucination_score,
        total=total,
        missing_items=missing_items,
        hallucination_flags=hallucination_flags,
    )
