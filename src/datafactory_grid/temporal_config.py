"""Temporal configuration for the PRIO-GRID spatiotemporal backbone."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TemporalConfig:
    """Configuration for the temporal dimension of a spatiotemporal grid.

    Stores start/end as plain integers (human-readable, serialisable).
    Properties derive numpy datetime64[M] values and step counts.

    The backbone representation is numpy.datetime64[M] -- standard,
    resolution-aware, and free of arbitrary epoch conventions.

    Validation uses month ordinals (year * 12 + month) solely to check
    that start is not after end. This is NOT the VIEWS month_id
    convention (which uses a 1980 epoch) -- see temporal_generator.py
    for VIEWS month_id conversion.
    """

    start_year: int = 1989
    start_month: int = 1
    end_year: int = 2024
    end_month: int = 12

    def __post_init__(self) -> None:
        if self.start_year < 1:
            raise ValueError(f"Year must be >= 1, got start_year={self.start_year}")
        if self.end_year < 1:
            raise ValueError(f"Year must be >= 1, got end_year={self.end_year}")
        if not (1 <= self.start_month <= 12):
            raise ValueError(
                f"Month must be in [1, 12], got start_month={self.start_month}"
            )
        if not (1 <= self.end_month <= 12):
            raise ValueError(
                f"Month must be in [1, 12], got end_month={self.end_month}"
            )
        # Ordinal comparison: year * 12 + month gives a monotonic ordering
        # for start-before-end validation. Not related to VIEWS month_id.
        start_ordinal = self.start_year * 12 + self.start_month
        end_ordinal = self.end_year * 12 + self.end_month
        if start_ordinal > end_ordinal:
            raise ValueError(
                f"start ({self.start_year}-{self.start_month:02d}) is after "
                f"end ({self.end_year}-{self.end_month:02d})"
            )

    @property
    def start_dt(self) -> np.datetime64:
        """Start as numpy datetime64[M]."""
        return np.datetime64(f"{self.start_year:04d}-{self.start_month:02d}", "M")

    @property
    def end_dt(self) -> np.datetime64:
        """End as numpy datetime64[M]."""
        return np.datetime64(f"{self.end_year:04d}-{self.end_month:02d}", "M")

    @property
    def n_steps(self) -> int:
        """Total number of monthly time steps (inclusive)."""
        return (
            (self.end_year - self.start_year) * 12
            + (self.end_month - self.start_month)
            + 1
        )
