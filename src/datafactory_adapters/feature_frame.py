"""FeatureFrame — canonical input-side transport object.

Analogous to PredictionFrame (model output) and EvaluationFrame
(evaluation input) from the VIEWS pipeline. Wraps spatiotemporal
feature data with identifiers and metadata.

Designed to be extractable: when moved to views-pipeline-core
or a micro-service, only numpy comes with it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

REQUIRED_IDENTIFIERS: set[str] = {"time", "unit"}


class FeatureFrame:
    """Canonical transport object for spatiotemporal features.

    Encapsulates features and their spatiotemporal identifiers,
    serving as the universal input format for models and
    evaluation pipelines.

    Attributes:
        y_features: Feature array of shape (N, D) or (N, D, S)
            where N = observations, D = features, S = samples
            (for uncertainty representation).
        identifiers: Dict mapping keys to 1D arrays of length N.
            Must include 'time' (month_id) and 'unit' (pgid).
        feature_names: List of D feature name strings.
        metadata: Optional dict of provenance, config, etc.
    """

    def __init__(
        self,
        y_features: np.ndarray,
        identifiers: dict[str, np.ndarray],
        feature_names: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._validate(y_features, identifiers, feature_names)
        self.y_features = np.asarray(
            y_features, dtype=np.float32
        )
        self.identifiers = identifiers
        self.feature_names = list(feature_names)
        self.metadata = metadata or {}

    def _validate(
        self,
        y_features: np.ndarray,
        identifiers: dict[str, np.ndarray],
        feature_names: list[str],
    ) -> None:
        # Shape: must be 2D (N, D) or 3D (N, D, S)
        if y_features.ndim not in (2, 3):
            err_msg = (
                f"y_features must be 2D (N, D) or "
                f"3D (N, D, S), got {y_features.ndim}D"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        n_rows = y_features.shape[0]
        n_features = y_features.shape[1]

        if n_rows < 1:
            err_msg = "y_features must have at least 1 row"
            logger.error(err_msg)
            raise ValueError(err_msg)

        # Feature names must match D
        if len(feature_names) != n_features:
            err_msg = (
                f"feature_names length ({len(feature_names)}) "
                f"must match y_features columns ({n_features})"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        # Required identifiers
        missing = REQUIRED_IDENTIFIERS - set(identifiers)
        if missing:
            err_msg = (
                f"Missing required identifiers: "
                f"{sorted(missing)}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        # Identifier lengths must match N
        for key, arr in identifiers.items():
            if len(arr) != n_rows:
                err_msg = (
                    f"Identifier '{key}' length "
                    f"({len(arr)}) must match "
                    f"y_features rows ({n_rows})"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)

    @property
    def n_rows(self) -> int:
        """Number of observations (N)."""
        return self.y_features.shape[0]

    @property
    def n_features(self) -> int:
        """Number of features (D)."""
        return self.y_features.shape[1]

    @property
    def sample_count(self) -> int:
        """Number of samples per observation (S).

        Returns 1 for deterministic (2D) features.
        """
        if self.y_features.ndim == 3:
            return self.y_features.shape[2]
        return 1

    @property
    def is_sample(self) -> bool:
        """True if features carry uncertainty samples."""
        return self.y_features.ndim == 3

    def save(self, directory: Path) -> None:
        """Write to disk as y_features.npy + identifiers.npz.

        Args:
            directory: Output directory (created if needed).
        """
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "y_features.npy", self.y_features)
        np.savez(
            directory / "identifiers.npz",
            **self.identifiers,
        )
        import json

        (directory / "feature_names.json").write_text(
            json.dumps(self.feature_names)
        )
        if self.metadata:
            (directory / "metadata.json").write_text(
                json.dumps(
                    self.metadata, sort_keys=True, default=str
                )
            )

    @classmethod
    def from_grid(
        cls,
        grid: np.ndarray,
        pgids: np.ndarray,
        time_steps: np.ndarray,
        feature_names: list[str],
        **kwargs: Any,
    ) -> FeatureFrame:
        """Construct from a [T, H, W, C] grid array.

        Convenience classmethod that wraps grid_to_feature_frame.
        Keeps the flattening convention knowledge in the class.

        Args:
            grid: Grid array [T, H, W, C].
            pgids: Cell IDs [H, W].
            time_steps: Time array [T] datetime64[M].
            feature_names: C feature names.
            **kwargs: Passed to grid_to_feature_frame
                (land_pgids, month_id_epoch, metadata).
        """
        from datafactory_adapters.grid_to_dataframe import (
            grid_to_feature_frame,
        )

        return grid_to_feature_frame(
            grid, pgids, time_steps, feature_names, **kwargs
        )

    @classmethod
    def load(cls, directory: Path) -> FeatureFrame:
        """Load from disk.

        Args:
            directory: Directory containing saved files.

        Returns:
            Reconstructed FeatureFrame.
        """
        import json

        y_features = np.load(directory / "y_features.npy")
        id_data = np.load(directory / "identifiers.npz")
        identifiers = {k: id_data[k] for k in id_data.files}
        feature_names = json.loads(
            (directory / "feature_names.json").read_text()
        )
        metadata_path = directory / "metadata.json"
        metadata = (
            json.loads(metadata_path.read_text())
            if metadata_path.exists()
            else {}
        )
        return cls(
            y_features=y_features,
            identifiers=identifiers,
            feature_names=feature_names,
            metadata=metadata,
        )
