"""Generate character masks from the configured TrueType font."""

from PIL import Image, ImageDraw, ImageFont

from . import config


def _render_glyph(character: str) -> tuple[Image.Image, Image.Image]:
    """Render one character and return its tight grayscale and binary masks."""
    scale = config.FONT_SUPERSAMPLE
    font_size = config.MASK_SIZE

    if font_size <= 0:
        raise ValueError(f"MASK_SIZE must be positive, got {font_size}")
    if scale <= 0:
        raise ValueError(
            f"FONT_SUPERSAMPLE must be positive, got {scale}"
        )

    font = ImageFont.truetype(str(config.FONT_PATH), font_size * scale)

    # A generously sized canvas avoids clipping glyphs at small render sizes.
    pad = 8 * scale
    canvas = Image.new(
        "L",
        (
            font_size * 4 * scale + 2 * pad,
            font_size * 3 * scale + 2 * pad,
        ),
        0,
    )

    draw = ImageDraw.Draw(canvas)
    draw.text((pad, pad), character, font=font, fill=255)

    bbox = canvas.getbbox()
    if bbox is None:
        raise RuntimeError(f"Font rendered no visible pixels for {character!r}")

    high_res = canvas.crop(bbox)
    target_size = (
        max(1, round(high_res.width / scale)),
        max(1, round(high_res.height / scale)),
    )

    gray = high_res.resize(target_size, Image.Resampling.LANCZOS)
    binary = gray.point(
        lambda pixel: 255 if pixel >= config.FONT_MASK_THRESHOLD else 0
    )

    # Tight-crop to the foreground pixels of the binary mask.
    binary_bbox = binary.getbbox()
    if binary_bbox is None:
        raise RuntimeError(
            f"Binary mask for {character!r} is empty. "
            "Check FONT_MASK_THRESHOLD."
        )

    binary = binary.crop(binary_bbox)
    gray = gray.crop(binary_bbox)

    # Template matching with TM_CCOEFF_NORMED is unreliable for a constant mask.
    if len(set(binary.getdata())) < 2:
        raise ValueError(
            f"Mask for {character!r} contains only one pixel value. "
            "This glyph cannot be used reliably with normalized correlation."
        )

    return gray, binary


def generate_masks() -> None:
    """Generate all configured masks into the active MASK_DIR.

    This is called automatically by load_templates() during pipeline startup.
    Existing files for the configured characters are overwritten.
    """
    if not config.FONT_PATH.is_file():
        raise FileNotFoundError(
            f"Font file not found: {config.FONT_PATH}\n"
            "Set FONT_PATH in preprocess/config.py to an existing .ttf file."
        )

    if not config.CHARS:
        raise ValueError("CHARS is empty; no font masks can be generated.")

    config.MASK_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating font masks")
    print(f"Font: {config.FONT_PATH}")
    print(f"Mask size: {config.MASK_SIZE}")
    print(f"Output directory: {config.MASK_DIR}")

    for character in config.CHARS:
        gray, binary = _render_glyph(character)
        gray_path = config.MASK_DIR / f"{character}_gray.png"
        mask_path = config.MASK_DIR / f"{character}_mask.png"

        gray.save(gray_path)
        binary.save(mask_path)

        print(
            f"  {character!r}: {binary.width}x{binary.height}px"
        )

    print(f"Generated {len(config.CHARS)} character masks.\n")
