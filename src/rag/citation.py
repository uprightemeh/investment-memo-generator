"""
Turns a DocumentChunk into a Citation attached to a specific claim, and
formats citations for display in the PDF (as footnotes / page references).
"""
from src.models.schemas import DocumentChunk, Citation


def make_citation(claim: str, chunk: DocumentChunk) -> Citation:
    return Citation(
        claim=claim,
        document_name=chunk.document_name,
        page_number=chunk.page_number,
        section=chunk.section,
    )


def format_citation_footnote(citation: Citation, index: int) -> str:
    """e.g. '[3] COST_10K_FY2024.pdf, Item 1A. Risk Factors, p. 12'"""
    return f"[{index}] {citation.document_name}, {citation.section}, p. {citation.page_number}"


def format_citations_block(citations: list[Citation]) -> str:
    return "\n".join(
        format_citation_footnote(c, i) for i, c in enumerate(citations, start=1)
    )
