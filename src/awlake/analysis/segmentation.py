"""Customer segmentation: K-means on individual (online) customers, reseller stores profiled separately.

Input: mart_customer_features (one row per individual) and mart_store_profile (one row per store).
Skewed money and count features (LOG_COLS) are log-transformed before scaling, so a few large customers do not
dominate the distances. k is chosen by a fixed rule (choose_k), and segments are named by rule from
their profile (segment_name), not by cluster number, so names survive a different K-means numbering.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.metrics import adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import SEED

FEATURES = ["total_revenue", "n_orders", "aov", "units_per_order", "recency_days", "n_categories", "bike_share"]
LOG_COLS = ["total_revenue", "n_orders", "aov", "units_per_order"]
K_RANGE = range(2, 9)


def make_pipe(k: int, seed: int = SEED, columns=FEATURES) -> Pipeline:
    """log1p on the skewed columns (LOG_COLS present in `columns`), standard scaling, K-means. Built from
    sklearn and numpy parts only, so MLflow can save it without trusting project code."""
    log_cols = [c for c in LOG_COLS if c in columns]
    log = ColumnTransformer([("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one"), log_cols)],
                            remainder="passthrough", verbose_feature_names_out=False)
    return make_pipeline(log, StandardScaler(), KMeans(n_clusters=k, n_init=10, random_state=seed))


def k_selection(X: pd.DataFrame, k_range=K_RANGE, seed: int = SEED, sample: int = 6000,
                stability_seeds=range(1, 6)) -> pd.DataFrame:
    """Quality of each k: inertia, silhouette (on a sample; it is O(n^2)), Davies-Bouldin,
    Calinski-Harabasz, stability (mean ARI against other seeds) and the smallest cluster's share."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), size=min(sample, len(X)), replace=False)
    rows = []
    for k in k_range:
        pipe = make_pipe(k, seed, X.columns).fit(X)
        Z = pipe[:-1].transform(X)
        lab = pipe[-1].labels_
        aris = [adjusted_rand_score(lab, make_pipe(k, s, X.columns).fit(X)[-1].labels_) for s in stability_seeds]
        rows.append({"k": k, "inertia": pipe[-1].inertia_,
                     "silhouette": silhouette_score(Z[idx], lab[idx]),
                     "davies_bouldin": davies_bouldin_score(Z, lab),
                     "calinski_harabasz": calinski_harabasz_score(Z, lab),
                     "stability_ari": float(np.mean(aris)),
                     "min_cluster_share": np.bincount(lab).min() / len(lab)})
    return pd.DataFrame(rows)


def choose_k(kq: pd.DataFrame, k_min: int = 3, k_max: int = 6, min_ari: float = 0.9,
             min_share: float = 0.03) -> int:
    """Among k in [k_min, k_max] that are stable (ARI >= min_ari) with no cluster under min_share of
    customers, take the best silhouette. k = 2 is excluded as too coarse to act on. Falls back to the
    best silhouette in range if no k qualifies."""
    in_range = kq[kq.k.between(k_min, k_max)]
    ok = in_range[(in_range.stability_ari >= min_ari) & (in_range.min_cluster_share >= min_share)]
    return int((ok if len(ok) else in_range).sort_values("silhouette", ascending=False).iloc[0]["k"])


def redundancy_check(X: pd.DataFrame, labels: np.ndarray, k: int, seed: int = SEED) -> pd.DataFrame:
    """ARI of the full model against refits without total_revenue (= n_orders x aov) and without the
    product-mix features. High ARI means the dropped features do not drive the segments."""
    variants = {
        "drop total_revenue": [f for f in X.columns if f != "total_revenue"],
        "drop product mix (n_categories, bike_share)": [f for f in X.columns
                                                        if f not in ("n_categories", "bike_share")],
    }
    return pd.DataFrame([{"variant": name,
                          "ari_vs_full": adjusted_rand_score(labels, make_pipe(k, seed, cols).fit(X[cols])[-1].labels_)}
                         for name, cols in variants.items()])


