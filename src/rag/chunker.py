"""
PDF chunking with page-level provenance.

The failure mode this file exists to prevent: most RAG tutorials chunk a
PDF into plain text blobs and throw away the page number. Then when the
LLM cites a fact, you have no way to point the reader back to the exact
page. Here, EVERY chunk carries (document_name, section, page_number) all
the way through retrieval and into the final citation -- that's the whole
mechanism behind 'Source Attribution'.

Uses pdfplumber for text extraction. For scanned/image-only filings you'd
add an OCR fallback (pytesseract) -- not included here since EDGAR filings
are almost always digitally-native text, not scans.
"""
import re
from src.models.schemas import DocumentChunk

# Section headers we recognize in a standard 10-K, used to tag chunks with
# their section even though pdfplumber only gives us raw text per page.
_SECTION_PATTERNS = [
    (re.compile(r"item\s+1a\.?\s+risk factors", re.IGNORECASE), "Item 1A. Risk Factors"),
    (re.compile(r"item\s+1\.?\s+business", re.IGNORECASE), "Item 1. Business"),
    (re.compile(r"item\s+7\.?\s+management.s discussion", re.IGNORECASE), "Item 7. MD&A"),
    (re.compile(r"item\s+7a\.?\s+quantitative and qualitative", re.IGNORECASE), "Item 7A. Market Risk"),
    (re.compile(r"item\s+8\.?\s+financial statements", re.IGNORECASE), "Item 8. Financial Statements"),
]


def detect_section(page_text: str, current_section: str) -> str:
    """Scan a page for a new section header; otherwise carry forward the
    last known section (since a section usually spans many pages)."""
    for pattern, label in _SECTION_PATTERNS:
        if pattern.search(page_text):
            return label
    return current_section


def chunk_pdf(
    pdf_path: str,
    document_name: str,
    max_chars_per_chunk: int = 1200,
) -> list[DocumentChunk]:
    """Extract text page-by-page, tag each page with its section, then split
    long pages into smaller retrieval-sized chunks -- all while keeping the
    page number and section attached to every resulting chunk.

    Requires pdfplumber (pip install pdfplumber). Import is local to this
    function so the rest of the package works even if pdfplumber isn't
    installed and you're only using the sample-data path.
    """
    import pdfplumber

    chunks: list[DocumentChunk] = []
    current_section = "Front Matter"
    chunk_counter = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            current_section = detect_section(text, current_section)

            # Split page text into sub-chunks if it's long, on paragraph
            # boundaries where possible so we don't cut a sentence in half.
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            buffer = ""
            for para in paragraphs:
                if len(buffer) + len(para) > max_chars_per_chunk and buffer:
                    chunk_counter += 1
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{document_name}-{chunk_counter}",
                            document_name=document_name,
                            section=current_section,
                            page_number=page_index,
                            text=buffer.strip(),
                        )
                    )
                    buffer = ""
                buffer += para + "\n\n"
            if buffer.strip():
                chunk_counter += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_name}-{chunk_counter}",
                        document_name=document_name,
                        section=current_section,
                        page_number=page_index,
                        text=buffer.strip(),
                    )
                )

    return chunks


def chunk_raw_text_pages(
    document_name: str,
    pages: list[str],
    max_chars_per_chunk: int = 1200,
) -> list[DocumentChunk]:
    """Same chunking logic as chunk_pdf, but for when you already have
    page text in memory (e.g. from the bundled sample filing, or from an
    HTML filing you parsed some other way). This is what the demo pipeline
    uses so it can run without a real PDF file on disk."""
    chunks: list[DocumentChunk] = []
    current_section = "Front Matter"
    chunk_counter = 0

    for page_index, text in enumerate(pages, start=1):
        if not text.strip():
            continue
        current_section = detect_section(text, current_section)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        buffer = ""
        for para in paragraphs:
            if len(buffer) + len(para) > max_chars_per_chunk and buffer:
                chunk_counter += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_name}-{chunk_counter}",
                        document_name=document_name,
                        section=current_section,
                        page_number=page_index,
                        text=buffer.strip(),
                    )
                )
                buffer = ""
            buffer += para + "\n\n"
        if buffer.strip():
            chunk_counter += 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document_name}-{chunk_counter}",
                    document_name=document_name,
                    section=current_section,
                    page_number=page_index,
                    text=buffer.strip(),
                )
            )

    return chunks
