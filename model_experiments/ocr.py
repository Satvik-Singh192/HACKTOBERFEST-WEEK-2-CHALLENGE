

from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from paddleocr import PaddleOCR
from rapidfuzz import fuzz, process


class SingleRowKillfeedOCR:
    def __init__(self, min_ocr_conf: float = 0.75, fuzzy_threshold: int = 65):

        self.min_ocr_conf = min_ocr_conf
        self.fuzzy_threshold = fuzzy_threshold

        # PaddleOCR configured for sensitive extraction of small HUD fonts
        self.ocr = PaddleOCR(
            use_angle_cls=False,
            lang="en",
            show_log=False,
            det_db_thresh=0.2,       # Catches low-contrast text edges
            det_db_box_thresh=0.3,   # Preserves smaller character bounding boxes
            det_db_unclip_ratio=1.8  # Avoids clipping thin letter edges
        )

    def preprocess(self, img_bgr: np.ndarray, scale: float = 2.0) -> Tuple[np.ndarray, float]:

        h, w = img_bgr.shape[:2]

        # 1. 2x bilinear upscale
        upscaled = cv2.resize(
            img_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_LINEAR
        )

        # 2. Grayscale conversion & CLAHE adaptive contrast
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR), scale

    def _build_player_team_lookup(self, team_roster: Dict[str, List[str]]) -> Tuple[List[str], Dict[str, str]]:
        """
        Flattens {Team: [Players]} into:
        1. A flat list of all players (plus 'Playzone') for RapidFuzz matching.
        2. A lookup mapping { PlayerName: TeamName }.
        """
        player_to_team = {}
        all_players = []

        for team_name, players in team_roster.items():
            for player in players:
                player_to_team[player] = team_name
                all_players.append(player)

        # Ensure Playzone is recognized as its own entity
        if "Playzone" not in player_to_team:
            player_to_team["Playzone"] = "Playzone"
            all_players.append("Playzone")

        return all_players, player_to_team

    def _resolve_name(
        self, raw_text: str, all_players: List[str], player_to_team: Dict[str, str]
    ) -> Optional[Tuple[str, str]]:
        """
        Fuzzy matches raw text against known players.
        Returns: (resolved_player_name, team_name) or None.
        """
        if not all_players:
            return None

        match = process.extractOne(raw_text, all_players, scorer=fuzz.ratio)
        if match and match[1] >= self.fuzzy_threshold:
            player_name = match[0]
            team_name = player_to_team.get(player_name, "Unknown")
            return player_name, team_name

        return None

    def extract(self, img_bgr: np.ndarray, team_roster: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:

        h, w = img_bgr.shape[:2]
        processed_img, scale = self.preprocess(img_bgr, scale=2.0)

        # Build dynamic lookup mappings
        all_players, player_to_team = self._build_player_team_lookup(
            team_roster)

        # Run OCR inference
        results = self.ocr.ocr(processed_img, cls=False)
        if not results or not results[0]:
            return None

        detected_entities = []
        for line in results[0]:
            box, (text, conf) = line
            clean_text = text.strip()

            # Strict 0.75 confidence threshold filter
            if float(conf) < self.min_ocr_conf or not clean_text:
                continue

            resolved = self._resolve_name(
                clean_text, all_players, player_to_team)
            if resolved:
                player_name, team_name = resolved

                # Re-scale bounding box coordinates back to original image dimensions
                x_min = int(min(pt[0] for pt in box) / scale)
                x_max = int(max(pt[0] for pt in box) / scale)

                detected_entities.append({
                    "player": player_name,
                    "team": team_name,
                    "raw_text": clean_text,
                    "confidence": round(float(conf), 2),
                    "x_min": x_min,
                    "x_max": x_max
                })

        # Require at least Attacker (left) and Victim (right)
        if len(detected_entities) < 2:
            return None

        # Sort left-to-right
        detected_entities.sort(key=lambda item: item["x_min"])
        attacker = detected_entities[0]
        victim = detected_entities[-1]

        # Prevent overlapping bounding boxes
        if attacker["x_max"] >= victim["x_min"]:
            return None

        return {
            "attacker": {
                "player": attacker["player"],
                "team": attacker["team"],
                "raw_text": attacker["raw_text"],
                "confidence": attacker["confidence"]
            },
            "victim": {
                "player": victim["player"],
                "team": victim["team"],
                "raw_text": victim["raw_text"],
                "confidence": victim["confidence"]
            },
            "icon_x_bounds": (attacker["x_max"], victim["x_min"]),
            "avg_confidence": round((attacker["confidence"] + victim["confidence"]) / 2, 2)
        }
