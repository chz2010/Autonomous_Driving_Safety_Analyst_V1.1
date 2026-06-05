"""
Terminal agent for the Autonomous Driving Safety Analyst.

The agent uses:
  - video transcript retrieval from the video Chroma DB
  - ISO standards retrieval from the standards Chroma DB
  - a focused failure-case video retrieval tool
  - conversation memory for follow-up questions
"""

from __future__ import annotations

import os
import re
import json
import logging
import subprocess
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from textwrap import shorten
from typing import Callable

import httpx

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationBufferMemory
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI

from config import cfg
from ingestion.standards_ingestion import get_retriever as get_standards_retriever
from ingestion.video_ingestion import get_vector_store as get_video_store


logger = logging.getLogger(__name__)

LIFECYCLE_REVIEW_KEYWORDS = (
    "hara",
    "asil",
    "safety lifecycle",
    "whole safety lifecycle",
    "lifecycle",
    "safety goals",
    "functional safety concept",
    "technical safety concept",
)


def _format_video_result(index: int, doc) -> str:
    meta = doc.metadata
    timestamp = int(float(meta.get("timestamp_start") or 0))
    url = meta.get("url", "")
    link = f"{url}&t={timestamp}s" if url and "?" in url else url
    return (
        f"[Video {index}]\n"
        f"Title: {meta.get('title', 'Unknown')}\n"
        f"Channel: {meta.get('channel', 'Unknown')}\n"
        f"Category: {meta.get('category', 'Unknown')}\n"
        f"Tags: {meta.get('tags', '')}\n"
        f"Timestamp: {timestamp}s\n"
        f"Link: {link}\n"
        f"Evidence: {shorten(doc.page_content, width=900, placeholder='...')}"
    )


def _format_standard_result(index: int, doc) -> str:
    meta = doc.metadata
    return (
        f"[Standard {index}]\n"
        f"Standard: {meta.get('standard', 'Unknown')}\n"
        f"Part: {meta.get('part', 'Unknown')}\n"
        f"Clause: {meta.get('clause', 'Unknown')}\n"
        f"Section: {meta.get('section_title', 'Unknown')}\n"
        f"Page: {meta.get('page', 'Unknown')}\n"
        f"Evidence: {shorten(doc.page_content, width=900, placeholder='...')}"
    )


def _format_standard_result_compact(index: int, doc) -> str:
    meta = doc.metadata
    return (
        f"[{index}] {meta.get('standard', 'Unknown')} | {meta.get('part', 'Unknown')} | "
        f"Clause {meta.get('clause', 'Unknown')} | Page {meta.get('page', 'Unknown')}\n"
        f"Section: {meta.get('section_title', 'Unknown')}\n"
        f"Evidence: {shorten(doc.page_content, width=500, placeholder='...')}"
    )


def _retrieval_llm() -> ChatOpenAI:
    """LLM used only to generate alternative retrieval queries."""
    return ChatOpenAI(
        model=cfg.LLM_MODEL,
        temperature=0,
        max_tokens=cfg.OPENAI_MAX_TOKENS,
        timeout=cfg.OPENAI_TIMEOUT,
        openai_api_key=cfg.OPENAI_API_KEY,
    )


def _dedupe_docs(docs: list) -> list:
    """Remove duplicate retrieved chunks while preserving order."""
    unique_docs = []
    seen: set[tuple] = set()
    for doc in docs:
        meta = doc.metadata
        key = (
            meta.get("filename"),
            meta.get("video_id"),
            meta.get("page"),
            meta.get("timestamp_start"),
            doc.page_content[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_docs.append(doc)
    return unique_docs


def _multi_query_search(retriever, query: str, max_results: int) -> list:
    """
    Expand a user query into multiple technical search queries, then retrieve.

    This helps short questions such as "why did the AV fail?" reach chunks about
    perception, ODD limitations, SOTIF triggering conditions, ML robustness, etc.
    """
    multi_query_retriever = MultiQueryRetriever.from_llm(
        retriever=retriever,
        llm=_retrieval_llm(),
    )
    return _dedupe_docs(multi_query_retriever.invoke(query))[:max_results]


@tool
def search_video_evidence(query: str = "") -> str:
    """Multi-query search autonomous-driving video transcripts for technical evidence."""
    query = query or "autonomous driving ADAS safety evidence perception planning failure scenario"
    store = get_video_store()
    retriever = store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 10},
    )
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return "No relevant video evidence found."
    return "\n\n".join(_format_video_result(i, doc) for i, doc in enumerate(docs, 1))


@tool
def search_failure_case_videos(query: str = "") -> str:
    """Multi-query search only failure-case videos about autonomous-driving failures and edge cases."""
    query = query or "autonomous driving failure case crash near miss perception limitation safety analysis"
    store = get_video_store()
    retriever = store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 10, "filter": {"category": "autonomous_driving_failure_case"}},
    )
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return "No relevant failure-case video evidence found."
    return "\n\n".join(_format_video_result(i, doc) for i, doc in enumerate(docs, 1))


@tool
def search_iso_standards(query: str = "") -> str:
    """Multi-query search ISO, Euro NCAP, and IIHS safety documents."""
    query = query or "ISO 26262 ISO 21448 SOTIF ISO 8800 safety lifecycle HARA validation evidence"
    retriever = get_standards_retriever(k=10)
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return "No relevant safety-document evidence found."
    return "\n\n".join(_format_standard_result(i, doc) for i, doc in enumerate(docs, 1))


@tool
def search_specific_standard(query: str = "", standard: str = "ISO 26262") -> str:
    """Multi-query search one source only. Use 'ISO 26262', 'ISO 21448', 'ISO 8800', 'Euro NCAP', or 'IIHS'."""
    query = query or f"{standard} autonomous driving safety requirements validation evidence"
    retriever = get_standards_retriever(k=10, filter_standard=standard)
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return f"No relevant evidence found in {standard}."
    return "\n\n".join(_format_standard_result(i, doc) for i, doc in enumerate(docs, 1))


@tool
def search_dataset_profiles(query: str = "") -> str:
    """Search dataset profiles for ISO 8800, SOTIF, AEB, and perception dataset coverage evidence."""
    query = query or "dataset profile perception vulnerable road users visibility occlusion AI safety ISO 8800"
    retriever = get_standards_retriever(k=10, filter_standard="Dataset Profile")
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return "No relevant dataset-profile evidence found."
    return "\n\n".join(_format_standard_result(i, doc) for i, doc in enumerate(docs, 1))


@tool
def search_project_safety_case_examples(query: str = "") -> str:
    """Search project-generated example safety cases. These are examples, not official ISO requirements."""
    query = query or "project safety case example item definition HARA lifecycle SOTIF ISO 8800"
    retriever = get_standards_retriever(k=10, filter_standard="Project Safety Case Example")
    docs = _multi_query_search(retriever, query, max_results=10)
    if not docs:
        return "No relevant project-generated safety case example found."
    return (
        "Project-generated examples only; use official ISO/SOTIF/ISO 8800 evidence separately.\n\n"
        + "\n\n".join(_format_standard_result(i, doc) for i, doc in enumerate(docs, 1))
    )


@tool
def search_sotif_evaluation_guidance(query: str = "") -> str:
    """Search SOTIF evaluation guidance for triggering conditions, ODD limits, scenario coverage, and residual risk."""
    query = query or "SOTIF intended functionality ODD triggering conditions validation residual risk"
    store = get_standards_retriever(k=1).vectorstore
    sections: list[str] = []

    scheme_docs = store.similarity_search(
        f"{query} SOTIF evaluation scheme triggering conditions ODD known unsafe unknown unsafe residual risk validation misuse",
        k=8,
        filter={"standard": "SOTIF Evaluation Scheme"},
    )
    sections.append(
        "## SOTIF Evaluation Scheme\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(scheme_docs, 1))
            if scheme_docs
            else "No direct retrieved SOTIF evaluation-scheme evidence."
        )
    )

    iso_docs = store.similarity_search(
        f"{query} ISO 21448 SOTIF intended functionality ODD triggering condition known unsafe unknown unsafe foreseeable misuse validation risk reduction",
        k=8,
        filter={"standard": "ISO 21448"},
    )
    sections.append(
        "## ISO 21448 / SOTIF\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(iso_docs, 1))
            if iso_docs
            else "No direct retrieved ISO 21448 evidence."
        )
    )

    return "\n\n".join(sections)


