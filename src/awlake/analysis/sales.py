"""Sales exploration on gold: category revenue, territory AOV by channel, monthly trends, the July 2013
catalog launch and reseller batching.

Inputs are gold marts and facts as pandas DataFrames:
  product_monthly  mart_product_monthly
  channel_monthly  mart_channel_monthly
  orders           fct_orders in the analysis window, joined to dim_territory (territory_name, territory_group)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import BREAK


def category_revenue(product_monthly: pd.DataFrame) -> pd.DataFrame:
    """Revenue, share, units and reseller share by category, largest first."""
    g = product_monthly.groupby("category_name").agg(
        revenue=("revenue", "sum"), units=("units", "sum"), reseller_revenue=("reseller_revenue", "sum"),
        products_sold=("product_id", "nunique"))
    g["share"] = g["revenue"] / g["revenue"].sum()
    g["reseller_share"] = g["reseller_revenue"] / g["revenue"]
    return g.drop(columns="reseller_revenue").sort_values("revenue", ascending=False).reset_index()


def territory_aov(orders: pd.DataFrame) -> pd.DataFrame:
    """Order count and AOV per territory, overall and within each channel, with the median online order."""
    o = orders.assign(is_reseller=orders["channel"].eq("reseller").astype(float))
    g = o.groupby(["territory_name", "territory_group"])
    out = pd.DataFrame({
        "orders": g.size(),
        "aov_all": g["revenue"].mean(),
        "aov_reseller": o[o.channel == "reseller"].groupby(["territory_name", "territory_group"])["revenue"].mean(),
        "aov_online": o[o.channel == "online"].groupby(["territory_name", "territory_group"])["revenue"].mean(),
        "median_online": o[o.channel == "online"].groupby(["territory_name", "territory_group"])["revenue"].median(),
        "reseller_order_share": g["is_reseller"].mean(),
    })
    return out.sort_values("aov_all", ascending=False).reset_index()


def channel_mix_correlation(terr: pd.DataFrame) -> float:
    """Correlation between a territory's share of reseller orders and its overall AOV."""
    return float(np.corrcoef(terr["reseller_order_share"], terr["aov_all"])[0, 1])


def monthly_pivot(channel_monthly: pd.DataFrame, value: str = "revenue") -> pd.DataFrame:
    """Month x channel table of one measure; empty reseller months stay as 0, not missing."""
    return (channel_monthly.pivot(index="month_start_date", columns="channel", values=value)
            .sort_index().asfreq("MS").fillna(0))


def yearly_summary(channel_monthly: pd.DataFrame) -> pd.DataFrame:
    """Orders, revenue and months covered per calendar year and channel."""
    d = channel_monthly.assign(year=channel_monthly["month_start_date"].dt.year)
    g = d.groupby(["year", "channel"]).agg(orders=("orders", "sum"), revenue=("revenue", "sum"),
                                           months=("month_start_date", "nunique")).reset_index()
    g["revenue_growth"] = g.sort_values("year").groupby("channel")["revenue"].pct_change()
    return g


def reseller_batching(channel_monthly: pd.DataFrame, max_orders: int = 5) -> pd.DataFrame:
    """Reseller months with no batch: no orders at all, or only a handful (the batch landed on the 1st of
    the next month instead, as in Feb and Apr 2014)."""
    r = channel_monthly[channel_monthly.channel == "reseller"].sort_values("month_start_date")
    out = r[r["orders"] <= max_orders][["month_start_date", "orders", "revenue"]].copy()
    out["kind"] = np.where(out["orders"].eq(0), "empty", "near-empty")
    return out.reset_index(drop=True)


def reseller_month_of_year(channel_monthly: pd.DataFrame, years=(2012, 2013)) -> pd.DataFrame:
    """Average reseller revenue by calendar month over complete years, indexed to the mean (1 = average)."""
    r = channel_monthly[(channel_monthly.channel == "reseller")
                        & channel_monthly["month_start_date"].dt.year.isin(years)]
    m = r.groupby(r["month_start_date"].dt.month)["revenue"].mean().rename("avg_revenue").to_frame()
    m.index.name = "month"
    m["index_vs_mean"] = m["avg_revenue"] / m["avg_revenue"].mean()
    return m.reset_index()


def catalog_launch(product_monthly: pd.DataFrame, break_month: pd.Timestamp = BREAK) -> pd.DataFrame:
    """Online units by category before and from the July 2013 break, with the first online sale month."""
    pm = product_monthly
    before = pm[pm.month_start_date < break_month].groupby("category_name")["online_units"].sum()
    after = pm[pm.month_start_date >= break_month].groupby("category_name")["online_units"].sum()
    first = pm[pm.online_units > 0].groupby("category_name")["month_start_date"].min()
    out = pd.DataFrame({"online_units_before": before, "online_units_from": after,
                        "first_online_month": first}).fillna({"online_units_before": 0, "online_units_from": 0})
    return out.sort_values("online_units_from", ascending=False).reset_index()
