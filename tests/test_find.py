"""Search as you type: forgiving name matching and /api/find (stocks,
politicians, funds). No network."""

import pytest

from stockskill.data.fuzzy import rank, score


def test_forgiving_names():
    for q in ("pelosi", "Pelosi", "nancy p", "nan pel", "palosi", "pelosy"):
        assert score(q, "Nancy Pelosi") >= 0.62, q
    for q in ("jones", "buffett", "xyz"):
        assert score(q, "Nancy Pelosi") < 0.62, q
    ppl = [{"name": n} for n in ("Adam Smith", "Nancy Pelosi", "Nancy Mace", "Josh Gottheimer")]
    assert [p["name"] for p in rank("nancy", ppl, lambda p: p["name"])] == ["Nancy Pelosi", "Nancy Mace"]
    assert rank("palosi", ppl, lambda p: p["name"])[0]["name"] == "Nancy Pelosi"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    return a


def test_find_api(app, monkeypatch):
    from stockskill.data import market_screen as MS, politicians as PL, search as SR
    monkeypatch.setitem(MS._STATE, "rows", [{"ticker": "NVDA", "name": "NVIDIA Corp", "mcap": 4e12},
                                            {"ticker": "NVO", "name": "Novo Nordisk", "mcap": 3e11},
                                            {"ticker": "PEP", "name": "PepsiCo", "mcap": 2e11}])
    monkeypatch.setattr(SR, "search_symbols", lambda q, limit=8: [])
    monkeypatch.setattr(PL, "directory", lambda cd=None: [
        {"id": "P000197", "name": "Nancy Pelosi", "party": "Democrat", "chamber": "House", "state": "CA"},
        {"id": "G000596", "name": "Marjorie Taylor Greene", "party": "Republican", "chamber": "House", "state": "GA"}])
    c = app.test_client()
    c.post("/auth/signup", json={"email": "a@example.com", "password": "a-long-password-1", "accept": True})
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json={"first_name": "A", "last_name": "L", "dob": "1990-01-01",
                                    "investor_type": "etf", "experience": "beginner"})
    c.post("/api/me/onboarded")
    d = c.get("/api/find?q=palosi").get_json()
    assert [p["name"] for p in d["politicians"]] == ["Nancy Pelosi"]
    d = c.get("/api/find?q=nv&kinds=stocks").get_json()
    assert [s["symbol"] for s in d["stocks"]] == ["NVDA", "NVO"] and "politicians" not in d
    d = c.get("/api/find?q=buffet").get_json()
    assert d["funds"][0]["fund"] == "Berkshire Hathaway"
    assert c.get("/api/find?q=").get_json() == {"ok": True, "q": ""}
