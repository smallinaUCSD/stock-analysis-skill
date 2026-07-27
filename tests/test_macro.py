from datetime import date
from stockskill.data.macro import next_fomc, fomc_alert, scan_headlines


def test_next_fomc_picks_soonest_future():
    assert next_fomc(date(2026, 7, 27)) == ("2026-07-29", 2)
    assert next_fomc(date(2026, 7, 29)) == ("2026-07-29", 0)
    assert next_fomc(date(2026, 7, 30)) == ("2026-09-16", 48)


def test_next_fomc_none_after_calendar():
    assert next_fomc(date(2027, 1, 1)) is None


def test_fomc_alert_only_within_window():
    a = fomc_alert(date(2026, 7, 27))
    assert a and "in 2d" in a.message and a.kind == "fed"
    assert fomc_alert(date(2026, 7, 30)) is None          # 48 days out
    assert "today" in fomc_alert(date(2026, 7, 29)).message


def test_scan_headlines_flags_and_dedupes():
    out = scan_headlines([
        "Amazon announces layoffs of 14,000 workers",
        "Fed holds rates steady after FOMC meeting",
        "CPI inflation cools to 2.1%",
        "Sunny skies expected this weekend",
        "Amazon announces layoffs of 14,000 workers",   # dup
    ])
    kinds = [a.kind for a in out]
    assert "layoffs" in kinds and "fed" in kinds and "inflation" in kinds
    assert len(out) == 3   # weather ignored, dup collapsed


def test_scan_headlines_respects_limit():
    titles = [f"layoffs at company {i}" for i in range(10)]
    assert len(scan_headlines(titles, limit=3)) == 3