@tool
def search_iso_8800_evaluation_guidance(query: str = "") -> str:
    """Search ISO 8800 evaluation guidance for AI safety, dataset coverage, robustness, release gates, and monitoring."""
    query = query or "ISO 8800 AI safety data quality model robustness uncertainty monitoring release gate"
    store = get_standards_retriever(k=1).vectorstore
    sections: list[str] = []

    scheme_docs = store.similarity_search(
        f"{query} ISO 8800 evaluation scheme AI safety data coverage robustness uncertainty release gate regression monitoring dataset model lifecycle",
        k=8,
        filter={"standard": "ISO 8800 Evaluation Scheme"},
    )
    sections.append(
        "## ISO 8800 Evaluation Scheme\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(scheme_docs, 1))
            if scheme_docs
            else "No direct retrieved ISO 8800 evaluation-scheme evidence."
        )
    )

    iso_docs = store.similarity_search(
        f"{query} ISO 8800 artificial intelligence safety data quality validation robustness monitoring model lifecycle AI road vehicles",
        k=8,
        filter={"standard": "ISO 8800"},
    )
    sections.append(
        "## ISO 8800\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(iso_docs, 1))
            if iso_docs
            else "No direct retrieved ISO 8800 evidence."
        )
    )

    dataset_docs = store.similarity_search(
        f"{query} dataset profile data coverage object classes visibility vulnerable road users AEB perception validation ISO 8800",
        k=5,
        filter={"standard": "Dataset Profile"},
    )
    sections.append(
        "## Dataset Profile Evidence\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(dataset_docs, 1))
            if dataset_docs
            else "No direct retrieved dataset-profile evidence."
        )
    )

    return "\n\n".join(sections)


@tool
def search_iso_26262_evaluation_guidance(query: str = "") -> str:
    """Search ISO 26262 evaluation guidance for item definition, HARA, safety goals, lifecycle, V&V, and safety case evidence."""
    query = query or "ISO 26262 item definition HARA safety goals functional safety concept technical safety concept lifecycle"
    store = get_standards_retriever(k=1).vectorstore
    sections: list[str] = []

    scheme_docs = store.similarity_search(
        f"{query} ISO 26262 evaluation scheme item definition HARA ASIL safety goals functional safety concept technical safety concept verification validation safety case",
        k=8,
        filter={"standard": "ISO 26262 Evaluation Scheme"},
    )
    sections.append(
        "## ISO 26262 Evaluation Scheme\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(scheme_docs, 1))
            if scheme_docs
            else "No direct retrieved ISO 26262 evaluation-scheme evidence."
        )
    )

    iso_docs = store.similarity_search(
        f"{query} ISO 26262 item definition HARA ASIL safety goal functional safety concept technical safety concept system hardware software safety analysis verification validation confirmation measures safety case",
        k=8,
        filter={"standard": "ISO 26262"},
    )
    sections.append(
        "## ISO 26262\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(iso_docs, 1))
            if iso_docs
            else "No direct retrieved ISO 26262 evidence."
        )
    )

    return "\n\n".join(sections)


@tool
def search_safety_lifecycle_guidance(system_item: str) -> str:
    """Retrieve lifecycle guidance for a system item across ISO 26262 Parts 2-9, ISO 21448/SOTIF, and ISO 8800."""
    store = get_standards_retriever(k=1).vectorstore

    iso_26262_queries = [
        ("ISO 26262 Part 2 - functional safety management", "Part 2", "management of functional safety safety plan confirmation measures safety lifecycle"),
        ("ISO 26262 Part 3 - concept phase", "Part 3", "item definition HARA hazard analysis risk assessment ASIL safety goals functional safety concept"),
        ("ISO 26262 Part 4 - system development", "Part 4", "system level product development technical safety concept system architectural design integration testing validation"),
        ("ISO 26262 Part 5 - hardware development", "Part 5", "hardware safety requirements hardware architectural metrics random hardware failures PMHF SPFM LFM evaluation"),
        ("ISO 26262 Part 6 - software development", "Part 6", "software safety requirements software architectural design unit verification integration testing ASIL"),
        ("ISO 26262 Part 7 - production and operation", "Part 7", "production operation service decommissioning safety lifecycle release for production field monitoring"),
        ("ISO 26262 Part 8 - supporting processes", "Part 8", "supporting processes configuration management change management verification documentation tool qualification safety case"),
        ("ISO 26262 Part 9 - safety analyses", "Part 9", "ASIL decomposition dependent failure analysis DFA freedom from interference safety analyses"),
    ]

    sections: list[str] = []
    for heading, part, query in iso_26262_queries:
        docs = store.similarity_search(
            f"{system_item} {query}",
            k=3,
            filter={"$and": [{"standard": "ISO 26262"}, {"part": part}]},
        )
        if docs:
            body = "\n\n".join(
                _format_standard_result_compact(i, doc) for i, doc in enumerate(docs, 1)
            )
        else:
            body = "No direct retrieved evidence for this part."
        sections.append(f"## {heading}\n{body}")

    sotif_docs = store.similarity_search(
        f"{system_item} ISO 21448 SOTIF intended functionality ODD triggering conditions known unsafe scenarios unknown unsafe scenarios verification validation sensor perception limitations",
        k=5,
        filter={"standard": "ISO 21448"},
    )
    sections.append(
        "## ISO 21448 / SOTIF\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(sotif_docs, 1))
            if sotif_docs
            else "No direct retrieved SOTIF evidence."
        )
    )

    iso_8800_docs = store.similarity_search(
        f"{system_item} ISO 8800 AI safety lifecycle machine learning model data quality training validation robustness monitoring artificial intelligence",
        k=5,
        filter={"standard": "ISO 8800"},
    )
    sections.append(
        "## ISO 8800\n"
        + (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(iso_8800_docs, 1))
            if iso_8800_docs
            else "No direct retrieved ISO 8800 evidence."
        )
    )

    return "\n\n".join(sections)


@tool
def search_hara_guidance(item_or_hazard: str) -> str:
    """Retrieve ISO 26262 Part 3 and exposure-catalogue HARA guidance for S/E/C, ASIL, and safety goals."""
    store = get_standards_retriever(k=1).vectorstore
    hara_queries = [
        ("HARA overview and hazardous events", "hazard analysis risk assessment HARA hazardous event operational situation malfunctioning behavior"),
        ("Severity rating guidance", "severity classification S0 S1 S2 S3 injuries harm severity class"),
        ("Exposure rating guidance", "exposure classification E0 E1 E2 E3 E4 operational situation probability exposure"),
        ("Controllability rating guidance", "controllability classification C0 C1 C2 C3 ability to avoid harm driver other traffic participants"),
        ("ASIL determination", "ASIL determination severity exposure controllability automotive safety integrity level QM ASIL A B C D"),
        ("Safety goals", "safety goals hazardous event ASIL functional safety concept safe state fault tolerant time interval"),
    ]

    sections: list[str] = []
    for heading, query in hara_queries:
        docs = store.similarity_search(
            f"{item_or_hazard} {query}",
            k=4,
            filter={"$and": [{"standard": "ISO 26262"}, {"part": "Part 3"}]},
        )
        body = (
            "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(docs, 1))
            if docs
            else "No direct retrieved HARA evidence."
        )
        sections.append(f"## {heading}\n{body}")

    exposure_catalogue_docs = store.similarity_search(
        f"{item_or_hazard} exposure catalogue operational situation frequency E0 E1 E2 E3 E4 ODD urban highway pedestrian crossing weather traffic rain night",
        k=6,
        filter={"standard": "HARA Exposure Catalogue"},
    )
    sections.append(
        "## HARA Exposure Catalogue\n"
        + (
            "\n\n".join(
                _format_standard_result_compact(i, doc)
                for i, doc in enumerate(exposure_catalogue_docs, 1)
            )
            if exposure_catalogue_docs
            else "No direct retrieved exposure-catalogue evidence."
        )
    )

    return "\n\n".join(sections)


LOCAL_RETRIEVAL_TOOL_DESCRIPTIONS = {
    "local_search_all_standards": "Broad search across the local standards/example DB.",
    "local_search_iso26262": "ISO 26262 functional safety, HARA, ASIL, safety lifecycle, system/hardware/software evidence.",
    "local_search_sotif": "ISO 21448 (SOTIF), intended-function limitations, triggering conditions, ODD and scenario risk.",
    "local_search_iso8800": "ISO 8800 AI safety, data quality, model robustness, uncertainty, release gates and monitoring.",
    "local_search_hara": "HARA exposure catalogue and ISO 26262 S/E/C guidance.",
    "local_search_dataset": "Dataset profile and perception/AEB data coverage evidence.",
    "local_search_project_examples": "Project-generated worked safety-case examples.",
    "local_search_lifecycle": "Lifecycle-focused evidence across ISO 26262 Parts 2-9, SOTIF and ISO 8800.",
}


@lru_cache(maxsize=1)
def _local_vector_store():
    """Return the local standards vector store used by the free draft backend."""
    return get_standards_retriever(k=1, embedding_backend="local").vectorstore


def _local_similarity_section(
    heading: str,
    query: str,
    *,
    k: int = 5,
    filter: dict | None = None,
) -> str:
    store = _local_vector_store()
    docs = store.similarity_search(query, k=k, filter=filter)
    body = (
        "\n\n".join(_format_standard_result_compact(i, doc) for i, doc in enumerate(docs, 1))
        if docs
        else "No direct retrieved local evidence."
    )
    return f"## {heading}\n{body}"


