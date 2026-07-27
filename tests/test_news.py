from stockskill.data.news import _iso, _age, _url, fetch_news


def test_iso_from_unix_and_string():
    assert _iso(0) is None or _iso(0).startswith("1970")
    assert _iso("2026-07-27T10:00:00Z") == "2026-07-27T10:00:00Z"
    assert _iso(None) is None


def test_url_prefers_clickthrough_then_canonical_then_link():
    assert _url({"clickThroughUrl": {"url": "https://a"}, "canonicalUrl": {"url": "https://b"}}) == "https://a"
    assert _url({"canonicalUrl": {"url": "https://b"}}) == "https://b"
    assert _url({"link": "https://c"}) == "https://c"
    assert _url({}) == ""


def test_age_empty_on_bad_input():
    assert _age(None) == ""
    assert _age("not-a-date") == ""


def test_fetch_news_normalizes_new_shape(monkeypatch):
    fake = [{"id": "1", "content": {
        "title": "Big news", "summary": "s", "pubDate": "2026-07-27T10:00:00Z",
        "provider": {"displayName": "Reuters"},
        "clickThroughUrl": {"url": "https://x/story"}, "contentType": "STORY"}}]

    class _T:
        def __init__(self, *a, **k): self.news = fake

    import stockskill.data.news as mod
    monkeypatch.setattr("yfinance.Ticker", _T, raising=False)
    out = fetch_news("AAPL", limit=5)
    assert len(out) == 1
    assert out[0]["title"] == "Big news"
    assert out[0]["publisher"] == "Reuters"
    assert out[0]["url"] == "https://x/story"
