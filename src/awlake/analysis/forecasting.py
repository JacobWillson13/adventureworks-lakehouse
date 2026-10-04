"""Monthly unit forecasts per product, with revenue alongside.

Input: mart_product_monthly (product x month, zero-filled after the first sale). Products are ranked on
units before the backtest window only, so selection never peeks at the test period. Candidates run from
naive baselines to ETS, plus two that encode the settled findings: ETS fitted after the July 2013 break,
and a channel split (online and reseller forecast separately, because reseller orders arrive in monthly
batches with empty months). Rolling-origin backtest, error = WAPE.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.seasonal import STL

from . import BREAK

TEST_START = pd.Timestamp("2013-12-01")
ORIGINS = pd.date_range("2013-11-01", "2014-02-01", freq="MS")   # last observed month at each origin
H = 3
TOP_N = 5
MIN_COVERAGE = 0.9
Z80, Z95 = 1.2816, 1.96


# --- data ------------------------------------------------------------------------------------------

def select_top_products(pm: pd.DataFrame, test_start: pd.Timestamp = TEST_START, n: int = TOP_N,
                        min_coverage: float = MIN_COVERAGE) -> pd.DataFrame:
    """Top n products by units before test_start, among those with sales in >= min_coverage of the
    training months (so the forecast is about demand, not a launch ramp)."""
    train = pm[pm.month_start_date < test_start]
    n_months = train.month_start_date.nunique()
    rank = (train.groupby(["product_id", "product_name", "category_name"])
            .agg(train_units=("units", "sum"), months_with_sales=("is_zero_month", lambda z: int((~z).sum())))
            .reset_index())
    rank["coverage"] = rank["months_with_sales"] / n_months
    return (rank[rank.coverage >= min_coverage].sort_values("train_units", ascending=False)
            .head(n).reset_index(drop=True))


def product_series(pm: pd.DataFrame, product_ids, column: str = "units") -> pd.DataFrame:
    """Month x product table (MS frequency) of one measure; months before a product's first sale are 0."""
    return (pm[pm.product_id.isin(product_ids)]
            .pivot(index="month_start_date", columns="product_id", values=column)
            .reindex(columns=list(product_ids)).sort_index().asfreq("MS").fillna(0).astype(float))


def recent_price(pm: pd.DataFrame, product_id: int, since: pd.Timestamp = TEST_START) -> float:
    """Average realized price per unit since `since`, to translate unit forecasts into revenue."""
    r = pm[(pm.product_id == product_id) & (pm.month_start_date >= since)]
    return float(r.revenue.sum() / max(r.units.sum(), 1))


# --- models: each takes a history (pd.Series, MS index) and a horizon, returns h forecasts ----------

def fc_naive(y: pd.Series, h: int) -> np.ndarray:
    return np.repeat(float(y.iloc[-1]), h)


def fc_snaive(y: pd.Series, h: int) -> np.ndarray:
    if len(y) < 12:
        return fc_naive(y, h)
    return np.array([float(y.iloc[-12 + (i % 12)]) for i in range(h)])


def fc_ma(y: pd.Series, h: int, window: int = 3) -> np.ndarray:
    return np.repeat(float(y.iloc[-window:].mean()), h)


def fit_ets(y: pd.Series, trend: str | None = None, damped: bool = False):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ETSModel(y.astype(float), error="add", trend=trend, damped_trend=damped).fit(disp=False)


def fc_ets(y: pd.Series, h: int) -> np.ndarray:
    return np.clip(fit_ets(y).forecast(h).values, 0, None)


def fc_ets_damped(y: pd.Series, h: int) -> np.ndarray:
    return np.clip(fit_ets(y, trend="add", damped=True).forecast(h).values, 0, None)


def post_break(y: pd.Series, break_month: pd.Timestamp = BREAK, min_points: int = 4) -> pd.Series:
    tail = y[y.index >= break_month]
    return tail if len(tail) >= min_points else y


def fc_ets_post(y: pd.Series, h: int) -> np.ndarray:
    return fc_ets(post_break(y), h)


