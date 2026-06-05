"""
ingestion/standards_ingestion.py

Pipeline — ISO standard PDFs → Chroma vector DB (standards_db)

Flow:
  PDF files (ISO 26262, SOTIF, ISO 8800, ...)
      ↓  pdfplumber (clause-aware extraction)
  Structured text with clause metadata
      ↓  RecursiveCharacterTextSplitter (clause-aligned)
  Chunks (300 tok, 40 overlap)
      ↓  OpenAIEmbeddings or local HuggingFace embeddings
  Chroma collection: iso_standards or local_iso_standards

Metadata stored per chunk:
  - standard      : e.g. "ISO 26262"
  - part          : e.g. "Part 4" (where applicable)
  - clause        : e.g. "6.4.3"
  - section_title : e.g. "Hardware architectural design"
  - asil_level    : e.g. "ASIL-D" (extracted if present)
  - source        : "iso_standard"
  - filename      : original PDF filename
  - page          : page number in the PDF
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

import pdfplumber
from tqdm import tqdm

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document

from config import cfg

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception:  # pragma: no cover - only needed when optional local deps are absent
    HuggingFaceEmbeddings = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── Standard definitions ─────────────────────────────────────────────────────
# Map each PDF filename to its standard metadata.
# Place your PDFs in the  standards_pdfs/  directory.
STANDARD_DEFINITIONS = {
    "iso_26262_part1.pdf": {
        "standard": "ISO 26262",
        "part": "Part 1",
        "description": "Vocabulary",
    },
    "iso_26262_part2.pdf": {
        "standard": "ISO 26262",
        "part": "Part 2",
        "description": "Management of functional safety",
    },
    "iso_26262_part3.pdf": {
        "standard": "ISO 26262",
        "part": "Part 3",
        "description": "Concept phase",
    },
    "iso_26262_part4.pdf": {
        "standard": "ISO 26262",
        "part": "Part 4",
        "description": "Product development at system level",
    },
    "iso_26262_part5.pdf": {
        "standard": "ISO 26262",
        "part": "Part 5",
        "description": "Product development at hardware level",
    },
    "iso_26262_part6.pdf": {
        "standard": "ISO 26262",
        "part": "Part 6",
        "description": "Product development at software level",
    },
    "iso_26262_part7.pdf": {
        "standard": "ISO 26262",
        "part": "Part 7",
        "description": "Production, operation, service and decommissioning",
    },
    "iso_26262_part8.pdf": {
        "standard": "ISO 26262",
        "part": "Part 8",
        "description": "Supporting processes",
    },
    "iso_26262_part9.pdf": {
        "standard": "ISO 26262",
        "part": "Part 9",
        "description": "ASIL-oriented and safety-oriented analyses",
    },
    "iso_26262_part10.pdf": {
        "standard": "ISO 26262",
        "part": "Part 10",
        "description": "Guidelines on ISO 26262",
    },
    "iso_26262_part11.pdf": {
        "standard": "ISO 26262",
        "part": "Part 11",
        "description": "Guidelines on application of ISO 26262 to semiconductors",
    },
    "iso_26262_part12.pdf": {
        "standard": "ISO 26262",
        "part": "Part 12",
        "description": "Adaptation of ISO 26262 for motorcycles",
    },
    "iso_21448_sotif.pdf": {
        "standard": "ISO 21448",
        "part": "Full standard",
        "description": "Safety of the intended functionality (SOTIF)",
    },
    "iso_8800.pdf": {
        "standard": "ISO 8800",
        "part": "Full standard",
        "description": "Road vehicles — Safety and artificial intelligence",
    },
    "iso_26262_evaluation_scheme.md": {
        "standard": "ISO 26262 Evaluation Scheme",
        "part": "Functional safety evaluation guidance",
        "description": "Structured ISO 26262 evaluation scheme for HARA, safety lifecycle, V&V, and safety case evidence",
    },
    "hara_exposure_catalogue_en.pdf": {
        "standard": "HARA Exposure Catalogue",
        "part": "Exposure classification",
        "description": "Exposure guidance for ISO 26262 HARA operational situations",
    },
    "nuscenes_dataset_profile.md": {
        "standard": "Dataset Profile",
        "part": "nuScenes",
        "description": "nuScenes dataset coverage and ISO 8800 safety relevance profile",
    },
    "sotif_evaluation_scheme.md": {
        "standard": "SOTIF Evaluation Scheme",
        "part": "Evaluation guidance",
        "description": "Structured SOTIF evaluation scheme for triggering conditions, scenario coverage, and residual risk",
    },
    "iso_8800_evaluation_scheme.md": {
        "standard": "ISO 8800 Evaluation Scheme",
        "part": "AI safety evaluation guidance",
        "description": "Structured ISO 8800 evaluation scheme for AI safety, data coverage, robustness, and model lifecycle risk",
    },
    "project_example_lidar_perception_safety_case.md": {
        "standard": "Project Safety Case Example",
        "part": "LiDAR perception item",
        "description": "Project-generated worked example safety case for LiDAR perception across ISO 26262, SOTIF, and ISO 8800",
    },
    "project_example_lane_maintaining_perception_safety_case.md": {
        "standard": "Project Safety Case Example",
        "part": "Lane maintaining perception item",
        "description": "Project-generated worked example safety case for lane maintaining perception across ISO 26262, SOTIF, and ISO 8800",
    },
    "project_example_aeb_pedestrian_safety_case.md": {
        "standard": "Project Safety Case Example",
        "part": "AEB pedestrian perception item",
        "description": "Project-generated worked example safety case for AEB pedestrian perception across ISO 26262, SOTIF, and ISO 8800",
    },
    "euro_ncap_lexus_lbx.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Lexus LBX safety assessment report",
    },
    "euro_ncap_audi_a6_e-tron.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Audi A6 e-tron safety assessment report",
    },
    "euro_ncap_honda_cr-v.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Honda CR-V safety assessment report",
    },
    "euro_ncap_mercedes-benz_cle_coupé.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Mercedes-Benz CLE Coupe safety assessment report",
    },
    "euro_ncap_tesla_model_3.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Tesla Model 3 safety assessment report",
    },
    "euro_ncap_tesla_model_y.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Tesla Model Y safety assessment report",
    },
    "euro_ncap_toyota_c-hr+.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Toyota C-HR+ safety assessment report",
    },
    "euro_ncap_volkswagen_id.7.pdf": {
        "standard": "Euro NCAP",
        "part": "Vehicle assessment report",
        "description": "Volkswagen ID.7 safety assessment report",
    },
    "iihs_2026_bmw_5_series.pdf": {
        "standard": "IIHS",
        "part": "Vehicle safety assessment report",
        "description": "2026 BMW 5 Series IIHS safety assessment report",
    },
    "iihs_2026_mercedes-benz_c-class.pdf": {
        "standard": "IIHS",
        "part": "Vehicle safety assessment report",
        "description": "2026 Mercedes-Benz C-Class IIHS safety assessment report",
    },
}

# Regex patterns for extracting structure from ISO documents
CLAUSE_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$", re.MULTILINE)
ASIL_PATTERN = re.compile(r"\bASIL[- ]?([A-D]|QM)\b", re.IGNORECASE)


# ── PDF extraction ───────────────────────────────────────────────────────────

def extract_pages(pdf_path: Path, standard_meta: dict) -> list[Document]:
    """
    Extract text from a PDF page by page using pdfplumber.
    Returns one Document per page with rich metadata.
    """
    docs = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                continue  # skip blank or near-blank pages

            # Detect the clause number from the first line of the page
            clause = _detect_clause(text)

            # Detect any ASIL levels mentioned on this page
            asil_levels = list(set(ASIL_PATTERN.findall(text)))

            metadata = {
                "standard": standard_meta["standard"],
                "part": standard_meta["part"],
                "description": standard_meta["description"],
                "clause": clause,
                "asil_level": ", ".join(asil_levels) if asil_levels else "not specified",
                "page": page_num,
                "filename": pdf_path.name,
                "source": "iso_standard",
            }

            docs.append(Document(page_content=text, metadata=metadata))

    log.info(
        f"Extracted {len(docs)} pages from {pdf_path.name} "
        f"({standard_meta['standard']} {standard_meta['part']})"
    )
    return docs


def extract_text_document(text_path: Path, standard_meta: dict) -> list[Document]:
    """Extract a Markdown or text safety document with section-level metadata."""
    text = text_path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    section_docs = _split_text_into_sections(text, text_path, standard_meta)
    log.info(
        f"Extracted text document: {text_path.name} "
        f"({standard_meta['standard']}, {len(section_docs)} sections)"
    )
    return section_docs


def _slugify_heading(value: str) -> str:
    """Create a stable metadata label from a Markdown heading."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def _metadata_for_text_section(
    text_path: Path,
    standard_meta: dict,
    clause: str,
    section_title: str,
    page: int,
) -> dict:
    """Build metadata for one Markdown/text section."""
    return {
        "standard": standard_meta["standard"],
        "part": standard_meta["part"],
        "description": standard_meta["description"],
        "clause": clause,
        "asil_level": "not specified",
        "page": page,
        "filename": text_path.name,
        "source": "safety_document",
        "section_title": section_title,
    }


