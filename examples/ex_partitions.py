#!/usr/bin/env python3
"""Verify: partition generation for training scripts.

Tests the standard partition pattern used by all pgm models:
    - calibration, validation, forecasting keys present
    - Each has train and test tuples
    - Fixed partitions match known values
    - Forecasting partition is dynamic (depends on current date)

VIEWS month_id encoding: month_id = (year - 1980) * 12 + month.
"""

from __future__ import annotations

import sys
from datetime import date


def _current_month_id() -> int:
    today = date.today()
    return (today.year - 1980) * 12 + today.month


def generate(steps: int = 36) -> dict:
    def forecasting_train_range():
        return (121, _current_month_id() - 1)

    def forecasting_test_range(steps):
        month_last = _current_month_id() - 1
        return (month_last + 1, month_last + 1 + steps)

    return {
        "calibration": {
            "train": (121, 444),
            "test": (445, 492),
        },
        "validation": {
            "train": (121, 492),
            "test": (493, 540),
        },
        "forecasting": {
            "train": forecasting_train_range(),
            "test": forecasting_test_range(steps=steps),
        },
    }


def main() -> int:
    partitions = generate()

    for key in ("calibration", "validation", "forecasting"):
        assert key in partitions, f"Missing partition key: {key}"
        assert "train" in partitions[key], f"{key} missing 'train'"
        assert "test" in partitions[key], f"{key} missing 'test'"

        train_start, train_end = partitions[key]["train"]
        test_start, test_end = partitions[key]["test"]

        assert isinstance(train_start, int) and isinstance(train_end, int), (
            f"{key}.train must be (int, int)"
        )
        assert isinstance(test_start, int) and isinstance(test_end, int), (
            f"{key}.test must be (int, int)"
        )
        assert train_start <= train_end, (
            f"{key}.train: start {train_start} > end {train_end}"
        )
        assert test_start <= test_end, (
            f"{key}.test: start {test_start} > end {test_end}"
        )

    cal = partitions["calibration"]
    assert cal["train"] == (121, 444), (
        f"calibration.train: expected (121, 444), got {cal['train']}"
    )
    assert cal["test"] == (445, 492), (
        f"calibration.test: expected (445, 492), got {cal['test']}"
    )

    val = partitions["validation"]
    assert val["train"] == (121, 492), (
        f"validation.train: expected (121, 492), got {val['train']}"
    )
    assert val["test"] == (493, 540), (
        f"validation.test: expected (493, 540), got {val['test']}"
    )

    fc = partitions["forecasting"]
    current = _current_month_id()
    assert fc["train"][0] == 121, (
        f"forecasting.train start: expected 121, got {fc['train'][0]}"
    )
    assert fc["train"][1] == current - 1, (
        f"forecasting.train end: expected {current - 1}, got {fc['train'][1]}"
    )
    assert fc["test"][0] == current, (
        f"forecasting.test start: expected {current}, got {fc['test'][0]}"
    )
    assert fc["test"][1] == current + 36, (
        f"forecasting.test end: expected {current + 36}, got {fc['test'][1]}"
    )

    print(f"PASS  ex_partitions — cal/val/fc OK, "
          f"forecasting dynamic (current={current})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL  ex_partitions — {e}")
        sys.exit(1)
