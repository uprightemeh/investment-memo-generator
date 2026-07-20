import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rag.chunker import chunk_raw_text_pages
from src.rag.retriever import ChunkRetriever
from src.rag.citation import make_citation, format_citation_footnote
from data.sample.cost_filing_text import SAMPLE_PAGES


def test_chunks_carry_correct_page_numbers():
    chunks = chunk_raw_text_pages("COST_10K_FY2024.pdf", SAMPLE_PAGES)
    assert len(chunks) > 0
    # page 3 in SAMPLE_PAGES (index 2) is where "Item 1A. Risk Factors" starts
    risk_chunks = [c for c in chunks if c.section == "Item 1A. Risk Factors"]
    assert len(risk_chunks) > 0
    assert all(c.page_number >= 3 for c in risk_chunks)


def test_section_detection_persists_across_pages():
    """Risk factors span pages 3-5 in the sample; page 5 has no new header
    but should still be tagged as Risk Factors since it continues the
    same section."""
    chunks = chunk_raw_text_pages("COST_10K_FY2024.pdf", SAMPLE_PAGES)
    page5_chunks = [c for c in chunks if c.page_number == 5]
    assert all(c.section == "Item 1A. Risk Factors" for c in page5_chunks)


def test_retriever_finds_supply_chain_risk():
    chunks = chunk_raw_text_pages("COST_10K_FY2024.pdf", SAMPLE_PAGES)
    retriever = ChunkRetriever(chunks)
    results = retriever.retrieve("supply chain disruption inventory risk", top_k=3)
    assert len(results) > 0
    assert any("supply chain" in r.text.lower() for r in results)


def test_retriever_finds_membership_fee_dependence():
    chunks = chunk_raw_text_pages("COST_10K_FY2024.pdf", SAMPLE_PAGES)
    retriever = ChunkRetriever(chunks)
    results = retriever.retrieve("membership fee income dependence risk", top_k=3)
    assert any("membership fee" in r.text.lower() for r in results)


def test_citation_round_trip():
    chunks = chunk_raw_text_pages("COST_10K_FY2024.pdf", SAMPLE_PAGES)
    retriever = ChunkRetriever(chunks)
    top_chunk = retriever.retrieve("labor costs unionization", top_k=1)[0]
    citation = make_citation("Rising labor costs could pressure margins.", top_chunk)
    footnote = format_citation_footnote(citation, 1)
    assert citation.page_number == top_chunk.page_number
    assert "COST_10K_FY2024.pdf" in footnote
    assert f"p. {top_chunk.page_number}" in footnote