def _run_local_retrieval_tool(tool_name: str, query: str) -> str:
    """Execute one deterministic local retrieval tool selected by Qwen."""
    query = query.strip() or "autonomous driving safety ISO 26262 SOTIF ISO 8800"

    if tool_name == "local_search_iso26262":
        return _local_similarity_section(
            "Local Tool: ISO 26262",
            f"{query} ISO 26262 HARA ASIL safety goals item definition functional safety concept technical safety concept system hardware software verification validation",
            k=7,
            filter={"standard": "ISO 26262"},
        )
    if tool_name == "local_search_sotif":
        return (
            _local_similarity_section(
                "Local Tool: SOTIF Evaluation Scheme",
                f"{query} SOTIF evaluation triggering conditions ODD known unsafe unknown unsafe residual risk validation misuse",
                k=5,
                filter={"standard": "SOTIF Evaluation Scheme"},
            )
            + "\n\n"
            + _local_similarity_section(
                "Local Tool: ISO 21448 / SOTIF",
                f"{query} ISO 21448 SOTIF intended functionality ODD triggering condition known unsafe unknown unsafe foreseeable misuse validation risk reduction",
                k=5,
                filter={"standard": "ISO 21448"},
            )
        )
    if tool_name == "local_search_iso8800":
        return (
            _local_similarity_section(
                "Local Tool: ISO 8800 Evaluation Scheme",
                f"{query} ISO 8800 evaluation AI safety data coverage robustness uncertainty release gate regression monitoring dataset model lifecycle",
                k=5,
                filter={"standard": "ISO 8800 Evaluation Scheme"},
            )
            + "\n\n"
            + _local_similarity_section(
                "Local Tool: ISO 8800",
                f"{query} ISO 8800 artificial intelligence safety data quality validation robustness monitoring model lifecycle AI road vehicles",
                k=5,
                filter={"standard": "ISO 8800"},
            )
        )
    if tool_name == "local_search_hara":
        return (
            _local_similarity_section(
                "Local Tool: ISO 26262 HARA Guidance",
                f"{query} HARA hazardous event operational situation severity exposure controllability ASIL safety goals",
                k=6,
                filter={"standard": "ISO 26262"},
            )
            + "\n\n"
            + _local_similarity_section(
                "Local Tool: HARA Exposure Catalogue",
                f"{query} exposure catalogue operational situation frequency E0 E1 E2 E3 E4 ODD urban highway pedestrian crossing weather traffic",
                k=5,
                filter={"standard": "HARA Exposure Catalogue"},
            )
        )
    if tool_name == "local_search_dataset":
        return _local_similarity_section(
            "Local Tool: Dataset Profile",
            f"{query} dataset profile perception vulnerable road users visibility occlusion weather lighting class imbalance AI safety ISO 8800 SOTIF",
            k=7,
            filter={"standard": "Dataset Profile"},
        )
    if tool_name == "local_search_project_examples":
        return _local_similarity_section(
            "Local Tool: Project Safety Case Examples",
            f"{query} project safety case example item definition HARA lifecycle SOTIF ISO 8800 system hardware software verification validation",
            k=7,
            filter={"standard": "Project Safety Case Example"},
        )
    if tool_name == "local_search_lifecycle":
        sections = [
            _local_similarity_section(
                "Local Tool: ISO 26262 Lifecycle",
                f"{query} ISO 26262 Parts 2 3 4 5 6 7 8 9 lifecycle item definition HARA system hardware software production supporting processes dependent failure analysis",
                k=8,
                filter={"standard": "ISO 26262"},
            ),
            _local_similarity_section(
                "Local Tool: SOTIF Lifecycle",
                f"{query} SOTIF lifecycle intended functionality ODD triggering conditions validation residual risk",
                k=5,
                filter={"standard": "ISO 21448"},
            ),
            _local_similarity_section(
                "Local Tool: ISO 8800 Lifecycle",
                f"{query} ISO 8800 AI lifecycle data model validation release monitoring change management",
                k=5,
                filter={"standard": "ISO 8800"},
            ),
        ]
        return "\n\n".join(sections)

    return _local_similarity_section(
        "Local Tool: Broad Standards Search",
        f"{query} autonomous driving safety ISO 26262 ISO 21448 SOTIF ISO 8800 HARA validation evidence engineering improvement",
        k=10,
    )


def _fallback_local_tool_plan(question: str) -> list[dict[str, str]]:
    """Deterministic tool plan if Qwen does not return usable JSON."""
    q = question.lower()
    plan = [{"tool": "local_search_all_standards", "query": question, "reason": "broad baseline"}]

    if any(term in q for term in ["hara", "asil", "severity", "exposure", "controllability", "s/e/c"]):
        plan.append({"tool": "local_search_hara", "query": question, "reason": "HARA or ASIL requested"})
        plan.append({"tool": "local_search_iso26262", "query": question, "reason": "ISO 26262 HARA basis"})

    if any(term in q for term in ["lifecycle", "safety case", "item definition", "system", "hardware", "software"]):
        plan.append({"tool": "local_search_lifecycle", "query": question, "reason": "lifecycle or safety case requested"})
        plan.append({"tool": "local_search_project_examples", "query": question, "reason": "worked examples help structure"})

    if any(term in q for term in ["sotif", "21448", "odd", "triggering", "functional limitation", "misuse"]):
        plan.append({"tool": "local_search_sotif", "query": question, "reason": "SOTIF relevance"})

    if any(term in q for term in ["8800", "ai", "ml", "model", "dataset", "data", "robustness", "uncertainty", "ood", "drift"]):
        plan.append({"tool": "local_search_iso8800", "query": question, "reason": "AI safety relevance"})
        plan.append({"tool": "local_search_dataset", "query": question, "reason": "dataset evidence relevance"})

    seen: set[str] = set()
    deduped = []
    for item in plan:
        if item["tool"] in seen:
            continue
        seen.add(item["tool"])
        deduped.append(item)
    return deduped[:6]


def _plan_local_retrieval(question: str) -> list[dict[str, str]]:
    """Ask Qwen to select local retrieval tools, with deterministic fallback."""
    tools_text = "\n".join(
        f"- {name}: {description}"
        for name, description in LOCAL_RETRIEVAL_TOOL_DESCRIPTIONS.items()
    )
    planner_prompt = f"""
You are planning retrieval for an autonomous-driving safety RAG assistant.
Choose up to 6 local retrieval tools that will provide the best evidence.

Available tools:
{tools_text}

Return JSON only in this exact shape:
{{
  "queries": [
    {{"tool": "local_search_iso26262", "query": "specific search query", "reason": "why this is needed"}}
  ]
}}

User question:
{question}
""".strip()
    try:
        raw = _call_ollama_chat(
            [{"role": "user", "content": planner_prompt}],
            temperature=0,
            json_mode=True,
        )
        payload = json.loads(raw)
        queries = payload.get("queries", [])
        plan = []
        for item in queries:
            tool_name = str(item.get("tool", "")).strip()
            if tool_name not in LOCAL_RETRIEVAL_TOOL_DESCRIPTIONS:
                continue
            plan.append(
                {
                    "tool": tool_name,
                    "query": str(item.get("query") or question).strip(),
                    "reason": str(item.get("reason") or "selected by local planner").strip(),
                }
            )
        return plan[:6] or _fallback_local_tool_plan(question)
    except Exception:
        return _fallback_local_tool_plan(question)


def _retrieve_local_draft_context(question: str) -> str:
    """Retrieve standards-only context for the open-source draft backend."""
    try:
        plan = _plan_local_retrieval(question)
        sections = [
            "## Local Retrieval Plan\n"
            + "\n".join(
                f"{i}. {item['tool']} — {item['reason']} — query: {item['query']}"
                for i, item in enumerate(plan, 1)
            )
        ]
        for item in plan:
            try:
                sections.append(_run_local_retrieval_tool(item["tool"], item["query"]))
            except Exception as exc:
                sections.append(
                    f"## Local Tool Failed: {item['tool']}\n"
                    f"{type(exc).__name__}: build/check the local standards DB with "
                    "python -m ingestion.standards_ingestion --embedding-backend local --reset"
                )
        return "\n\n".join(sections)
    except Exception as exc:
        return (
            "## Local Retrieval Failed\n"
            f"{type(exc).__name__}: build/check the local standards DB with "
            "python -m ingestion.standards_ingestion --embedding-backend local --reset"
        )


def _call_ollama_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    """Call an Ollama-compatible local chat model."""
    base_url = cfg.LOCAL_LLM_BASE_URL.rstrip("/")
    payload = {
        "model": model or cfg.LOCAL_LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": cfg.LOCAL_LLM_NUM_CTX,
            "num_predict": cfg.LOCAL_LLM_NUM_PREDICT,
        },
    }
    if json_mode:
        payload["format"] = "json"

    response = httpx.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=cfg.LOCAL_LLM_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("message", {}).get("content", "")
    if not content.strip():
        raise RuntimeError("Local model returned an empty answer.")
    return content.strip()


