"""Generate, load, and validate character templates."""

import cv2
import numpy as np

from . import config
from .mask_generator import generate_masks


def load_templates() -> dict[str, np.ndarray]:
    """Generate the configured masks, then load them for matching.

    Calling this function at pipeline startup ensures that MASK_SIZE and
    FONT_PATH in config.py determine the masks used in that run.
    """
    generate_masks()

    templates: dict[str, np.ndarray] = {}

    for character in config.CHARS:
        path = config.MASK_DIR / f"{character}_mask.png"
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

        if template is None:
            raise RuntimeError(f"Could not read generated template: {path}")

        # Ensure a strict binary template: black background, white foreground.
        _, template = cv2.threshold(
            template,
            0,
            255,
            cv2.THRESH_BINARY,
        )

        height, width = template.shape
        if height > config.MATCH_HEIGHT or width > config.MATCH_WIDTH:
            raise ValueError(
                f"Template {path.name} is {width}x{height}px, which exceeds "
                f"the {config.MATCH_WIDTH}x{config.MATCH_HEIGHT}px matching ROI."
            )

        # Normalized correlation can behave badly with a constant-valued mask.
        if np.unique(template).size < 2:
            raise ValueError(
                f"Template {path.name} contains only one pixel value and "
                "cannot be matched reliably."
            )

        templates[character] = template
        print(f"Loaded {character!r}: {width}x{height}px")

    if not templates:
        raise RuntimeError("No character templates were loaded.")

    print(f"Loaded {len(templates)} character templates.\n")
    return templates
