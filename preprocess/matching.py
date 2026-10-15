
import cv2
import numpy as np

from .config import (
    MASK_MATCH_THRESHOLD,
    MAX_PEAKS_PER_TEMPLATE,
    OVERLAP_SUPPRESSION_THRESHOLD,
)


def overlap_over_smaller(a, b):
    """
    Calculate the fraction of the smaller rectangle covered
    by the intersection of two match rectangles.
    """
    left = max(a["x"], b["x"])
    top = max(a["y"], b["y"])

    right = min(
        a["x"] + a["width"],
        b["x"] + b["width"],
    )

    bottom = min(
        a["y"] + a["height"],
        b["y"] + b["height"],
    )

    intersection = (
        max(0, right - left)
        * max(0, bottom - top)
    )

    area_a = a["width"] * a["height"]
    area_b = b["width"] * b["height"]

    return intersection / max(1, min(area_a, area_b))


def find_template_matches(
    binary_roi,
    templates,
    threshold=MASK_MATCH_THRESHOLD,
):
    """
    Find distinct spatial matches for all character templates.

    Args:
        binary_roi: Binary image of the kill-feed region.
        templates: Dictionary mapping characters to binary masks.
        threshold: Minimum acceptable template similarity score.

    Returns:
        List of distinct matches, sorted approximately from
        left to right and top to bottom.

        Each match contains:
            char, score, x, y, width, height
    """
    proposals = []

    for char, template in templates.items():
        # Find the similarity score at every possible position.
        scores = cv2.matchTemplate(
            binary_roi,
            template,
            cv2.TM_CCOEFF_NORMED,
        )

        height, width = template.shape

        # Identify local maxima to avoid collecting every
        # nearby position around the same letter.
        kernel = np.ones(
            (height, width),
            dtype=np.uint8,
        )

        local_max = cv2.dilate(scores, kernel)

        peak_mask = (
            (scores >= threshold)
            & (scores >= local_max - 1e-6)
        )

        ys, xs = np.where(peak_mask)

        # Keep only the strongest locations for this character.
        if len(xs) > MAX_PEAKS_PER_TEMPLATE:
            peak_scores = scores[ys, xs]

            strongest = np.argsort(peak_scores)[
                -MAX_PEAKS_PER_TEMPLATE:
            ]

            xs = xs[strongest]
            ys = ys[strongest]

        for x, y in zip(xs, ys):
            proposals.append({
                "char": char,
                "score": float(scores[y, x]),
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
            })

    # Consider stronger matches first.
    proposals.sort(
        key=lambda match: match["score"],
        reverse=True,
    )

    distinct_matches = []

    for candidate in proposals:
        overlaps_existing = any(
            overlap_over_smaller(candidate, accepted)
            >= OVERLAP_SUPPRESSION_THRESHOLD
            for accepted in distinct_matches
        )

        if not overlaps_existing:
            distinct_matches.append(candidate)

    # Return matches in approximate reading order.
    distinct_matches.sort(
        key=lambda match: (
            match["y"],
            match["x"],
        )
    )

    return distinct_matches
