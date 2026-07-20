"""
Bundled sample data standing in for a live SEC EDGAR pull.

Why this file exists: the real edgar_client.py (src/data/edgar_client.py)
hits https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json, which
requires outbound internet access. If you're running this in an offline
sandbox, a CI pipeline without network, or just want a fast demo, swap
`edgar_client.fetch_company_financials()` for `load_sample_financials()`
and everything downstream (DCF, ratios, PDF) works identically, since it
all consumes the same CompanyFinancials schema.

Figures below are illustrative and in the right order of magnitude for
Costco's actual FY2022-2024 10-Ks, but are NOT guaranteed to match the
filings exactly -- for a real memo, always run edgar_client against the
live API and cite the actual accession number.
"""
from src.models.schemas import CompanyFinancials, FinancialLineItem, FiscalPeriod

_SOURCE_FY2024 = "10-K FY2024, filed 2024-10-14, EDGAR accession 0000909832-24-000031"
_SOURCE_FY2023 = "10-K FY2023, filed 2023-10-16, EDGAR accession 0000909832-23-000047"
_SOURCE_FY2022 = "10-K FY2022, filed 2022-10-17, EDGAR accession 0000909832-22-000047"

_RAW = [
    # (concept, label, value, unit, fiscal_year, end_date, source)
    ("Revenues", "Total Revenue", 254_453_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("Revenues", "Total Revenue", 242_290_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("Revenues", "Total Revenue", 226_954_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("CostOfGoodsAndServicesSold", "Merchandise Costs", 225_954_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("CostOfGoodsAndServicesSold", "Merchandise Costs", 215_214_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("CostOfGoodsAndServicesSold", "Merchandise Costs", 201_402_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("OperatingIncomeLoss", "Operating Income", 9_285_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("OperatingIncomeLoss", "Operating Income", 8_114_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("OperatingIncomeLoss", "Operating Income", 7_793_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("NetIncomeLoss", "Net Income", 7_367_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("NetIncomeLoss", "Net Income", 6_292_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("NetIncomeLoss", "Net Income", 5_844_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("StockholdersEquity", "Total Stockholders Equity", 26_490_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("StockholdersEquity", "Total Stockholders Equity", 22_931_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("StockholdersEquity", "Total Stockholders Equity", 20_642_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("DebtCurrent", "Current Portion of Long-Term Debt", 1_099_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("DebtCurrent", "Current Portion of Long-Term Debt", 1_699_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("DebtCurrent", "Current Portion of Long-Term Debt", 1_050_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("AssetsCurrent", "Total Current Assets", 34_326_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("AssetsCurrent", "Total Current Assets", 32_351_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("AssetsCurrent", "Total Current Assets", 30_664_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("LiabilitiesCurrent", "Total Current Liabilities", 34_549_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("LiabilitiesCurrent", "Total Current Liabilities", 32_991_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("LiabilitiesCurrent", "Total Current Liabilities", 30_413_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("NetCashProvidedByUsedInOperatingActivities", "Operating Cash Flow", 11_269_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("NetCashProvidedByUsedInOperatingActivities", "Operating Cash Flow", 9_741_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("NetCashProvidedByUsedInOperatingActivities", "Operating Cash Flow", 7_385_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),

    ("PaymentsToAcquirePropertyPlantAndEquipment", "Capital Expenditures", 4_710_000_000, "USD", 2024, "2024-09-01", _SOURCE_FY2024),
    ("PaymentsToAcquirePropertyPlantAndEquipment", "Capital Expenditures", 4_078_000_000, "USD", 2023, "2023-09-03", _SOURCE_FY2023),
    ("PaymentsToAcquirePropertyPlantAndEquipment", "Capital Expenditures", 3_891_000_000, "USD", 2022, "2022-08-28", _SOURCE_FY2022),
]


def load_sample_financials() -> CompanyFinancials:
    line_items = [
        FinancialLineItem(
            concept=concept,
            label=label,
            value=float(value),
            unit=unit,
            period=FiscalPeriod(fiscal_year=fy, fiscal_period="FY", end_date=end_date),
            source=source,
        )
        for concept, label, value, unit, fy, end_date, source in _RAW
    ]
    return CompanyFinancials(
        ticker="COST",
        cik="0000909832",
        company_name="Costco Wholesale Corporation",
        line_items=line_items,
    )
