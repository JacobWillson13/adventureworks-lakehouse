import pytest

from awlake.repair import rejoin_rows

# Shape of the real ProductReview.csv: CRLF everywhere, unquoted line breaks inside Comments.
SAMPLE = (
    "1\t709\tJohn Smith\t2013-09-18 00:00:00\tjohn@fourthcoffee.com\t5\tI can't believe I'm singing the praises of a pair of socks, but\r\n"
    "3-day ride and these socks really helped.\r\n"
    "\r\n"
    "I won't go on another trip without them!\t2013-09-18 00:00:00\r\n"
    "2\t937\tDavid\t2013-11-13 00:00:00\tdavid@graphicdesigninstitute.com\t4\tA little on the heavy side.\t2013-11-13 00:00:00\r\n"
)


def test_rejoins_multiline_comments():
    rows = rejoin_rows(SAMPLE, n_cols=8)
    assert len(rows) == 2
    assert rows[0][0] == "1" and rows[0][-1] == "2013-09-18 00:00:00"
    assert rows[0][6].count("\n") == 3 and rows[0][6].endswith("without them!")
    assert rows[1][2] == "David"


def test_wrong_field_count_raises():
    with pytest.raises(ValueError, match="expected 9"):
        rejoin_rows(SAMPLE, n_cols=9)


def test_empty_fields_become_none():
    rows = rejoin_rows("1\t2\t\t4\r\n", n_cols=4)
    assert rows == [["1", "2", None, "4"]]