def run_open_source_draft_answer(question: str) -> str:
    """
    Generate a lower-cost draft answer with an open-source local model.

    This path avoids LangChain tool calling because small local models are less
    reliable with tool schemas. Retrieval runs first, then the local model gets
    a compact context package.
    """
    if cfg.LOCAL_LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LOCAL_LLM_PROVIDER: {cfg.LOCAL_LLM_PROVIDER}")

    context = _retrieve_local_draft_context(question)
    system = _build_local_system_prompt()
    user = _build_local_grounded_user_prompt(question, context)
    answer = _call_ollama_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return _ensure_local_answer_scheme(
        question,
        context,
        answer,
        lambda revision_prompt: _call_ollama_chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": revision_prompt},
            ]
        ),
    )


def _draft_with_local_ollama_model(question: str, model: str) -> str:
    """Generate a retrieved local draft using a specific Ollama model name."""
    context = _retrieve_local_draft_context(question)
    system = _build_local_system_prompt()
    user = _build_local_grounded_user_prompt(question, context)
    answer = _call_ollama_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
    )
    return _ensure_local_answer_scheme(
        question,
        context,
        answer,
        lambda revision_prompt: _call_ollama_chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": revision_prompt},
            ],
            model=model,
        ),
    )


def run_finetuned_lora_answer(question: str) -> str:
    """
    Call a running Qwen LoRA inference endpoint.

    The trained adapter is a PEFT/Hugging Face adapter, not an Ollama model.
    For app demos, run the Colab serving script and set LOCAL_LORA_API_URL to
    its public Gradio share URL, or to a direct JSON endpoint returning
    {"answer": "..."}.
    """
    if cfg.LOCAL_LORA_OLLAMA_MODEL:
        try:
            return _draft_with_local_ollama_model(question, cfg.LOCAL_LORA_OLLAMA_MODEL)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        except httpx.HTTPError:
            if cfg.LOCAL_LORA_API_URL:
                pass
            else:
                raise

    if not cfg.LOCAL_LORA_API_URL:
        return (
            "Fine-tuned Qwen LoRA is trained, but it is not currently connected to an inference endpoint.\n\n"
            f"Expected local Ollama model: `{cfg.LOCAL_LORA_OLLAMA_MODEL}`.\n\n"
            "To make it independent from Colab, merge/export the LoRA with "
            "`training/merge_qwen_lora_colab.py`, create the Ollama model, then restart the app. "
            "For a temporary demo, run `training/serve_qwen_lora_colab.py` in Colab and set "
            "`LOCAL_LORA_API_URL` in `.env` to the Gradio URL. "
            "Until then, use `Local Qwen - before fine-tuning` for the free local model."
        )

    context = _retrieve_local_draft_context(question)
    grounded_prompt = _build_local_grounded_user_prompt(question, context)

    def call_lora_endpoint(prompt: str) -> str:
        if "gradio.live" in cfg.LOCAL_LORA_API_URL or "gradio.app" in cfg.LOCAL_LORA_API_URL:
            try:
                from gradio_client import Client
            except ImportError as exc:
                raise RuntimeError(
                    "Install gradio_client to call the fine-tuned LoRA Gradio endpoint: "
                    "pip install gradio_client"
                ) from exc

            try:
                result = Client(cfg.LOCAL_LORA_API_URL).predict(
                    prompt=prompt,
                    api_name="/generate",
                )
            except Exception as exc:
                raise RuntimeError(
                    "Fine-tuned LoRA Gradio endpoint is not reachable. "
                    "Restart the Colab serving script, copy the new gradio.live URL, "
                    "update LOCAL_LORA_API_URL in .env, then restart Streamlit."
                ) from exc
            if isinstance(result, dict):
                endpoint_answer = str(result.get("answer", "")).strip()
            else:
                endpoint_answer = str(result).strip()
            if not endpoint_answer:
                raise RuntimeError("Fine-tuned LoRA Gradio endpoint returned an empty answer.")
            return endpoint_answer

        response = httpx.post(
            cfg.LOCAL_LORA_API_URL,
            json={"prompt": prompt},
            timeout=cfg.LOCAL_LORA_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        endpoint_answer = str(payload.get("answer", "")).strip()
        if not endpoint_answer:
            raise RuntimeError("Fine-tuned LoRA endpoint returned an empty answer.")
        return endpoint_answer

    answer = call_lora_endpoint(grounded_prompt)
    if is_degenerate_model_answer(answer):
        answer = call_lora_endpoint(_build_lora_recovery_prompt(question, context))
    if is_degenerate_model_answer(answer):
        raise RuntimeError(
            "Fine-tuned LoRA returned an invalid numeric/debug-style generation. "
            "Restart the Colab endpoint and serve it with lower limits, for example "
            "`--max-input-tokens 2048 --max-new-tokens 1800`, then rerun evaluation."
        )
    return _ensure_local_answer_scheme(
        question,
        context,
        answer,
        call_lora_endpoint,
    )


SYSTEM_PROMPT = """You are Autonomous Driving Safety Analyst, an expert autonomous-driving safety analyst and technical RAG assistant.

Your job is to answer questions about autonomous driving using grounded evidence from:
1. video transcripts in the video vector database,
2. ISO 26262 functional safety,
3. ISO 21448 / SOTIF,
4. ISO 8800 safety and artificial intelligence,
5. Euro NCAP and IIHS safety assessment documents.
6. HARA exposure-catalogue guidance for exposure classification.
7. Dataset profiles for perception, AEB, SOTIF, and ISO 8800 dataset coverage.
8. SOTIF evaluation scheme guidance for triggering conditions and residual risk.
9. ISO 8800 evaluation scheme guidance for AI safety, data coverage, robustness,
   release gates, and monitoring.
10. ISO 26262 evaluation scheme guidance for item definition, HARA, safety goals,
    safety lifecycle, verification/validation, and safety case evidence.

Use the tools before answering technical questions. Adapt your technical depth to
the user's apparent expertise level: use plain explanations for newcomers, and use
specific safety-engineering terminology and ISO clause references for engineers.

For any substantive autonomous-driving, ADAS, self-driving, perception, planning,
control, AI/ML, decision-making, reinforcement learning, Markov decision process
(MDP), safety, validation, or failure question, explicitly include a "Safety and
standards relevance" section that connects the topic to ISO 26262, ISO
21448/SOTIF, and ISO 8800. Also identify where the system could fail and propose
practical engineering improvements. For simple definition questions, answer
briefly and add a short safety relevance note rather than a full safety analysis.

Routing rules:
- Failure, crash, disengagement, edge-case, or abnormal-behavior questions:
  query video evidence and standards evidence. Prefer search_failure_case_videos.
- "What does ISO/NCAP/IIHS say about X" questions: query standards only; use
  search_specific_standard when the requested source is clear.
- Company, channel, or video-demonstration questions: query video evidence only.
- Concept questions about autonomous-driving perception, planning, control,
  reinforcement learning, MDPs, prediction, sensor fusion, or AI/ML: query video
  evidence for the technical concept and standards evidence for safety relevance.
- Dataset, training/validation data, class imbalance, perception/AEB dataset, or
  data-quality questions: use search_dataset_profiles and
  search_iso_8800_evaluation_guidance, then connect to ISO 8800 and SOTIF.
- Lifecycle, development process, safety case, or whole safety lifecycle
  questions: use search_safety_lifecycle_guidance. When the user asks for a
  worked example, template, complete example, or item safety case, also use
  search_project_safety_case_examples, but clearly treat those results as
  project-generated examples rather than official ISO requirements.
- HARA, ASIL, safety goal, Severity, Exposure, or Controllability questions:
  use search_hara_guidance and show S, E, C separately before ASIL/QM.
- For ISO 26262 topics, always retrieve and apply ISO 26262 evaluation guidance
  in addition to ISO 26262 standard content.
- For ISO 21448/SOTIF topics, always retrieve and apply SOTIF evaluation
  guidance in addition to ISO 21448/SOTIF standard content.
- For ISO 8800, AI safety, ML/data/model, release gate, drift, monitoring, OOD,
  or AI lifecycle topics, always retrieve and apply ISO 8800 evaluation guidance
  in addition to ISO 8800 standard content.

User-provided scenario intake:
- Do not ask the user for a video link and do not frame video links as a normal
  input path. The primary workflow is scenario, item, system, evidence, and
  requirement analysis from user-provided text.
- If the user includes a link anyway, treat it only as a non-inspected reference.
  Do not claim that you watched, downloaded, or transcribed it. Analyze only the
  user-provided description and state: "I did not inspect external link content;
  this analysis is based on the scenario details provided and stated assumptions."
- If the user gives too little detail, do not stop unless the missing data makes
  the analysis impossible. Ask for the most important missing details only when
  needed; otherwise proceed with explicit assumptions.
- Blank or unknown fields are allowed. Fill missing fields with reasonable
  baseline assumptions based on common scenario type, and mark them as
  assumptions, not facts:
  - urban VRU/AEB scenario: assume urban road, 30-50 km/h ego speed, pedestrian
    or cyclist 3-15 km/h, moderate traffic, possible occlusion, short TTC.
  - highway lane/ACC/lane-change scenario: assume highway road, 80-130 km/h ego
    speed, moderate traffic, driver supervision if L2, short reaction time for
    fast lateral/longitudinal events.
  - parking/low-speed scenario: assume 5-15 km/h ego speed, close obstacles,
    high exposure in parking areas, lower severity unless VRUs are involved.
- Always include an "Assumptions used" table when analyzing a user-described
  scenario with missing fields. Include road type, ego speed, object/road-user
  speed, traffic density, weather, lighting, occlusion, automation mode, ODD
  status, TTC/reaction-time assumption, and AI/ML involvement.
- Explain how different assumptions could change Severity, Exposure,
  Controllability, SOTIF risk, ISO 8800 data/model concern, and recommended
  improvements.
- When useful, offer this intake template for the user to fill, but make clear
  that every field is optional:
  1. Item/system:
  2. Main functions:
  3. What happened:
  4. Expected behavior:
  5. Actual behavior:
  6. Road type:
  7. Ego vehicle speed:
  8. Object/road-user speed:
  9. Weather:
  10. Lighting:
  11. Occlusion or visibility issue:
  12. Traffic density:
  13. Automation/ADAS mode:
  14. ODD status, if known:
  15. AI/ML involved, if known:
  16. Collision, near miss, warning, fallback, or disengagement outcome:
  17. Available logs/test reports/sensor evidence:

Failure classification:
- Before analyzing a failure, classify the main failure type:
  1. Hardware fault or systematic/random E/E fault: ISO 26262 is most relevant.
  2. Functional limitation, insufficient performance, foreseeable misuse, or ODD
     edge case: ISO 21448 / SOTIF is most relevant.
  3. ML model behavior, training-data quality, validation dataset coverage,
     robustness, bias, uncertainty, distribution shift, or AI lifecycle concern:
     ISO 8800 is most relevant.
- A case can involve more than one type. If so, explain the overlap and use the
  relevant standards together.
- Apply this distinction beyond explicit failure analysis. In HARA, lifecycle,
  concept, dataset, validation, and improvement answers, separate:
  1. ISO 26262 malfunction risk: the E/E item fails or behaves incorrectly.
  2. SOTIF insufficiency risk: the function works as designed but is unsafe in
     an ODD limit, triggering condition, foreseeable misuse, or edge case.
  3. ISO 8800 AI/data/model risk: unsafe behavior comes from dataset coverage,
     labels, model robustness, uncertainty, OOD/distribution shift, release, or
     monitoring gaps.
  Do not merge all three into one generic "safety risk"; state which lens is
  primary and when the risk is mixed.

HARA evaluation rules:
- When performing a HARA, first define the item/function, malfunctioning
  behavior, operational situation, hazardous event, and possible harm.
- If the user does not specify enough scenario detail, define a clear baseline
  ODD before rating: road type, ego speed, object/road-user speed if relevant,
  traffic density, weather, lighting, automation level, driver fallback
  expectation, and time-to-collision or reaction-time assumption.
- Use the same baseline assumptions consistently across HARA rows. Do not change
  road type, speed, traffic density, weather, ODD, automation level, or driver
  fallback assumptions between rows unless explicitly stated.
- Always reason Severity, Exposure, and Controllability before deriving ASIL/QM.
  Severity must explain the harm mechanism; Exposure must explain how often the
  operational situation occurs; Controllability must explain who can avoid the
  harm, by what action, and with how much time or fallback authority.
- Use this HARA table shape where practical: function, malfunction or
  insufficiency, hazardous event, scenario assumptions, Severity rationale,
  Exposure rationale, Controllability rationale, ASIL/QM, uncertainty, and next
  action.
- HARA coverage is a consistency requirement. If the functional decomposition
  lists N functions, the HARA section must account for those same N functions.
  For every function listed in functional decomposition, provide either:
  1. a HARA row with S/E/C and ASIL/QM, or
  2. a row marked "not safety-relevant for ISO 26262" or "QM candidate" with
     rationale.
  Do not collapse multiple functions into one representative row unless the user
  explicitly asks for a short example.
- In detailed lifecycle answers, if the functional decomposition contains
  detection/perception, estimation, tracking, confidence/uncertainty,
  health/diagnostics, calibration/freshness, and interface/actuation functions,
  the HARA table must include rows for each of those groups. A two-row HARA
  table is insufficient for a multi-function item.
- Before moving from HARA to safety goals, check that every function from the
  functional decomposition is either rated or explicitly screened out with
  rationale.
- Always consider ego-vehicle speed and object/road-user speed when evaluating
  Severity, Exposure, and Controllability. If speeds are not provided, state
  explicit speed assumptions and explain how higher or lower speeds would change
  the S/E/C ratings.
- If assumptions are weak or multiple operating situations are plausible, provide
  an ASIL range or scenario-dependent rating, such as "ASIL B-C depending on
  speed, traffic density, and driver fallback", instead of pretending one rating
  is definitive.
- Do not claim the S/E/C ratings are definitive unless the retrieved evidence
  and user-provided scenario are sufficient. Present them as an engineering
  estimate.
- For each hazardous event, distinguish whether the primary cause is ISO 26262
  E/E malfunction, SOTIF intended-function insufficiency, ISO 8800 AI/data/model
  weakness, or mixed. Do not treat every hazard as ISO 26262-only.
- Finish with candidate safety goals and possible functional safety
  requirements linked to the HARA result.

Default report format for failure analysis:
1. Observed issue
2. Failure type classification
3. Video evidence
4. ISO 26262 view
5. SOTIF / ISO 21448 view
6. ISO 8800 view
7. Recommended improvements
8. Evidence and limitations

Deep analysis mode:
- Use deep analysis mode when the user asks for analysis, detailed analysis,
  comparison, failure investigation, root cause analysis, safety assessment,
  improvement recommendations, or when the question involves a real/suspected
  autonomous-driving failure.
- In deep analysis mode, produce this exact report structure:
  1. Summary
  2. Observed behavior
  3. Failure classification
  4. Technical root causes
  5. ISO 26262 interpretation
  6. SOTIF interpretation
  7. ISO 8800 interpretation
  8. NCAP/IIHS assessment relevance
  9. Recommended engineering actions
  10. Evidence and limitations
- If one section is not supported by retrieved evidence, keep the section and
  clearly state what evidence is missing.

For non-failure questions, use a shorter structure that fits the question, but
still cite retrieved evidence when available.

Lifecycle and item-analysis rules:
- For lifecycle questions, first decompose the item into all relevant functions
  and safety-related outputs. Do not analyze only one representative function
  unless the user explicitly asks for one.
- For each function, screen credible ISO 26262 malfunctions, SOTIF intended-
  function insufficiencies, and ISO 8800 AI/data/model concerns where relevant.
  If an ISO 26262 row is QM, explain why and stop ISO 26262 derivation for that
  row, but continue SOTIF/ISO 8800 analysis and continue analyzing other
  functions.
- Apply the same function-by-function depth to SOTIF and ISO 8800 as to ISO
  26262. Do not give only one SOTIF or ISO 8800 example when the item has
  multiple relevant functions.
- Use rationale, not just checklist wording. For every major phase or important
  row, explain why the activity is needed, what unsafe behavior it prevents,
  what assumption it verifies, and how the evidence supports the safety argument.

Recommended lifecycle structure:
1. Opening map: ISO 26262 = E/E malfunction risk; SOTIF = unsafe intended
   functionality from limitations/ODD/triggering conditions; ISO 8800 = AI/data/
   model assurance risk.
2. Item definition: functions, inputs, outputs, interfaces, ODD, assumptions,
   safety role.
3. Functional decomposition: function, output, possible malfunction, possible
   SOTIF insufficiency, possible ISO 8800 concern, applicable standard(s), and
   HARA carried forward? yes/no with rationale. Always format this section as a
   markdown table, not repeated "Function: ..." blocks.
4. HARA screening: evaluate the functions from the functional decomposition,
   not just one or two functions. Use columns: function,
   malfunction/insufficiency, hazardous event, operational situation, speed
   assumptions, S rationale, E rationale, C rationale, ASIL/QM, uncertainty, and
   next action. The HARA table must include the same functions listed in the
   section 3 functional decomposition. If a function is not carried forward, include
   it in the HARA table as QM or not safety-relevant with rationale. For lane
   maintaining, LiDAR, AEB, ACC, or any other item, use the functions actually
   listed in section 3 rather than a fixed predefined function set.
5. Safety goals, functional safety concept, and technical safety concept:
   provide tables, not a paragraph. Include:
   - safety goals table: ID, related function, hazardous event prevented, ASIL
     or safety relevance, safe state/degraded behavior, main standard.
   - functional safety concept table: fault/condition, vehicle-level safe
     response, driver/HMI response, degraded mode, rationale.
   - technical safety concept table: mechanism, allocated component, fault or
     limitation addressed, diagnostic/fallback behavior, timing target,
     verification evidence.
6. ISO 26262 Part 2-9 lifecycle table:
   use columns: ISO 26262 part, purpose, item-specific engineering activities,
   work products/evidence, rationale/unsafe behavior prevented, and interaction
   with SOTIF/ISO 8800. Cover all parts:
   - Part 2: functional safety management, DIA/supplier interface, safety plan,
     confirmation measures, impact analysis, release responsibilities.
   - Part 3: item definition, ODD assumptions, HARA, S/E/C, ASIL, safety goals,
     functional safety concept.
   - Part 4: system development, technical safety concept, architecture,
     requirements allocation, integration, validation, vehicle-level behavior.
   - Part 5: hardware development, hardware safety requirements, FMEDA, random
     hardware metrics, diagnostic coverage, SPFM/LFM/PMHF where applicable.
   - Part 6: software development, software safety requirements, architecture,
     freedom from interference, freshness/plausibility checks, watchdogs,
     degraded-mode logic, unit/integration tests.
   - Part 7: production, operation, service, decommissioning, end-of-line
     calibration, service recalibration, DTCs, field monitoring.
   - Part 8: supporting processes, configuration/change management,
     requirements traceability, verification planning, documentation, tool or
     component qualification, safety case evidence.
   - Part 9: ASIL decomposition, dependent failure analysis, common-cause/
     cascading failure analysis, freedom from interference, FMEA, FTA, DFA.
   Each row must contain item-specific rationale, not only the name of the ISO
   activity.
7. SOTIF function analysis:
   provide a function-by-function table with columns: item function, intended
   performance limitation, triggering condition, ODD boundary/assumption, unsafe
   effect, known or unknown scenario status, validation evidence needed,
   mitigation/degradation, residual risk rationale. Use triggering conditions
   relevant to the item and ODD. Explain why these are not necessarily E/E
   malfunctions.
8. ISO 8800 function assurance:
   provide a function-by-function AI assurance table with columns: AI-related
   function, AI safety role, data requirement, dataset/label-quality gap,
   robustness or uncertainty risk, OOD/distribution-shift risk, release-gate
   criterion, monitoring/change-control evidence, residual AI risk rationale.
   Use data, labeling, robustness, uncertainty, release, and monitoring concerns
   relevant to the item and its AI-related functions.
9. Verification and validation matrix: include ISO 26262 malfunction tests, SOTIF
   performance tests, ISO 8800 AI tests, and vehicle-level validation. Each row
   should have test case, injected condition/scenario, expected safe behavior,
   measurable acceptance criterion, evidence artifact, and linked requirement.
10. Production and operation:
    provide an operational-control table with columns: lifecycle stage,
    operational risk, control activity, pass/fail or release criterion, evidence
    artifact, operation monitoring evidence, and rationale. Cover end-of-line calibration,
    sensor health checks, software/model version traceability, service
    recalibration, DTCs, field monitoring, incident/near-miss review, OTA gates,
    staged rollout, rollback, drift monitoring, and ODD restriction/disabling
    criteria.
11. Worst-case scenario:
    use tables, not a short paragraph. Include:
    - scenario assumptions table: ego speed, object speed, weather, lighting,
      occlusion, road type, traffic density, automation mode, TTC or available
      sensing time, driver fallback assumption, and road friction if relevant.
    - accident-chain table: step, degraded/missing signal, system interpretation,
      vehicle response, hazard escalation, and evidence needed.
    - standard-view table: ISO 26262 malfunction view, SOTIF limitation view,
      ISO 8800 AI/data/model view, expected mitigation, and verification
      evidence.
    - engineering-decision table: design/process decision, risk reduced,
      rationale, measurable acceptance criterion, and residual risk.
12. Final safety argument: explain how ISO 26262, SOTIF, and ISO 8800 combine
    into one safety case for the item.

Prefer compact tables for lifecycle work products, mechanisms, triggering
conditions, AI risks, tests, and safety goals, but include reasoning in the
table cells. Never give a HARA row like "S3/E4/C3 -> ASIL D" without explaining
speed assumptions, harm mechanism, exposure frequency, controllability/fallback
assumptions, and uncertainty.

Engineering specificity rules:
- Avoid generic standalone phrases such as "improve robustness", "validate the
  model", "ensure data quality", "add redundancy", "monitor performance", or
  "perform testing". If such a phrase is used, immediately make it concrete:
  specify the mechanism, failure mode addressed, evidence/work product, and
  verification or acceptance criterion.
- For each recommended improvement, include four parts: engineering action, why
  it reduces risk, which ISO/SOTIF/ISO 8800 concern it addresses, and how to
  verify it worked.
- Use realistic engineering parameters when helpful: ego speed, object speed,
  time-to-collision, sensing latency, detection range, confidence threshold,
  diagnostic detection time, fallback time, ODD condition, weather/lighting, and
  pass/fail criteria. State assumptions when values are not provided.
- Explain the causal chain. For example: degraded point cloud -> delayed object
  classification -> late AEB trigger -> reduced stopping distance -> collision
  risk. Do not only name the risk.
- When discussing ISO 26262, distinguish requirement, architecture, diagnostic,
  verification, validation, production/operation, and safety-analysis work.
- When discussing SOTIF, distinguish known unsafe scenario, unknown unsafe
  scenario, triggering condition, ODD limitation, validation gap, and risk
  reduction measure.
- When discussing ISO 8800, distinguish data coverage, label quality, model
  robustness, uncertainty/calibration, distribution shift, release gate,
  monitoring, and regression control.
- For dataset-gap, perception-validation, ISO 8800, or SOTIF questions, do not
  answer only with broad categories. Provide concrete vulnerable-road-user
  examples when relevant: children, elderly people, wheelchair users,
  pedestrians with strollers, e-scooters, cargo bikes, recumbent bikes, group
  cyclists, cyclists walking a bicycle, occlusion behind parked cars or buses,
  dark clothing at night, rain/fog/glare/spray, sensor contamination, motion
  blur, LiDAR sparsity, missing or inconsistent labels, negative samples,
  temporal-sequence gaps, and near-miss gaps. Explain the causal chain from
  dataset gap -> weak learned feature -> wrong or missing perception output ->
  wrong world model -> delayed/no braking or avoidance -> hazardous event.
- If the answer starts to become broad, prioritize the most safety-relevant 3-5
  mechanisms and explain them deeply rather than listing many shallow items.

Rules:
- Do not pretend the retrieved text proves more than it proves.
- If retrieval returns no relevant results, explicitly state what you searched
  and what is missing. Do not answer from general knowledge without disclosing it.
- Cite evidence using video title/channel/timestamp and ISO standard/part/clause/page.
  When ISO evidence is used, cite the exact clause number if the retrieved
  metadata or text provides it. If the exact clause is not available in the
  retrieved evidence, cite the standard/part/page or say "exact clause not found
  in retrieved evidence"; never invent clause numbers.
- Provide detailed engineering analysis when the user asks for analysis,
  comparison, or failure investigation. Be concise only for simple factual questions.
- When ISO text is relevant, connect it to the video evidence in practical engineering terms.
- Give ISO 8800 explicit attention whenever the question involves ML model
  behavior, data quality, validation, robustness, or AI lifecycle concerns.
"""


def _build_local_system_prompt() -> str:
    """
    Reuse the main safety-analysis prompt for local draft mode, with only the
    tool-calling and evidence-source assumptions adapted to the local path.
    """
    local_constraints = """

Local open-source draft mode constraints:
- Apply the same safety-analysis depth, report structure, HARA rules, function
  coverage rules, lifecycle rules, and ISO 26262 / ISO 21448 (SOTIF) / ISO 8800
  reasoning expectations as above.
- You do not have LangChain tools in this mode. Retrieval has already been run
  before this prompt. Use only the retrieved local standards/example context
  supplied by the user message.
- Treat routing rules as retrieval intent, not as callable tools. Do not write
  tool calls, action JSON, or tool names in the answer.
- This local mode uses standards/evaluation-scheme/project-example context only.
  It does not use the video transcript DB. If the main prompt asks for video
  evidence, replace that section with "Retrieved standards/example evidence" or
  "Evidence and limitations".
- Be honest when retrieved evidence is thin. Do not invent exact ISO clause
  numbers unless the retrieved context gives them.
- Prefer a complete but readable answer. For lifecycle and safety-case
  questions, include enough detail to be useful to an engineer, even if the
  local model answer is labeled as a draft.
"""
    return f"{SYSTEM_PROMPT.strip()}\n{local_constraints.strip()}"


LOCAL_STRICT_ANSWER_SCHEME = """
Mandatory answer scheme for local Qwen:
- Do not summarize lifecycle or safety-case questions into a short answer.
- For lifecycle, safety case, item development, or "whole safety lifecycle"
  questions, use exactly these numbered sections:
  1. Opening Map
  2. Item Definition
  3. Functional Decomposition
  4. HARA Screening
  5. Safety Goals, Functional Safety Concept, and Technical Safety Concept
  6. ISO 26262 Part 2-9 Lifecycle Assessment
  7. ISO 21448 (SOTIF) Function Analysis
  8. ISO 8800 Function Assurance
  9. Verification and Validation Matrix
  10. Production and Operation Controls
  11. Worst-Case Scenario
  12. Final Safety Argument
- Section 3 must be a markdown table.
- Section 4 must be a markdown HARA table and must include the same functions
  listed in section 3. If section 3 has N functions, section 4 must have N
  function rows. Do not analyze only one representative function.
- Section 6 must explicitly include ISO 26262 Part 2, Part 3, Part 4, Part 5,
  Part 6, Part 7, Part 8, and Part 9. Include item-specific engineering
  activities, work products/evidence, rationale, and interaction with SOTIF
  and ISO 8800.
- Section 7 must be function-by-function, with performance limitation,
  triggering condition, ODD assumption, unsafe effect, validation evidence,
  mitigation, and residual risk rationale.
- Section 8 must be function-by-function, with AI safety role, data
  requirement, dataset/label-quality gap, robustness/uncertainty risk,
  OOD/distribution-shift risk, release gate, monitoring/change-control
  evidence, and residual AI risk rationale.
- Use compact markdown tables, but include engineering rationale in the cells.
- Use retrieved standards/example evidence as grounding. If exact clauses are
  not present in retrieved context, do not invent exact clause numbers.
- Before finalizing, self-check that sections 3, 4, 6, 7, and 8 are present and
  not replaced by a short paragraph.
"""


def is_degenerate_model_answer(answer: str) -> bool:
    """Detect invalid local-model outputs such as long token/id number streams."""
    text = answer.strip()
    if not text:
        return True

    lowered = text.lower()
    endpoint_error_terms = (
        "endpoint ran out of gpu memory",
        "cuda out of memory",
        "fine-tuned lora endpoint ran out",
        "fine-tuned lora generated invalid numeric",
    )
    if any(term in lowered for term in endpoint_error_terms):
        return True

    numbers = re.findall(r"\b\d{1,5}\b", text)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z/-]{2,}\b", text)

    # The failure seen from the LoRA endpoint is a long comma-separated stream
    # like "41, 42, 43, ...", not an engineering answer.
    if len(numbers) >= 80 and len(words) < 25:
        return True
    if len(numbers) >= 120 and len(numbers) > max(80, len(words) * 5):
        return True

    numeric_chars = sum(1 for char in text if char.isdigit() or char in ", \n\t")
    if len(text) > 500 and numeric_chars / max(1, len(text)) > 0.82 and len(words) < 40:
        return True

    return False


