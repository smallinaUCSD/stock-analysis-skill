"""Virtue of Complexity — Kelly, Malamud & Zhou (2024), Journal of Finance.

Predict the MARKET's next-month return with a deliberately *complex* model: a
ridge regression over many nonlinear **random features** of a few predictors,
with far more parameters than observations. KMZ show that out-of-sample
predictability and timing Sharpe tend to *rise* with complexity (given ridge
shrinkage) — the opposite of the usual "keep it simple".

EXPERIMENTAL and DEBATED. Market timing is hard and the result is contested, so
this runs an honest **expanding-window out-of-sample** test and reports what it
actually finds (often near zero) rather than asserting an edge. Not a signal to
obey. The predictors here are technical features of the index's own history
(return lags, moving-average ratios, realized vol) — a self-contained proxy for
the paper's macro predictor set. Base features are scaled on the full sample
(a minor, disclosed simplification); the regression fit itself has no look-ahead.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoCResult:
    prediction: float          # latest next-month expected market return
    signal: str                # risk-on | risk-off | neutral
    oos_r2: float              # out-of-sample R^2 vs a zero forecast
    timing_sharpe: float       # annualized Sharpe of the timing strategy (OOS)
    buyhold_sharpe: float
    n_features: int
    n_test: int


def _base_features(r, n_lags: int = 12):
    """From monthly returns r, build predictors known at month t and target r[t+1]."""
    import numpy as np
    M = len(r)
    start = max(n_lags, 12)
    X, y = [], []
    for t in range(start, M - 1):
        lags = r[t - n_lags + 1:t + 1][::-1]
        feat = np.concatenate([lags, [r[t - 2:t + 1].mean(), r[t - 11:t + 1].mean(),
                                      r[t - 2:t + 1].std(), r[t - 11:t + 1].std()]])
        X.append(feat)
        y.append(r[t + 1])
    return np.asarray(X, float), np.asarray(y, float)


def _ridge_predict(Ztr, ytr, Zte, ridge):
    import numpy as np
    n, p = Ztr.shape
    A = Ztr.T @ Ztr / n + ridge * np.eye(p)
    beta = np.linalg.solve(A, Ztr.T @ ytr / n)
    return Zte @ beta


def voc_timing(closes, n_features: int = 1000, ridge: float = 1e-2, gamma: float = 0.3,
               seed: int = 0, step: int = 21, min_train: int = 24) -> VoCResult | None:
    """Expanding-window OOS market-return prediction via complex random features."""
    import numpy as np

    px = np.asarray(closes[::step], float)
    px = px[px > 0]
    if len(px) < min_train + 30:
        return None
    r = np.diff(px) / px[:-1]
    X, y = _base_features(r)
    if len(y) < min_train + 6:
        return None

    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Xs = (X - mu) / sd

    rng = np.random.default_rng(seed)                 # fixed random feature map
    W = rng.normal(0.0, gamma, size=(Xs.shape[1], n_features))
    b = rng.uniform(0.0, 2 * np.pi, size=n_features)
    Z = np.sqrt(2.0 / n_features) * np.cos(Xs @ W + b)

    preds, actuals = [], []
    for t in range(min_train, len(y)):
        preds.append(float(_ridge_predict(Z[:t], y[:t], Z[t:t + 1], ridge)[0]))
        actuals.append(float(y[t]))
    preds, actuals = np.asarray(preds), np.asarray(actuals)

    ss_tot = float(np.sum(actuals ** 2))
    oos_r2 = 1.0 - float(np.sum((actuals - preds) ** 2)) / ss_tot if ss_tot > 0 else 0.0

    def sharpe(x):
        return float(x.mean() / x.std() * np.sqrt(12)) if x.std() > 0 else 0.0

    strat = np.sign(preds) * actuals                  # scale exposure by the forecast sign
    cur = preds[-1]
    return VoCResult(
        prediction=float(cur),
        signal="risk-on" if cur > 0 else ("risk-off" if cur < 0 else "neutral"),
        oos_r2=oos_r2, timing_sharpe=sharpe(strat), buyhold_sharpe=sharpe(actuals),
        n_features=n_features, n_test=len(preds))
