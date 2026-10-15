
import cv2

from .config import (
    DIFF_THRESHOLD,
    COOLDOWN_SECONDS,
)


class PixelChangeDetector:
    """
    Detect candidate events from pixel changes between
    consecutive grayscale frames.

    A candidate is triggered when:
    1. The mean absolute pixel difference reaches the threshold.
    2. The previous frame's difference was below the threshold.
    3. The cooldown period has elapsed.
    """

    def __init__(
        self,
        threshold=DIFF_THRESHOLD,
        cooldown_seconds=COOLDOWN_SECONDS,
    ):
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds

        self.previous_gray = None
        self.previous_score = 0.0

        self.last_event_time = -cooldown_seconds

    def update(self, gray, timestamp):
        """
        Process the current grayscale ROI.

        Args:
            gray: Grayscale image of the kill-feed region.
            timestamp: Current frame timestamp in seconds.

        Returns:
            tuple[float, bool]:
                score: Mean absolute pixel difference.
                triggered: Whether a candidate event occurred.
        """
        # The first frame initializes the detector.
        if self.previous_gray is None:
            self.previous_gray = gray.copy()
            return 0.0, False

        if gray.shape != self.previous_gray.shape:
            raise ValueError(
                "Consecutive grayscale frames must have "
                "the same dimensions."
            )

        # Preserve the original baseline calculation.
        difference = cv2.absdiff(
            gray,
            self.previous_gray,
        )

        score = float(difference.mean())

        crossed_threshold = (
            score >= self.threshold
            and self.previous_score < self.threshold
        )

        cooldown_passed = (
            timestamp - self.last_event_time
            >= self.cooldown_seconds
        )

        triggered = crossed_threshold and cooldown_passed

        if triggered:
            self.last_event_time = timestamp

        # Update state on every frame, including non-events.
        self.previous_gray = gray.copy()
        self.previous_score = score

        return score, triggered