def _build_local_grounded_user_prompt(question: str, context: str) -> str:
    """Build the final user prompt for both base and fine-tuned local models."""
    return f"""
User question:
{question}

Retrieved standards/example context:
{context}

{LOCAL_STRICT_ANSWER_SCHEME}

Draft the answer now. Follow the mandatory answer scheme strictly when the
question asks for lifecycle, safety case, item development, HARA, ISO 26262,
ISO 21448 (SOTIF), or ISO 8800 analysis.
""".strip()


def _build_lora_recovery_prompt(question: str, context: str) -> str:
    """Build a shorter prompt when the remote LoRA endpoint emits invalid text."""
    return f"""
The previous generation failed. Produce a normal markdown safety analysis, not
numbers, token ids, arrays, or debug output.

User question:
{question}

Relevant retrieved context summary:
{shorten(context, width=4500, placeholder='...')}

{LOCAL_STRICT_ANSWER_SCHEME}

Write the complete answer using the mandatory sections. Keep each table compact
but include concrete S/E/C, ASIL/QM, ISO 26262 Part 2-9, ISO 21448 (SOTIF), ISO
8800, V&V, worst-case scenario, and final safety argument content.
""".strip()


def _missing_local_answer_scheme_items(question: str, answer: str) -> list[str]:
    """Identify missing mandatory lifecycle/safety-case sections in local answers."""
    if not _needs_lifecycle_review(question, answer):
        return []

    text = answer.lower()
    missing: list[str] = []
    required_terms = [
        ("Opening Map", "opening map"),
        ("Item Definition", "item definition"),
        ("Functional Decomposition", "functional decomposition"),
        ("HARA Screening", "hara"),
        ("Safety Goals/FSC/TSC", "safety goal"),
        ("SOTIF Function Analysis", "sotif"),
        ("ISO 8800 Function Assurance", "iso 8800"),
        ("Verification and Validation Matrix", "verification"),
        ("Production and Operation Controls", "production"),
        ("Worst-Case Scenario", "worst"),
        ("Final Safety Argument", "safety argument"),
    ]
    for label, term in required_terms:
        if term not in text:
            missing.append(label)

    missing.extend(_missing_iso26262_lifecycle_parts(question, answer))

    decomposition = _extract_section(
        answer,
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?functional decomposition\b.*$",
    )
    if decomposition and "|" not in decomposition:
        missing.append("Section 3 markdown table")

    functions = _extract_listed_functions(answer)
    missing_hara = _missing_hara_functions(answer, functions)
    if missing_hara:
        missing.append(f"HARA rows for: {', '.join(missing_hara)}")

    if len(answer.strip()) < 2500:
        missing.append("answer too short for requested lifecycle depth")

    seen: set[str] = set()
    unique: list[str] = []
    for item in missing:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _build_local_revision_prompt(
    question: str,
    context: str,
    draft_answer: str,
    missing_items: list[str],
) -> str:
    """Build a same-model correction prompt for incomplete local answers."""
    return f"""
Your previous answer was incomplete for the requested standards lifecycle analysis.

Missing or weak items:
{chr(10).join(f"- {item}" for item in missing_items)}

Original user question:
{question}

Retrieved standards/example context:
{context}

Previous incomplete answer:
{draft_answer}

{LOCAL_STRICT_ANSWER_SCHEME}

Rewrite the full answer now from scratch. Do not apologize. Do not say the
previous answer was incomplete. Use the mandatory answer scheme exactly for
the lifecycle/safety-case analysis. Keep it engineering-specific and grounded
in the retrieved context.
""".strip()


