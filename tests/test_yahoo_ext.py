"""Yahoo extended-hours quote parsing (pre/post-market by market state)."""

from stockskill.data.yahoo_ext import _ext_from_quote


def test_post_market():
    q = {"marketState": "POST", "postMarketPrice": 201.5, "postMarketChangePercent": 1.2}
    assert _ext_from_quote(q) == {"market_state": "POST", "ext_price": 201.5,
                                  "ext_change": 0.012}


def test_pre_market():
    q = {"marketState": "PRE", "preMarketPrice": 98.0, "preMarketChangePercent": -0.5}
    r = _ext_from_quote(q)
    assert r["ext_price"] == 98.0 and r["ext_change"] == -0.005


def test_regular_session_has_no_ext():
    assert _ext_from_quote({"marketState": "REGULAR", "regularMarketPrice": 100.0}) is None


def test_post_but_no_price():
    assert _ext_from_quote({"marketState": "POST", "postMarketPrice": None}) is None
