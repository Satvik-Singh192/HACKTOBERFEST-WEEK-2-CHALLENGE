import csv
import cv2
from pathlib import Path

# Run this script from the project root.
VIDEO_PATH = Path("data/trimmed.mp4")
OUTPUT_DIR = Path("output/change_detection")

# Process only the first 5 minutes of this trimmed video.
DURATION_SECONDS = 5 * 60

# Your validated normalized crop boundaries.
YMIN_RATIO = 0.272
YMAX_RATIO = 0.355
XMIN_RATIO = 0.005
XMAX_RATIO = 0.265

# Tune this after inspecting the results.
# Mean absolute grayscale difference, range: 0-255.
DIFF_THRESHOLD = 12.0

# Avoid saving many detections during one animation.
# This does NOT skip reading or comparing frames.
COOLDOWN_SECONDS = 0.5


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    crops_dir = OUTPUT_DIR / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        raise RuntimeError("Invalid video FPS")

    video_duration = total_frames / fps
    frames_to_process = min(
        total_frames,
        int(DURATION_SECONDS * fps),
    )

    print(f"Video FPS: {fps:.2f}")
    print(f"Video duration: {video_duration / 60:.2f} minutes")
    print(f"Frames to process: {frames_to_process}")
    print(f"Difference threshold: {DIFF_THRESHOLD}")

    previous_gray = None
    previous_score = 0.0
    last_saved_time = -COOLDOWN_SECONDS

    detections = []
    frame_index = 0

    try:
        while frame_index < frames_to_process:
            success, frame = cap.read()

            if not success:
                break

            height, width = frame.shape[:2]

            # Convert normalized boundaries to pixel coordinates.
            x1 = int(width * XMIN_RATIO)
            x2 = int(width * XMAX_RATIO)
            y1 = int(height * YMIN_RATIO)
            y2 = int(height * YMAX_RATIO)

            crop = frame[y1:y2, x1:x2]

            # Grayscale comparison.
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            timestamp = frame_index / fps
            score = 0.0

            if previous_gray is not None:
                # Mean absolute pixel difference.
                diff = cv2.absdiff(gray, previous_gray)
                score = float(diff.mean())

                # Trigger when crossing above the threshold.
                crossed_threshold = (
                    score >= DIFF_THRESHOLD
                    and previous_score < DIFF_THRESHOLD
                )

                cooldown_passed = (
                    timestamp - last_saved_time
                    >= COOLDOWN_SECONDS
                )

                if crossed_threshold and cooldown_passed:
                    filename = f"frame_{frame_index:06d}.jpg"
                    crop_path = crops_dir / filename

                    if cv2.imwrite(str(crop_path), crop):
                        detections.append({
                            "frame_index": frame_index,
                            "timestamp_seconds": round(timestamp, 3),
                            "difference_score": round(score, 3),
                            "crop_path": str(crop_path),
                        })

                        last_saved_time = timestamp

                        print(
                            f"[CHANGE] t={timestamp:7.2f}s "
                            f"frame={frame_index:6d} "
                            f"score={score:6.2f}"
                        )

            previous_gray = gray
            previous_score = score
            frame_index += 1

            if frame_index % int(fps * 10) == 0:
                print(
                    f"Processed {timestamp:.0f}s / "
                    f"{DURATION_SECONDS}s | "
                    f"changes saved: {len(detections)}"
                )

    finally:
        cap.release()

    # Save detection metadata.
    csv_path = OUTPUT_DIR / "detections.csv"

    with csv_path.open("w", newline="") as file:
        columns = [
            "frame_index",
            "timestamp_seconds",
            "difference_score",
            "crop_path",
        ]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(detections)

    print("\nFinished.")
    print(f"Frames processed: {frame_index}")
    print(f"Changes saved: {len(detections)}")
    print(f"CSV: {csv_path}")
    print(f"Crops: {crops_dir}")


if __name__ == "__main__":
    main()

"""
295 candidate generated from 18000 frames pool (5 minute vid at 60 fps)
21/23 kill feed detected...best peroformance yet

"""