def _ensure_local_answer_scheme(
    question: str,
    context: str,
    answer: str,
    revise: Callable[[str], str],
) -> str:
    """Run one same-model rewrite when a local answer skips required sections."""
    missing = _missing_local_answer_scheme_items(question, answer)
    if not missing:
        return answer
    revision_prompt = _build_local_revision_prompt(question, context, answer, missing)
    revised = revise(revision_prompt).strip()
    if is_degenerate_model_answer(revised):
        return answer
    return revised or answer


def build_agent() -> AgentExecutor:
    """Create the LangChain tool agent with memory."""
    cfg.validate()
    os.environ["LANGCHAIN_TRACING_V2"] = cfg.LANGCHAIN_TRACING_V2
    os.environ["LANGCHAIN_PROJECT"] = cfg.LANGCHAIN_PROJECT

    llm = ChatOpenAI(
        model=cfg.LLM_MODEL,
        temperature=0.1,
        max_tokens=cfg.OPENAI_MAX_TOKENS,
        timeout=cfg.OPENAI_TIMEOUT,
        openai_api_key=cfg.OPENAI_API_KEY,
    )

    tools = [
        search_video_evidence,
        search_failure_case_videos,
        search_iso_standards,
        search_specific_standard,
        search_dataset_profiles,
        search_project_safety_case_examples,
        search_sotif_evaluation_guidance,
        search_iso_8800_evaluation_guidance,
        search_iso_26262_evaluation_guidance,
        search_safety_lifecycle_guidance,
        search_hara_guidance,
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
    )
    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=6,
    )


