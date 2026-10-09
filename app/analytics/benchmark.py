"""Small repeatable benchmark for the NumPy and Numba score implementations."""

from __future__ import annotations

import time

import numpy as np

from app.analytics.scoring import NUMBA_AVAILABLE, calculate_trend_scores


def main() -> None:
    rng = np.random.default_rng(42)
    arrays = (
        rng.integers(1, 1_000_000, 100_000),
        rng.integers(0, 100_000, 100_000),
        rng.integers(0, 10_000, 100_000),
        rng.integers(0, 10_000, 100_000),
        rng.uniform(1, 720, 100_000),
    )
    # Compile once; compilation is intentionally excluded from the timing.
    if NUMBA_AVAILABLE:
        calculate_trend_scores(*arrays, use_numba=True)
        calculate_trend_scores(*arrays, use_numba=True, parallel=True)
    for label, enabled, parallel in (
        ("NumPy", False, False),
        ("Numba", True, False),
        ("Numba parallel", True, True),
    ):
        if enabled and not NUMBA_AVAILABLE:
            print("Numba: unavailable (using the NumPy fallback in this environment)")
            continue
        started = time.perf_counter()
        calculate_trend_scores(*arrays, use_numba=enabled, parallel=parallel)
        print(f"{label}: {(time.perf_counter() - started) * 1000:.2f} ms")


if __name__ == "__main__":
    main()
