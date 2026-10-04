"""Parse Microsoft's AdventureWorks DDL (instawdb.sql) into config/aw_schema.json.

The raw CSVs have no header row, so column names, order and target types come
from the official install script:
https://github.com/microsoft/sql-server-samples/blob/master/samples/databases/adventure-works/oltp-install-script/instawdb.sql

Usage (from repo root):
    curl -sSLo /tmp/instawdb.sql https://raw.githubusercontent.com/microsoft/sql-server-samples/master/samples/databases/adventure-works/oltp-install-script/instawdb.sql
    python scripts/build_schema.py /tmp/instawdb.sql config/aw_schema.json
"""
import json
import re
import sys

src = open(sys.argv[1], encoding="utf-8-sig").read()
UDT = {"AccountNumber": "nvarchar", "Flag": "bit", "NameStyle": "bit", "Name": "nvarchar",
       "OrderNumber": "nvarchar", "Phone": "nvarchar"}
SPARK = {"decimal": None, "numeric": None, "int": "INT", "smallint": "SMALLINT", "tinyint": "TINYINT", "bigint": "BIGINT", "bit": "BOOLEAN",
         "money": "DECIMAL(19,4)", "smallmoney": "DECIMAL(10,4)", "float": "DOUBLE", "real": "FLOAT",
         "datetime": "TIMESTAMP", "smalldatetime": "TIMESTAMP", "date": "DATE", "time": "STRING",
         "uniqueidentifier": "STRING", "xml": "STRING", "varbinary": "BINARY", "hierarchyid": "STRING", "geography": "STRING",
         "nvarchar": "STRING", "varchar": "STRING", "nchar": "STRING", "char": "STRING", "sysname": "STRING"}

# Computed columns: result types per SQL Server type rules for each expression.
COMPUTED = {
    "AccountNumber": ("nvarchar", "STRING"),
    "SalesOrderNumber": ("nvarchar(25)", "STRING"),
    "DocumentLevel": ("smallint", "SMALLINT"),
    "OrganizationLevel": ("smallint", "SMALLINT"),
    "TotalDue": ("money", "DECIMAL(19,4)"),
    ("PurchaseOrderDetail", "LineTotal"): ("money", "DECIMAL(19,4)"),
    ("SalesOrderDetail", "LineTotal"): ("numeric(38,6)", "DECIMAL(38,6)"),
    ("PurchaseOrderDetail", "StockedQty"): ("decimal(9,2)", "DECIMAL(9,2)"),
    ("WorkOrder", "StockedQty"): ("int", "INT"),
}

def split_top(body):
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out

def strip_comments(t): return re.sub(r"--[^\n]*", "", t)

tables = {}
for m in re.finditer(r"CREATE TABLE \[(\w+)\]\.\[(\w+)\]\s*\((.*?)\)\s*ON \[PRIMARY\]", src, re.S):
    schema, name, body = m.groups()
    cols = []
    for part in split_top(strip_comments(body)):
        p = " ".join(part.split())
        if not p or p.upper().startswith("CONSTRAINT"):
            continue
        cm = re.match(r"\[([^\]]+)\]\s+(.*)", p)
        if not cm:
            continue
        col, rest = cm.groups()
        if re.match(r"AS\b", rest, re.I):
            sqlt, spark = COMPUTED.get((name, col), COMPUTED.get(col))
            cols.append({"name": col, "sql_type": sqlt, "spark_type": spark, "nullable": False,
                         "computed": True, "expression": rest[3:]})
            continue
        tm = re.match(r"\[?(\w+)\]?(?:\(([^)]*)\))?", rest)
        sqlt, arg = tm.group(1), tm.group(2)
        base = UDT.get(sqlt, sqlt).lower()
        spark = SPARK[base]
        if base in ("decimal", "numeric") or spark is None:
            spark = f"DECIMAL({arg.replace(' ', '')})" if arg else "DECIMAL(18,0)"
        nullable = "NOT NULL" not in rest.upper() or (sqlt in UDT and "NOT NULL" not in rest.upper())
        cols.append({"name": col, "sql_type": base + (f"({arg})" if arg and base not in ("xml",) else ""),
                     "spark_type": spark, "nullable": nullable, "computed": False})
    tables[name] = {"source_schema": schema, "columns": cols}
json.dump(tables, open(sys.argv[2], "w"), indent=2)
print(len(tables), "tables written")
