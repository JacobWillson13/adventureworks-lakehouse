"""Analysis functions (awlake.analysis) on small synthetic frames shaped like the gold marts."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("statsmodels")

from awlake.analysis import forecasting as fc  # noqa: E402
from awlake.analysis import margin, sales, segmentation, supplier  # noqa: E402

MONTHS = pd.date_range("2011-05-01", "2014-05-01", freq="MS")


def product_monthly(products: dict) -> pd.DataFrame:
    """products: id -> (category, first month, units function of month index, online share)."""
    rows = []
    for pid, (cat, first, units, online) in products.items():
        for i, m in enumerate(MONTHS):
            if m < pd.Timestamp(first):
                continue
            u = float(units(i))
            rows.append({"product_id": pid, "product_name": f"P{pid}", "category_name": cat,
                         "month_start_date": m, "units": u, "revenue": 10.0 * u,
                         "online_units": u * online, "reseller_units": u * (1 - online),
                         "online_revenue": 10.0 * u * online, "reseller_revenue": 10.0 * u * (1 - online),
                         "is_zero_month": u == 0})
    return pd.DataFrame(rows)


def channel_monthly(reseller_orders) -> pd.DataFrame:
    rows = []
    for m, n in zip(MONTHS, reseller_orders):
        rows.append({"month_start_date": m, "channel": "reseller", "orders": n, "revenue": 1000.0 * n})
        rows.append({"month_start_date": m, "channel": "online", "orders": 50, "revenue": 500.0})
    return pd.DataFrame(rows)


# --- sales -----------------------------------------------------------------------------------------

def test_category_revenue_shares_and_reseller_share():
    pm = product_monthly({1: ("Bikes", "2011-05-01", lambda i: 3, 0.25),
                          2: ("Clothing", "2011-05-01", lambda i: 1, 1.0)})
    cat = sales.category_revenue(pm)
    assert cat.category_name.tolist() == ["Bikes", "Clothing"]
    assert cat.share.sum() == pytest.approx(1)
    assert cat.set_index("category_name").reseller_share.to_dict() == pytest.approx({"Bikes": 0.75, "Clothing": 0})


def test_reseller_batching_flags_empty_and_near_empty_months():
    orders = [100] * len(MONTHS)
    orders[1], orders[33] = 0, 3
    cm = channel_monthly(orders)
    b = sales.reseller_batching(cm)
    assert b.month_start_date.tolist() == [MONTHS[1], MONTHS[33]]
    assert b.kind.tolist() == ["empty", "near-empty"]
    # the pivot keeps empty months as zeros instead of dropping them
    assert sales.monthly_pivot(cm, "orders").loc[MONTHS[1], "reseller"] == 0
    assert len(sales.monthly_pivot(cm)) == len(MONTHS)


def test_catalog_launch_splits_online_units_at_break():
    pm = product_monthly({1: ("Accessories", "2013-05-01", lambda i: 10, 1.0),
                          2: ("Bikes", "2011-05-01", lambda i: 1, 1.0)})
    c = sales.catalog_launch(pm).set_index("category_name")
    assert c.loc["Accessories", "online_units_before"] == 20   # May and June 2013
    assert c.loc["Accessories", "first_online_month"] == pd.Timestamp("2013-05-01")
    assert c.loc["Bikes", "online_units_from"] == 11            # Jul 2013 to May 2014


def test_territory_aov_within_channel():
    orders = pd.DataFrame({"territory_name": ["A"] * 3 + ["B"] * 2, "territory_group": ["G"] * 5,
                           "channel": ["reseller", "online", "online", "online", "online"],
                           "revenue": [900.0, 100.0, 50.0, 10.0, 20.0]})
    t = sales.territory_aov(orders).set_index("territory_name")
    assert t.loc["A", "aov_reseller"] == 900 and t.loc["A", "aov_online"] == 75
    assert np.isnan(t.loc["B", "aov_reseller"]) and t.loc["A", "reseller_order_share"] == pytest.approx(1 / 3)


# --- segmentation ----------------------------------------------------------------------------------

def features(n_per=60, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    groups = [  # revenue, orders, bike_share, categories
        (2500, 2, 0.95, 2.5), (2400, 1, 1.0, 1.0), (50, 1, 0.0, 1.3)]
    rows = []
    for rev, n, bike, cats in groups:
        for _ in range(n_per):
            r = rev * rng.lognormal(0, 0.1)
            rows.append({"total_revenue": r, "n_orders": n, "aov": r / n, "units_per_order": 2.0,
                         "recency_days": rng.integers(30, 300), "tenure_days": 400,
                         "n_categories": round(cats + rng.normal(0, 0.1)), "bike_share": bike,
                         "first_order_before_jun2013": rev > 100})
    return pd.DataFrame(rows)


def test_choose_k_rule():
    kq = pd.DataFrame({"k": [2, 3, 4, 5], "silhouette": [0.9, 0.5, 0.6, 0.7],
                       "stability_ari": [1, 0.95, 0.95, 0.5], "min_cluster_share": [0.4, 0.1, 0.01, 0.1]})
    # k=2 excluded; k=4 has a tiny cluster; k=5 is unstable; so k=3 despite the lower silhouette
    assert segmentation.choose_k(kq) == 3


def test_segment_names_by_rule():
    assert segmentation.segment_name(0.2, 2.0) == "Accessory & clothing buyers"
    assert segmentation.segment_name(0.9, 2.0) == "Bike + gear buyers"
    assert segmentation.segment_name(0.9, 1.0) == "Bike-only buyers"


def test_segment_customers_recovers_three_groups():
    feat = features()
    seg = segmentation.segment_customers(feat, k_range=range(2, 5))
    assert seg["k"] == 3
    prof = seg["profiles"]
    assert set(prof.segment) == {"Bike + gear buyers", "Bike-only buyers", "Accessory & clothing buyers"}
    assert prof.customers.tolist() == [60, 60, 60]
    assert prof.customer_share.sum() == pytest.approx(1)


def test_pipeline_logs_only_skewed_columns():
    X = features()[segmentation.FEATURES]
    Z = segmentation.make_pipe(2)[:1].fit_transform(X)        # the log step only
    out = pd.DataFrame(Z, columns=segmentation.make_pipe(2)[:1].fit(X).get_feature_names_out())
    assert np.allclose(out["total_revenue"], np.log1p(X["total_revenue"]))
    assert np.allclose(out["recency_days"], X["recency_days"])


def test_profile_stores_tiers_and_lapsed():
    stores = pd.DataFrame({"customer_id": range(8), "total_revenue": [1, 2, 3, 4, 5, 6, 70, 80.0],
                           "recency_days": [10, 10, 10, 10, 10, 10, 10, 200]})
    s, summary = segmentation.profile_stores(stores)
    assert (s.value_tier == "Q1 (top)").sum() == 2
    assert summary["lapsed_top_quartile_stores"] == 1 and summary["lapsed_top_quartile_revenue"] == 80
    assert summary["top20_revenue_share"] == pytest.approx(80 / 171)


# --- forecasting -----------------------------------------------------------------------------------

def test_simple_models():
    y = pd.Series([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], index=MONTHS[:13])
    assert fc.fc_naive(y, 2).tolist() == [13, 13]
    assert fc.fc_ma(y, 1).tolist() == [12]
    assert fc.fc_snaive(y, 2).tolist() == [2, 3]
    assert fc.wape([10, 10], [5, 15]) == 0.5


def test_top_products_do_not_peek_at_test_period():
    pm = product_monthly({
        1: ("Clothing", "2011-05-01", lambda i: 100, 0.5),
        2: ("Clothing", "2011-05-01", lambda i: 50, 0.5),
        3: ("Clothing", "2011-05-01", lambda i: 10 if MONTHS[i] < fc.TEST_START else 10_000, 0.5),
        4: ("Clothing", "2013-05-01", lambda i: 5_000, 0.5),        # launch ramp: low coverage
    })
    top = fc.select_top_products(pm, n=2)
    assert top.product_id.tolist() == [1, 2]
    assert 4 not in fc.select_top_products(pm, n=4).product_id.tolist()


def test_product_series_fills_months_before_first_sale_with_zero():
    pm = product_monthly({1: ("Bikes", "2011-05-01", lambda i: 1, 1.0), 2: ("Bikes", "2012-01-01", lambda i: 2, 1.0)})
    s = fc.product_series(pm, [1, 2])
    assert s.index.freqstr == "MS" and len(s) == len(MONTHS)
    assert s.loc["2011-12-01", 2] == 0 and s.loc["2012-01-01", 2] == 2


def test_change_point_found_at_step():
    y = np.r_[np.full(20, 10.0), np.full(17, 50.0)]
    assert fc.segment_mean_shifts(y, penalty=100) == [20]


def test_forecast_top_products_end_to_end():
    rng = np.random.default_rng(1)
    noise = {p: rng.normal(0, 5, len(MONTHS)) for p in (1, 2)}
    pm = product_monthly({1: ("Clothing", "2011-05-01", lambda i: 100 + noise[1][i], 0.5),
                          2: ("Clothing", "2011-05-01", lambda i: 60 + noise[2][i], 0.5)})
    top = fc.select_top_products(pm, n=2)
    res = fc.forecast_top_products(pm, top)
    f = res["forecast"]
    assert len(f) == 2 * fc.H and f.month.min() == pd.Timestamp("2014-06-01")
    assert (f.lo95 <= f.lo80).all() and (f.lo80 <= f.units).all() and (f.units <= f.hi80).all()
    assert (f.hi80 <= f.hi95).all()
    assert set(res["scores"].index) == set(fc.MODELS) | {fc.CHANNEL_SPLIT}
    assert res["selected_wape"] < 0.2      # stationary series: errors are noise only
    assert len(res["backtest"]) == 2 * len(fc.ORIGINS) * fc.H * (len(fc.MODELS) + 1)


# --- margin ----------------------------------------------------------------------------------------

def test_margin_recomputed_from_sums_not_averaged():
    mm = pd.DataFrame({"month_start_date": pd.to_datetime(["2013-01-01"] * 2 + ["2013-02-01"]),
                       "category_name": ["Bikes", "Accessories", "Bikes"], "channel": ["online"] * 3,
                       "units": [1, 1, 1], "revenue": [1000.0, 10.0, 100.0], "cost": [900.0, 5.0, 120.0],
                       "gross_margin": [100.0, 5.0, -20.0]})
    monthly = margin.monthly_margin(mm)
    assert monthly.margin_pct.iloc[0] == pytest.approx(105 / 1010)   # not (0.1 + 0.5) / 2
    r = margin.margin_range(monthly)
    assert r["min_month"] == "2013-02" and r["min_margin_pct"] == pytest.approx(-0.2)
    assert r["window_margin_pct"] == pytest.approx(85 / 1110)
    assert len(margin.negative_margin_months(mm)) == 1


# --- supplier --------------------------------------------------------------------------------------

def vendor_quality():
    base = {"credit_rating": 1, "preferred_vendor_status": True, "active_flag": True, "purchase_orders": 1,
            "order_lines": 1, "stocked_qty": 0, "lines_with_rejections": 0, "purchase_value": 0.0,
            "avg_planned_lead_time_days": 14.0, "avg_declared_lead_time_days": 17.0}
    rows = [
        {"vendor_id": 1, "vendor_name": "Big", "month_start_date": pd.Timestamp("2013-01-01"),
         "ordered_qty": 1000, "received_qty": 1000.0, "rejected_qty": 50.0, "rejected_qty_on_rejected_orders": 30.0},
        {"vendor_id": 1, "vendor_name": "Big", "month_start_date": pd.Timestamp("2013-02-01"),
         "ordered_qty": 1000, "received_qty": 1000.0, "rejected_qty": 10.0, "rejected_qty_on_rejected_orders": 0.0},
        {"vendor_id": 2, "vendor_name": "Tiny", "month_start_date": pd.Timestamp("2013-01-01"),
         "ordered_qty": 10, "received_qty": 10.0, "rejected_qty": 5.0, "rejected_qty_on_rejected_orders": 0.0},
    ]
    return pd.DataFrame([{**base, **r} for r in rows])


def test_vendor_rates_and_minimum_size():
    vq = vendor_quality()
    s = supplier.vendor_summary(vq).set_index("vendor_name")
    assert s.loc["Big", "rejection_rate"] == pytest.approx(60 / 2000)
    assert s.loc["Big", "partial_rejection_rate"] == pytest.approx(30 / 2000)
    assert supplier.worst_vendors(s.reset_index()).vendor_name.tolist() == ["Big"]   # Tiny is below 1,000
    m = supplier.monthly_quality(vq)
    assert m.rejection_rate.tolist() == pytest.approx([55 / 1010, 10 / 1000])
    assert supplier.overall(vq)["rejection_rate"] == pytest.approx(65 / 2010)


def test_lead_time_support_reports_constant_planned_lead_time():
    lines = pd.DataFrame({"planned_lead_time_days": [14] * 99 + [30], "declared_lead_time_days": [15] * 50 + [60] * 50})
    r = supplier.lead_time_support(lines)
    assert r["planned_lead_time_mode_days"] == 14 and r["share_at_mode"] == pytest.approx(0.99)


# --- plots (smoke) ---------------------------------------------------------------------------------

def test_figures_render(tmp_path):
    from awlake.analysis import plots
    cm = channel_monthly([100] * len(MONTHS))
    fig = plots.monthly_trends(sales.monthly_pivot(cm), sales.monthly_pivot(cm, "orders"), [MONTHS[3]])
    assert plots.save(fig, tmp_path, "t.png").stat().st_size > 0
    s = supplier.vendor_summary(vendor_quality())
    assert plots.save(plots.worst_vendors(s), tmp_path, "w.png").exists()
