"""GeoTIFF reading for raster-based viewpoint builders."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import tifffile

logger = logging.getLogger(__name__)


def read_geotiff(
    path: Path,
) -> tuple[np.ndarray, float, float, float, float]:
    """Read GeoTIFF and extract geotransform from TIFF tags.

    Returns native dtype — no in-memory conversion. Strip-based
    aggregation handles any input dtype directly.

    Returns:
        (data, tiepoint_x, tiepoint_y, pixel_scale_x, pixel_scale_y)
        where tiepoint is the top-left geographic coordinate.
    """
    with tifffile.TiffFile(str(path)) as tif:
        page = tif.pages.first
        data = page.asarray(maxworkers=1)

        scale_tag = page.tags.get("ModelPixelScaleTag")
        tie_tag = page.tags.get("ModelTiepointTag")

        if scale_tag is None or tie_tag is None:
            msg = (
                f"GeoTIFF {path} missing geotransform tags "
                "(ModelPixelScaleTag, ModelTiepointTag)"
            )
            logger.error(msg)
            raise ValueError(msg)

        scale = scale_tag.value
        tie = tie_tag.value

        pixel_scale_x = float(scale[0])
        pixel_scale_y = float(scale[1])
        tiepoint_x = float(tie[3])
        tiepoint_y = float(tie[4])

    return data, tiepoint_x, tiepoint_y, pixel_scale_x, pixel_scale_y
