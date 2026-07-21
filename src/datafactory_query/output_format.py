"""Public output-format contract for ``load_dataset`` (ADR-050).

This module is the importable projection of the consumer contract
whose canonical, language-neutral form lives at
``tests/fixtures/feature_frame_contract/contract.json``. A test
asserts the two never drift (three-way agreement with the internal
``_VALID_FORMATS`` alias).

Stability promise (ADR-050):
- The meaning of existing members never changes.
- Removing or renaming a member is a MAJOR version event for the
  package and for CONTRACT_VERSION.
- Adding a member is a MINOR event for both.
- CONTRACT_VERSION is independent of the package version and
  changes only for contract-affecting changes (vocabulary, on-disk
  layout, identifier/dtype semantics).

Consumers who cannot install the views-datafactory wheel should
read contract.json instead — both adoption paths are first-class.
"""

from __future__ import annotations

from enum import StrEnum

CONTRACT_VERSION: str = "1.0.0"


class OutputFormat(StrEnum):
    """Valid ``load_dataset(output_format=...)`` values.

    Each member names what ``load_dataset`` returns:

    - ``FEATURE_FRAME``: a ``views_frames.FeatureFrame`` — float32
      values of shape (N, F, S), index identifiers ``time`` (VIEWS
      month_id, epoch 1980) and ``unit`` (``priogrid_id``).
    - ``DATAFRAME``: a ``pandas.DataFrame`` with a
      ``(month_id, priogrid_id)`` MultiIndex, one column per
      feature.
    - ``COUNTRY_MONTH``: a ``pandas.DataFrame`` with a
      ``(month_id, country_id)`` MultiIndex — grid cells summed
      per country for declared-extensive features (ADR-048).
    """

    FEATURE_FRAME = "feature_frame"
    DATAFRAME = "dataframe"
    COUNTRY_MONTH = "country_month"


def is_valid_output_format(value: str) -> bool:
    """True when *value* is a valid ``output_format`` string."""
    return value in OutputFormat._value2member_map_
