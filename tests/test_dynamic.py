from stockskill.watchlist.dynamic import (
    Candidate, build_smart_universe, write_sectioned,
)
from stockskill.watchlist import parse_tickers


def _cands():
    return [
        Candidate("AAPL", growth=0.50, mos=None),      # pinned
        Candidate("HIGROW", growth=0.90, mos=None),
        Candidate("MIDGROW", growth=0.30, mos=None),
        Candidate("CHEAP", growth=None, mos=0.40),      # most undervalued
        Candidate("CHEAP2", growth=None, mos=0.20),
        Candidate("EXPENSIVE", growth=None, mos=-0.30), # not undervalued -> excluded
        Candidate("NVDA", growth=0.55, mos=None),       # has a leveraged variant
    ]


def test_build_smart_universe():
    u = build_smart_universe(_cands(), ["XLK", "XLF", "XLE"], pinned=["AAPL"],
                             n_growth=2, n_value=1, n_sectors=2)
    s = u["sections"]
    assert s["PINNED"] == ["AAPL"]
    assert s["GROWTH"] == ["HIGROW", "NVDA"]            # top-2 growth, AAPL excluded (pinned)
    assert s["VALUE"] == ["CHEAP"]                       # top undervalued
    assert "TECL" in s["SECTOR"] and "FAS" in s["SECTOR"]  # XLK/XLF leveraged
    assert s["LEVERAGED"] == ["AAPU", "NVDU"]           # AAPL(pinned)+NVDA(growth) have variants
    assert "EXPENSIVE" not in u["all"]                   # negative MoS, no growth


def test_pinned_never_rotated_out():
    # AAPL scores low growth but is pinned -> always present, never a growth pick.
    u = build_smart_universe(_cands(), [], pinned=["AAPL"], n_growth=2, n_value=0)
    assert "AAPL" in u["sections"]["PINNED"]
    assert "AAPL" not in u["sections"]["GROWTH"]


def test_all_deduped():
    u = build_smart_universe(_cands(), ["XLK"], pinned=["AAPL"], n_growth=3, n_value=2)
    assert len(u["all"]) == len(set(u["all"]))


def test_write_and_parse_roundtrip(tmp_path):
    u = build_smart_universe(_cands(), ["XLK"], pinned=["AAPL"], n_growth=2, n_value=1)
    f = tmp_path / "smart.csv"
    write_sectioned(str(f), u)
    parsed = parse_tickers(str(f))
    assert "PINNED" in parsed["sections"] and "GROWTH" in parsed["sections"]
    assert set(u["all"]) == set(parsed["all"])