def _split_text_into_sections(text: str, text_path: Path, standard_meta: dict) -> list[Document]:
    """Split Markdown into heading sections and assign clause-like labels."""
    heading_matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
    if not heading_matches:
        return [
            Document(
                page_content=text,
                metadata=_metadata_for_text_section(
                    text_path=text_path,
                    standard_meta=standard_meta,
                    clause="document",
                    section_title=text_path.stem,
                    page=1,
                ),
            )
        ]

    docs: list[Document] = []
    if heading_matches[0].start() > 0:
        preamble = text[: heading_matches[0].start()].strip()
        if preamble:
            docs.append(
                Document(
                    page_content=preamble,
                    metadata=_metadata_for_text_section(
                        text_path=text_path,
                        standard_meta=standard_meta,
                        clause="preamble",
                        section_title="Preamble",
                        page=1,
                    ),
                )
            )

    for idx, match in enumerate(heading_matches, start=1):
        start = match.start()
        end = heading_matches[idx].start() if idx < len(heading_matches) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue

        heading = match.group(2).strip()
        numbered = re.match(r"^(\d+(?:\.\d+)*)[.)]?\s+(.+)$", heading)
        if numbered:
            clause = numbered.group(1)
            section_title = numbered.group(2).strip()
        else:
            clause = _slugify_heading(heading)
            section_title = heading

        docs.append(
            Document(
                page_content=section_text,
                metadata=_metadata_for_text_section(
                    text_path=text_path,
                    standard_meta=standard_meta,
                    clause=clause,
                    section_title=section_title,
                    page=len(docs) + 1,
                ),
            )
        )

    return docs


