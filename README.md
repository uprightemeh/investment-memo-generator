# Investment Memo Generator

   ![tests](https://github.com/uprightemeh/investment-memo-generator/actions/workflows/tests.yml/badge.svg)

   Generates a sell-side-style equity research memo (DCF, comps, ratios,
   risks/catalysts with citations, buy/hold/sell) as a PDF, from a stock
   ticker. Includes a fully formula-driven Excel DCF model as a companion
   deliverable.
## Quickstart

```bash
pip install -r requirements.txt
python main.py --ticker COST --sample
```

Output: `output/COST_investment_memo.pdf`

`--sample` uses bundled offline data so the whole pipeline runs with no
API key and no network access — good for demoing or for a CI test run.
Drop it (once you wire in an `ANTHROPIC_API_KEY` and want live SEC data)
to hit real SEC EDGAR and generate live LLM narrative — see the two
`LIVE MODE` comments in `main.py` for exactly what to swap.

## Why this isn't just a stock screener

Most "AI investment memo" projects are a prompt: dump some numbers into an
LLM and ask it to write a report. That produces plausible-sounding prose
built on numbers the model may have invented. This project is architected
so that's structurally impossible for the financial figures:

**1. The LLM never computes a number.**
`src/engine/dcf.py`, `ratios.py`, and `comparables.py` are pure,
unit-tested Python functions with zero LLM involvement (see
`tests/test_dcf.py`, `test_ratios.py`). By the time an LLM touches
anything (`src/llm/narrative.py`), every margin, growth rate, and DCF
output already exists as a verified number. The LLM's only access to
numbers is a tool call (`src/llm/tool_math.py`) that looks up an
already-computed value — it cannot "call a calculator wrong" because it
never calculates anything.

**2. Every qualitative claim is grounded and cited to an exact page.**
`src/rag/chunker.py` extracts filing text with page number + SEC section
attached to every chunk. `src/rag/retriever.py` does TF-IDF retrieval to
find the chunks relevant to "risks" or "catalysts." The LLM is only shown
those retrieved excerpts and required to return each claim paired with
which excerpt it came from (`src/llm/narrative.py::generate_grounded_bullets`).
The citation that ends up in the PDF footnote — document, section, page —
is the real metadata carried through from extraction, not something the
model asserts.

**3. Multimodal-ready document parsing.**
`chunker.py`'s `chunk_pdf()` uses `pdfplumber` to walk a real 10-K PDF
page by page, tagging each page with its `Item` section via regex on
recognized 10-K headers. It's structured so the qualitative sections
(Risk Factors, MD&A) get chunked with provenance for RAG, while the
numeric financial statements are pulled separately and exactly via SEC's
XBRL API (`src/data/edgar_client.py`) rather than parsed out of PDF text —
XBRL tags are already machine-readable, so this sidesteps a whole class
of "OCR misread a number" bugs for anything EDGAR tags.

## Architecture

```
data/sample/              Bundled sample data (Costco) for offline demo
  cost_financials.py         XBRL-shaped financials, same schema as live EDGAR pull
  cost_filing_text.py        Sample 10-K narrative text, paginated

src/models/schemas.py     Pydantic schemas — the shared contract every module uses

src/data/
  edgar_client.py            REAL SEC EDGAR client (live, needs network)

src/engine/                DETERMINISTIC MATH — no LLM, fully unit tested
  dcf.py                      DCF: per-year projection, terminal value, sensitivity table
  ratios.py                   Margins, ROE, growth, liquidity ratios
  comparables.py              Peer multiple statistics (median/mean)

src/rag/                   RETRIEVAL + CITATION
  chunker.py                  PDF -> page-tagged, section-tagged chunks
  retriever.py                TF-IDF retrieval over chunks
  citation.py                 Chunk -> Citation -> formatted footnote

src/llm/                   THE ONLY LAYER THAT TALKS TO AN LLM
  tool_math.py                Tool schema + dispatcher for verified-metric lookup
  narrative.py                Real Anthropic SDK calls: grounded bullets, tool-use math loop
  mock.py                     Offline stand-in with the same interface, used by --sample

src/report/                 PRESENTATION ONLY
  charts.py                    matplotlib charts from already-computed data
  pdf_builder.py                ReportLab assembly of the final PDF

main.py                    Orchestrates all of the above
tests/                     pytest suite for engine + RAG layers
```

## Extending to a real live run

1. Get a free Anthropic API key, `export ANTHROPIC_API_KEY=...`
2. In `main.py`, follow the two `LIVE MODE` comments:
   - swap `load_sample_financials()` for `edgar_client.fetch_company_financials(ticker)`
   - download the 10-K from `edgar_client.fetch_filing_document_url(ticker)`,
     run it through `chunker.chunk_pdf()`, and swap `mock_grounded_bullets`
     for `narrative.generate_grounded_bullets(client, topic, chunks)`
3. Swap the hardcoded `comps` list and `current_price` for a real market
   data API (Alpha Vantage / Polygon.io both have free tiers)

## Known limitations / honest caveats

- Sample financial figures are illustrative (right order of magnitude for
  Costco, not guaranteed to match the actual 10-K to the dollar) — always
  verify against `edgar_client`'s live pull before treating a memo as real.
- The DCF assumptions in `main.py` (WACC, growth rates, margins) are
  simplistic defaults for demo purposes. A real memo needs those tuned
  per-company, and the sensitivity table (`dcf.sensitivity_table`) exists
  specifically because a single-point DCF output is misleadingly precise.
- Comparable company multiples in the demo are hardcoded illustrative
  values, not live market data.
- This is not investment advice — see the disclaimer on the last page of
  the generated PDF.