MODELS = {
    "Naive": fc_naive,
    "Seasonal naive": fc_snaive,
    "Moving avg (3)": fc_ma,
    "ETS (A,N,N)": fc_ets,
    "ETS (A,Ad,N)": fc_ets_damped,
    "ETS (A,N,N) post-break": fc_ets_post,
}
CHANNEL_SPLIT = "Channel split"   # online: ETS post-break; reseller: 6-month mean (spans skipped batches)


def fc_channel_split(online: pd.Series, reseller: pd.Series, h: int) -> np.ndarray:
    return fc_ets_post(online, h) + fc_ma(reseller, h, window=6)


# --- backtest --------------------------------------------------------------------------------------

def backtest(series: pd.DataFrame, online: pd.DataFrame, reseller: pd.DataFrame,
             origins=ORIGINS, h: int = H) -> pd.DataFrame:
    """Expanding-window backtest: for each product, origin and model, h forecasts against actuals."""
    rows = []
    for pid in series.columns:
        y_all = series[pid]
        for origin in origins:
            y_tr, y_te = y_all[y_all.index <= origin], y_all[y_all.index > origin].iloc[:h]
            preds = {name: f(y_tr, h) for name, f in MODELS.items()}
            preds[CHANNEL_SPLIT] = fc_channel_split(online[pid][online.index <= origin],
                                                    reseller[pid][reseller.index <= origin], h)
            for name, pred in preds.items():
                for step, (month, actual) in enumerate(y_te.items(), start=1):
                    rows.append({"product_id": pid, "model": name, "origin": origin, "h": step,
                                 "month": month, "actual": actual, "forecast": float(pred[step - 1])})
    bt = pd.DataFrame(rows)
    bt["abs_err"] = (bt.actual - bt.forecast).abs()
    return bt


