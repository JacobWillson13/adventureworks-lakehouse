"""Margin over time from mart_margin_monthly (month x category x channel, cost by effective date).

Margins are always recomputed from summed revenue and cost, never averaged across rows.
"""
from __future__ import annotations

import pandas as pd


def _rollup(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by, as_index=False)[["units", "revenue", "cost", "gross_margin"]].sum()
    g["margin_pct"] = g["gross_margin"] / g["revenue"]
    return g


def monthly_margin(mm: pd.DataFrame) -> pd.DataFrame:
    """Total revenue, cost and margin per month."""
    return _rollup(mm, ["month_start_date"]).sort_values("month_start_date").reset_index(drop=True)


def margin_by(mm: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Whole-window margin by one dimension (category_name or channel), largest revenue first."""
    return _rollup(mm, [dim]).sort_values("revenue", ascending=False).reset_index(drop=True)


def monthly_margin_pct(mm: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Month x dim table of margin_pct."""
    return _rollup(mm, ["month_start_date", dim]).pivot(index="month_start_date", columns=dim,
                                                       values="margin_pct").sort_index()


def margin_range(monthly: pd.DataFrame) -> dict:
    """Lowest and highest monthly margin, with their months, and the whole-window margin."""
    lo, hi = monthly.loc[monthly.margin_pct.idxmin()], monthly.loc[monthly.margin_pct.idxmax()]
    return {"min_margin_pct": float(lo.margin_pct), "min_month": lo.month_start_date.strftime("%Y-%m"),
            "max_margin_pct": float(hi.margin_pct), "max_month": hi.month_start_date.strftime("%Y-%m"),
            "window_margin_pct": float(monthly.gross_margin.sum() / monthly.revenue.sum())}


def negative_margin_months(mm: pd.DataFrame, dim: str = "channel") -> pd.DataFrame:
    """Month and dim combinations sold below standard cost in total."""
    r = _rollup(mm, ["month_start_date", dim])
    return r[r.gross_margin < 0].sort_values("month_start_date").reset_index(drop=True)