def _detect_clause(text: str) -> str:
    """
    Try to detect the primary clause number from a block of text.
    Returns 'unknown' if no clause pattern is found.
    """
    match = CLAUSE_PATTERN.search(text)
    if match:
        return match.group(1)
    markdown_match = re.search(r"(?m)^#{1,6}\s+(\d+(?:\.\d+)*)[.)]?\s+", text)
    if markdown_match:
        return markdown_match.group(1)
    return "unknown"


def _detect_section_title(text: str) -> str:
    """Extract first heading-like line from text as the section title."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 5 and len(line) < 120 and not line[0].islower():
            return line[:100]
    return "Unknown section"


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_documents(docs: list[Document]) -> list[Document]:
    """
    Split ISO documents into clause-aligned chunks.
    Separators prioritise clause/section breaks first.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.STANDARDS_CHUNK_SIZE,
        chunk_overlap=cfg.STANDARDS_CHUNK_OVERLAP,
        separators=[
            "\n\n\n",       # major section breaks
            "\n\n",         # paragraph breaks
            "\n",           # line breaks
            ". ",           # sentence breaks
            " ",
            "",
        ],
        length_function=len,
    )

    chunks = splitter.split_documents(docs)

    # Enrich each chunk with section title derived from its content
    for chunk in chunks:
        chunk.metadata["section_title"] = chunk.metadata.get("section_title") or _detect_section_title(chunk.page_content)
        detected_clause = _detect_clause(chunk.page_content)
        if detected_clause != "unknown":
            chunk.metadata["clause"] = detected_clause

    log.info(f"Produced {len(chunks)} chunks from {len(docs)} pages")
    return chunks


# ── Vector store ─────────────────────────────────────────────────────────────

def _normalise_embedding_backend(embedding_backend: str) -> str:
    backend = embedding_backend.strip().lower()
    if backend not in {"openai", "local"}:
        raise ValueError("embedding_backend must be either 'openai' or 'local'.")
    return backend


def get_embeddings(embedding_backend: str = "openai"):
    """Return the embedding function for the selected backend."""
    backend = _normalise_embedding_backend(embedding_backend)

    if backend == "local":
        if HuggingFaceEmbeddings is None:
            raise ImportError(
                "Local embeddings require sentence-transformers. "
                "Install project requirements, then run ingestion again."
            )
        return HuggingFaceEmbeddings(
            model_name=cfg.LOCAL_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return OpenAIEmbeddings(
        model=cfg.EMBEDDING_MODEL,
        openai_api_key=cfg.OPENAI_API_KEY,
    )


def get_vector_store(embedding_backend: str = "openai") -> Chroma:
    """Return the persistent standards collection for the selected embedding backend."""
    backend = _normalise_embedding_backend(embedding_backend)
    persist_directory = (
        cfg.CHROMA_LOCAL_STANDARDS_DB_PATH
        if backend == "local"
        else cfg.CHROMA_STANDARDS_DB_PATH
    )
    collection_name = (
        cfg.LOCAL_STANDARDS_COLLECTION_NAME
        if backend == "local"
        else cfg.STANDARDS_COLLECTION_NAME
    )

    os.makedirs(persist_directory, exist_ok=True)

    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(backend),
        persist_directory=persist_directory,
    )


