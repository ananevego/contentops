"""Vectorized trend scoring with an optional Numba acceleration path."""

from __future__ import annotations

import numpy as np

try:  # Importing ContentOps must still work when an optional accelerator is absent.
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in minimal deployments
    NUMBA_AVAILABLE = False

    def njit(*_args, **_kwargs):
        def decorator(function):
            return function

        return decorator

    prange = range


def _trend_scores_numpy(
    views: np.ndarray,
    likes: np.ndarray,
    comments: np.ndarray,
    shares: np.ndarray,
    age_hours: np.ndarray,
) -> np.ndarray:
    safe_views = np.maximum(views, 1.0)
    safe_age_hours = np.maximum(age_hours, 1.0)
    engagement = likes + comments * 2.0 + shares * 3.0
    return np.sqrt(safe_views) * (engagement / safe_views) / (1.0 + safe_age_hours / 24.0)


@njit(cache=True)
def _trend_scores_numba(
    views: np.ndarray,
    likes: np.ndarray,
    comments: np.ndarray,
    shares: np.ndarray,
    age_hours: np.ndarray,
) -> np.ndarray:
    result = np.empty(views.size, dtype=np.float64)
    for index in range(views.size):
        safe_views = max(views[index], 1.0)
        safe_age = max(age_hours[index], 1.0)
        engagement = likes[index] + comments[index] * 2.0 + shares[index] * 3.0
        result[index] = np.sqrt(safe_views) * (engagement / safe_views) / (1.0 + safe_age / 24.0)
    return result


@njit(cache=True, parallel=True)
def _trend_scores_numba_parallel(
    views: np.ndarray,
    likes: np.ndarray,
    comments: np.ndarray,
    shares: np.ndarray,
    age_hours: np.ndarray,
) -> np.ndarray:
    """Embarrassingly parallel numeric kernel; suitable for independent rows."""
    result = np.empty(views.size, dtype=np.float64)
    for index in prange(views.size):
        safe_views = max(views[index], 1.0)
        safe_age = max(age_hours[index], 1.0)
        engagement = likes[index] + comments[index] * 2.0 + shares[index] * 3.0
        result[index] = np.sqrt(safe_views) * (engagement / safe_views) / (1.0 + safe_age / 24.0)
    return result


def calculate_trend_scores(
    views: np.ndarray,
    likes: np.ndarray,
    comments: np.ndarray,
    shares: np.ndarray,
    age_hours: np.ndarray,
    *,
    use_numba: bool = True,
    parallel: bool = False,
) -> np.ndarray:
    """Calculates scores on numeric arrays; I/O and ORM stay outside Numba."""
    arrays = tuple(
        np.ascontiguousarray(values, dtype=np.float64)
        for values in (views, likes, comments, shares, age_hours)
    )
    if len({array.size for array in arrays}) != 1:
        raise ValueError("All metric arrays must have equal length")
    if use_numba and NUMBA_AVAILABLE:
        scores = _trend_scores_numba_parallel(*arrays) if parallel else _trend_scores_numba(*arrays)
    else:
        scores = _trend_scores_numpy(*arrays)
    return np.round(scores, 4)
