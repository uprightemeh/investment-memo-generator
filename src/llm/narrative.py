"""
LLM orchestration layer. This is the ONLY file in the pipeline that talks
to a language model, and it's deliberately thin: its job is prose
generation and citation selection, never arithmetic.

Two guardrails enforced here:
  1. Math: the system prompt forbids stating a number the model didn't get
     from the `lookup_financial_metric` tool (see tool_math.py). We also
     pass VerifiedMetricStore values directly into the prompt as already-
     computed facts for the sections that don't need a live tool loop --
     belt and suspenders, since a static prompt-injected fact is even
     harder to hallucinate around than a tool the model might skip.
  2. Citations: for narrative claims about risks/catalysts, the model is
     required to return structured JSON with a citation naming the exact
     document/section/page, sourced from the chunks we retrieved via
     rag/retriever.py -- not from its own training data about the company.

Requires: pip install anthropic, and an ANTHROPIC_API_KEY environment
variable. This file is NOT executed against a live model in the bundled
demo (see main.py, which uses build_mock_narrative for offline runs) --
swap in `generate_section` once you have an API key.
"""
import os
import json
import anthropic
from src.models.schemas import DocumentChunk, Citation
from src.llm.tool_math import TOOL_SCHEMA, VerifiedMetricStore

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a sell-side equity research analyst writing a section \
of an investment memo. Follow these rules strictly:

1. NEVER state a computed financial number (a margin, growth rate, ratio, \
valuation, or multiple) from memory or estimation. If you need a number, \
call the lookup_financial_metric tool. If the tool returns an error, say \
the figure is unavailable rather than estimating it.
2. Every factual claim about the company's risks, strategy, or business \
model must be grounded in the provided source excerpts. Do not use \
outside knowledge about the company for qualitative claims.
3. Return your response as JSON matching the requested schema exactly, \
with no markdown formatting or commentary outside the JSON object.
"""


def build_citation_prompt(topic: str, chunks: list[DocumentChunk]) -> str:
    """Build the retrieval-grounded portion of the prompt: numbered source
    excerpts the model must cite by index, each carrying its real page
    number so the citation it returns is traceable."""
    excerpt_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        excerpt_blocks.append(
            f"[Source {i}] Document: {chunk.document_name} | "
            f"Section: {chunk.section} | Page: {chunk.page_number}\n"
            f"{chunk.text}"
        )
    excerpts = "\n\n".join(excerpt_blocks)

    return f"""Topic: {topic}

Source excerpts (cite ONLY from these, using the [Source N] labels):

{excerpts}

Return JSON in this exact shape:
{{
  "bullets": [
    {{"claim": "...", "source_index": 1}},
    {{"claim": "...", "source_index": 2}}
  ]
}}

Write 3-5 bullets. Each claim must be a paraphrase (your own words, not a \
quote) of something actually stated in the cited source excerpt."""


def generate_grounded_bullets(
    client: anthropic.Anthropic, topic: str, chunks: list[DocumentChunk]
) -> tuple[list[str], list[Citation]]:
    """Calls the LLM to produce claims + citations for a qualitative
    section (risks or catalysts), grounded in retrieved chunks."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_citation_prompt(topic, chunks)}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    parsed = json.loads(raw_text)

    claims: list[str] = []
    citations: list[Citation] = []
    for bullet in parsed["bullets"]:
        idx = bullet["source_index"] - 1
        if idx < 0 or idx >= len(chunks):
            continue  # model cited a source index that doesn't exist; drop it
        chunk = chunks[idx]
        claims.append(bullet["claim"])
        citations.append(
            Citation(
                claim=bullet["claim"],
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                section=chunk.section,
            )
        )
    return claims, citations


def generate_narrative_with_verified_math(
    client: anthropic.Anthropic,
    topic: str,
    metric_store: VerifiedMetricStore,
    prompt: str,
) -> str:
    """Runs a tool-use loop: the model can call lookup_financial_metric as
    many times as it needs, and we only ever answer with values that
    already came out of dcf.py / ratios.py -- see tool_math.py."""
    messages = [{"role": "user", "content": prompt}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=[TOOL_SCHEMA],
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = metric_store.dispatch_tool_call(block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
        messages.append({"role": "user", "content": tool_results})


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY in your environment to use live narrative "
            "generation. For an offline demo, use llm.mock.build_mock_narrative "
            "instead."
        )
    return anthropic.Anthropic(api_key=api_key)
