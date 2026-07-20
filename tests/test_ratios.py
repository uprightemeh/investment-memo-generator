import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.ratios import compute_ratios_for_year, compute_ratio_history
from data.sample.cost_financials import load_sample_financials


def test_gross_margin_matches_manual_calc():
    fin = load_sample_financials()
    snap = compute_ratios_for_year(fin, 2024)
    # (254,453 - 225,954) / 254,453
    expected = (254_453_000_000 - 225_954_000_000) / 254_453_000_000
    assert abs(snap.gross_margin - expected) < 1e-9


def test_revenue_growth_yoy_computed_correctly():
    fin = load_sample_financials()
    snap = compute_ratios_for_year(fin, 2024)
    expected = (254_453_000_000 - 242_290_000_000) / 242_290_000_000
    assert abs(snap.revenue_growth_yoy - expected) < 1e-9


def test_missing_prior_year_yields_none_not_crash():
    fin = load_sample_financials()
    # 2022 is the earliest year in the sample, so YoY growth is undefined
    snap = compute_ratios_for_year(fin, 2022)
    assert snap.revenue_growth_yoy is None


def test_ratio_history_covers_all_years():
    fin = load_sample_financials()
    history = compute_ratio_history(fin)
    years = [s.fiscal_year for s in history]
    assert years == [2022, 2023, 2024]
