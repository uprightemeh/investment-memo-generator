"""
Chart generation using matplotlib.

Earlier draft of this file used Plotly + kaleido for static image export.
kaleido v1+ requires a real Chrome binary to rasterize figures, which is a
brittle dependency in headless environments (CI runners, Docker containers
without a browser, sandboxes like this one) -- it fails hard with a
ChromeNotFoundError rather than degrading gracefully. matplotlib renders
PNGs directly with no browser/subprocess dependency, so it's the more
robust choice for a report-generation pipeline meant to run unattended.

Same rule as the rest of report/: every chart function takes already-
computed data (RatioSnapshot, DCFResult, etc.) and visualizes it. No chart
function computes a new number.
"""
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, no display needed
import matplotlib.pyplot as plt
from src.models.schemas import RatioSnapshot, DCFResult, ComparableCompany

_NAVY = "#1f3a5f"
_BLUE = "#4a7ba6"
_GRID = "#dddddd"


def _style_ax(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=13, color=_NAVY, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, color=_GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def revenue_growth_chart(ratios: list[RatioSnapshot], out_path: str) -> str:
    years = [r.fiscal_year for r in ratios]
    growth = [r.revenue_growth_yoy * 100 if r.revenue_growth_yoy is not None else 0 for r in ratios]

    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    ax.bar([str(y) for y in years], growth, color=_NAVY, width=0.5, zorder=3)
    _style_ax(ax, "Revenue Growth YoY (%)", "Fiscal Year", "Growth %")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def margin_trend_chart(ratios: list[RatioSnapshot], out_path: str) -> str:
    years = [str(r.fiscal_year) for r in ratios]
    gross = [r.gross_margin * 100 if r.gross_margin is not None else None for r in ratios]
    operating = [r.operating_margin * 100 if r.operating_margin is not None else None for r in ratios]
    net = [r.net_margin * 100 if r.net_margin is not None else None for r in ratios]

    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    ax.plot(years, gross, marker="o", label="Gross Margin", color=_NAVY, zorder=3)
    ax.plot(years, operating, marker="o", label="Operating Margin", color=_BLUE, zorder=3)
    ax.plot(years, net, marker="o", label="Net Margin", color="#8a8a8a", zorder=3)
    _style_ax(ax, "Margin Trends", "Fiscal Year", "Margin %")
    ax.legend(fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def dcf_fcf_bridge_chart(dcf: DCFResult, out_path: str) -> str:
    years = [p.year for p in dcf.projections]
    fcf = [p.free_cash_flow / 1e9 for p in dcf.projections]
    pv = [p.present_value / 1e9 for p in dcf.projections]

    x = range(len(years))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    ax.bar([i - width / 2 for i in x], fcf, width=width, label="Free Cash Flow", color=_BLUE, zorder=3)
    ax.bar([i + width / 2 for i in x], pv, width=width, label="Present Value", color=_NAVY, zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Yr {y}" for y in years])
    _style_ax(ax, "Projected FCF vs. Present Value ($B)", "Projection Year", "USD (Billions)")
    ax.legend(fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def comps_multiple_chart(comps: list[ComparableCompany], out_path: str) -> str:
    tickers = [c.ticker for c in comps]
    ev_ebitda = [c.ev_ebitda if c.ev_ebitda is not None else 0 for c in comps]

    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    ax.bar(tickers, ev_ebitda, color=_BLUE, width=0.5, zorder=3)
    _style_ax(ax, "EV / EBITDA - Peer Comparison", "Company", "EV / EBITDA (x)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