def wape(actual, forecast) -> float:
    """Sum of absolute errors over sum of actuals (comparable across products of different size)."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.abs(actual - forecast).sum() / actual.sum())


def score_models(bt: pd.DataFrame) -> pd.DataFrame:
    """MAE and WAPE per model over all products, origins and horizons, best first."""
    return (bt.groupby("model").apply(lambda g: pd.Series({"MAE": g.abs_err.mean(),
                                                           "WAPE": wape(g.actual, g.forecast)}),
                                      include_groups=False).sort_values("WAPE"))


def wape_by_product(bt: pd.DataFrame) -> pd.DataFrame:
    """Product x model WAPE."""
    return (bt.groupby(["product_id", "model"]).apply(lambda g: wape(g.actual, g.forecast), include_groups=False)
            .unstack("model"))


# --- final forecasts -------------------------------------------------------------------------------

def forecast_product(y: pd.Series, online: pd.Series, reseller: pd.Series, model: str, bt_errors: pd.DataFrame,
                     h: int = H) -> pd.DataFrame:
    """Point forecast and 80%/95% intervals for the next h months with one model, refit on all history.
    ETS intervals come from the fitted model; the others use the spread of the model's backtest errors
    at each horizon."""
    future = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    if model.startswith("ETS"):
        y_fit = post_break(y) if "post-break" in model else y
        trend, damped = ("add", True) if "Ad" in model else (None, False)
        res = fit_ets(y_fit, trend, damped)
        pr = res.get_prediction(start=len(y_fit), end=len(y_fit) + h - 1)
        f95, f80 = pr.summary_frame(alpha=0.05), pr.summary_frame(alpha=0.20)
        point = f95["mean"].values
        lo95, hi95, lo80, hi80 = (f95["pi_lower"].values, f95["pi_upper"].values,
                                  f80["pi_lower"].values, f80["pi_upper"].values)
    else:
        point = (fc_channel_split(online, reseller, h) if model == CHANNEL_SPLIT else MODELS[model](y, h))
        e = bt_errors.assign(e=bt_errors.actual - bt_errors.forecast)
        sd = e.groupby("h")["e"].std().reindex(range(1, h + 1)).ffill().fillna(0).values
        lo95, hi95, lo80, hi80 = point - Z95 * sd, point + Z95 * sd, point - Z80 * sd, point + Z80 * sd
    clip = lambda a: np.clip(a, 0, None)  # noqa: E731
    return pd.DataFrame({"month": future, "model": model, "units": clip(point), "lo80": clip(lo80),
                         "hi80": clip(hi80), "lo95": clip(lo95), "hi95": clip(hi95)})


def forecast_top_products(pm: pd.DataFrame, top: pd.DataFrame, h: int = H) -> dict:
    """The whole forecasting analysis: series, backtest, scores, per-product best model and the
    h-month forecast with revenue at the recent average price."""
    ids = top.product_id.tolist()
    series, online, reseller = (product_series(pm, ids, c) for c in ("units", "online_units", "reseller_units"))
    bt = backtest(series, online, reseller, h=h)
    scores, by_prod = score_models(bt), wape_by_product(bt)
    best = by_prod.idxmin(axis=1)
    fcs = []
    for pid in ids:
        f = forecast_product(series[pid], online[pid], reseller[pid], best[pid],
                             bt[(bt.product_id == pid) & (bt.model == best[pid])], h)
        f.insert(0, "product_id", pid)
        f["est_revenue"] = f["units"] * recent_price(pm, pid)
        fcs.append(f)
    forecast = pd.concat(fcs, ignore_index=True)
    names = dict(zip(top.product_id, top.product_name))
    forecast.insert(1, "product_name", forecast.product_id.map(names))
    best_wape = float(np.mean([by_prod.loc[p, best[p]] for p in ids]))
    selected = bt[bt.apply(lambda r: r.model == best[r.product_id], axis=1)]
    return {"series": series, "online": online, "reseller": reseller, "backtest": bt, "scores": scores,
            "wape_by_product": by_prod, "best_model": best, "forecast": forecast, "names": names,
            "selected_wape": wape(selected.actual, selected.forecast), "mean_best_wape": best_wape}


# --- diagnostics -----------------------------------------------------------------------------------

def stl_strength(total: pd.Series, period: int = 12) -> tuple[dict, object]:
    """Trend and seasonal strength from a robust STL (0 = none, 1 = dominant)."""
    stl = STL(total, period=period, robust=True).fit()
    trend = max(0.0, 1 - np.var(stl.resid) / np.var(stl.trend + stl.resid))
    season = max(0.0, 1 - np.var(stl.resid) / np.var(stl.seasonal + stl.resid))
    return {"trend_strength": float(trend), "seasonal_strength": float(season)}, stl


def segment_mean_shifts(y, penalty: float, min_size: int = 3) -> list[int]:
    """Exact optimal partition of y into constant-mean segments (dynamic programming), minimizing
    within-segment squared error + penalty per segment. Returns break positions (segment starts)."""
    y = np.asarray(y, float)
    n = len(y)
    cs, cs2 = np.r_[0, np.cumsum(y)], np.r_[0, np.cumsum(y ** 2)]

    def cost(i, j):
        return (cs2[j] - cs2[i]) - (cs[j] - cs[i]) ** 2 / (j - i)

    best, prev = np.full(n + 1, np.inf), np.zeros(n + 1, int)
    best[0] = -penalty
    for j in range(min_size, n + 1):
        for i in range(j - min_size + 1):
            if i != 0 and i < min_size:
                continue
            c = best[i] + cost(i, j) + penalty
            if c < best[j]:
                best[j], prev[j] = c, i
    breaks, j = [], n
    while j > 0:
        j = prev[j]
        if j > 0:
            breaks.append(j)
    return sorted(breaks)


def change_points(series: pd.DataFrame, names: dict, multipliers=(2, 4, 8)) -> pd.DataFrame:
    """Change points per product at several BIC-like penalties (mult * sigma^2 * log n, sigma from a
    robust estimate on first differences). Breaks found at every setting are the robust ones."""
    rows = []
    for pid in series.columns:
        y = series[pid].values
        sigma2 = np.median(np.abs(np.diff(y))) ** 2 / 0.4549
        for mult in multipliers:
            bks = segment_mean_shifts(y, penalty=mult * sigma2 * np.log(len(y)))
            rows.append({"product_name": names[pid], "penalty": f"x{mult}",
                         "breaks": ", ".join(series.index[b].strftime("%Y-%m") for b in bks) or "none"})
    return pd.DataFrame(rows).pivot(index="product_name", columns="penalty", values="breaks").reset_index()
