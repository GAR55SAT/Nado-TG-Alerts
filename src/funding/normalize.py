from __future__ import annotations

SECONDS_PER_YEAR = 365 * 24 * 3600


def rate_to_apr_pct(rate: float, interval_seconds: float) -> float:
    """Convert per-period funding rate (decimal) to simple annual APR %."""
    if interval_seconds <= 0:
        return 0.0
    periods = SECONDS_PER_YEAR / interval_seconds
    return rate * periods * 100


def variational_rate_to_apr_pct(rate: float) -> float:
    """Variational returns funding as decimal; multiply by 100 for APR %."""
    return rate * 100
