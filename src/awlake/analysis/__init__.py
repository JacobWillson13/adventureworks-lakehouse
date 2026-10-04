"""Analyses on gold: plain pandas functions, so notebooks stay thin and the logic is tested locally.

Each module takes the gold marts as DataFrames (read with awlake.analysis.runtime.read_gold) and returns
DataFrames or numbers; plotting lives in awlake.analysis.plots and MLflow logging in
awlake.analysis.tracking. Settled decisions (docs/PLAN.md) are constants in this package, not notebook
parameters: revenue = sub_total, analysis window ends 2014-05-31, July 2013 structural break.
"""
import pandas as pd

WINDOW_END = pd.Timestamp("2014-05-31")
REFERENCE_DATE = pd.Timestamp("2014-06-01")   # recency and tenure are counted to the day after the window
BREAK = pd.Timestamp("2013-07-01")            # accessories and clothing launched online
SEED = 42
