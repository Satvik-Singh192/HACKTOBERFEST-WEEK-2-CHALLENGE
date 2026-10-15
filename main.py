"""Run the BGMI kill-feed pipeline from the project root.

Supports both recorded video replays and live OBS Virtual Camera capture.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from preprocess import config
from preprocess.camera_source import OBSCameraSource, list_available_cameras
from preprocess.pipeline import VideoFileSource, run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BGMI Live Kill-Feed Capture & Points Table Pipeline"
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
        help="Run OCR on candidates to extract kills and sync with live backend (default: True)",
    )
    parser.add_argument(
        "--no-ocr",
        dest="ocr",
        action="store_false",
        help="Disable OCR parsing and run candidate detection only",
    )
    return parser.parse_args()


DEFAULT_ROSTER = {
    "KRAIT": ["Ravi", "Kabir", "Arjun", "Rav1", "R4VI"],
    "NOVA": ["Aarav", "Rahul", "Vicky", "Aar4v", "NOVA_A"],
    "ZENITH": ["Sam", "Rex", "Max", "5am", "Z3NlTH_Sam"],
    "VORTEX": ["Isha", "Ron", "Karan", "lsha", "V0RT3X_lsha"],
    "ASHEN": ["Kabir", "Rishi", "Aman", "K4bir"],
    "MIRAGE": ["Rohan", "Tara", "Sid", "M1RAGE_Rohan"],
    "TALON": ["Dev", "Rocky", "Sunny", "D3v"],
    "OBSIDIAN": ["Neel", "Aryan", "Veer", "N3el"],
}


def load_live_roster() -> dict[str, list[str]]:
    """Load active roster dynamically from data/roster.json or fallback to DEFAULT_ROSTER."""
    import json
    roster_file = Path("data/roster.json")
    if roster_file.is_file():
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                lookup: dict[str, list[str]] = {}
                for entry in data:
                    tname = entry.get("team", "")
                    players = []
                    for p in entry.get("players", []):
                        if p.get("name"):
                            players.append(p["name"])
                        for a in p.get("aliases", []):
                            if a:
                                players.append(a)
                    if tname:
                        lookup[tname] = players
                if lookup:
                    return lookup
        except Exception:
            pass
    return DEFAULT_ROSTER


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
        print("Starting LIVE pipeline with OBS Virtual Camera...")
        source = OBSCameraSource(
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
        def __init__(self, inner):
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
            print("Initializing OCR Engine (PaddleOCR) for kill-feed parsing...")
            import json
            import urllib.error
            import urllib.request
            from model_experiments.ocr import SingleRowKillfeedOCR

            ocr_engine = SingleRowKillfeedOCR(min_ocr_conf=0.70, fuzzy_threshold=60)
            active_roster = load_live_roster()
            print(f"OCR Engine ready. Loaded {len(active_roster)} teams with player aliases from live roster.")
            print("Detected kills will sync automatically to http://127.0.0.1:8000/api/kill\n")

            def handle_candidate(candidate):
                try:
                    # Refresh roster periodically or on each call
                    current_roster = load_live_roster()
                    result = ocr_engine.extract(candidate.crop_bgr, current_roster)
                    if result:
                        attacker = result["attacker"]
                        victim = result["victim"]
                        attacker_team = attacker["team"]
                        victim_team = victim["team"]
                        attacker_player = attacker["player"]
                        victim_player = victim["player"]
                        conf = result.get("avg_confidence", 0.0)
                        print(
                            f"\n>>> [OCR DETECTED KILL] t={candidate.timestamp_seconds:.2f}s | "
                            f"{attacker_player} ({attacker_team}) -> {victim_player} ({victim_team}) "
                            f"(conf: {conf:.2f})"
                        )
                        # Sync with backend if alive
                        url = "http://127.0.0.1:8000/api/kill"
                        payload = json.dumps({
                            "team": attacker_team,
                            "player": attacker_player,
                            "delta": 1,
                        }).encode("utf-8")
                        req = urllib.request.Request(
                            url,
                            data=payload,
                            headers={"Content-Type": "application/json"},
                        )
                        try:
                            with urllib.request.urlopen(req, timeout=1.0) as resp:
                                body = json.loads(resp.read().decode("utf-8"))
                                if body.get("status") == "blocked":
                                    print(f"    [MATCH STATUS] {body.get('message')}")
                                else:
                                    print(f"    [SYNC] Live scoreboard updated: +1 Kill to {attacker_player} ({attacker_team})")
                        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
                            print("    [SYNC] Backend not reachable at http://127.0.0.1:8000 - skipping WebSocket broadcast.")
                except Exception as exc:
                    print(f"Error processing OCR on candidate: {exc}")

            on_candidate = handle_candidate
        except Exception as e:
            print(f"Notice: Could not initialize OCR engine ({e}). Running candidate extraction without OCR.")

    run_pipeline(DebugFrameSourceWrapper(source), on_candidate=on_candidate)


if __name__ == "__main__":
    main()
