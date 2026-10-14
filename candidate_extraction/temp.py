
import csv
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


VIDEO_PATH = Path("data/trimmed.mp4")
DURATION_SECONDS = 5 * 60
OUTPUT_ROOT = Path("output/weighted_change_test")

# Validated normalized crop boundaries
YMIN_RATIO = 0.272
YMAX_RATIO = 0.355
XMIN_RATIO = 0.005
XMAX_RATIO = 0.265

DIFF_THRESHOLD = 12.0

# Spatial weights
OUTER_SHELL_WEIGHT = 0.35
INNER_MARGIN_X_RATIO = 0.05
INNER_MARGIN_Y_RATIO = 0.15


def crop_feed(frame):
    h, w = frame.shape[:2]

    x1 = int(w * XMIN_RATIO)
    x2 = int(w * XMAX_RATIO)
    y1 = int(h * YMIN_RATIO)
    y2 = int(h * YMAX_RATIO)

    return frame[y1:y2, x1:x2]


def build_weight_mask(height, width):
    weights = np.full(
        (height, width),
        OUTER_SHELL_WEIGHT,
        dtype=np.float32,
    )

    margin_x = int(width * INNER_MARGIN_X_RATIO)
    margin_y = int(height * INNER_MARGIN_Y_RATIO)

    weights[
        margin_y:height - margin_y,
        margin_x:width - margin_x,
    ] = 1.0

    return weights


def weighted_difference(current, previous, weights):
    diff = cv2.absdiff(current, previous).astype(np.float32)
    return float(np.sum(diff * weights) / np.sum(weights))


def main():
    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0 or total_frames <= 0:
        cap.release()
        raise RuntimeError("Invalid video FPS or frame count")

    frame_limit = min(total_frames, int(DURATION_SECONDS * fps))

    # Use a fresh directory for each run.
    run_dir = OUTPUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    crops_dir = run_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    previous_gray = None
    previous_score = 0.0
    weights = None

    frame_index = 0
    trigger_count = 0

    scores_path = run_dir / "frame_scores.csv"
    detections_path = run_dir / "detections.csv"

    print(f"FPS: {fps:.2f}")
    print(f"Processing first {frame_limit / fps:.1f} seconds")
    print(f"Threshold: {DIFF_THRESHOLD}")
    print(f"Output: {run_dir}")

    try:
        with (
            scores_path.open("w", newline="") as scores_file,
            detections_path.open("w", newline="") as detections_file,
        ):
            score_writer = csv.DictWriter(
                scores_file,
                fieldnames=[
                    "frame_index",
                    "timestamp_seconds",
                    "weighted_diff_score",
                    "triggered",
                ],
            )
            score_writer.writeheader()

            detection_writer = csv.DictWriter(
                detections_file,
                fieldnames=[
                    "frame_index",
                    "timestamp_seconds",
                    "weighted_diff_score",
                    "crop_path",
                ],
            )
            detection_writer.writeheader()

            while frame_index < frame_limit:
                ok, frame = cap.read()
                if not ok:
                    break

                timestamp = frame_index / fps
                crop = crop_feed(frame)
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

                if weights is None:
                    weights = build_weight_mask(*gray.shape)

                    mask_image = np.clip(
                        weights * 255, 0, 255
                    ).astype(np.uint8)

                    cv2.imwrite(
                        str(run_dir / "weight_mask.png"),
                        mask_image,
                    )

                score = 0.0
                triggered = False

                if previous_gray is not None:
                    score = weighted_difference(
                        gray, previous_gray, weights
                    )

                    # Save only when the score crosses the threshold.
                    triggered = (
                        score >= DIFF_THRESHOLD
                        and previous_score < DIFF_THRESHOLD
                    )

                crop_path = ""

                if triggered:
                    filename = f"frame_{frame_index:06d}.jpg"
                    output_path = crops_dir / filename

                    if cv2.imwrite(str(output_path), crop):
                        crop_path = str(output_path)
                        trigger_count += 1

                        detection_writer.writerow({
                            "frame_index": frame_index,
                            "timestamp_seconds": round(timestamp, 3),
                            "weighted_diff_score": round(score, 3),
                            "crop_path": crop_path,
                        })

                        print(
                            f"[CHANGE] t={timestamp:7.2f}s "
                            f"score={score:6.2f} "
                            f"saved={filename}"
                        )

                score_writer.writerow({
                    "frame_index": frame_index,
                    "timestamp_seconds": round(timestamp, 3),
                    "weighted_diff_score": round(score, 3),
                    "triggered": triggered,
                })

                previous_gray = gray
                previous_score = score
                frame_index += 1

                if frame_index % int(fps * 10) == 0:
                    print(
                        f"Processed {frame_index / fps:.0f}s / "
                        f"{frame_limit / fps:.0f}s | "
                        f"crops saved: {trigger_count}"
                    )

    finally:
        cap.release()

    print("\nFinished.")
    print(f"Frames processed: {frame_index}")
    print(f"Crops saved: {trigger_count}")
    print(f"Detections: {detections_path}")
    print(f"Frame scores: {scores_path}")


if __name__ == "__main__":
    main()
