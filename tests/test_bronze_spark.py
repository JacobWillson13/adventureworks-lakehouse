"""Runs the real bronze reader on small files that reproduce each raw-format quirk.
Skipped when pyspark is not installed."""
import pytest

pyspark = pytest.importorskip("pyspark")

from conftest import ROOT
from awlake.bronze import read_source
from awlake.config import Config

cfg = Config(ROOT)


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = SparkSession.builder.master("local[1]").appName("aw-tests").config("spark.ui.enabled", "false").getOrCreate()
    yield s
    s.stop()


def write(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_crlf_and_null_fields(spark, tmp_path):
    path = write(tmp_path, "Customer.csv",
                 b"1\t\t934\t1\tAW00000001\t{3F5AE95E-B87D-4AED-95B4-C3797AFCB74F}\t2014-09-12 11:15:07.263000000\r\n"
                 b"2\t\t1028\t1\tAW00000002\t{E552F657-A9AF-4A7D-A645-C429D6E02491}\t2014-09-12 11:15:07.263000000\r\n")
    rows = read_source(spark, path, cfg.spec("Customer")).collect()
    assert len(rows) == 2
    assert rows[0]["PersonID"] is None and rows[0]["StoreID"] == "934"
    assert rows[0]["ModifiedDate"] == "2014-09-12 11:15:07.263000000"  # no trailing \r


def test_quoted_xml_with_doubled_quotes_and_newline(spark, tmp_path):
    xml = '"<IndividualSurvey xmlns=""http://x""><TotalPurchaseYTD>0</TotalPurchaseYTD>\n</IndividualSurvey>"'
    line = f"1\tEM\t0\t\tKen\tJ\tSánchez\t\t0\t\t{xml}\t92C4279F-1207-48A3-8448-4636514EB7E2\t2009-01-07 00:00:00\n"
    path = write(tmp_path, "Person.csv", line.encode("utf-8"))
    rows = read_source(spark, path, cfg.spec("Person")).collect()
    assert len(rows) == 1
    assert rows[0]["LastName"] == "Sánchez"
    assert rows[0]["Demographics"].startswith('<IndividualSurvey xmlns="http://x">')


def test_cp1252_address(spark, tmp_path):
    line = "552\t25730, boul. St-Régis\t\tDorval\t57\tH9P 1H1\t0xE6100000\t{AAAA}\t2014-09-12 00:00:00\r\n"
    path = write(tmp_path, "Address.csv", line.encode("cp1252"))
    rows = read_source(spark, path, cfg.spec("Address")).collect()
    assert rows[0]["AddressLine1"] == "25730, boul. St-Régis"


def test_extra_field_fails_fast(spark, tmp_path):
    path = write(tmp_path, "AddressType.csv", b"1\tBilling\t{G}\t2008-04-30 00:00:00\textra\r\n")
    with pytest.raises(Exception):
        read_source(spark, path, cfg.spec("AddressType")).collect()


def test_productreview_rejoin(spark, tmp_path):
    data = ("1\t709\tJohn Smith\t2013-09-18 00:00:00\tjohn@x.com\t5\tline one\r\nline two\t2013-09-18 00:00:00\r\n"
            "2\t937\tDavid\t2013-11-13 00:00:00\tdavid@x.com\t4\tshort\t2013-11-13 00:00:00\r\n").encode()
    path = write(tmp_path, "ProductReview.csv", data)
    rows = read_source(spark, path, cfg.spec("ProductReview")).collect()
    assert len(rows) == 2 and rows[0]["Comments"] == "line one\nline two"


def test_empty_file(spark, tmp_path):
    path = write(tmp_path, "ErrorLog.csv", b"")
    df = read_source(spark, path, cfg.spec("ErrorLog"))
    assert df.count() == 0 and len(df.columns) == 9


def test_cp1252_extended_range(spark, tmp_path):
    # 0x80-0x9F differ between cp1252 and latin-1 (e.g. 0x92 is a right single quote in cp1252).
    line = "700\t30, avenue de l’Union\t\tParis\t1\t75000\t0xE6\t{B}\t2014-09-12 00:00:00\r\n"
    path = write(tmp_path, "Address.csv", line.encode("cp1252"))
    assert read_source(spark, path, cfg.spec("Address")).collect()[0]["AddressLine1"] == "30, avenue de l’Union"
