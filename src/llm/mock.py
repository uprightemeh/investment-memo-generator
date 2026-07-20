"""
Offline stand-in for narrative.py, used by main.py's demo run so the whole
pipeline (including PDF output) can be exercised without an ANTHROPIC_API_KEY
or network access. It follows the exact same contract as the real
functions -- same inputs, same return types -- so swapping this for
narrative.generate_grounded_bullets / generate_narrative_with_verified_math
is a one-line change in main.py, not a rewrite.

Nothing here calls an LLM. It mimics what grounded generation SHOULD
produce (claims paired 1:1 with real chunk citations) using simple
template logic, purely so you can see the full pipeline run and inspect
a real PDF before wiring in an API key.
"""
from src.models.schemas import DocumentChunk, Citation
from src.rag.citation import make_citation


def mock_grounded_bullets(
    topic: str, chunks: list[DocumentChunk], max_bullets: int = 4
) -> tuple[list[str], list[Citation]]:
    claims: list[str] = []
    citations: list[Citation] = []
    for chunk in chunks[:max_bullets]:
        first_sentence = chunk.text.strip().split(".")[0].strip()
        claim = f"({topic}) {first_sentence[:180]}."
        claims.append(claim)
        citations.append(make_citation(claim, chunk))
    return claims, citations


def mock_narrative_paragraph(topic: str, key_facts: dict) -> str:
    """A deliberately plain templated paragraph -- stands in for what the
    real LLM call would produce once it's narrating pre-verified numbers
    from VerifiedMetricStore."""
    facts_str = "; ".join(f"{k}: {v}" for k, v in key_facts.items())
    return (
        f"[MOCK NARRATIVE for '{topic}' -- replace with narrative.py once "
        f"ANTHROPIC_API_KEY is set] Based on verified figures ({facts_str}), "
        f"this section would normally contain LLM-generated prose "
        f"interpreting these results in context."
    )
