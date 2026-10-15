
import csv
from pathlib import Path

import cv2

from .config import OUTPUT_DIR


class OutputManager:
    """
    Save candidate frames, confirmed detections, binary masks,
    match visualizations, and CSV reports.
    """

    def __init__(self, output_dir=OUTPUT_DIR):
        self.output_dir = Path(output_dir)

        self.candidates_dir = self.output_dir / "candidates"
        self.detections_dir = self.output_dir / "detections"
        self.binary_dir = self.output_dir / "binary_masks"
        self.debug_dir = self.output_dir / "match_debug"

        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.detections_dir.mkdir(parents=True, exist_ok=True)
        self.binary_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.candidates = []
        self.detections = []

    @staticmethod
    def _save_image(path, image):
        """Save an image and raise an error if saving fails."""
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Failed to save image: {path}")

    @staticmethod
    def _get_best_match(matches):
        """Return the strongest match, or a default if none exist."""
        if matches:
            return max(matches, key=lambda match: match["score"])

        return {
            "char": "",
            "score": 0.0,
            "x": -1,
            "y": -1,
            "width": 0,
            "height": 0,
        }

    @staticmethod
    def _create_debug_image(normalized, matches):
        """Draw all accepted match locations on the normalized ROI."""
        debug_image = normalized.copy()

        for match in matches:
            x = match["x"]
            y = match["y"]
            width = match["width"]
            height = match["height"]

            cv2.rectangle(
                debug_image,
                (x, y),
                (x + width - 1, y + height - 1),
                (0, 0, 255),
                1,
            )

            cv2.putText(
                debug_image,
                f'{match["char"]}:{match["score"]:.2f}',
                (x, max(10, y - 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.30,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return debug_image

    def save_event(
        self,
        frame_index,
        timestamp,
        difference_score,
        crop,
        normalized,
        binary_roi,
        matches,
        confirmed,
    ):
        """
        Save one pixel-change candidate and its matching results.

        Args:
            frame_index: Index of the video frame.
            timestamp: Timestamp in seconds.
            difference_score: Mean grayscale pixel difference.
            crop: Original, native-resolution ROI.
            normalized: Resized BGR ROI.
            binary_roi: Binary image used for matching.
            matches: Distinct spatial matches from matching.py.
            confirmed: Whether the candidate passed the match-count rule.

        Returns:
            A dictionary describing the candidate.
        """
        filename = f"frame_{frame_index:06d}.jpg"
        stem = f"frame_{frame_index:06d}"

        candidate_path = self.candidates_dir / filename
        binary_path = self.binary_dir / f"{stem}.png"
        debug_path = self.debug_dir / filename

        # Save all three diagnostic artifacts.
        self._save_image(candidate_path, crop)
        self._save_image(binary_path, binary_roi)

        debug_image = self._create_debug_image(
            normalized,
            matches,
        )
        self._save_image(debug_path, debug_image)

        best = self._get_best_match(matches)

        match_count = len(matches)
        matched_chars = "".join(
            match["char"] for match in matches
        )

        detection_path = ""

        # Only confirmed candidates go into detections/.
        if confirmed:
            detection_file = self.detections_dir / filename
            self._save_image(detection_file, crop)
            detection_path = str(detection_file)

        candidate_record = {
            "frame_index": frame_index,
            "timestamp_seconds": round(timestamp, 3),
            "difference_score": round(difference_score, 3),
            "best_char": best["char"],
            "mask_score": round(best["score"], 4),
            "match_count": match_count,
            "matched_chars": matched_chars,
            "match_x": best["x"],
            "match_y": best["y"],
            "mask_confirmed": confirmed,
            "candidate_path": str(candidate_path),
            "detection_path": detection_path,
            "binary_path": str(binary_path),
            "debug_path": str(debug_path),
        }

        self.candidates.append(candidate_record)

        if confirmed:
            detection_record = {
                "frame_index": frame_index,
                "timestamp_seconds": round(timestamp, 3),
                "difference_score": round(difference_score, 3),
                "best_char": best["char"],
                "mask_score": round(best["score"], 4),
                "match_count": match_count,
                "matched_chars": matched_chars,
                "match_x": best["x"],
                "match_y": best["y"],
                "crop_path": detection_path,
            }

            self.detections.append(detection_record)

        return candidate_record

    @staticmethod
    def _write_csv(path, rows, columns):
        """Write records to a CSV file."""
        with path.open("w", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=columns,
            )
            writer.writeheader()
            writer.writerows(rows)

    def write_reports(self):
        """Write candidate and confirmed-detection CSV reports."""
        candidate_columns = [
            "frame_index",
            "timestamp_seconds",
            "difference_score",
            "best_char",
            "mask_score",
            "match_count",
            "matched_chars",
            "match_x",
            "match_y",
            "mask_confirmed",
            "candidate_path",
            "detection_path",
            "binary_path",
            "debug_path",
        ]

        detection_columns = [
            "frame_index",
            "timestamp_seconds",
            "difference_score",
            "best_char",
            "mask_score",
            "match_count",
            "matched_chars",
            "match_x",
            "match_y",
            "crop_path",
        ]

        candidates_csv = self.output_dir / "candidates.csv"
        detections_csv = self.output_dir / "detections.csv"

        self._write_csv(
            candidates_csv,
            self.candidates,
            candidate_columns,
        )

        self._write_csv(
            detections_csv,
            self.detections,
            detection_columns,
        )

        print(f"Candidate CSV: {candidates_csv}")
        print(f"Detection CSV: {detections_csv}")
        print(f"Candidate crops: {self.candidates_dir}")
        print(f"Confirmed crops: {self.detections_dir}")
        print(f"Binary masks: {self.binary_dir}")
        print(f"Match visualizations: {self.debug_dir}")
