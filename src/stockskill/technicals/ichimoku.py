"""Ichimoku Cloud: conversion/base lines, the projected cloud, and a signal."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


@dataclass
class Ichimoku:
    tenkan: float          # conversion line (9)
    kijun: float           # base line (26)
    senkou_a: float        # leading span A at the current bar (cloud edge)
    senkou_b: float        # leading span B at the current bar (cloud edge)
    price_vs_cloud: str    # "above" (bullish) | "below" (bearish) | "in_cloud"
    tk_state: str          # "bull" (tenkan>=kijun) | "bear"


def ichimoku(highs, lows, closes, tenkan_p: int = 9, kijun_p: int = 26,
             senkou_b_p: int = 52) -> Ichimoku | None:
    """Ichimoku snapshot. The cloud at the current bar is the leading spans
    projected forward ``kijun_p`` bars, i.e. computed ``kijun_p`` bars ago."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) < senkou_b_p + kijun_p:
        return None

    def mid(period: int) -> pd.Series:
        return (h.rolling(period).max() + l.rolling(period).min()) / 2.0

    conv = mid(tenkan_p)
    base = mid(kijun_p)
    span_a = ((conv + base) / 2.0).shift(kijun_p)   # cloud edge at current bar
    span_b = mid(senkou_b_p).shift(kijun_p)

    price = c.iloc[-1]
    a, b = span_a.iloc[-1], span_b.iloc[-1]
    if pd.isna(a) or pd.isna(b):
        return None
    top, bottom = max(a, b), min(a, b)
    if price > top:
        pvc = "above"
    elif price < bottom:
        pvc = "below"
    else:
        pvc = "in_cloud"
    tk = "bull" if conv.iloc[-1] >= base.iloc[-1] else "bear"
    return Ichimoku(float(conv.iloc[-1]), float(base.iloc[-1]), float(a), float(b),
                    pvc, tk)
