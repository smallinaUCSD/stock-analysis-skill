from stockskill.server import create_app


def _rules(app):
    return {r.rule for r in app.url_map.iter_rules()}


def test_public_mode_omits_holdings_only():
    r = _rules(create_app(public=True))
    # holdings is personal -> gated out
    for gone in ("/holdings", "/api/holdings", "/api/holdings/trade", "/api/holdings/cash"):
        assert gone not in r, gone
    # the watchlist (incl. add-ticker) and read-only tools stay
    for kept in ("/", "/indicators", "/api/watchlist/add", "/api/watchlist/remove",
                 "/api/lookthrough/<ticker>", "/api/search"):
        assert kept in r, kept


def test_local_mode_has_holdings():
    assert "/holdings" in _rules(create_app(public=False))


def test_healthz_reports_mode():
    app = create_app(public=True)
    c = app.test_client()
    assert c.get("/healthz").get_json() == {"ok": True, "public": True}
