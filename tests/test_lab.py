"""Portfolio lab: Markowitz / Black-Litterman, Brownian-motion paths, and
ideas (stocks to add, funds and politicians to follow). Synthetic data only."""

import numpy as np
import pytest

from stockskill.lab import optimize as O, paths as P, recommend as RC


def _returns(T=756, seed=1):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.01, T)
    return np.column_stack([f + rng.normal(0.0008, 0.012, T), 0.5 * f + rng.normal(0.0003, 0.008, T),
                            rng.normal(0.0002, 0.005, T), f + rng.normal(0.0001, 0.015, T)])


def test_projection_respects_budget_and_cap():
    w = O.project(np.array([3.0, 1.0, -2.0, 0.5]), 0.4)
    assert abs(w.sum() - 1) < 1e-6 and w.max() <= 0.4 + 1e-9 and w.min() >= 0


def test_frontier_mixes():
    mu, S = O.estimate(_returns())
    fr = O.frontier(mu, S, cap=0.5)
    ms, mv = fr["max_sharpe"], fr["min_var"]
    for p in (ms, mv):
        assert abs(p["w"].sum() - 1) < 1e-6 and p["w"].max() <= 0.5 + 1e-6
    eq = np.full(4, 0.25)
    assert mv["vol"] <= float(np.sqrt(eq @ S @ eq)) + 1e-9            # lowest-risk beats equal weights on risk
    assert ms["sharpe"] >= O.stats(eq, mu, S, 0.04)["sharpe"] - 1e-9   # best risk-adjusted beats equal on Sharpe
    vols = [p["vol"] for p in fr["curve"]]
    assert vols == sorted(vols)


def test_black_litterman():
    mu, S = O.estimate(_returns())
    w = np.array([0.4, 0.3, 0.2, 0.1])
    pi, post = O.black_litterman(S, w, {})
    assert np.allclose(pi, post) and np.allclose(pi, 2.5 * S @ w)
    _, post2 = O.black_litterman(S, w, {2: (0.30, 0.6)})
    assert post2[2] > pi[2] + 0.05                                     # a bullish view lifts that stock
    views = O.analyst_views(["A", "B", "C"], {"A": {"price": 100, "target": 200, "analysts": 30},
                                              "B": {"price": 50, "target": 45, "analysts": 2}})
    assert views[0] == (0.4, 0.6) and views[1][0] == pytest.approx(-0.1) and 2 not in views


def test_brownian_paths():
    closes = list(100 * np.exp(np.cumsum(_returns()[:, 0])))
    f = P.one(closes, days=126, n=1500)
    assert f["p5_end"] < f["bands"]["p50"][-1] < f["p95_end"] and 0 < f["prob_up"] < 1
    assert len(f["samples"]) == 8 and len(f["t"]) == len(f["bands"]["p50"])
    pf = P.portfolio(_returns(), np.array([0.25, 0.25, 0.25, 0.25]), days=63, n=1000)
    assert pf["start"] == 10_000 and pf["p5_end"] < pf["p95_end"]


UNIVERSE = [
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "Technology", "industry": "Semiconductors", "mcap": 4e12, "price": 1,
     "rev_growth": 0.9, "net_margin": 0.5, "roe": 0.9, "fcf_yield": 0.02, "pe": 45},
    {"ticker": "AMD", "name": "AMD", "sector": "Technology", "industry": "Semiconductors", "mcap": 3e11, "price": 1,
     "rev_growth": 0.3, "net_margin": 0.1, "roe": 0.05, "fcf_yield": 0.02, "pe": 90},
    {"ticker": "AVGO", "name": "Broadcom", "sector": "Technology", "industry": "Semiconductors", "mcap": 1.5e12, "price": 1,
     "rev_growth": 0.4, "net_margin": 0.3, "roe": 0.3, "fcf_yield": 0.03, "pe": 35},
    {"ticker": "KO", "name": "Coca-Cola", "sector": "Consumer Defensive", "industry": "Beverages", "mcap": 3e11, "price": 1,
     "rev_growth": 0.03, "net_margin": 0.25, "roe": 0.4, "fcf_yield": 0.04, "pe": 24},
    {"ticker": "XOM", "name": "Exxon", "sector": "Energy", "industry": "Oil & Gas", "mcap": 5e11, "price": 1,
     "rev_growth": -0.05, "net_margin": 0.1, "roe": 0.15, "fcf_yield": 0.07, "pe": 13},
    {"ticker": "TINY", "name": "Tiny", "sector": "Technology", "industry": "Semiconductors", "mcap": 1e8, "price": 1},
]


