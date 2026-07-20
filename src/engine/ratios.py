"""
Financial ratio engine. Same philosophy as dcf.py: pure functions over
structured inputs, nothing computed by the LLM. Every ratio here maps to a
FinancialLineItem concept pulled straight from XBRL, so you can always
answer "where did this 43.2% gross margin come from" with two numbers and
a division, not a paragraph of trust-me.
"""
from src.models.schemas import CompanyFinancials, RatioSnapshot


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def compute_ratios_for_year(financials: CompanyFinancials, fiscal_year: int) -> RatioSnapshot:
    """Compute one year's ratio snapshot. Looks up each line item by concept
    and fiscal year; missing data yields None rather than a fabricated
    number or a crash."""

    def value_for(concept: str) -> float | None:
        series = financials.get_series(concept)
        matches = [li for li in series if li.period.fiscal_year == fiscal_year]
        return matches[-1].value if matches else None

    revenue = value_for("Revenues")
    cogs = value_for("CostOfGoodsAndServicesSold")
    operating_income = value_for("OperatingIncomeLoss")
    net_income = value_for("NetIncomeLoss")
    total_equity = value_for("StockholdersEquity")
    total_debt = value_for("DebtCurrent")  # simplified; real model would sum current+LT debt
    current_assets = value_for("AssetsCurrent")
    current_liabilities = value_for("LiabilitiesCurrent")
    operating_cash_flow = value_for("NetCashProvidedByUsedInOperatingActivities")
    capex = value_for("PaymentsToAcquirePropertyPlantAndEquipment")

    prior_year_revenue_matches = [
        li for li in financials.get_series("Revenues")
        if li.period.fiscal_year == fiscal_year - 1
    ]
    prior_revenue = prior_year_revenue_matches[-1].value if prior_year_revenue_matches else None

    gross_profit = (revenue - cogs) if (revenue is not None and cogs is not None) else None
    fcf = (
        operating_cash_flow - capex
        if (operating_cash_flow is not None and capex is not None)
        else None
    )

    return RatioSnapshot(
        fiscal_year=fiscal_year,
        gross_margin=_safe_div(gross_profit, revenue),
        operating_margin=_safe_div(operating_income, revenue),
        net_margin=_safe_div(net_income, revenue),
        roe=_safe_div(net_income, total_equity),
        roic=_safe_div(operating_income, total_equity),  # simplified proxy
        current_ratio=_safe_div(current_assets, current_liabilities),
        debt_to_equity=_safe_div(total_debt, total_equity),
        revenue_growth_yoy=_safe_div(
            (revenue - prior_revenue) if (revenue is not None and prior_revenue is not None) else None,
            prior_revenue,
        ),
        fcf_margin=_safe_div(fcf, revenue),
    )


def compute_ratio_history(financials: CompanyFinancials) -> list[RatioSnapshot]:
    """Ratio snapshot for every fiscal year present in the data."""
    years = sorted({li.period.fiscal_year for li in financials.line_items})
    return [compute_ratios_for_year(financials, y) for y in years]
