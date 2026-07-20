"""
This is the enforcement mechanism behind 'Strict Math & Fact Verification'.

The trick isn't just "have a Python function available" -- it's that the
LLM is architecturally prevented from putting a computed number in its
output without going through this tool first. We do that by:
  1. Never handing the LLM raw numbers to do arithmetic on in a prompt.
  2. Exposing ONLY these pre-computed, already-run results as tool
     outputs -- the LLM calls a tool, gets back a number WE computed with
     src/engine/*, and can only narrate that number, not invent a new one.

In other words: by the time narrative.py talks to the LLM, dcf.py and
ratios.py have ALREADY run. The LLM's "tool call" here is really a lookup
into results we already trust, not a live computation -- which is a
stronger guarantee than trusting the LLM to call a calculator correctly.
"""
from typing import Any
from src.models.schemas import DCFResult, RatioSnapshot, ComparableCompany


TOOL_SCHEMA = {
    "name": "lookup_financial_metric",
    "description": (
        "Look up a pre-computed, verified financial metric. This is the ONLY "
        "way to get a numeric financial figure -- never state a computed "
        "number (margin, growth rate, valuation, ratio) without calling this "
        "tool first. Available metric_paths are listed in the system prompt."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric_path": {
                "type": "string",
                "description": (
                    "Dot-path into the verified results, e.g. "
                    "'dcf.implied_share_price', 'ratios.2024.gross_margin', "
                    "'comps.median.ev_ebitda'."
                ),
            }
        },
        "required": ["metric_path"],
    },
}


class VerifiedMetricStore:
    """Holds the already-computed engine outputs and resolves dot-paths
    against them. This is what actually answers `lookup_financial_metric`
    tool calls -- deterministic dict/attribute lookups, not computation."""

    def __init__(
        self,
        dcf: DCFResult,
        ratios: list[RatioSnapshot],
        comps_summary: dict,
    ):
        self.dcf = dcf
        self.ratios_by_year = {r.fiscal_year: r for r in ratios}
        self.comps_summary = comps_summary

    def resolve(self, metric_path: str) -> Any:
        parts = metric_path.split(".")
        root = parts[0]

        if root == "dcf":
            value: Any = self.dcf
            for p in parts[1:]:
                value = getattr(value, p)
            return value

        if root == "ratios":
            year = int(parts[1])
            field = parts[2]
            snapshot = self.ratios_by_year.get(year)
            if snapshot is None:
                raise KeyError(f"No ratio snapshot for fiscal year {year}")
            return getattr(snapshot, field)

        if root == "comps":
            stat = parts[1]   # "median" or "mean"
            field = parts[2]
            return self.comps_summary[field][stat]

        raise KeyError(f"Unrecognized metric_path root: {root}")

    def dispatch_tool_call(self, tool_input: dict) -> dict:
        """What you'd wire into the Anthropic API's tool_result flow --
        takes the tool call's input, returns a tool_result content block."""
        metric_path = tool_input["metric_path"]
        try:
            value = self.resolve(metric_path)
            return {"metric_path": metric_path, "value": value, "error": None}
        except (KeyError, AttributeError) as e:
            return {"metric_path": metric_path, "value": None, "error": str(e)}
