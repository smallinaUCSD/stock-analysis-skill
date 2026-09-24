from datetime import date

from stockskill.signals.insiders import classify_trade, summarize


def _t(name, iso, code="P", shares=1000, price=50.0):
    return {"name": name, "date": iso, "code": code, "shares": shares, "price": price}


HIST = [
    # Routine: buys every January
    _t("ROUTINE", "2023-01-19"), _t("ROUTINE", "2024-01-18"), _t("ROUTINE", "2025-01-21"),
    # Opportunistic: traded each prior year, but in other months
    _t("OPP", "2023-05-02", "S"), _t("OPP", "2024-08-10", "S"), _t("OPP", "2025-03-03", "S"),
    # New insider: no history
    # Mechanical codes never count
    _t("ROUTINE", "2026-01-05", "A"), _t("OPP", "2026-01-06", "M"),
]


def test_classify_routine_opportunistic_unclassified():
    assert classify_trade(_t("ROUTINE", "2026-01-20"), HIST) == "routine"
    assert classify_trade(_t("OPP", "2026-01-20"), HIST) == "opportunistic"
    assert classify_trade(_t("NEWBIE", "2026-01-20"), HIST) == "unclassified"


def test_summarize_labels_opportunistic_buying():
    trades = HIST + [_t("ROUTINE", "2026-01-20"), _t("OPP", "2026-01-22", shares=2000, price=40.0),
                     _t("NEWBIE", "2026-01-25", "S", 500, 60.0)]
    s = summarize(trades, today=date(2026, 2, 15))
    assert s["buys"] == 2 and s["opportunistic_buys"] == 1 and s["routine_buys"] == 1
    assert s["buy_value"] == 1000 * 50 + 2000 * 40
    assert s["sells"] == 1 and s["sell_value"] == 30000
    assert s["label"].startswith("Opportunistic insider buying") and s["tone"] == "up"
    assert s["buyers"] == ["OPP", "ROUTINE"]


def test_summarize_ignores_old_and_mechanical_trades():
    s = summarize(HIST, today=date(2026, 2, 15))
    assert s["buys"] == 0 and s["sells"] == 0
    assert s["label"] == "No open-market insider trades"
