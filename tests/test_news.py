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


def test_fetch_news_ranks_most_recent_first_and_limits(monkeypatch):
    def item(title, iso):
        return {"content": {"title": title, "pubDate": iso,
                            "provider": {"displayName": "P"},
                            "clickThroughUrl": {"url": "https://x/" + title}}}
    fake = [
        item("older", "2026-07-25T10:00:00Z"),
        item("newest", "2026-07-27T09:00:00Z"),
        item("middle", "2026-07-26T12:00:00Z"),
        item("undated", None),
    ]

    class _T:
        def __init__(self, *a, **k): self.news = fake

    monkeypatch.setattr("yfinance.Ticker", _T, raising=False)
    out = fetch_news("AAPL", limit=3)
    assert [n["title"] for n in out] == ["newest", "middle", "older"]  # undated dropped by limit
    assert "_ts" not in out[0]   # internal sort key stripped
