"""Shared constants and validation for UCDP GED API sources.

Extracted from ucdp_annual.py so that candidate and .9 harvesters
can validate API envelopes without importing a sibling source module.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ENVELOPE_KEYS: set[str] = {"TotalCount", "TotalPages", "Result"}

UCDP_GED_API_BASE: str = "https://ucdpapi.pcr.uu.se/api/gedevents"


def validate_envelope(data: dict) -> None:
    """Validate the API response envelope structure."""
    missing = ENVELOPE_KEYS - set(data.keys())
    if missing:
        err_msg = (
            f"UCDP API response envelope missing keys: {missing}. "
            f"Available keys: {sorted(data.keys())}."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    if not isinstance(data["Result"], list):
        err_msg = (
            f"UCDP API 'Result' is {type(data['Result']).__name__}, "
            f"expected list."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
