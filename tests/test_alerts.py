import json

from stockskill.alerts import auto_alerts, custom_alerts, all_alerts, load_custom_alerts
from stockskill.watchlist.row import TickerRow


def row(ticker="X", price=100.0, day=0.0, flags=None, signal="HOLD", rsi=50.0, vol_spike=False):
    return TickerRow(ticker=ticker, price=price, changes={"1d": day},
                     flags=set(flags or ()), signal=signal, rsi=rsi, vol_spike=vol_spike)


def test_auto_alerts_from_flags_and_signal():
    r = row("AAPL", day=0.12, flags={"near_52w_high", "surge", "squeeze"}, signal="BUY")
    kinds = {a.kind for a in auto_alerts([r])}
    assert {"52w_high", "surge", "squeeze", "signal_buy"} <= kinds


def test_auto_alerts_signal_variants():
    assert auto_alerts([row(signal="SHORT")])[0].kind == "signal_short"
    assert auto_alerts([row(signal="HOLD")]) == []          # HOLD isn't alerted
    assert auto_alerts([row(price=None)]) == []             # no data


def test_custom_alerts():
    r = row("NVDA", price=150.0, day=0.06, rsi=25.0, signal="BUY")
    defs = [
        {"ticker": "NVDA", "condition": "price_above", "value": 100},
        {"ticker": "NVDA", "condition": "price_below", "value": 100},   # not met
        {"ticker": "NVDA", "condition": "day_change_above", "value": 5},  # 6% > 5%
        {"ticker": "NVDA", "condition": "rsi_oversold"},
        {"ticker": "NVDA", "condition": "buy"},
        {"ticker": "MSFT", "condition": "buy"},                          # no such row
    ]
    got = {a.kind for a in custom_alerts([r], defs)}
    assert got == {"custom:price_above", "custom:day_change_above",
                   "custom:rsi_oversold", "custom:buy"}


def test_all_alerts_custom_first():
    r = row("T", price=50.0, signal="BUY")
    defs = [{"ticker": "T", "condition": "price_below", "value": 100}]
    alerts = all_alerts([r], defs)
    assert alerts[0].kind == "custom:price_below"           # custom prioritized
    assert any(a.kind == "signal_buy" for a in alerts)


def test_load_custom_alerts(tmp_path):
    f = tmp_path / "alerts.json"
    f.write_text(json.dumps([{"ticker": "AAPL", "condition": "price_above", "value": 200}]))
    defs = load_custom_alerts(str(f))
    assert defs[0]["ticker"] == "AAPL"
    assert load_custom_alerts(str(tmp_path / "missing.json")) == []
