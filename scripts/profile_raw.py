"""Profile every raw AdventureWorks CSV against config/aw_schema.json.

Checks per file: encoding, line terminator, header presence, row count,
field-count distribution vs. the expected column count, and the first row
mapped to column names (so column order can be eyeballed).

Usage (from repo root):
    python scripts/profile_raw.py      # prints summary, writes data/_profile/raw_profile.json
"""
from __future__ import annotations

import codecs
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SCHEMA = json.loads((ROOT / "config" / "aw_schema.json").read_text())
# Under data/ so it stays gitignored: first_row samples include Password/CreditCard values.
OUT = ROOT / "data" / "_profile" / "raw_profile.json"

# Files in this export that are not in Microsoft's DDL; profile against their nearest table.
ALIASES = {"JobCandidate_TOREMOVE": "JobCandidate", "ProductModelorg": "ProductModel"}

csv.field_size_limit(sys.maxsize)


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def line_terminator(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        return f"mixed (crlf={crlf}, lf={lf})"
    return "crlf" if crlf else "lf" if lf else "none"


def profile(path: Path) -> dict:
    raw = path.read_bytes()
    enc = detect_encoding(raw)
    text = raw.decode(enc)
    table = ALIASES.get(path.stem, path.stem)
    cols = [c["name"] for c in SCHEMA[table]["columns"]] if table in SCHEMA else None

    rows = list(csv.reader(_io(text), delimiter="\t", quotechar='"'))
    widths = Counter(len(r) for r in rows)
    first = rows[0] if rows else []
    looks_like_header = bool(cols) and [f.strip().lower() for f in first[: len(cols)]] == [c.lower() for c in cols[: len(first)]]

    rec = {
        "file": path.name,
        "table": table,
        "bytes": len(raw),
        "encoding": enc,
        "line_terminator": line_terminator(raw),
        "rows": len(rows),
        "expected_cols": len(cols) if cols else None,
        "field_counts": dict(widths.most_common()),
        "header_row": looks_like_header,
        "status": "ok",
    }
    if cols is None:
        rec["status"] = "NO_SCHEMA"
    elif set(widths) != {len(cols)}:
        rec["status"] = "COL_MISMATCH"
        bad = [i for i, r in enumerate(rows) if len(r) != len(cols)][:3]
        rec["bad_row_examples"] = {i: [v[:60] for v in rows[i]] for i in bad}
    if rows:
        names = cols if cols and len(cols) == len(first) else [f"c{i}" for i in range(len(first))]
        rec["first_row"] = {n: v[:80] for n, v in zip(names, first)}
    return rec


def _io(text: str) -> io.StringIO:
    return io.StringIO(text, newline="")


def main() -> None:
    files = sorted(RAW.glob("*.csv"))
    if not files:
        sys.exit(f"No CSVs in {RAW}")
    results = [profile(f) for f in files]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"{'file':42} {'enc':9} {'eol':6} {'rows':>8} {'exp':>4}  field_counts  status")
    for r in results:
        print(f"{r['file']:42} {r['encoding']:9} {r['line_terminator'][:6]:6} {r['rows']:>8} "
              f"{str(r['expected_cols']):>4}  {r['field_counts']}  {r['status']}")
    print(f"\n{Counter(r['status'] for r in results)}  ->  full report: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
