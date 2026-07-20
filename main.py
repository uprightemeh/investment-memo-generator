"""
Orchestrates the full pipeline: data -> deterministic math -> RAG citations
-> (mock or real) narrative -> PDF.

Run:
    python main.py --ticker COST --sample

The --sample flag uses bundled data (no network / API key required). Drop
--sample once you've wired up ANTHROPIC_API_KEY and want live EDGAR data +
real LLM narrative generation -- see the two TODOs marked LIVE MODE below
for exactly what to swap.
"""
import argparse
import os

from src.engine.dcf import run_dcf
from src.engine.ratios import compute_ratio_history
from src.engine.comparables import build_comps_summary
from src.rag.chunker import chunk_raw_text_pages
from src.rag.retriever import ChunkRetriever
from src.llm.mock import mock_grounded_bullets
from src.report.charts import (
    revenue_growth_chart, margin_trend_chart, dcf_fcf_bridge_chart, comps_multiple_chart,
)
from src.report.pdf_builder import build_pdf
from src.models.schemas import DCFAssumptions, ComparableCompany, Recommendation, InvestmentMemo

from data.sample.cost_financials import load_sample_financials
from data.sample.cost_filing_text import SAMPLE_PAGES


def run_pipeline(ticker: str, use_sample: bool, out_dir: str = "output"):
    os.makedirs(out_dir, exist_ok=True)

    # ---------------------------------------------------------------
    # 1. DATA LAYER
    # ---------------------------------------------------------------
    if use_sample:
        financials = load_sample_financials()
        filing_pages = SAMPLE_PAGES
        document_name = f"{ticker}_10K_FY2024.pdf"
    else:
        # LIVE MODE: swap in the real EDGAR client + a real parsed PDF.
        from src.data.edgar_client import fetch_company_financials
        financials = fetch_company_financials(ticker)
        raise NotImplementedError(
            "Live mode needs a downloaded 10-K PDF for chunk_pdf() -- "
            "fetch_filing_document_url() gives you the URL to download it, "
            "then pass the local path to rag.chunker.chunk_pdf()."
        )

    # ---------------------------------------------------------------
    # 2. DETERMINISTIC MATH ENGINE (no LLM anywhere in this block)
    # ---------------------------------------------------------------
    ratios = compute_ratio_history(financials)
    latest_revenue = financials.latest("Revenues").value

    dcf_assumptions = DCFAssumptions(
        base_revenue=latest_revenue,
        revenue_growth_rates=[0.07, 0.065, 0.06, 0.055, 0.05],
        ebit_margin=ratios[-1].operating_margin or 0.036,
        tax_rate=0.25,
        capex_pct_revenue=0.018,
        da_pct_revenue=0.012,
        nwc_pct_revenue_change=0.01,
        wacc=0.08,
        terminal_growth_rate=0.025,
        projection_years=5,
        net_debt=-10_000_000_000,
        diluted_shares_outstanding=443_000_000,
    )
    dcf_result = run_dcf(dcf_assumptions)

    # Illustrative peer set with representative multiples (in a live build,
    # source these from the same market-data API as the target's price).
    comps = [
        ComparableCompany(ticker="WMT", company_name="Walmart Inc.", ev_ebitda=15.2, pe_ratio=28.4, ev_revenue=1.1, revenue_growth=0.056, operating_margin=0.044),
        ComparableCompany(ticker="TGT", company_name="Target Corp.", ev_ebitda=8.1, pe_ratio=16.3, ev_revenue=0.6, revenue_growth=0.021, operating_margin=0.055),
        ComparableCompany(ticker="BJ", company_name="BJ's Wholesale Club", ev_ebitda=11.4, pe_ratio=19.8, ev_revenue=0.7, revenue_growth=0.041, operating_margin=0.033),
        ComparableCompany(ticker="DG", company_name="Dollar General Corp.", ev_ebitda=9.7, pe_ratio=17.5, ev_revenue=0.9, revenue_growth=0.032, operating_margin=0.049),
    ]
    comps_summary = build_comps_summary(comps)

    # ---------------------------------------------------------------
    # 3. RAG / CITATION LAYER
    # ---------------------------------------------------------------
    chunks = chunk_raw_text_pages(document_name, filing_pages)
    retriever = ChunkRetriever(chunks)

    risk_chunks = retriever.retrieve("competition supply chain labor membership risk", top_k=4)
    catalyst_chunks = retriever.retrieve("growth expansion warehouse international e-commerce investment", top_k=3)

    # LIVE MODE: replace mock_grounded_bullets with
    # narrative.generate_grounded_bullets(client, topic, chunks) once you
    # have ANTHROPIC_API_KEY set -- same inputs/outputs, real LLM prose.
    risks, risk_citations = mock_grounded_bullets("Risk", risk_chunks)
    catalysts, catalyst_citations = mock_grounded_bullets("Catalyst", catalyst_chunks)

    # ---------------------------------------------------------------
    # 4. CHARTS
    # ---------------------------------------------------------------
    chart_paths = {
        "revenue_growth": revenue_growth_chart(ratios, f"{out_dir}/revenue_growth.png"),
        "margins": margin_trend_chart(ratios, f"{out_dir}/margins.png"),
        "dcf_bridge": dcf_fcf_bridge_chart(dcf_result, f"{out_dir}/dcf_bridge.png"),
        "comps": comps_multiple_chart(comps, f"{out_dir}/comps.png"),
    }

    # ---------------------------------------------------------------
    # 5. ASSEMBLE MEMO + RECOMMENDATION
    # ---------------------------------------------------------------
    current_price = 920.00  # in live mode, pull from a market data API
    upside = (dcf_result.implied_share_price - current_price) / current_price * 100
    rating = "Buy" if upside > 10 else "Sell" if upside < -10 else "Hold"

    memo = InvestmentMemo(
        ticker=financials.ticker,
        company_name=financials.company_name,
        as_of_date="2026-07-18",
        industry_overview=(
            f"{financials.company_name} operates in the membership warehouse "
            "retail segment, competing on scale-driven low pricing against "
            "big-box and e-commerce retailers. The category is characterized "
            "by thin merchandise margins offset by high-margin membership fee "
            "income, making member retention a key structural driver of "
            "profitability relative to pure-play grocery or discount retail."
        ),
        revenue_growth_analysis=(
            f"Revenue grew from ${financials.get_series('Revenues')[0].value/1e9:.1f}B "
            f"to ${financials.get_series('Revenues')[-1].value/1e9:.1f}B over the "
            "period shown, driven by comparable warehouse sales growth and "
            "continued e-commerce expansion (see chart below; figures are "
            "verified from the deterministic ratio engine, not LLM-estimated)."
        ),
        margin_analysis=(
            "Operating margin has expanded modestly, reflecting operating "
            "leverage on membership fee income against a relatively stable "
            "merchandise gross margin -- consistent with the business model's "
            "low-margin/high-volume positioning."
        ),
        risks=risks,
        risk_citations=risk_citations,
        catalysts=catalysts,
        catalyst_citations=catalyst_citations,
        dcf=dcf_result,
        ratios=ratios,
        comparables=comps,
        recommendation=Recommendation(
            rating=rating,
            target_price=dcf_result.implied_share_price,
            current_price=current_price,
            upside_downside_pct=round(upside, 1),
            rationale=(
                f"DCF-implied fair value of ${dcf_result.implied_share_price:,.2f} "
                f"per share ({upside:+.1f}% vs. current price) is derived entirely "
                "from the deterministic DCF engine above; no valuation figure in "
                "this memo was generated by the language model."
            ),
        ),
    )

    # ---------------------------------------------------------------
    # 6. PDF OUTPUT
    # ---------------------------------------------------------------
    out_path = f"{out_dir}/{ticker}_investment_memo.pdf"
    build_pdf(memo, chart_paths, out_path)
    print(f"Memo written to {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="COST")
    parser.add_argument("--sample", action="store_true", help="Use bundled sample data (no network/API key needed)")
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    if not args.sample:
        print("Live mode requires ANTHROPIC_API_KEY and SEC EDGAR network access. Run with --sample for the offline demo.")
    run_pipeline(args.ticker, use_sample=True, out_dir=args.out_dir)
