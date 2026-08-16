from stockskill.server import create_app


def _rules(app):
    return {r.rule for r in app.url_map.iter_rules()}


def test_public_mode_omits_personal_routes():
    r = _rules(create_app(public=True))
    for gone in ("/holdings", "/api/holdings", "/api/holdings/trade",
                 "/api/watchlist/add", "/api/watchlist/remove"):
        assert gone not in r, gone
    # read-only analysis stays available
    for kept in ("/", "/indicators", "/api/lookthrough/<ticker>", "/api/search"):
        assert kept in r, kept


def test_local_mode_has_holdings():
    assert "/holdings" in _rules(create_app(public=False))


def test_healthz_reports_mode():
    app = create_app(public=True)
    c = app.test_client()
    assert c.get("/healthz").get_json() == {"ok": True, "public": True}
