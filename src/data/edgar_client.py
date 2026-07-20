"""
Real SEC EDGAR client. Not a mock -- this hits the live API.

SEC EDGAR exposes structured XBRL data ("company facts") for free, no API
key required, which solves most of the "don't let the LLM hallucinate
financial numbers" problem before an LLM is even involved: revenue, net
income, etc. come as tagged, machine-readable numbers straight from the
filing, not as text the LLM has to parse out of a PDF.

Docs: https://www.sec.gov/edgar/sec-api-documentation
Rate limit: 10 requests/second. SEC requires a descriptive User-Agent
identifying you (they will block generic/missing User-Agents).
"""
import requests
import time
from src.models.schemas import CompanyFinancials, FinancialLineItem, FiscalPeriod

SEC_HEADERS = {
    # Replace with your own name/email -- SEC blocks requests without a
    # real identifying User-Agent, per their fair-access policy.
    "User-Agent": "Investment Memo Generator research-tool@example.com"
}

# The XBRL "concepts" (US-GAAP tags) we pull for the memo. You can find the
# full concept list for any company at:
# https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
CONCEPTS_TO_FETCH = [
    "Revenues",
    "CostOfGoodsAndServicesSold",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    "StockholdersEquity",
    "DebtCurrent",
    "AssetsCurrent",
    "LiabilitiesCurrent",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
]


def lookup_cik(ticker: str) -> str:
    """SEC maps tickers to CIK numbers via a bulk JSON file. In production
    you'd cache this locally (it's ~800KB and updates daily) rather than
    refetching per call."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker {ticker} not found in SEC company_tickers.json")


def fetch_company_financials(ticker: str) -> CompanyFinancials:
    """Pull structured XBRL facts for `ticker` and normalize them into our
    CompanyFinancials schema. This is the live equivalent of
    data/sample/cost_financials.py's load_sample_financials().
    """
    cik = lookup_cik(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    company_name = raw.get("entityName", ticker)
    facts = raw.get("facts", {}).get("us-gaap", {})

    line_items: list[FinancialLineItem] = []
    for concept in CONCEPTS_TO_FETCH:
        concept_data = facts.get(concept)
        if not concept_data:
            continue  # not every company reports every tag; skip silently
        units = concept_data.get("units", {})
        usd_values = units.get("USD", [])
        for entry in usd_values:
            # Only keep full-year (10-K) figures, not quarterly 10-Qs, to
            # avoid mixing annual and quarterly numbers in one series.
            if entry.get("form") != "10-K":
                continue
            fy = entry.get("fy")
            end_date = entry.get("end")
            if fy is None or end_date is None:
                continue
            accession = entry.get("accn", "unknown accession")
            filed = entry.get("filed", "unknown filing date")
            line_items.append(
                FinancialLineItem(
                    concept=concept,
                    label=concept,  # could map to friendlier labels via a lookup table
                    value=float(entry["val"]),
                    unit="USD",
                    period=FiscalPeriod(fiscal_year=fy, fiscal_period="FY", end_date=end_date),
                    source=f"10-K FY{fy}, filed {filed}, EDGAR accession {accession}",
                )
            )
        time.sleep(0.11)  # stay safely under SEC's 10 req/sec rate limit

    return CompanyFinancials(
        ticker=ticker.upper(), cik=cik, company_name=company_name, line_items=line_items
    )


def fetch_filing_document_url(ticker: str, form_type: str = "10-K") -> str:
    """Get the URL of the most recent filing of a given type, for downstream
    PDF/HTML parsing in the RAG layer (risk factors, MD&A, etc. aren't in
    XBRL, so they still need to be fetched and parsed as documents)."""
    cik = lookup_cik(ticker)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    recent = data["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == form_type:
            accession = recent["accessionNumber"][i].replace("-", "")
            doc = recent["primaryDocument"][i]
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
    raise ValueError(f"No {form_type} filing found for {ticker}")
