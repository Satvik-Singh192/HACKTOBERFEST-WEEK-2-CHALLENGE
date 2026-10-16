"""Comprehensive Kill-Feed Pipeline Debugger.

Captures, saves, and traces every layer of the detection & scoring pipeline:
1. Frames that make it to the OCR input layer (raw crop, 2x CLAHE-enhanced ocr_input, annotated overlay).
2. ML Model outputs (PaddleOCR words/boxes/confidence, YOLO icon detections, generated Event).
3. Score calculations triggered in TeamManager & StateStore (fuzzy matching, player status transitions,
   knock tracking, kill point attribution, squad wipeouts, placement points, and leaderboard standings).
"""

from __future__ import annotations

import os
import sys
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows PyTorch DLL safety
venv_site = Path(sys.executable).parent.parent / "Lib" / "site-packages"
torch_lib = venv_site / "torch" / "lib"
if torch_lib.is_dir() and hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(str(torch_lib))
    except Exception:
        pass

from backend.events import Event, Icon
from backend.teams import PlayerStatus
from backend.state import store
from model_experiments.pipeline import KillfeedPipeline


class PipelineDebugger:
    """Manages recording, saving, and reporting of all pipeline stages."""

    def __init__(
        self,
        output_dir: Path | str | None = None,
        min_ocr_conf: float = 0.45,
        yolo_conf: float = 0.25,
        yolo_weights: Optional[str] = None,
        reset_match_on_start: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir or (PROJECT_ROOT / "output" / "pipeline_debug"))
        self.frames_dir = self.output_dir / "frames"
        self.ml_dir = self.output_dir / "ml_outputs"
        self.scoring_dir = self.output_dir / "scoring_triggers"

        self._ensure_dirs()

        if reset_match_on_start:
            store.reset_current_match()

        default_yolo = PROJECT_ROOT / "best_openvino_model"
        weights = yolo_weights or (str(default_yolo) if default_yolo.exists() else None)

        self.ml_pipeline = KillfeedPipeline(
            yolo_weights_path=weights,
            min_ocr_conf=min_ocr_conf,
            yolo_conf=yolo_conf,
            imgsz=352,
        )

        self.step_counter = 0
        self.history_records: List[Dict[str, Any]] = []

    def _ensure_dirs(self) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.ml_dir.mkdir(parents=True, exist_ok=True)
        self.scoring_dir.mkdir(parents=True, exist_ok=True)

    def draw_annotated_frame(
        self,
        crop_bgr: np.ndarray,
        words: List[Dict[str, Any]],
        yolo_detections: List[Dict[str, Any]],
        event: Optional[Event] = None,
    ) -> np.ndarray:
        """Create an annotated visualization with bounding boxes for OCR words and YOLO icons."""
        h, w = crop_bgr.shape[:2]
        # Create an expanded canvas with a header banner for readable text
        banner_h = 32
        canvas = np.zeros((h + banner_h, w, 3), dtype=np.uint8)
        canvas[:banner_h, :] = (24, 24, 27)  # Dark banner background
        canvas[banner_h:, :] = crop_bgr.copy()

        # 1. Draw OCR Word Bounding Boxes
        for idx, word in enumerate(words):
            x1 = word.get("x_min", 0)
            x2 = word.get("x_max", 0)
            y1 = word.get("y_min", 0) + banner_h
            y2 = word.get("y_max", h) + banner_h
            text = word.get("text", "")
            conf = word.get("confidence", 0.0)

            # Leftmost is typically attacker (green), rightmost is victim (red)
            if idx == 0:
                box_color = (74, 222, 128)  # Emerald green
                role = "ATT"
            elif idx == len(words) - 1:
                box_color = (96, 96, 248)  # Crimson red
                role = "VIC"
            else:
                box_color = (250, 204, 21)  # Yellow
                role = "MID"

            cv2.rectangle(canvas, (x1, y1), (x2, y2), box_color, 1)
            label = f"{role}:{text}({int(conf * 100)}%)"
            cv2.putText(
                canvas,
                label,
                (max(0, x1), max(banner_h + 10, y1 - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                box_color,
                1,
                cv2.LINE_AA,
            )

        # 2. Draw YOLO Icon Bounding Boxes
        for det in yolo_detections:
            box = det.get("box")
            if box and len(box) == 4:
                bx1, by1, bx2, by2 = box
                by1 += banner_h
                by2 += banner_h
                cls_name = det.get("class", "icon")
                icon_conf = det.get("confidence", 0.0)
                cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (255, 165, 0), 1)
                cv2.putText(
                    canvas,
                    f"{cls_name} ({int(icon_conf * 100)}%)",
                    (bx1, max(banner_h + 10, by1 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    (255, 165, 0),
                    1,
                    cv2.LINE_AA,
                )

        # 3. Top Banner Summary
        if event is not None:
            icon_str = "+".join([i.value if hasattr(i, "value") else str(i) for i in event.icons])
            banner_text = f"EVENT: {event.attacker} -> [{icon_str}] -> {event.victim}"
            banner_col = (56, 189, 248)
        else:
            banner_text = f"WORDS: {len(words)} | NO EVENT ASSEMBLED"
            banner_col = (148, 163, 184)

        cv2.putText(
            canvas,
            banner_text,
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            banner_col,
            1,
            cv2.LINE_AA,
        )

        return canvas

    def process_frame(
        self,
        crop_bgr: np.ndarray,
        frame_index: int = 0,
        timestamp_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """Execute full debugging pipeline for one frame crop."""
        self.step_counter += 1
        step_id = self.step_counter

        # ---------------- 1. ML RECOGNITION & OCR LAYER ----------------
        event, ml_debug = self.ml_pipeline.process_debug(crop_bgr)
        ocr_input = ml_debug.get("ocr_input")
        words = ml_debug.get("words", [])
        yolo_detections = ml_debug.get("yolo_detections", [])

        # File prefixes
        prefix = f"step_{step_id:04d}_frame_{frame_index:06d}"

        # Save 1: Raw Crop
        crop_path = self.frames_dir / f"{prefix}_crop.png"
        cv2.imwrite(str(crop_path), crop_bgr)

        # Save 2: OCR Input (Exact 2x CLAHE-enhanced image fed into PaddleOCR)
        ocr_input_path = None
        if ocr_input is not None:
            ocr_input_path = self.frames_dir / f"{prefix}_ocr_input.png"
            cv2.imwrite(str(ocr_input_path), ocr_input)

        # Save 3: Annotated Visualization
        annotated = self.draw_annotated_frame(crop_bgr, words, yolo_detections, event)
        annotated_path = self.frames_dir / f"{prefix}_annotated.png"
        cv2.imwrite(str(annotated_path), annotated)

        # Save 4: ML Output JSON
        ml_record = {
            "step": step_id,
            "frame_index": frame_index,
            "timestamp_seconds": round(timestamp_seconds, 3),
            "status": ml_debug.get("status"),
            "timings": ml_debug.get("timings"),
            "raw_ocr_detections": ml_debug.get("ocr_raw", []),
            "parsed_words": [
                {
                    "text": w["text"],
                    "confidence": w["confidence"],
                    "x_min": w["x_min"],
                    "x_max": w["x_max"],
                }
                for w in words
            ],
            "extracted_entities": {
                "attacker_text": ml_debug.get("attacker_text"),
                "victim_text": ml_debug.get("victim_text"),
            },
            "yolo_detections": yolo_detections,
            "assembled_event": {
                "attacker": event.attacker,
                "icons": [i.value if hasattr(i, "value") else str(i) for i in event.icons],
                "victim": event.victim,
            }
            if event
            else None,
        }
        ml_json_path = self.ml_dir / f"{prefix}_ml_output.json"
        with open(ml_json_path, "w", encoding="utf-8") as f:
            json.dump(ml_record, f, indent=2, ensure_ascii=False)

        # ---------------- 2. SCOREBOARD & SCORING TRIGGER ----------------
        scoring_record = {
            "step": step_id,
            "frame_index": frame_index,
            "timestamp_seconds": round(timestamp_seconds, 3),
            "event_processed": bool(event is not None),
            "resolution": None,
            "action_taken": None,
            "state_changes": {},
            "points_impact": {},
            "scoreboard_top3": [],
        }

        if event is not None:
            # Capture state before event
            before_players = {
                p.name: {
                    "kills": p.kills,
                    "status": p.status.value,
                    "team": t.name,
                }
                for t in store.team_manager.teams.values()
                for p in t.players
            }
            before_teams = {
                t.name: {
                    "placement": t.placement,
                    "placement_points": t.placement_points,
                    "kills": sum(p.kills for p in t.players),
                    "total": sum(p.kills for p in t.players) + t.placement_points,
                }
                for t in store.team_manager.teams.values()
            }
            before_last_knock = dict(store.team_manager.last_knocked_by)

            # Trace player matching resolution
            resolved_event = None
            resolution_error = None
            try:
                resolved_event = store.team_manager.resolve_event(event)
            except Exception as e:
                resolution_error = str(e)

            if resolved_event is not None:
                attacker_team = None
                victim_team = None
                try:
                    if resolved_event.attacker and resolved_event.attacker != "Playzone":
                        attacker_team = store.team_manager.get_team(resolved_event.attacker).name
                except Exception:
                    pass
                try:
                    victim_team = store.team_manager.get_team(resolved_event.victim).name
                except Exception:
                    pass

                scoring_record["resolution"] = {
                    "raw_attacker": event.attacker,
                    "resolved_attacker": resolved_event.attacker,
                    "attacker_team": attacker_team,
                    "raw_victim": event.victim,
                    "resolved_victim": resolved_event.victim,
                    "victim_team": victim_team,
                }

                # Determine action type
                is_knock = Icon.KNOCK in resolved_event.icons
                is_finish = Icon.OBJECT in resolved_event.icons
                if is_knock:
                    scoring_record["action_taken"] = "KNOCK"
                elif is_finish:
                    scoring_record["action_taken"] = "FINISH"
                else:
                    scoring_record["action_taken"] = "OTHER"

                # Execute scoring event through StateStore & TeamManager
                snapshot = store.process_event(resolved_event)

                # Compute state diffs
                after_players = {
                    p.name: {
                        "kills": p.kills,
                        "status": p.status.value,
                        "team": t.name,
                    }
                    for t in store.team_manager.teams.values()
                    for p in t.players
                }
                after_teams = {
                    t.name: {
                        "placement": t.placement,
                        "placement_points": t.placement_points,
                        "kills": sum(p.kills for p in t.players),
                        "total": sum(p.kills for p in t.players) + t.placement_points,
                    }
                    for t in store.team_manager.teams.values()
                }

                # Player status changes
                status_diffs = []
                for pname, b_info in before_players.items():
                    a_info = after_players.get(pname, {})
                    if b_info["status"] != a_info.get("status"):
                        status_diffs.append({
                            "player": pname,
                            "team": b_info["team"],
                            "from": b_info["status"],
                            "to": a_info.get("status"),
                        })

                # Kill increments
                kill_diffs = []
                for pname, b_info in before_players.items():
                    a_info = after_players.get(pname, {})
                    if a_info.get("kills", 0) > b_info["kills"]:
                        kill_diffs.append({
                            "player": pname,
                            "team": b_info["team"],
                            "kills_added": a_info["kills"] - b_info["kills"],
                            "new_kills": a_info["kills"],
                        })

                # Placement points changes
                placement_diffs = []
                for tname, b_info in before_teams.items():
                    a_info = after_teams.get(tname, {})
                    if (
                        a_info.get("placement_points", 0) != b_info["placement_points"]
                        or a_info.get("placement") != b_info["placement"]
                    ):
                        placement_diffs.append({
                            "team": tname,
                            "placement": a_info.get("placement"),
                            "placement_points_added": a_info.get("placement_points", 0) - b_info["placement_points"],
                            "total_placement_points": a_info.get("placement_points", 0),
                            "new_total_points": a_info.get("total", 0),
                        })

                scoring_record["state_changes"] = {
                    "player_status_transitions": status_diffs,
                    "kills_awarded": kill_diffs,
                    "placement_points_awarded": placement_diffs,
                    "previous_knocker": before_last_knock.get(resolved_event.victim),
                    "current_last_knocked_by": store.team_manager.last_knocked_by.get(resolved_event.victim),
                }

                # Top 3 standings
                teams_list = snapshot.get("teams", [])
                scoring_record["scoreboard_top3"] = [
                    {
                        "rank": t["rank"],
                        "team": t["team"],
                        "kills": t["kills"],
                        "place": t["place"],
                        "total": t["total"],
                        "eliminated": t.get("eliminated", False),
                    }
                    for t in teams_list[:3]
                ]

            else:
                scoring_record["resolution_error"] = resolution_error
                scoring_record["action_taken"] = "MATCH_FAILED"

        # Save Scoring Trigger JSON
        scoring_json_path = self.scoring_dir / f"{prefix}_scoring.json"
        with open(scoring_json_path, "w", encoding="utf-8") as f:
            json.dump(scoring_record, f, indent=2, ensure_ascii=False)

        # Store in-memory record for report generation
        combined_record = {
            "step": step_id,
            "frame_index": frame_index,
            "timestamp": timestamp_seconds,
            "crop_file": crop_path.name,
            "ocr_input_file": ocr_input_path.name if ocr_input_path else None,
            "annotated_file": annotated_path.name,
            "ml_json_file": ml_json_path.name,
            "scoring_json_file": scoring_json_path.name,
            "ml": ml_record,
            "scoring": scoring_record,
        }
        self.history_records.append(combined_record)
        return combined_record

    def generate_markdown_report(self) -> Path:
        """Generate human-readable PIPELINE_DEBUG_REPORT.md with full timeline & scores."""
        report_path = self.output_dir / "PIPELINE_DEBUG_REPORT.md"
        snap = store.get_match_snapshot()

        lines = [
            "# BGMI Kill-Feed Pipeline Debugging & Trace Report",
            f"\n*Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            f"\n**Total Frames / Steps Processed:** {len(self.history_records)}",
            f"**Current Match Status:** {snap.get('status')}",
            f"**Total Teams Registered:** {len(snap.get('teams', []))}",
            "\n---\n",
            "## 1. Chronological Event & Scoring Timeline\n",
            "| Step | Frame | Time | OCR Attacker | Icon(s) | OCR Victim | Resolved (Team) -> (Team) | Action | Score Impact | Links |",
            "|:----:|:-----:|:----:|:------------:|:-------:|:----------:|:--------------------------:|:------:|:------------:|:-----:|",
        ]

        for rec in self.history_records:
            step = rec["step"]
            f_idx = rec["frame_index"]
            ts = f"{rec['timestamp']:.2f}s"
            ml = rec["ml"]
            sc = rec["scoring"]

            att_text = ml["extracted_entities"].get("attacker_text") or "-"
            vic_text = ml["extracted_entities"].get("victim_text") or "-"
            icons_str = "+".join(ml["assembled_event"]["icons"]) if ml.get("assembled_event") else "-"

            if sc.get("resolution"):
                res = sc["resolution"]
                pair = f"{res['resolved_attacker']} ({res['attacker_team']}) -> {res['resolved_victim']} ({res['victim_team']})"
            else:
                pair = sc.get("resolution_error") or "No Match"

            action = sc.get("action_taken") or ml.get("status")

            # Impact summary
            impact_parts = []
            if sc.get("state_changes"):
                st = sc["state_changes"]
                for k in st.get("kills_awarded", []):
                    impact_parts.append(f"+1 Kill ({k['team']})")
                for pl in st.get("placement_points_awarded", []):
                    impact_parts.append(f"{pl['team']} Place {pl['placement']} (+{pl['placement_points_added']} pts)")
                for tr in st.get("player_status_transitions", []):
                    impact_parts.append(f"{tr['player']} {tr['to'].upper()}")
            impact_str = "<br>".join(impact_parts) if impact_parts else "-"

            links = f"[Crop](frames/{rec['crop_file']}) | [OCR](frames/{rec['ocr_input_file']}) | [Annotated](frames/{rec['annotated_file']})"

            lines.append(
                f"| {step} | {f_idx} | {ts} | `{att_text}` | `{icons_str}` | `{vic_text}` | {pair} | **{action}** | {impact_str} | {links} |"
            )

        lines.extend([
            "\n---\n",
            "## 2. Final Standings Snapshot\n",
            "| Rank | Team | Color | Kills | Placement Pts | Total Points | Status |",
            "|:----:|:----:|:-----:|:-----:|:-------------:|:------------:|:------:|",
        ])

        for t in snap.get("teams", []):
            status_badge = "ELIMINATED" if t.get("eliminated") else "ALIVE"
            lines.append(
                f"| {t['rank']} | **{t['team']}** | `{t.get('color', '#94A3B8')}` | {t['kills']} | {t['place']} | **{t['total']}** | {status_badge} |"
            )

        top_fraggers = snap.get("top_fraggers", [])
        if top_fraggers:
            lines.extend([
                "\n---\n",
                "## 3. Top Fraggers\n",
                "| Rank | Player | Team | Kills | Status |",
                "|:----:|:------:|:----:|:-----:|:------:|",
            ])
            for f in top_fraggers:
                lines.append(
                    f"| {f['rank']} | **{f['player']}** | {f['team']} | {f['kills']} | {f.get('status', 'alive')} |"
                )

        report_content = "\n".join(lines)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return report_path


def run_debug_on_candidates(
    sample_limit: int = 10,
    detections_dir: Optional[Path] = None,
) -> Path:
    """Run debugging pipeline on stored detection frame crops."""
    det_dir = detections_dir or (PROJECT_ROOT / "output" / "mask_detection" / "detections")
    if not det_dir.exists():
        raise FileNotFoundError(f"Detections directory not found: {det_dir}")

    image_files = sorted(list(det_dir.glob("*.jpg")) + list(det_dir.glob("*.png")))
    if not image_files:
        raise FileNotFoundError(f"No image crops found in: {det_dir}")

    total_available = len(image_files)
    selected_files = image_files[:sample_limit]

    print("=" * 70)
    print("BGMI KILL-FEED PIPELINE DEBUGGER")
    print("=" * 70)
    print(f"Candidate images found: {total_available}")
    print(f"Processing first {len(selected_files)} candidate crops...")
    print(f"Output directory: {PROJECT_ROOT / 'output' / 'pipeline_debug'}\n")

    debugger = PipelineDebugger(reset_match_on_start=True)

    for idx, img_path in enumerate(selected_files, start=1):
        crop = cv2.imread(str(img_path))
        if crop is None:
            continue

        # Extract frame index from filename if available (e.g. frame_000034.jpg)
        f_idx = idx
        name_stem = img_path.stem
        if "frame_" in name_stem:
            try:
                f_idx = int(name_stem.replace("frame_", ""))
            except ValueError:
                pass

        ts = f_idx / 30.0  # approximate 30 fps
        rec = debugger.process_frame(crop, frame_index=f_idx, timestamp_seconds=ts)
        ml = rec["ml"]
        sc = rec["scoring"]

        print(
            f"[{rec['step']:03d}/{len(selected_files):03d}] Frame {f_idx:06d} (t={ts:.2f}s) | "
            f"Attacker: '{ml['extracted_entities']['attacker_text']}' | "
            f"Victim: '{ml['extracted_entities']['victim_text']}' | "
            f"Action: {sc.get('action_taken')}"
        )

    report_path = debugger.generate_markdown_report()
    print("\n" + "=" * 70)
    print("DEBUGGING PIPELINE RUN COMPLETE!")
    print(f"Annotated Frames & OCR Inputs: {debugger.frames_dir}")
    print(f"ML Outputs JSON: {debugger.ml_dir}")
    print(f"Scoring Triggers JSON: {debugger.scoring_dir}")
    print(f"Comprehensive Report: {report_path}")
    print("=" * 70)
    return report_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Debug BGMI Killfeed ML Pipeline & Scoring Logic")
    parser.add_argument(
        "--samples",
        type=int,
        default=12,
        help="Number of candidate crops to debug from output/mask_detection/detections (default: 12)",
    )
    args = parser.parse_args()
    run_debug_on_candidates(sample_limit=args.samples)
