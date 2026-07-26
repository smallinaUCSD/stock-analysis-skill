from datetime import datetime

from stockskill.marketclock import market_status


def _et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)  # naive -> treated as ET


def test_regular_session():
    # 2026-07-22 is a Wednesday
    assert market_status(_et(2026, 7, 22, 10, 0)).label == "open"
    assert market_status(_et(2026, 7, 22, 10, 0)).is_open is True


def test_open_and_close_boundaries():
    assert market_status(_et(2026, 7, 22, 9, 30)).label == "open"     # exactly open
    assert market_status(_et(2026, 7, 22, 16, 0)).label == "after-hours"  # exactly close
    assert market_status(_et(2026, 7, 22, 15, 59)).is_open is True


def test_pre_and_after():
    assert market_status(_et(2026, 7, 22, 8, 0)).label == "pre-market"
    assert market_status(_et(2026, 7, 22, 18, 0)).label == "after-hours"
    assert market_status(_et(2026, 7, 22, 22, 0)).label == "closed"
    assert market_status(_et(2026, 7, 22, 2, 0)).label == "closed"


def test_weekend():
    # 2026-07-25 is a Saturday, 2026-07-26 a Sunday
    assert market_status(_et(2026, 7, 25, 10, 0)).label == "weekend"
    assert market_status(_et(2026, 7, 26, 10, 0)).label == "weekend"
    assert market_status(_et(2026, 7, 25, 10, 0)).is_open is False
