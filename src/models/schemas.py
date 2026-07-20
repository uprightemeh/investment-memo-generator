"""
Core data contracts for the pipeline.

Why this file exists / why it's the first thing to build:
Every other module (EDGAR client, DCF engine, RAG retriever, LLM narrator,
PDF builder) passes data through these shapes. If you don't pin them down
first, you end up with dicts-of-dicts everywhere and no way to catch a typo
in a key name until the PDF silently renders "None". Pydantic gives us
runtime validation for free -- e.g. if the EDGAR client returns revenue as
a string instead of a float, this throws immediately at the data layer
instead of producing a wrong number three layers downstream in a chart.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


# ---------------------------------------------------------------------------
# Raw financial data (from SEC EDGAR XBRL, or market data API)
# ---------------------------------------------------------------------------

class FiscalPeriod(BaseModel):
    fiscal_year: int
    fiscal_period: str  # "FY", "Q1", "Q2", "Q3", "Q4"
    end_date: str        # ISO date


class FinancialLineItem(BaseModel):
    """One reported number, tagged with exactly where it came from.

    This 'source' field is the whole point of Source Attribution: every
    number that ends up in the memo can be traced back to the SEC filing
    that reported it, not to an LLM's guess.
    """
    concept: str          # XBRL tag, e.g. "Revenues", "NetIncomeLoss"
    label: str             # human-readable, e.g. "Total Revenue"
    value: float
    unit: str              # "USD", "USD/shares", etc.
    period: FiscalPeriod
    source: str             # e.g. "10-K FY2024, filed 2024-10-01, EDGAR accession 0000320187-24-000097"


class CompanyFinancials(BaseModel):
    ticker: str
    cik: str                # SEC Central Index Key
    company_name: str
    line_items: list[FinancialLineItem] = Field(default_factory=list)

    def get_series(self, concept: str) -> list[FinancialLineItem]:
        """All historical values for one line item, oldest to newest."""
        items = [li for li in self.line_items if li.concept == concept]
        return sorted(items, key=lambda x: x.period.end_date)

    def latest(self, concept: str) -> Optional[FinancialLineItem]:
        series = self.get_series(concept)
        return series[-1] if series else None


# ---------------------------------------------------------------------------
# Deterministic engine outputs (DCF, ratios, comps)
# ---------------------------------------------------------------------------

class DCFAssumptions(BaseModel):
    """Every input the DCF used, so the memo can disclose its own assumptions
    instead of presenting a fair value number as if it fell from the sky."""
    base_revenue: float
    revenue_growth_rates: list[float]  # one per projection year
    ebit_margin: float
    tax_rate: float
    capex_pct_revenue: float
    da_pct_revenue: float
    nwc_pct_revenue_change: float
    wacc: float
    terminal_growth_rate: float
    projection_years: int
    net_debt: float
    diluted_shares_outstanding: float


class DCFYearProjection(BaseModel):
    year: int
    revenue: float
    ebit: float
    nopat: float
    capex: float
    d_and_a: float
    change_in_nwc: float
    free_cash_flow: float
    discount_factor: float
    present_value: float


class DCFResult(BaseModel):
    assumptions: DCFAssumptions
    projections: list[DCFYearProjection]
    sum_pv_fcf: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    equity_value: float
    implied_share_price: float


class RatioSnapshot(BaseModel):
    fiscal_year: int
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    fcf_margin: Optional[float] = None


class ComparableCompany(BaseModel):
    ticker: str
    company_name: str
    ev_ebitda: Optional[float] = None
    pe_ratio: Optional[float] = None
    ev_revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    operating_margin: Optional[float] = None


# ---------------------------------------------------------------------------
# RAG / citation layer
# ---------------------------------------------------------------------------

class DocumentChunk(BaseModel):
    """A retrievable unit of text with enough metadata to cite it exactly.
    This is what keeps 'source attribution' honest -- the page number and
    section travel with the text through retrieval, so the LLM never has
    to reconstruct where a fact came from after the fact."""
    chunk_id: str
    document_name: str   # e.g. "COST_10K_FY2024.pdf"
    section: str           # e.g. "Item 1A. Risk Factors"
    page_number: int
    text: str


class Citation(BaseModel):
    claim: str
    document_name: str
    page_number: int
    section: str


# ---------------------------------------------------------------------------
# Final memo assembly
# ---------------------------------------------------------------------------

class Recommendation(BaseModel):
    rating: str  # "Buy" | "Hold" | "Sell"
    target_price: float
    current_price: float
    upside_downside_pct: float
    rationale: str
    citations: list[Citation] = Field(default_factory=list)


class InvestmentMemo(BaseModel):
    ticker: str
    company_name: str
    as_of_date: str
    industry_overview: str
    revenue_growth_analysis: str
    margin_analysis: str
    risks: list[str]
    risk_citations: list[Citation]
    catalysts: list[str]
    catalyst_citations: list[Citation]
    dcf: DCFResult
    ratios: list[RatioSnapshot]
    comparables: list[ComparableCompany]
    recommendation: Recommendation
