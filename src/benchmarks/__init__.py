"""Benchmark helpers: timing, medians, dispersion (real runs only)."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from typing import Any


def time_call(fn: Callable[[], Any], repeats: int = 5) -> dict[str, Any]:
    """Run fn N times, return seconds list + median + stdev."""
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    summary: dict[str, Any] = {
        "samples_s": samples,
        "median_s": statistics.median(samples),
        "repeats": repeats,
    }
    if len(samples) > 1:
        summary["stdev_s"] = statistics.stdev(samples)
    return summary
