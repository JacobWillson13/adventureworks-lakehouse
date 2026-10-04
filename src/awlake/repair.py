"""Repairs for raw files that a standard CSV reader cannot parse."""
from __future__ import annotations

import re

# A record in ProductReview starts with ProductReviewID<TAB>ProductID<TAB>.
DEFAULT_RECORD_START = r"^\d+\t\d+\t"


def rejoin_rows(text: str, n_cols: int, record_start: str = DEFAULT_RECORD_START, sep: str = "\t") -> list[list[str]]:
    """Rebuild records whose free-text field contains unquoted line breaks.

    Any physical line that does not match `record_start` is a continuation of the
    previous record and is re-attached with a newline. Raises if a rebuilt record
    does not have exactly `n_cols` fields, so a bad repair fails loudly.
    """
    pattern = re.compile(record_start)
    records: list[str] = []
    for line in text.rstrip("\r\n").splitlines():
        if pattern.match(line) or not records:
            records.append(line)
        else:
            records[-1] += "\n" + line

    rows = []
    for i, rec in enumerate(records):
        fields = rec.split(sep)
        if len(fields) != n_cols:
            raise ValueError(f"record {i} has {len(fields)} fields, expected {n_cols}: {rec[:120]!r}")
        rows.append([f if f != "" else None for f in fields])
    return rows
