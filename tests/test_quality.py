import pytest

from stockskill.valuation.quality import accruals_ratio, piotroski, quality_read

PREV = {"net_income": 80, "total_assets": 1000, "cfo": 90, "long_term_debt": 300,
        "current_assets": 400, "current_liabilities": 300, "shares": 100,
        "revenue": 900, "gross_profit": 360}
BETTER = {"net_income": 120, "total_assets": 1050, "cfo": 160, "long_term_debt": 280,
          "current_assets": 450, "current_liabilities": 300, "shares": 99,
          "revenue": 1000, "gross_profit": 420}
WORSE = {"net_income": -20, "total_assets": 1100, "cfo": -10, "long_term_debt": 400,
         "current_assets": 350, "current_liabilities": 320, "shares": 110,
         "revenue": 850, "gross_profit": 300}


def test_piotroski_all_pass_and_all_fail():
    assert piotroski(BETTER, PREV)["score"] == 9
    worse = piotroski(WORSE, PREV)
    assert worse["score"] == 1 and worse["max"] == 9        # only "cash flow > earnings" (-10 > -20)


def test_piotroski_skips_missing_items_instead_of_guessing():
    bank = dict(BETTER, current_assets=None, current_liabilities=None, gross_profit=None)
    f = piotroski(bank, dict(PREV, current_assets=None, current_liabilities=None, gross_profit=None))
    assert f["max"] == 7 and f["score"] == 7
    names = [c[0] for c in f["checks"] if c[1] is None]
    assert "Current ratio improved" in names and "Gross margin improved" in names


def test_accruals_ratio():
    assert accruals_ratio(BETTER, PREV) == pytest.approx((120 - 160) / 1025)
    assert accruals_ratio({"net_income": 1}) is None


def test_quality_read_labels():
    assert quality_read(BETTER, PREV)["tone"] == "up"
    assert quality_read(WORSE, PREV)["label"].startswith("Weak")
    hi_acc = dict(BETTER, net_income=300, cfo=50)
    assert "cash flow" in quality_read(hi_acc, PREV)["label"]
    assert quality_read({}, {})["label"].startswith("Not enough")
