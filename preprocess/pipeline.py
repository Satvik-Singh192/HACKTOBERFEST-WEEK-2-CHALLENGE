"""Pre-model BGMI kill-feed candidate generation.

Responsibilities:
- Read frames from a frame source (currently an MP4 source).
- Crop the kill-feed region.
- Detect pixel-change threshold crossings with cooldown.
- Apply character-template matching to triggered candidates.
- Emit only mask-confirmed candidate crops to a caller-supplied callback.

This module does not run ML inference, calculate scores, or publish WebSocket
updates. Those belong to later application-level components.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

import cv2
import numpy as np

from . import config
from .change_detector import PixelChangeDetector
from .matching import find_template_matches
from .output import OutputManager
from .roi import crop_killfeed_roi, make_binary_roi
from .templates import load_templates


@dataclass(frozen=True)
class FramePacket:
    """One full video frame and its source timestamp."""

    frame_index: int
    timestamp_seconds: float
    frame_bgr: np.ndarray


class FrameSource(Protocol):
    """Interface implemented by MP4, OBS, or another frame source."""

    def frames(self) -> Iterator[FramePacket]:
        """Yield frames in chronological order."""
        ...


class VideoFileSource:
    """Read a local video sequentially, presenting it as a frame stream."""

    def __init__(
        self,
        video_path: Path = config.VIDEO_PATH,
        duration_seconds: float | None = config.DURATION_SECONDS,
    ) -> None:
        self.video_path = Path(video_path)
        self.duration_seconds = duration_seconds

    def frames(self) -> Iterator[FramePacket]:
        if not self.video_path.is_file():
            raise FileNotFoundError(f"Video not found: {self.video_path}")

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Cannot open video: {self.video_path}")

        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps <= 0:
                raise RuntimeError(f"Invalid video FPS: {fps}")

            if self.duration_seconds is None:
                frame_limit = total_frames
            else:
                frame_limit = min(
                    total_frames,
                    max(0, int(self.duration_seconds * fps)),
                )

            print(f"Input video: {self.video_path}")
            print(f"FPS: {fps:.2f}")
            print(f"Video duration: {total_frames / fps:.2f}s")
            print(f"Frames to process: {frame_limit}\n")

            for frame_index in range(frame_limit):
                success, frame = cap.read()
                if not success:
                    break

                yield FramePacket(
                    frame_index=frame_index,
                    timestamp_seconds=frame_index / fps,
                    frame_bgr=frame,
                )
        finally:
            cap.release()


@dataclass(frozen=True)
class ValidFrameCandidate:
    """A crop that passed both pixel-change and character-mask filters.

    `crop_bgr` is the original-resolution kill-feed ROI and is the primary
    payload intended for the ML model. The other fields are useful metadata
    for logging, evaluation, and debugging.
    """

    frame_index: int
    timestamp_seconds: float
    crop_bgr: np.ndarray
    difference_score: float
    match_count: int
    matched_chars: str
    matches: tuple[dict[str, Any], ...]


CandidateHandler = Callable[[ValidFrameCandidate], None]


def iter_valid_frames(source: FrameSource) -> Iterator[ValidFrameCandidate]:
    """Yield only crops accepted by both deterministic filtering stages.

    The first filter runs for every input frame: ROI pixel-change threshold
    crossing plus cooldown. Character matching runs only on those candidates.
    A crop is yielded only when the distinct match count meets
    `config.MIN_MATCHED_LETTERS`.

    Diagnostic images and CSV reports are still written through OutputManager.
    """
    output = OutputManager(config.OUTPUT_DIR)
    templates = load_templates()
    change_detector = PixelChangeDetector(
        threshold=config.DIFF_THRESHOLD,
        cooldown_seconds=config.COOLDOWN_SECONDS,
    )

    processed_frames = 0
    candidate_count = 0
    confirmed_count = 0
    last_progress_timestamp = -10.0

    print("Starting pre-model candidate generation")
    print(f"Font: {config.FONT_NAME}; mask size: {config.MASK_SIZE}")
    print(f"Pixel-difference threshold: {config.DIFF_THRESHOLD}")
    print(f"Cooldown: {config.COOLDOWN_SECONDS}s")
    print(f"Template score threshold: {config.MASK_MATCH_THRESHOLD}")
    print(f"Minimum distinct matches: {config.MIN_MATCHED_LETTERS}\n")

    try:
        for packet in source.frames():
            processed_frames += 1

            crop = crop_killfeed_roi(packet.frame_bgr)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            difference_score, triggered = change_detector.update(
                gray,
                packet.timestamp_seconds,
            )

            if triggered:
                candidate_count += 1
                normalized, binary_roi = make_binary_roi(crop)

                matches = find_template_matches(
                    binary_roi,
                    templates,
                    threshold=config.MASK_MATCH_THRESHOLD,
                )

                match_count = len(matches)
                matched_chars = "".join(match["char"] for match in matches)
                confirmed = match_count >= config.MIN_MATCHED_LETTERS

                # Keep the current diagnostic output behavior for evaluation.
                output.save_event(
                    frame_index=packet.frame_index,
                    timestamp=packet.timestamp_seconds,
                    difference_score=difference_score,
                    crop=crop,
                    normalized=normalized,
                    binary_roi=binary_roi,
                    matches=matches,
                    confirmed=confirmed,
                )

                status = "VALID CANDIDATE" if confirmed else "MASK REJECTED"
                print(
                    f"[{status}] t={packet.timestamp_seconds:7.2f}s "
                    f"frame={packet.frame_index:6d} "
                    f"diff={difference_score:6.2f} "
                    f"matches={match_count} chars={matched_chars!r}"
                )

                if confirmed:
                    confirmed_count += 1
                    # Copy the crop so the downstream consumer owns its pixels.
                    yield ValidFrameCandidate(
                        frame_index=packet.frame_index,
                        timestamp_seconds=packet.timestamp_seconds,
                        crop_bgr=crop.copy(),
                        difference_score=difference_score,
                        match_count=match_count,
                        matched_chars=matched_chars,
                        matches=tuple(dict(match) for match in matches),
                    )

            if packet.timestamp_seconds - last_progress_timestamp >= 10.0:
                last_progress_timestamp = packet.timestamp_seconds
                print(
                    f"Processed {packet.timestamp_seconds:.0f}s | "
                    f"frames={processed_frames} | candidates={candidate_count} | "
                    f"valid={confirmed_count}"
                )

    finally:
        # The reports are finalized when the iterator finishes or is closed.
        output.write_reports()
        print("\nPre-model processing finished.")
        print(f"Frames processed: {processed_frames}")
        print(f"Pixel-change candidates: {candidate_count}")
        print(f"Valid pre-model candidates: {confirmed_count}")
        print(f"Output directory: {config.OUTPUT_DIR}")


def run_pipeline(
    source: FrameSource,
    on_candidate: CandidateHandler | None = None,
) -> None:
    """Process a source and optionally hand each valid crop to a consumer.

    With no callback, the pipeline runs for diagnostics and saves outputs.
    When an ML adapter is ready, pass a callback that accepts one
    `ValidFrameCandidate`; this module itself remains ML/backend-independent.
    """
    candidate_stream = iter_valid_frames(source)
    try:
        for candidate in candidate_stream:
            if on_candidate is not None:
                on_candidate(candidate)
    finally:
        # Ensure reports are written if a callback raises or stops processing.
        candidate_stream.close()