def _needs_lifecycle_review(question: str, answer: str) -> bool:
    """Return True when a second-pass lifecycle/HARA consistency check is useful."""
    text = f"{question}\n{answer}".lower()
    return any(keyword in text for keyword in LIFECYCLE_REVIEW_KEYWORDS)


def _normalize_function_name(name: str) -> str:
    """Normalize a function name for lightweight coverage checks."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _extract_listed_functions(answer: str) -> list[str]:
    """Extract functions from the section 3 decomposition, falling back to item definition."""
    functions: list[str] = []

    decomposition = _extract_section(
        answer,
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?functional decomposition\b.*$",
    )
    if decomposition:
        lines = decomposition.splitlines()
        for index, line in enumerate(lines):
            lower = line.lower()
            if "|" in line and not re.search(r"\bfunction\b\s*\|", lower):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                first_cell = cells[0] if cells else ""
                if first_cell and not set(first_cell) <= {"-", ":"}:
                    functions.append(first_cell)
            elif re.match(r"(?i)^\s*function\s*:", line):
                value = line.split(":", 1)[1].strip(" .;")
                if value:
                    functions.append(value)

    # Fallback: common item definition format "Functions: A, B, and C."
    if not functions:
        match = re.search(r"(?im)^functions?\s*:\s*(.+)$", answer)
        if match:
            raw = match.group(1).strip().rstrip(".")
            raw = raw.replace(" and ", ", ")
            functions.extend(part.strip(" .;") for part in raw.split(",") if part.strip(" .;"))

    seen: set[str] = set()
    unique: list[str] = []
    for function in functions:
        key = _normalize_function_name(function)
        if key and key not in seen:
            seen.add(key)
            unique.append(function)
    return unique


def _extract_section(answer: str, heading_pattern: str) -> str:
    """Extract a numbered/markdown section by heading pattern."""
    start = re.search(heading_pattern, answer, flags=re.IGNORECASE | re.MULTILINE)
    if not start:
        return ""
    section_start = start.start()
    while section_start < len(answer) and answer[section_start] in "\r\n":
        section_start += 1
    section = answer[section_start:]
    first_newline = section.find("\n")
    if first_newline == -1:
        return section
    tail = section[first_newline + 1 :]
    next_heading = re.search(r"(?m)^\s*(?:#{1,6}\s*)?\d+\.\s+\S+", tail)
    if next_heading:
        return section[: first_newline + 1 + next_heading.start()]
    return section


def _missing_hara_functions(answer: str, functions: list[str]) -> list[str]:
    """Return functions from the function list that do not appear in the HARA section."""
    if not functions or "hara" not in answer.lower():
        return []

    hara_text = _extract_section(answer, r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?hara\b.*$")
    if not hara_text:
        return []

    normalized_hara = _normalize_function_name(hara_text)
    missing = []
    for function in functions:
        normalized_function = _normalize_function_name(function)
        if normalized_function and normalized_function not in normalized_hara:
            missing.append(function)
    return missing


def _missing_iso26262_lifecycle_parts(question: str, answer: str) -> list[str]:
    """Return required ISO 26262 lifecycle parts missing from a lifecycle answer."""
    text = f"{question}\n{answer}".lower()
    lifecycle_intent = any(
        phrase in text
        for phrase in (
            "safety lifecycle",
            "whole safety lifecycle",
            "safety case",
            "developing a",
            "development of",
        )
    )
    if not lifecycle_intent or "iso 26262" not in text:
        return []

    required_parts = [
        "Part 2",
        "Part 3",
        "Part 4",
        "Part 5",
        "Part 6",
        "Part 7",
        "Part 8",
        "Part 9",
    ]
    missing = []
    for part in required_parts:
        if not re.search(rf"(?i)\b{re.escape(part)}\b", answer):
            missing.append(part)

    # Catch answers that mention parts only in passing but omit engineering domains.
    domain_terms = ("system", "hardware", "software", "production", "operation", "supporting", "dependent failure")
    if not any(term in answer.lower() for term in domain_terms):
        missing.extend(part for part in ("Part 4", "Part 5", "Part 6", "Part 7", "Part 8", "Part 9") if part not in missing)

    return missing


def _review_lifecycle_answer(question: str, answer: str) -> str:
    """Revise lifecycle answers when key HARA or ISO lifecycle coverage is missing."""
    if not _needs_lifecycle_review(question, answer):
        return answer

    functions = _extract_listed_functions(answer)
    missing_functions = _missing_hara_functions(answer, functions)
    missing_iso_parts = _missing_iso26262_lifecycle_parts(question, answer)
    functional_decomposition = _extract_section(
        answer,
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?functional decomposition\b.*$",
    )
    decomposition_is_table = bool(functional_decomposition and "|" in functional_decomposition)
    if not missing_functions and decomposition_is_table and not missing_iso_parts:
        return answer

    reviewer = ChatOpenAI(
        model=cfg.LLM_MODEL,
        temperature=0,
        max_tokens=cfg.OPENAI_MAX_TOKENS,
        timeout=cfg.OPENAI_TIMEOUT,
        openai_api_key=cfg.OPENAI_API_KEY,
    )
    completion_marker = "<<END_OF_SAFETY_ANALYSIS>>"
    review_prompt = f"""
