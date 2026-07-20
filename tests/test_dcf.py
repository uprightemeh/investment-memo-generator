import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.models.schemas import DCFAssumptions
from src.engine.dcf import run_dcf, project_year, sensitivity_table


def make_assumptions(**overrides) -> DCFAssumptions:
    defaults = dict(
        base_revenue=254_453_000_000,  # Costco FY2024 revenue, ~ actual order of magnitude
        revenue_growth_rates=[0.07, 0.065, 0.06, 0.055, 0.05],
        ebit_margin=0.036,
        tax_rate=0.25,
        capex_pct_revenue=0.018,
        da_pct_revenue=0.012,
        nwc_pct_revenue_change=0.01,
        wacc=0.08,
        terminal_growth_rate=0.025,
        projection_years=5,
        net_debt=-10_000_000_000,  # negative = net cash position
        diluted_shares_outstanding=443_000_000,
    )
    defaults.update(overrides)
    return DCFAssumptions(**defaults)


def test_project_year_basic_arithmetic():
    proj = project_year(
        prior_revenue=100.0,
        growth_rate=0.10,
        ebit_margin=0.05,
        tax_rate=0.25,
        capex_pct_revenue=0.02,
        da_pct_revenue=0.01,
        nwc_pct_revenue_change=0.01,
        year=1,
        discount_rate=0.10,
    )
    assert proj.revenue == 110.0
    assert proj.ebit == pytest.approx(5.5)
    assert proj.nopat == pytest.approx(4.125, abs=0.01)
    assert proj.capex == pytest.approx(2.2)
    assert proj.d_and_a == pytest.approx(1.1)
    # revenue increased by 10, NWC change = 1% of that = 0.10
    assert proj.change_in_nwc == pytest.approx(0.10)
    # FCF = NOPAT + D&A - CapEx - dNWC = 4.125 + 1.1 - 2.2 - 0.10 = 2.925
    assert proj.free_cash_flow == pytest.approx(2.925, abs=0.01)
    assert proj.discount_factor == pytest.approx(1 / 1.10)


def test_run_dcf_produces_positive_share_price():
    result = run_dcf(make_assumptions())
    assert result.implied_share_price > 0
    assert len(result.projections) == 5
    # enterprise value should be sum of discounted FCFs + discounted terminal value
    assert result.enterprise_value == pytest.approx(
        result.sum_pv_fcf + result.pv_terminal_value, rel=1e-6
    )


def test_run_dcf_rejects_wacc_below_terminal_growth():
    bad = make_assumptions(wacc=0.02, terminal_growth_rate=0.03)
    with pytest.raises(ValueError, match="must exceed"):
        run_dcf(bad)


def test_run_dcf_rejects_mismatched_growth_rate_count():
    bad = make_assumptions(revenue_growth_rates=[0.05, 0.05])  # only 2, expects 5
    with pytest.raises(ValueError, match="Expected 5"):
        run_dcf(bad)


def test_higher_wacc_lowers_implied_price():
    """Sanity check the direction of the relationship, not just that it runs."""
    low_wacc = run_dcf(make_assumptions(wacc=0.07))
    high_wacc = run_dcf(make_assumptions(wacc=0.10))
    assert low_wacc.implied_share_price > high_wacc.implied_share_price


def test_sensitivity_table_shape():
    table = sensitivity_table(
        make_assumptions(),
        wacc_range=[0.07, 0.08, 0.09],
        terminal_growth_range=[0.02, 0.025],
    )
    # 3 wacc x 2 terminal growth = 6 valid combos (all valid here since wacc > tg always)
    assert len(table) == 6
    for price in table.values():
        assert price > 0
