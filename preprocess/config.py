from pathlib import Path


# ---------------- PROJECT PATHS ----------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

VIDEO_PATH = PROJECT_ROOT / "data" / "trimmed.mp4"
OUTPUT_DIR = PROJECT_ROOT / "output" / "mask_detection"

# Path to the TrueType font used to generate masks.
# Change this if you want to test another font file.
FONT_PATH = PROJECT_ROOT / "fonts" / "RobotoCondensed-Bold.ttf"
FONT_NAME = FONT_PATH.stem

# Change this to experiment with different rendered font sizes.
# For example, 11, 13, or 15. The masks are generated at startup.
MASK_SIZE = 13

# Generated masks are stored here and overwritten at startup for MASK_SIZE.
MASK_DIR = (
    PROJECT_ROOT
    / "font_templates"
    / FONT_NAME
    / f"size_{MASK_SIZE:02d}"
)


# ---------------- CHARACTER TEMPLATES ----------------

# Uppercase and lowercase alphabet, excluding uppercase I, lowercase i and l.
CHARS = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefghjkmnopqrstuvwxyz"

# Font-mask rendering options. Kept separate from GRAY_THRESHOLD below,
# which applies to video crops rather than generated font glyphs.
FONT_SUPERSAMPLE = 4
FONT_MASK_THRESHOLD = 128


# ---------------- VIDEO PROCESSING ----------------

DURATION_SECONDS = 5 * 60


# ---------------- REGION OF INTEREST ----------------

YMIN_RATIO = 0.272
YMAX_RATIO = 0.355
XMIN_RATIO = 0.005
XMAX_RATIO = 0.265


# ---------------- CHANGE DETECTION ----------------

DIFF_THRESHOLD = 12.0
COOLDOWN_SECONDS = 0.5


# ---------------- IMAGE PREPROCESSING ----------------

GRAY_THRESHOLD = 150
MATCH_WIDTH = 333
MATCH_HEIGHT = 60


# ---------------- TEMPLATE MATCHING ----------------

MASK_MATCH_THRESHOLD = 0.68
MIN_MATCHED_LETTERS = 3
MAX_PEAKS_PER_TEMPLATE = 20
OVERLAP_SUPPRESSION_THRESHOLD = 0.50