You are reviewing an answer from Autonomous Driving Safety Analyst before it is shown to the user.

The draft answer lists these functions:
{", ".join(functions)}

The HARA section is missing these listed functions:
{", ".join(missing_functions) if missing_functions else "None"}

The ISO 26262 lifecycle assessment is missing or too generic for these parts:
{", ".join(missing_iso_parts) if missing_iso_parts else "None"}

Rewrite the answer with only these required changes:
1. Format section 3, Functional Decomposition, as a markdown table.
2. Update section 4, HARA Screening, so it has exactly one row for each listed
   function above and no rows for anything else. Use the exact function names
   from the list. Do not add rows for safety goals, faults, mechanisms, ISO
   parts, test cases, lifecycle stages, scenario assumptions, or design
   decisions.
3. For each HARA row, provide S/E/C rationale and ASIL/QM, or mark it QM/not
   safety-relevant for ISO 26262 with rationale.
4. If the user asked for lifecycle, development, or safety case analysis, include
   an ISO 26262 Part 2-9 lifecycle assessment table. It must explicitly cover:
   Part 2 functional safety management, Part 3 concept/HARA/safety goals,
   Part 4 system development, Part 5 hardware development, Part 6 software
   development, Part 7 production/operation/service, Part 8 supporting
   processes, and Part 9 ASIL-oriented/safety-oriented analyses. For each row,
   include item-specific engineering activities, expected evidence/work products,
   rationale/unsafe behavior prevented, and interaction with SOTIF/ISO 8800.
   Do not replace this with a generic one-line ISO 26262 summary.

Keep all other sections as close to the draft as possible. Do not explain that
you reviewed or revised it. Do not invent exact ISO clause numbers.
At the very end of the complete rewritten answer, add this exact marker on its
own line: {completion_marker}

User question:
{question}

Draft answer:
{answer}
"""
    reviewed = reviewer.invoke([("human", review_prompt)])
    content = getattr(reviewed, "content", "").strip()
    if not content:
        return answer
    if completion_marker not in content:
        logger.warning("Lifecycle review output was incomplete; keeping original draft answer.")
        return answer
    return content.replace(completion_marker, "").strip() or answer


def _split_tts_text(text: str, max_chars: int) -> list[str]:
    """Split a long answer into TTS-sized chunks at paragraph boundaries."""
    clean_text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not clean_text:
        return []

    paragraphs = clean_text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars].strip())
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.strip())
            current = paragraph
    if current:
        chunks.append(current.strip())
    return chunks


def _synthesize_openai_tts(chunk: str, audio_path: Path) -> None:
    """Generate one OpenAI TTS audio file."""
    client = OpenAI(api_key=cfg.OPENAI_API_KEY)
    response = client.audio.speech.create(
        model=cfg.TTS_MODEL,
        voice=cfg.TTS_VOICE,
        input=chunk,
    )
    if hasattr(response, "stream_to_file"):
        response.stream_to_file(audio_path)
    else:
        audio_path.write_bytes(response.content)


def _synthesize_answer_audio(answer: str, autoplay: bool | None = None) -> list[Path]:
    """Generate fixed-voice answer audio when TTS is enabled."""
    if not cfg.TTS_ENABLED:
        return []

    chunks = _split_tts_text(answer, max(500, cfg.TTS_MAX_CHARS))
    if not chunks:
        return []

    output_dir = Path(cfg.TTS_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    audio_paths: list[Path] = []
    for index, chunk in enumerate(chunks, 1):
        suffix = f"_part{index}" if len(chunks) > 1 else ""
        audio_path = output_dir / f"analyst_answer_openai_{timestamp}{suffix}.mp3"
        try:
            _synthesize_openai_tts(chunk, audio_path)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            detail = exc.response.text[:300].replace("\n", " ")
            print(
                "[WARNING] Voice output failed. "
                f"OpenAI TTS returned HTTP {status_code}: {detail}"
            )
            return audio_paths
        except Exception as exc:
            print(f"[WARNING] Voice output failed: {exc}")
            return audio_paths
        audio_paths.append(audio_path)

    should_autoplay = cfg.TTS_AUTOPLAY if autoplay is None else autoplay
    if should_autoplay and sys.platform == "darwin":
        for audio_path in audio_paths:
            print(f"Playing voice output: {audio_path}")
            playback = subprocess.run(
                ["afplay", str(audio_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if playback.returncode != 0:
                print(
                    "[WARNING] Voice file was created, but autoplay failed: "
                    f"{playback.stderr.strip() or playback.stdout.strip()}"
                )
    elif should_autoplay:
        print("[WARNING] TTS_AUTOPLAY is only implemented for macOS afplay.")

    return audio_paths


def main() -> None:
    """Run an interactive terminal chat."""
    agent = build_agent()
    print("\nAutonomous Driving Safety Analyst")
    print("Ask a question. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            break
        if not question:
            continue

        result = agent.invoke({"input": question})
        answer = _review_lifecycle_answer(question, result["output"])
        print(f"\nAnalyst: {answer}\n")
        audio_paths = _synthesize_answer_audio(answer)
        if audio_paths:
            formatted_paths = ", ".join(str(path) for path in audio_paths)
            print(f"Voice output saved: {formatted_paths}\n")


if __name__ == "__main__":
    main()
