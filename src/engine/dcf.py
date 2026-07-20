"""
Deterministic DCF engine.

This is the answer to "Strict Math & Fact Verification". The LLM never
computes a financial number in this pipeline -- it only:
  1. reads assumptions out of structured data (extracted from filings), and
  2. narrates the OUTPUT of these functions in prose.

Every function here is pure (same input -> same output, no side effects,
no API calls), which is what makes it unit-testable and auditable. If a
number in the final PDF looks wrong, you can trace it to one function and
one set of inputs -- you're not debugging a hallucination, you're debugging
arithmetic.
"""
from src.models.schemas import (
    DCFAssumptions,
    DCFYearProjection,
    DCFResult,
)


def project_year(
    prior_revenue: float,
    growth_rate: float,
    ebit_margin: float,
    tax_rate: float,
    capex_pct_revenue: float,
    da_pct_revenue: float,
    nwc_pct_revenue_change: float,
    year: int,
    discount_rate: float,
) -> DCFYearProjection:
    """Project a single year of free cash flow. This is the atomic unit of
    the whole model -- get this function right and the rest is just a loop
    and a sum."""
    revenue = prior_revenue * (1 + growth_rate)
    ebit = revenue * ebit_margin
    nopat = ebit * (1 - tax_rate)
    capex = revenue * capex_pct_revenue
    d_and_a = revenue * da_pct_revenue
    revenue_change = revenue - prior_revenue
    change_in_nwc = revenue_change * nwc_pct_revenue_change

    # Unlevered FCF = NOPAT + D&A - CapEx - Increase in NWC
    free_cash_flow = nopat + d_and_a - capex - change_in_nwc

    discount_factor = 1 / ((1 + discount_rate) ** year)
    present_value = free_cash_flow * discount_factor

    return DCFYearProjection(
        year=year,
        revenue=round(revenue, 2),
        ebit=round(ebit, 2),
        nopat=round(nopat, 2),
        capex=round(capex, 2),
        d_and_a=round(d_and_a, 2),
        change_in_nwc=round(change_in_nwc, 2),
        free_cash_flow=round(free_cash_flow, 2),
        discount_factor=round(discount_factor, 6),
        present_value=round(present_value, 2),
    )


def run_dcf(assumptions: DCFAssumptions) -> DCFResult:
    """Full DCF: projects N years of FCF, computes terminal value via the
    Gordon Growth method, discounts everything back, and bridges enterprise
    value to an implied share price.

    Raises ValueError on assumptions that would break the math (e.g. WACC
    <= terminal growth, which makes the terminal value formula divide by a
    non-positive number and blow up to infinity/negative -- a classic DCF
    bug that silently produces nonsense instead of erroring).
    """
    if assumptions.wacc <= assumptions.terminal_growth_rate:
        raise ValueError(
            f"WACC ({assumptions.wacc}) must exceed terminal growth rate "
            f"({assumptions.terminal_growth_rate}), or the terminal value "
            f"formula is undefined/negative."
        )
    if len(assumptions.revenue_growth_rates) != assumptions.projection_years:
        raise ValueError(
            f"Expected {assumptions.projection_years} growth rates, "
            f"got {len(assumptions.revenue_growth_rates)}."
        )

    projections: list[DCFYearProjection] = []
    prior_revenue = assumptions.base_revenue

    for i, growth_rate in enumerate(assumptions.revenue_growth_rates, start=1):
        proj = project_year(
            prior_revenue=prior_revenue,
            growth_rate=growth_rate,
            ebit_margin=assumptions.ebit_margin,
            tax_rate=assumptions.tax_rate,
            capex_pct_revenue=assumptions.capex_pct_revenue,
            da_pct_revenue=assumptions.da_pct_revenue,
            nwc_pct_revenue_change=assumptions.nwc_pct_revenue_change,
            year=i,
            discount_rate=assumptions.wacc,
        )
        projections.append(proj)
        prior_revenue = proj.revenue

    sum_pv_fcf = sum(p.present_value for p in projections)

    # Terminal value at end of final projection year, using Gordon Growth
    final_year_fcf = projections[-1].free_cash_flow
    terminal_value = (
        final_year_fcf * (1 + assumptions.terminal_growth_rate)
        / (assumptions.wacc - assumptions.terminal_growth_rate)
    )
    pv_terminal_value = terminal_value * projections[-1].discount_factor

    enterprise_value = sum_pv_fcf + pv_terminal_value
    equity_value = enterprise_value - assumptions.net_debt
    implied_share_price = equity_value / assumptions.diluted_shares_outstanding

    return DCFResult(
        assumptions=assumptions,
        projections=projections,
        sum_pv_fcf=round(sum_pv_fcf, 2),
        terminal_value=round(terminal_value, 2),
        pv_terminal_value=round(pv_terminal_value, 2),
        enterprise_value=round(enterprise_value, 2),
        equity_value=round(equity_value, 2),
        implied_share_price=round(implied_share_price, 2),
    )


def sensitivity_table(
    base_assumptions: DCFAssumptions,
    wacc_range: list[float],
    terminal_growth_range: list[float],
) -> dict[tuple[float, float], float]:
    """Implied share price across a grid of WACC x terminal growth. This is
    standard practice in real equity research -- a single DCF output number
    is misleadingly precise, so you always show how sensitive it is to the
    two assumptions people argue about most.

    Returns a dict keyed by (wacc, terminal_growth) -> implied share price.
    """
    results = {}
    for wacc in wacc_range:
        for tg in terminal_growth_range:
            if wacc <= tg:
                continue  # skip invalid combinations rather than erroring
            trial = base_assumptions.model_copy(
                update={"wacc": wacc, "terminal_growth_rate": tg}
            )
            result = run_dcf(trial)
            results[(wacc, tg)] = result.implied_share_price
    return results
