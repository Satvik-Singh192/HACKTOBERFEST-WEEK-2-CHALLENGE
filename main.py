"""Run the BGMI kill-feed pipeline from the project root.

Supports:
- Input sources: Recorded video replay or live OBS Virtual Camera capture.
- Recognition: OpenVINO YOLO weapon/icon classification + PaddleOCR text extraction.
- Scoring & Broadcast: Automatic fuzzy team roster matching & real-time WebSocket broadcast.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from preprocess import config
from preprocess.camera_source import OBSCameraSource, list_available_cameras
from preprocess.pipeline import FrameSource, VideoFileSource, run_pipeline
from model_experiments.pipeline import KillfeedPipeline
from backend.event_pipeline import EventPipeline

YOLO_WEIGHTS = Path("./best_openvino_model/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BGMI Live Kill-Feed Capture, ML Detection & Points Table Pipeline"
    )
    parser.add_argument(
        "--source",
        choices=["file", "obs"],
        default="file",
        help="Input frame source: 'file' for video replay or 'obs' for live OBS Virtual Camera",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Shortcut to run with live OBS Virtual Camera source",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=1,
        help="Camera device index for OBS Virtual Camera (default: 1)",
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=config.VIDEO_PATH,
        help=f"Path to input video file (default: {config.VIDEO_PATH})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=config.DURATION_SECONDS,
        help=f"Process limit in seconds for file replay (default: {config.DURATION_SECONDS})",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="List all active camera indices detected on the machine and exit",
    )
    parser.add_argument(
        "--ocr",
        dest="ocr",
        action="store_true",
        default=True,
        help="Run OCR & ML recognition on candidates (default: True)",
    )
    parser.add_argument(
        "--no-ocr",
        dest="ocr",
        action="store_false",
        help="Disable OCR/ML inference and run candidate detection only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.probe:
        print("Probing available camera indices via DirectShow...")
        indices = list_available_cameras(max_probe=6)
        if indices:
            print(f"Available camera devices found at indices: {indices}")
            print("Tip: If OBS Virtual Camera is running, it will typically be index 0 or 1.")
        else:
            print("No video capture devices found. Please ensure OBS Virtual Camera is started.")
        return

    # Determine frame source
    if args.live or args.source == "obs":
        print(f"Starting LIVE pipeline with OBS Virtual Camera (device {args.camera})...")
        source: FrameSource = OBSCameraSource(
            camera_index=args.camera,
            target_fps=30,
            width=1920,
            height=1080,
        )
    else:
        print(f"Starting video replay pipeline from file: {args.video}...")
        source = VideoFileSource(
            video_path=args.video,
            duration_seconds=args.duration,
        )

    # Save a visual snapshot of what the camera sees with the ROI box drawn
    class DebugFrameSourceWrapper:
        def __init__(self, inner: FrameSource):
            self.inner = inner

        def frames(self):
            import cv2
            saved = False
            for packet in self.inner.frames():
                if not saved:
                    saved = True
                    try:
                        out_dir = Path("output")
                        out_dir.mkdir(parents=True, exist_ok=True)
                        preview = packet.frame_bgr.copy()
                        h, w = preview.shape[:2]
                        x1 = int(w * config.XMIN_RATIO)
                        x2 = int(w * config.XMAX_RATIO)
                        y1 = int(h * config.YMIN_RATIO)
                        y2 = int(h * config.YMAX_RATIO)
                        cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 0), 3)
                        cv2.putText(
                            preview,
                            f"KILL FEED ROI ({x1},{y1}) to ({x2},{y2})",
                            (x1, max(30, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                        )
                        debug_file = out_dir / "live_roi_box.jpg"
                        cv2.imwrite(str(debug_file), preview)
                        crop_file = out_dir / "live_roi_crop.jpg"
                        cv2.imwrite(str(crop_file), packet.frame_bgr[y1:y2, x1:x2])
                        print(f"[DEBUG PREVIEW] Saved live frame with ROI box to: {debug_file}")
                        print(f"[DEBUG PREVIEW] Saved live ROI crop to: {crop_file}\n")
                    except Exception as e:
                        print(f"Warning: could not save ROI preview: {e}")

                yield packet

    on_candidate = None
    if args.ocr:
        try:
            print("Initializing ML & OCR Pipeline (OpenVINO YOLO + PaddleOCR)...")
            ml_pipeline = KillfeedPipeline(
                yolo_weights_path=str(YOLO_WEIGHTS),
                min_ocr_conf=0.50,
                yolo_conf=0.25,
                imgsz=352,
            )
            event_pipeline = EventPipeline(sync_scoreboard=True)
            print("Pipeline ready. Recognized events will sync live to scoreboard & OBS overlay.\n")

            def handle_candidate(candidate) -> None:
                try:
                    event = ml_pipeline.process(candidate.crop_bgr)
                    if event is None:
                        return

                    event_pipeline.process_event(event)

                    print(
                        f">>> [EVENT DETECTED] t={candidate.timestamp_seconds:.2f}s | "
                        f"Attacker: {event.attacker} | "
                        f"Icons: {[i.value for i in event.icons]} | "
                        f"Victim: {event.victim}"
                    )
                except Exception as exc:
                    print(f"Error handling candidate: {exc}")

            on_candidate = handle_candidate
        except Exception as e:
            print(f"Notice: ML Pipeline could not be initialized ({e}). Running candidate detection only.")

    run_pipeline(
        source=DebugFrameSourceWrapper(source),
        on_candidate=on_candidate,
    )


if __name__ == "__main__":
    main()
