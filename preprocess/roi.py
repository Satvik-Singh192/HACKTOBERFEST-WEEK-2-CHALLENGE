"""Crop the kill-feed ROI and prepare it for character matching."""

import cv2
import numpy as np

from .config import (
    GRAY_THRESHOLD,
    MATCH_WIDTH,
    MATCH_HEIGHT,
    XMIN_RATIO,
    XMAX_RATIO,
    YMIN_RATIO,
    YMAX_RATIO,
)


def crop_killfeed_roi(frame_bgr: np.ndarray) -> np.ndarray:
    """Crop the configured normalized kill-feed region from a full frame."""
    frame_height, frame_width = frame_bgr.shape[:2]

    x1 = int(frame_width * XMIN_RATIO)
    x2 = int(frame_width * XMAX_RATIO)
    y1 = int(frame_height * YMIN_RATIO)
    y2 = int(frame_height * YMAX_RATIO)

    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError(
            "Kill-feed ROI is empty. Check X/Y crop ratios in config.py."
        )

    return crop


def normalize_crop(crop: np.ndarray) -> np.ndarray:
    """Resize a kill-feed crop to the template matching dimensions."""
    source_height, source_width = crop.shape[:2]

    interpolation = (
        cv2.INTER_AREA
        if source_width >= MATCH_WIDTH and source_height >= MATCH_HEIGHT
        else cv2.INTER_LINEAR
    )

    return cv2.resize(
        crop,
        (MATCH_WIDTH, MATCH_HEIGHT),
        interpolation=interpolation,
    )


def make_binary_roi(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the normalized BGR crop and its binary grayscale mask."""
    normalized = normalize_crop(crop)
    gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(
        gray,
        GRAY_THRESHOLD,
        255,
        cv2.THRESH_BINARY,
    )

    return normalized, binary