# ── Main ingestion ────────────────────────────────────────────────────────────

def ingest_standards(
    pdf_dir: str = "./standards_pdfs",
    filenames: Optional[list[str]] = None,
    reset: bool = False,
    embedding_backend: str = "openai",
) -> Chroma:
    """
    Main entry point for standards ingestion.

    Args:
        pdf_dir  : directory containing ISO PDF files.
        filenames: optional list of specific filenames to ingest.
                   If None, all recognised PDFs in pdf_dir are processed.
        reset    : if True, wipe the collection before ingesting.
        embedding_backend: "openai" for the main DB or "local" for the
                   open-source draft-mode DB.

    Returns:
        Chroma vector store ready for retrieval.
    """
    backend = _normalise_embedding_backend(embedding_backend)
    if backend == "openai":
        cfg.validate()

    pdf_path = Path(pdf_dir)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF directory '{pdf_dir}' not found. "
            f"Create it and place your ISO standard PDFs inside."
        )

    vector_store = get_vector_store(embedding_backend=backend)

    if reset:
        log.warning(
            "Resetting %s standards vector store — all existing documents will be deleted.",
            backend,
        )
        vector_store.delete_collection()
        vector_store = get_vector_store(embedding_backend=backend)

    # Determine which files to process
    if filenames:
        target_files = [pdf_path / f for f in filenames]
    else:
        target_files = sorted(
            [
                *pdf_path.glob("*.pdf"),
                *pdf_path.glob("*.md"),
                *pdf_path.glob("*.txt"),
            ]
        )

    if not target_files:
        log.warning(f"No PDF files found in '{pdf_dir}'.")
        return vector_store

    all_chunks: list[Document] = []

    for pdf_file in tqdm(target_files, desc="Processing ISO standards"):
        if not pdf_file.exists():
            log.warning(f"File not found: {pdf_file}")
            continue

        # Look up metadata definition; fall back to generic if unknown
        standard_meta = STANDARD_DEFINITIONS.get(
            pdf_file.name.lower(),
            {
                "standard": pdf_file.stem.upper().replace("_", " "),
                "part": "Full standard",
                "description": "Unknown standard",
            },
        )

        try:
            if pdf_file.suffix.lower() == ".pdf":
                pages = extract_pages(pdf_file, standard_meta)
            elif pdf_file.suffix.lower() in {".md", ".txt"}:
                pages = extract_text_document(pdf_file, standard_meta)
            else:
                log.warning(f"Unsupported document type: {pdf_file}")
                continue
            chunks = chunk_documents(pages)
            all_chunks.extend(chunks)
        except Exception as e:
            log.error(f"Failed to process {pdf_file.name}: {e}")
            continue

    if all_chunks:
        batch_size = 50
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            vector_store.add_documents(batch)
            log.info(f"Stored batch {i // batch_size + 1} ({len(batch)} chunks)")

    log.info(
        f"Standards ingestion complete. "
        f"Total chunks: {len(all_chunks)} "
        f"in collection '"
        f"{cfg.LOCAL_STANDARDS_COLLECTION_NAME if backend == 'local' else cfg.STANDARDS_COLLECTION_NAME}'"
    )
    return vector_store


def get_retriever(
    k: int = 4,
    filter_standard: Optional[str] = None,
    embedding_backend: str = "openai",
):
    """
    Return a retriever over the standards DB.

    Args:
        k               : number of chunks to retrieve.
        filter_standard : optionally restrict to one standard,
                          e.g. "ISO 26262" or "ISO 21448"
        embedding_backend: "openai" for the main DB or "local" for the
                          open-source draft-mode standards DB.
    """
    vector_store = get_vector_store(embedding_backend=embedding_backend)

    search_kwargs: dict = {"k": k}
    if filter_standard:
        search_kwargs["filter"] = {"standard": filter_standard}

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest ISO standard PDFs into the standards vector DB"
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default="./standards_pdfs",
        help="Directory containing PDF files",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Specific PDF filenames to ingest (e.g. iso_26262_part4.pdf)",
    )
    parser.add_argument("--reset", action="store_true", help="Wipe DB before ingesting")
    parser.add_argument(
        "--embedding-backend",
        choices=["openai", "local"],
        default="openai",
        help="Embedding backend and vector DB to build",
    )
    args = parser.parse_args()

    ingest_standards(
        pdf_dir=args.pdf_dir,
        filenames=args.files,
        reset=args.reset,
        embedding_backend=args.embedding_backend,
    )
