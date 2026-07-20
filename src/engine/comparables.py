"""
Comparable companies ('comps') analysis. In real sell-side research this
is often the more load-bearing valuation method than DCF, because DCF is
extremely sensitive to WACC/terminal growth assumptions while comps
anchor to what the market is actually paying for similar businesses today.
"""
import statistics
from src.models.schemas import ComparableCompany


def peer_median(comps: list[ComparableCompany], field: str) -> float | None:
    values = [getattr(c, field) for c in comps if getattr(c, field) is not None]
    return statistics.median(values) if values else None


def peer_mean(comps: list[ComparableCompany], field: str) -> float | None:
    values = [getattr(c, field) for c in comps if getattr(c, field) is not None]
    return statistics.mean(values) if values else None


def implied_value_from_multiple(
    target_metric_value: float, peer_multiple: float
) -> float:
    """e.g. target EBITDA * peer median EV/EBITDA = implied enterprise value."""
    return target_metric_value * peer_multiple


def build_comps_summary(comps: list[ComparableCompany]) -> dict:
    """Median/mean across the peer set for each multiple -- the numbers you'd
    actually put in a comps table footer row."""
    fields = ["ev_ebitda", "pe_ratio", "ev_revenue", "revenue_growth", "operating_margin"]
    return {
        field: {"median": peer_median(comps, field), "mean": peer_mean(comps, field)}
        for field in fields
    }
