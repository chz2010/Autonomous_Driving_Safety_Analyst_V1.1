"""
MCP server for the Autonomous Driving Safety Analyst knowledge base.

This exposes Project 1 as a read-only standards and evidence retrieval service
for agentic clients such as Project 2 or a future Project 3 co-pilot.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ingestion.standards_ingestion import get_vector_store as get_standards_store
from ingestion.video_ingestion import get_vector_store as get_video_store


mcp = FastMCP(
    "Autonomous Driving Safety Analyst Knowledge Base",
    json_response=True,
)


def _limit_k(k: int) -> int:
    """Keep retrieval bounded for MCP clients."""
    return max(1, min(int(k), 10))


def _safe_text(text: str, max_chars: int = 1200) -> str:
    """Trim long chunks while keeping tool responses readable."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _doc_payload(doc: Any, index: int, source_type: str) -> dict[str, Any]:
    """Convert a LangChain document into a stable MCP response payload."""
    metadata = dict(getattr(doc, "metadata", {}) or {})
    return {
        "rank": index,
        "source_type": source_type,
        "content": _safe_text(getattr(doc, "page_content", "")),
        "metadata": metadata,
    }


def _error_payload(tool: str, exc: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "tool": tool,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }


@mcp.tool()
def get_knowledge_base_status() -> dict[str, Any]:
    """
    Return basic status and chunk counts for the standards and video databases.

    Use this before retrieval to confirm that Project 1 has ingested evidence.
    """
    status: dict[str, Any] = {"status": "ok", "databases": {}}

    try:
        standards_store = get_standards_store(embedding_backend="openai")
        status["databases"]["standards"] = {
            "available": True,
            "collection": standards_store._collection.name,
            "chunk_count": standards_store._collection.count(),
        }
    except Exception as exc:
        status["databases"]["standards"] = {
            "available": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }

    try:
        local_standards_store = get_standards_store(embedding_backend="local")
        status["databases"]["local_standards"] = {
            "available": True,
            "collection": local_standards_store._collection.name,
            "chunk_count": local_standards_store._collection.count(),
        }
    except Exception as exc:
        status["databases"]["local_standards"] = {
            "available": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }

    try:
        video_store = get_video_store()
        status["databases"]["videos"] = {
            "available": True,
            "collection": video_store._collection.name,
            "chunk_count": video_store._collection.count(),
        }
    except Exception as exc:
        status["databases"]["videos"] = {
            "available": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }

    return status


@mcp.tool()
def search_safety_standards(
    query: str,
    k: int = 5,
    standard: str | None = None,
    embedding_backend: str = "openai",
) -> dict[str, Any]:
    """
    Search the standards/document database for safety engineering evidence.

    Args:
        query: Safety, ADAS, HARA, SOTIF, ISO 8800, validation, or assurance query.
        k: Number of chunks to return, capped at 10.
        standard: Optional metadata filter, for example "ISO 26262",
            "ISO 21448", "ISO 8800", "Euro NCAP", "IIHS", "Dataset Profile",
            or "Project Safety Case Example".
        embedding_backend: "openai" for the main standards DB or "local" for
            the local HuggingFace standards DB.
    """
    try:
        store = get_standards_store(embedding_backend=embedding_backend)
        search_kwargs: dict[str, Any] = {"k": _limit_k(k)}
        if standard:
            search_kwargs["filter"] = {"standard": standard}
        docs = store.similarity_search(query, **search_kwargs)
        return {
            "status": "ok",
            "query": query,
            "standard_filter": standard,
            "embedding_backend": embedding_backend,
            "result_count": len(docs),
            "results": [
                _doc_payload(doc, index, "standards")
                for index, doc in enumerate(docs, start=1)
            ],
        }
    except Exception as exc:
        return _error_payload("search_safety_standards", exc)


@mcp.tool()
def search_video_evidence(
    query: str,
    k: int = 5,
    failure_cases_only: bool = False,
) -> dict[str, Any]:
    """
    Search the video transcript database for scenario, failure, and lecture evidence.

    Args:
        query: Technical scenario or concept query.
        k: Number of chunks to return, capped at 10.
        failure_cases_only: Restrict to autonomous-driving failure-case videos.
    """
    try:
        store = get_video_store()
        search_kwargs: dict[str, Any] = {"k": _limit_k(k)}
        if failure_cases_only:
            search_kwargs["filter"] = {"category": "autonomous_driving_failure_case"}
        docs = store.similarity_search(query, **search_kwargs)
        return {
            "status": "ok",
            "query": query,
            "failure_cases_only": failure_cases_only,
            "result_count": len(docs),
            "results": [
                _doc_payload(doc, index, "video_transcript")
                for index, doc in enumerate(docs, start=1)
            ],
        }
    except Exception as exc:
        return _error_payload("search_video_evidence", exc)


@mcp.tool()
def search_combined_safety_context(
    query: str,
    k_per_source: int = 4,
    standard: str | None = None,
) -> dict[str, Any]:
    """
    Search both standards/documents and video transcripts for combined context.

    This is useful when another project needs both normative/reference evidence
    and practical scenario evidence for one safety engineering question.
    """
    standards = search_safety_standards(
        query=query,
        k=k_per_source,
        standard=standard,
        embedding_backend="openai",
    )
    videos = search_video_evidence(query=query, k=k_per_source)

    return {
        "status": "ok",
        "query": query,
        "standards": standards,
        "videos": videos,
    }


@mcp.resource("safety-analyst://usage")
def usage_notes() -> str:
    """Return concise usage notes for MCP clients."""
    return (
        "Use this MCP server as a read-only retrieval layer for Project 1. "
        "The standards database contains ISO 26262, ISO 21448/SOTIF, ISO 8800, "
        "NCAP/IIHS documents, dataset profiles, and project examples when they "
        "have been ingested locally. The video database contains YouTube or "
        "Whisper transcript chunks, including public educational railway RAMS "
        "lecture context if ingested. Railway lecture transcripts are educational "
        "context only and must not be presented as official IEC/EN standard text."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
