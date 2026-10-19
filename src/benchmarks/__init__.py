"""Benchmark helpers: timing, medians, dispersion (real runs only).

Every number published in the README comes from these helpers, so the rules
are simple and explicit: run the callable ``repeats`` times, return the raw
samples, the median and the standard deviation. The median is used because a
single cold-cache outlier would skew a mean.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from typing import Any


def time_call(fn: Callable[[], Any], repeats: int = 5) -> dict[str, Any]:
    """Run ``fn`` N times, return seconds list + median + stdev.

    ``time.perf_counter`` is a monotonic high-resolution clock, immune to system
    clock changes. ``stdev`` is only computed when there is more than one
    sample (statistics.stdev requires at least two data points).
    """
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
