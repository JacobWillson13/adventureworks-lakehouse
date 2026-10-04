"""Supplier quality from mart_vendor_quality (vendor x month, every purchase order through 2014-09;
the sales analysis window does not apply).

Rejection rate = rejected_qty / received_qty, recomputed from sums. Two kinds of rejection are kept
apart: whole deliveries refused (purchase orders with status 'rejected') and partial rejections at
receipt on otherwise accepted orders.
"""
from __future__ import annotations

import pandas as pd

MIN_RECEIVED = 1000   # vendors below this many received units are too small to rank


def _rates(g: pd.DataFrame) -> pd.DataFrame:
    g["rejection_rate"] = g["rejected_qty"] / g["received_qty"]
    partial_rejected = g["rejected_qty"] - g["rejected_qty_on_rejected_orders"]
    g["partial_rejection_rate"] = partial_rejected / g["received_qty"]
    g["fill_rate"] = g["received_qty"] / g["ordered_qty"]
    return g


SUMS = ["purchase_orders", "order_lines", "ordered_qty", "received_qty", "rejected_qty", "stocked_qty",
        "rejected_qty_on_rejected_orders", "lines_with_rejections", "purchase_value"]


def vendor_summary(vq: pd.DataFrame) -> pd.DataFrame:
    """One row per vendor over the window, worst rejection rate first."""
    keys = ["vendor_id", "vendor_name", "credit_rating", "preferred_vendor_status", "active_flag"]
    g = vq.groupby(keys, as_index=False, dropna=False)[SUMS].sum()
    lead = vq.groupby("vendor_id").apply(
        lambda d: pd.Series({"declared_lead_time_days": (d.avg_declared_lead_time_days * d.order_lines).sum()
                             / d.order_lines.sum()}), include_groups=False).reset_index()
    g = _rates(g.merge(lead, on="vendor_id"))
    return g.sort_values("rejection_rate", ascending=False).reset_index(drop=True)


def worst_vendors(summary: pd.DataFrame, n: int = 10, min_received: float = MIN_RECEIVED) -> pd.DataFrame:
    """The n vendors with the highest rejection rate among those with at least min_received units."""
    return summary[summary.received_qty >= min_received].head(n).reset_index(drop=True)


def monthly_quality(vq: pd.DataFrame) -> pd.DataFrame:
    """All vendors per month: received, rejected and the two rejection rates."""
    g = vq.groupby("month_start_date", as_index=False)[SUMS].sum()
    return _rates(g).sort_values("month_start_date").reset_index(drop=True)


def overall(vq: pd.DataFrame) -> dict:
    t = vq[SUMS].sum()
    return {"vendors": int(vq.vendor_id.nunique()), "received_qty": float(t.received_qty),
            "rejected_qty": float(t.rejected_qty), "rejection_rate": float(t.rejected_qty / t.received_qty),
            "partial_rejection_rate": float((t.rejected_qty - t.rejected_qty_on_rejected_orders) / t.received_qty)}


def by_credit_rating(summary: pd.DataFrame) -> pd.DataFrame:
    """Rejection rate by vendor credit rating (1 superior ... 5 below average)."""
    g = summary.groupby("credit_rating", as_index=False)[SUMS].sum()
    g["vendors"] = summary.groupby("credit_rating").size().values
    return _rates(g)


def lead_time_support(purchase_lines: pd.DataFrame) -> dict:
    """Whether the data supports a lead time analysis: share of lines whose planned lead time (due date
    minus order date) is the single most common value. The source has no receipt date at all."""
    planned = purchase_lines["planned_lead_time_days"]
    mode = int(planned.mode().iloc[0])
    return {"planned_lead_time_mode_days": mode, "share_at_mode": float((planned == mode).mean()),
            "declared_lead_time_min": int(purchase_lines.declared_lead_time_days.min()),
            "declared_lead_time_max": int(purchase_lines.declared_lead_time_days.max())}