def segment_name(mean_bike_share: float, mean_categories: float) -> str:
    if mean_bike_share < 0.5:
        return "Accessory & clothing buyers"
    return "Bike + gear buyers" if mean_categories >= 1.5 else "Bike-only buyers"


def profile_clusters(feat: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Segment profiles in business units, largest revenue first, named by rule. If two clusters get the
    same name, the cluster number is appended so names stay unique."""
    prof = feat.assign(cluster=labels).groupby("cluster").agg(
        customers=("n_orders", "size"), revenue=("total_revenue", "sum"),
        median_revenue=("total_revenue", "median"), mean_orders=("n_orders", "mean"),
        median_aov=("aov", "median"), median_units_per_order=("units_per_order", "median"),
        median_recency_days=("recency_days", "median"), median_tenure_days=("tenure_days", "median"),
        mean_categories=("n_categories", "mean"), mean_bike_share=("bike_share", "mean"),
        first_order_before_jun2013=("first_order_before_jun2013", "mean"))
    prof["customer_share"] = prof["customers"] / prof["customers"].sum()
    prof["revenue_share"] = prof["revenue"] / prof["revenue"].sum()
    prof = prof.sort_values("revenue", ascending=False)
    names = [segment_name(r.mean_bike_share, r.mean_categories) for r in prof.itertuples()]
    if len(set(names)) != len(names):
        names = [f"{n} ({c})" for n, c in zip(names, prof.index)]
    prof.insert(0, "segment", names)
    return prof.reset_index()


def segment_customers(feat: pd.DataFrame, seed: int = SEED, k_range=K_RANGE) -> dict:
    """The whole individual-customer segmentation: k table, chosen k, fitted pipeline, labels, profiles,
    redundancy check and the chosen model's quality metrics."""
    X = feat[FEATURES].astype(float)
    kq = k_selection(X, k_range, seed)
    k = choose_k(kq)
    pipe = make_pipe(k, seed, X.columns).fit(X)
    labels = pipe[-1].labels_
    chosen = kq[kq.k == k].iloc[0]
    return {
        "k_table": kq, "k": k, "pipeline": pipe, "labels": labels,
        "profiles": profile_clusters(feat, labels),
        "redundancy": redundancy_check(X, labels, k, seed),
        "metrics": {"k": k, "silhouette": chosen.silhouette, "davies_bouldin": chosen.davies_bouldin,
                    "calinski_harabasz": chosen.calinski_harabasz, "stability_ari": chosen.stability_ari,
                    "customers": len(feat)},
    }


def profile_stores(stores: pd.DataFrame, active_days: int = 120) -> tuple[pd.DataFrame, dict]:
    """Value quartile (by revenue) and active/lapsed status per store, plus headline numbers:
    revenue share of the top 20% of stores and the top-quartile stores that have lapsed."""
    s = stores.copy()
    s["value_tier"] = pd.qcut(s["total_revenue"].rank(method="first"), 4,
                              labels=["Q4 (lowest)", "Q3", "Q2", "Q1 (top)"])
    s["status"] = np.where(s["recency_days"] <= active_days, f"Active (<= {active_days} days)",
                           f"Lapsed (> {active_days} days)")
    top = s.nlargest(int(len(s) * 0.2), "total_revenue")
    lapsed_q1 = s[(s.value_tier == "Q1 (top)") & s.status.str.startswith("Lapsed")]
    summary = {"stores": len(s), "top20_revenue_share": top.total_revenue.sum() / s.total_revenue.sum(),
               "lapsed_top_quartile_stores": len(lapsed_q1),
               "lapsed_top_quartile_revenue": float(lapsed_q1.total_revenue.sum())}
    return s, summary


def store_tier_table(s: pd.DataFrame) -> pd.DataFrame:
    """Stores and revenue by value tier and status."""
    return (s.groupby(["value_tier", "status"], observed=False)
            .agg(stores=("customer_id", "size"), revenue=("total_revenue", "sum")).reset_index())