def test_stock_ideas_similar_and_diversify():
    sim = RC.stocks(["NVDA", "AMD"], UNIVERSE, style="similar", fund_holders={"AVGO": 3}, politician_buys={"AVGO": 2})
    assert sim[0]["ticker"] == "AVGO" and "NVDA" not in [x["ticker"] for x in sim]
    assert any("Same industry as" in r for r in sim[0]["reasons"]) and any("tracked funds" in r for r in sim[0]["reasons"])
    assert "TINY" not in [x["ticker"] for x in sim]                                  # too small
    div = RC.stocks(["NVDA", "AMD"], UNIVERSE, style="diversify", corr=lambda t: {"KO": 0.1, "XOM": 0.2}.get(t, 0.9))
    assert div[0]["ticker"] in ("KO", "XOM") and any("don't hold" in r for r in div[0]["reasons"])


def test_people_to_follow():
    reps = [{"cik": 1, "fund": "Fund A", "manager": "A", "holdings": [{"ticker": "NVDA", "weight": 0.3}, {"ticker": "KO", "weight": 0.1}]},
            {"cik": 2, "fund": "Fund B", "manager": "B", "holdings": [{"ticker": "XOM", "weight": 0.5}]}]
    f = RC.funds_to_follow(["NVDA", "AMD"], reps)
    assert [x["cik"] for x in f] == [1] and "30%" in f[0]["reason"]
    trades = [{"ticker": "NVDA", "member": "Nancy Pelosi"}, {"ticker": "AMD", "member": "Nancy Pelosi"},
              {"ticker": "KO", "member": "Someone"}]
    p = RC.politicians_to_follow(["NVDA", "AMD"], trades, lambda t: t["member"].lower().replace(" ", "-"))
    assert p[0]["id"] == "nancy-pelosi" and p[0]["stocks"] == 2 and len(p) == 1


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    from stockskill.watchlist.pipeline import TickerData
    app = create_app(tickers_path=str(tk), public=True)
    app.config["ACCT"]["board"] = None
    rng = np.random.default_rng(3)
    dates = [f"2023-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)][:300]

    class Snap:
        def __init__(self, t):
            self.price, self.target_mean, self.analyst_count, self.market_cap = 100.0, 120.0, 20, 1e11
            self.name, self.sector = t, "Technology"

    def fake_fetch(t, period=None, cache_dir=None, ttl=None):
        c = list(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, 300))))
        return TickerData(t, {"dates": dates, "open": c, "high": c, "low": c, "close": c, "volume": [1] * 300}, Snap(t))
    import stockskill.watchlist.pipeline as PL
    monkeypatch.setattr(PL, "fetch_one", fake_fetch)
    c = app.test_client()
    c.post("/auth/signup", json={"email": "a@example.com", "password": "a-long-password-1", "accept": True})
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json={"first_name": "A", "last_name": "L", "dob": "1990-01-01",
                                    "investor_type": "etf", "experience": "beginner"})
    c.post("/api/me/onboarded")
    return c


def test_lab_endpoints(client):
    assert client.get("/lab").status_code == 200
    d = client.get("/api/lab/optimize?t=AAA,BBB,CCC&cap=0.5").get_json()
    assert d["ok"] and d["tickers"] == ["AAA", "BBB", "CCC"] and d["bl_views"] == 3
    for k in ("max_sharpe", "min_var", "black_litterman", "market", "equal"):
        assert abs(sum(d["portfolios"][k]["w"]) - 1) < 1e-3, k
    assert client.get("/api/lab/optimize?t=AAA").status_code == 400
    s = client.get("/api/lab/simulate?t=AAA&days=63").get_json()
    assert s["ok"] and s["kind"] == "stock" and len(s["samples"]) == 8
    w = ",".join(str(x) for x in d["portfolios"]["max_sharpe"]["w"])
    p = client.get(f"/api/lab/simulate?t=AAA,BBB,CCC&days=63&w={w}").get_json()
    assert p["ok"] and p["kind"] == "portfolio"
