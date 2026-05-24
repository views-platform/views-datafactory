"""Temporal interpolation for epoch-based viewpoint builders."""

from __future__ import annotations

VALID_TEMPORAL_INTERPOLATIONS = ("step", "linear")


def interpolate_temporal(
    epoch_values: dict[int, float],
    *,
    strategy: str,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> list[float]:
    """Interpolate epoch values to monthly time steps.

    Strategies:
        step — hold last known epoch value until the next epoch.
        linear — linearly interpolate between adjacent epochs;
                 hold flat before the first and after the last.

    Args:
        epoch_values: Mapping of epoch year -> aggregated value.
        strategy: One of VALID_TEMPORAL_INTERPOLATIONS.
        start_year, start_month: First output month.
        end_year, end_month: Last output month (inclusive).

    Returns:
        List of float values, one per month.
    """
    n_months = (
        (end_year - start_year) * 12
        + (end_month - start_month)
        + 1
    )

    sorted_epochs = sorted(epoch_values.keys())

    if strategy == "step":
        return interp_step(
            n_months, sorted_epochs, epoch_values,
            start_year, start_month,
        )
    if strategy == "linear":
        return interp_linear(
            n_months, sorted_epochs, epoch_values,
            start_year, start_month,
        )
    msg = (
        f"Unknown interpolation strategy '{strategy}'. "
        f"Valid: {VALID_TEMPORAL_INTERPOLATIONS}"
    )
    raise ValueError(msg)


def interp_step(
    n_months: int,
    sorted_epochs: list[int],
    epoch_values: dict[int, float],
    start_year: int,
    start_month: int,
) -> list[float]:
    result: list[float] = []
    for i in range(n_months):
        year = start_year + (start_month - 1 + i) // 12
        value = 0.0
        for ep in sorted_epochs:
            if ep <= year:
                value = epoch_values[ep]
            else:
                break
        result.append(value)
    return result


def interp_linear(
    n_months: int,
    sorted_epochs: list[int],
    epoch_values: dict[int, float],
    start_year: int,
    start_month: int,
) -> list[float]:
    result: list[float] = []
    for i in range(n_months):
        year = start_year + (start_month - 1 + i) // 12
        month = (start_month - 1 + i) % 12 + 1
        t = year + (month - 1) / 12.0

        if not sorted_epochs or t < sorted_epochs[0]:
            result.append(0.0)
            continue

        if t >= sorted_epochs[-1]:
            result.append(epoch_values[sorted_epochs[-1]])
            continue

        for j in range(len(sorted_epochs) - 1):
            ep_lo = sorted_epochs[j]
            ep_hi = sorted_epochs[j + 1]
            if ep_lo <= t < ep_hi:
                frac = (t - ep_lo) / (ep_hi - ep_lo)
                val = (
                    epoch_values[ep_lo] * (1 - frac)
                    + epoch_values[ep_hi] * frac
                )
                result.append(val)
                break

    return result
