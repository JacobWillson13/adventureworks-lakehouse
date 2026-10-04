"""Figures for the analyses. Each function returns a matplotlib Figure; save() writes it to
reports/figures. Colors are fixed per entity (channel, category, product slot), never by rank.
Categorical palette validated for lightness, chroma and colorblind separation; the two light hues fall
below 3:1 contrast, so every chart carries a legend or direct labels."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # files only; notebooks show the saved figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import BREAK  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e87ba4"]
CHANNEL = {"reseller": "#2a78d6", "online": "#eb6834"}
CHANNEL_LABEL = {"reseller": "Reseller (stores)", "online": "Online (individuals)"}
CATEGORY = {"Bikes": "#2a78d6", "Components": "#eb6834", "Clothing": "#1baf7a", "Accessories": "#eda100",
            "Unassigned": "#8a8984"}
INK, MUTED, GRID = "#2b2b2a", "#8a8984", "#e6e5e0"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": "#52514e", "ytick.color": "#52514e", "lines.linewidth": 2,
    "legend.frameon": False, "font.size": 10, "figure.facecolor": "white",
})


def save(fig, figures_dir: Path, name: str) -> Path:
    path = Path(figures_dir) / name
    fig.savefig(path, bbox_inches="tight")
    return path


def _break_line(ax, label: bool = False):
    ax.axvline(BREAK, color=MUTED, linestyle=":", linewidth=1)
    if label:
        x = (BREAK + pd.Timedelta(days=8)).to_pydatetime()
        ax.text(x, ax.get_ylim()[1] * 0.92, "Jul 2013", color=MUTED, fontsize=8.5)


def _hbar(ax, labels, values, colors, fmt):
    ax.barh(labels, values, color=colors, height=0.6)
    for y, v in enumerate(values):
        ax.text(v, y, "  " + fmt(v), va="center", color=INK, fontsize=8.5)
    ax.set_xlim(0, max(values) * 1.28)
    ax.grid(axis="y", visible=False)


# --- sales -----------------------------------------------------------------------------------------

def category_revenue(cat: pd.DataFrame):
    d = cat.sort_values("revenue")
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.barh(d["category_name"], d["revenue"] / 1e6, color=[CATEGORY[c] for c in d["category_name"]], height=0.6)
    for y, (v, s) in enumerate(zip(d["revenue"] / 1e6, d["share"])):
        ax.text(v, y, f"  ${v:,.1f}M ({s:.0%})", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, d["revenue"].max() / 1e6 * 1.25)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Revenue, $M (sub_total: excl. tax and freight)")
    ax.set_title("Revenue by product category, May 2011 to May 2014", loc="left")
    return fig


def territory_aov(terr: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, col, ch in [(axes[0], "aov_reseller", "reseller"), (axes[1], "aov_online", "online")]:
        d = terr.dropna(subset=[col]).sort_values(col)
        _hbar(ax, d["territory_name"], d[col].values, CHANNEL[ch], lambda v: f"${v:,.0f}")
        ax.set_title(f"AOV by territory: {CHANNEL_LABEL[ch]}", loc="left")
        ax.set_xlabel("Average order value, $")
    fig.tight_layout()
    return fig


def monthly_trends(revenue: pd.DataFrame, orders: pd.DataFrame, empty_months=()):
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    for ch in ("reseller", "online"):
        axes[0].plot(revenue.index, revenue[ch] / 1e6, "-o", ms=3.5, color=CHANNEL[ch], label=CHANNEL_LABEL[ch])
        axes[1].plot(orders.index, orders[ch], "-o", ms=3.5, color=CHANNEL[ch], label=CHANNEL_LABEL[ch])
    for m in empty_months:
        axes[0].axvspan(m, m + pd.offsets.MonthEnd(1), color=GRID, alpha=0.6, linewidth=0)
    axes[0].set_ylabel("Revenue, $M")
    axes[1].set_ylabel("Orders")
    axes[0].set_title("Monthly revenue by channel (shaded: months without a reseller batch)", loc="left")
    axes[1].set_title("Monthly order count by channel", loc="left")
    for ax in axes:
        _break_line(ax)
    _break_line(axes[1], label=True)
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    return fig


# --- segmentation ----------------------------------------------------------------------------------

def k_selection(kq: pd.DataFrame, k: int):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.4))
    for ax, col, label in [(axes[0], "silhouette", "Silhouette (higher is better)"),
                           (axes[1], "davies_bouldin", "Davies-Bouldin (lower is better)"),
                           (axes[2], "stability_ari", "Stability across seeds, ARI")]:
        ax.plot(kq["k"], kq[col], "-o", color=SERIES[0], ms=6)
        row = kq[kq.k == k].iloc[0]
        ax.plot([k], [row[col]], "o", ms=11, mfc="none", mec=INK, mew=1.5)
        ax.set_title(label, loc="left", fontsize=10.5)
        ax.set_xlabel("k (ring = chosen)")
    fig.tight_layout()
    return fig


def segments(prof: pd.DataFrame, feat: pd.DataFrame, labels: np.ndarray, seed: int = 42):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
    x = np.arange(len(prof))
    axes[0].bar(x - 0.2, prof["customer_share"], 0.38, color=MUTED, label="Share of customers")
    axes[0].bar(x + 0.2, prof["revenue_share"], 0.38, color=SERIES[0], label="Share of revenue")
    axes[0].set_xticks(x, [s.replace(" buyers", "\nbuyers") for s in prof["segment"]])
    axes[0].yaxis.set_major_formatter("{x:.0%}")
    axes[0].set_title("Customers vs revenue by segment", loc="left")
    axes[0].legend()
    for i, r in enumerate(prof.itertuples()):
        s = feat[labels == r.cluster].sample(min(600, int((labels == r.cluster).sum())), random_state=seed)
        axes[1].scatter(s["recency_days"], np.log10(s["total_revenue"]), s=10, alpha=0.5,
                        color=SERIES[i % len(SERIES)], label=r.segment)
    axes[1].set_xlabel("Recency, days since last order")
    axes[1].set_ylabel("Total revenue, log10 $")
    axes[1].set_title("Segments by recency and value (sample)", loc="left")
    axes[1].legend(markerscale=2, fontsize=8.5)
    fig.tight_layout()
    return fig


def store_tiers(tiers: pd.DataFrame):
    p = tiers.pivot(index="value_tier", columns="status", values="stores").fillna(0)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    left = np.zeros(len(p))
    for i, col in enumerate(p.columns):
        ax.barh(p.index.astype(str), p[col], left=left, color=[SERIES[0], MUTED][i % 2], height=0.6,
                label=col, edgecolor="white", linewidth=2)
        for y, (l0, v) in enumerate(zip(left, p[col])):
            if v:
                ax.text(l0 + v / 2, y, f"{int(v)}", ha="center", va="center", color="white", fontsize=8.5)
        left += p[col].values
    ax.set_xlabel("Stores")
    ax.set_title("Reseller stores by value quartile and status", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    return fig


# --- forecasting -----------------------------------------------------------------------------------

def top_products(series: pd.DataFrame, names: dict, test_start: pd.Timestamp):
    fig, ax = plt.subplots(figsize=(11, 4))
    for i, pid in enumerate(series.columns):
        ax.plot(series.index, series[pid], "-o", ms=3, color=SERIES[i], label=names[pid])
    ax.axvline(test_start, color=MUTED, linestyle="--", linewidth=1)
    ax.text(test_start, ax.get_ylim()[1] * 0.95, "  backtest window", color=MUTED, fontsize=8.5)
    _break_line(ax)
    ax.set_ylabel("Units per month")
    ax.set_title("Monthly units, top 5 products (dotted: Jul 2013 break)", loc="left")
    ax.legend(fontsize=8.5, ncol=2)
    return fig


def stl_components(total: pd.Series, stl):
    fig, axes = plt.subplots(3, 1, figsize=(11, 6), sharex=True)
    for ax, comp, title in [(axes[0], stl.trend, "Trend"), (axes[1], stl.seasonal, "Seasonal"),
                            (axes[2], stl.resid, "Remainder")]:
        ax.plot(total.index, comp, color=SERIES[0])
        ax.set_title(f"{title} (STL, total units of top 5)", loc="left", fontsize=10)
    fig.tight_layout()
    return fig


def backtest_wape(scores: pd.DataFrame):
    d = scores.sort_values("WAPE", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    colors = [SERIES[0] if i == len(d) - 1 else "#9fc0ea" for i in range(len(d))]
    _hbar(ax, d.index, d["WAPE"].values, colors, lambda v: f"{v:.1%}")
    ax.xaxis.set_major_formatter("{x:.0%}")
    ax.set_xlabel("WAPE across products, 4 origins, h = 1 to 3 (lower is better)")
    ax.set_title("Backtest accuracy by model", loc="left")
    return fig


def forecasts(series: pd.DataFrame, fc: pd.DataFrame, names: dict):
    ids = list(series.columns)
    fig, axes = plt.subplots(len(ids), 1, figsize=(11, 2.3 * len(ids)), sharex=True, squeeze=False)
    for ax, pid, c in zip(axes[:, 0], ids, SERIES):
        f = fc[fc.product_id == pid]
        ax.plot(series.index, series[pid], "-o", ms=2.5, color=c)
        ax.fill_between(f["month"], f["lo95"], f["hi95"], color=c, alpha=0.12, linewidth=0)
        ax.fill_between(f["month"], f["lo80"], f["hi80"], color=c, alpha=0.25, linewidth=0)
        ax.plot(f["month"], f["units"], "--o", ms=3, color=c)
        ax.set_title(f"{names[pid]}: {f['model'].iloc[0]}", loc="left", fontsize=9.5)
        ax.set_ylabel("Units")
    fig.suptitle("History and Jun to Aug 2014 forecast (bands = 80% and 95% intervals)", x=0.01, ha="left",
                 fontsize=11)
    fig.tight_layout()
    return fig


# --- margin ----------------------------------------------------------------------------------------

def margin_over_time(monthly: pd.DataFrame, by_category: pd.DataFrame, by_channel: pd.DataFrame):
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)
    axes[0].plot(monthly.month_start_date, monthly.margin_pct, "-o", ms=3, color=INK)
    axes[0].set_title("Gross margin, all sales (revenue - standard cost on the order date)", loc="left")
    for col in by_category.columns:
        axes[1].plot(by_category.index, by_category[col], "-o", ms=2.5, color=CATEGORY.get(col, MUTED), label=col)
    axes[1].set_title("Gross margin by category", loc="left")
    axes[1].legend(ncol=4, fontsize=8.5, loc="lower left")
    for col in by_channel.columns:
        axes[2].plot(by_channel.index, by_channel[col], "-o", ms=2.5, color=CHANNEL[col], label=CHANNEL_LABEL[col])
    axes[2].set_title("Gross margin by channel", loc="left")
    axes[2].legend(fontsize=8.5, loc="lower left")
    for ax in axes:
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.axhline(0, color=MUTED, linewidth=0.8)
        _break_line(ax)
    fig.tight_layout()
    return fig


# --- supplier quality ------------------------------------------------------------------------------

def worst_vendors(worst: pd.DataFrame):
    d = worst.sort_values("rejection_rate")
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(d) + 1.2))
    ax.barh(d["vendor_name"], d["partial_rejection_rate"], color=SERIES[0], height=0.6,
            label="Rejected at receipt", edgecolor="white", linewidth=2)
    ax.barh(d["vendor_name"], d["rejection_rate"] - d["partial_rejection_rate"], left=d["partial_rejection_rate"],
            color=SERIES[1], height=0.6, label="Whole delivery refused", edgecolor="white", linewidth=2)
    for y, v in enumerate(d["rejection_rate"]):
        ax.text(v, y, f"  {v:.1%}", va="center", fontsize=8.5, color=INK)
    ax.set_xlim(0, d["rejection_rate"].max() * 1.2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Rejected units / received units")
    ax.set_title("Highest rejection rates (vendors with >= 1,000 units received)", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    return fig


def rejection_over_time(monthly: pd.DataFrame):
    # Months with no purchase orders become gaps in the lines instead of being bridged.
    monthly = monthly.set_index("month_start_date").asfreq("MS").reset_index()
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.6), sharex=True)
    axes[0].bar(monthly.month_start_date, monthly.received_qty / 1e3, width=20, color=SERIES[0])
    axes[0].set_ylabel("Units, thousands")
    axes[0].set_title("Units received per month, all vendors", loc="left")
    axes[1].plot(monthly.month_start_date, monthly.rejection_rate, "-o", ms=3, color=SERIES[1], label="All rejections")
    axes[1].plot(monthly.month_start_date, monthly.partial_rejection_rate, "-o", ms=3, color=SERIES[0],
                 label="Rejected at receipt only")
    axes[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    axes[1].set_title("Rejection rate per month", loc="left")
    axes[1].legend(fontsize=8.5)
    fig.tight_layout()
    return fig
