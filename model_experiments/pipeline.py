from typing import Any, Dict, Optional, Tuple
import time
import cv2
import numpy as np
from pathlib import Path
from backend.events import Event, Icon

# Import preprocessing & OCR engine directly from your existing ocr.py before torch/YOLO
from .ocr import SingleRowKillfeedOCR

class KillfeedPipeline:
    def __init__(
        self,
        yolo_weights_path: Optional[str] = None,
        min_ocr_conf: float = 0.50,
        yolo_conf: float = 0.25,
        imgsz: int = 352,
    ):
        self.min_ocr_conf = min_ocr_conf
        self.yolo_conf = yolo_conf
        self.imgsz = imgsz

        # Initialize OCR engine
        self.ocr_engine = SingleRowKillfeedOCR(min_ocr_conf=min_ocr_conf)

        # Optional YOLO model
        self.icon_model = None
        if yolo_weights_path and Path(yolo_weights_path).exists():
            try:
                from ultralytics import YOLO
                self.icon_model = YOLO(yolo_weights_path)
            except Exception as e:
                print(f"[Notice] YOLO model could not be loaded ({e}). Running in OCR-only mode.")
        else:
            print("[Notice] YOLO model skipped or weights not found. Running in OCR-only mode.")

    def process_debug(self, image_input: Any) -> Tuple[Optional[Event], Dict[str, Any]]:
        """Process candidate crop and return both the Event and complete intermediate debug artifacts."""
        t_total_start = time.perf_counter()
        debug_info: Dict[str, Any] = {
            "crop": None,
            "ocr_input": None,
            "scale": 2.0,
            "ocr_raw": [],
            "words": [],
            "attacker_text": None,
            "victim_text": None,
            "yolo_detections": [],
            "detected_icons": [],
            "icons": [],
            "event": None,
            "status": "INIT",
            "timings": {},
        }

        # --- Phase 1: Image Load ---
        t0 = time.perf_counter()
        if isinstance(image_input, (str, Path)):
            frame = cv2.imread(str(image_input))
            if frame is None:
                debug_info["status"] = f"IMAGE_LOAD_FAILED: {image_input}"
                return None, debug_info
        else:
            frame = image_input
        debug_info["crop"] = frame.copy() if frame is not None else None
        debug_info["timings"]["load"] = time.perf_counter() - t0

        if frame is None or frame.size == 0:
            debug_info["status"] = "EMPTY_FRAME"
            return None, debug_info

        # --- Phase 2: OCR Preprocessing ---
        t0 = time.perf_counter()
        ocr_input, scale = self.ocr_engine.preprocess(frame, scale=2.0)
        debug_info["ocr_input"] = ocr_input.copy()
        debug_info["scale"] = scale
        debug_info["timings"]["preprocess"] = time.perf_counter() - t0

        # --- Phase 3: OCR Inference ---
        t0 = time.perf_counter()
        results = self.ocr_engine.ocr.ocr(ocr_input, cls=False)
        debug_info["timings"]["ocr_infer"] = time.perf_counter() - t0

        if not results or not results[0]:
            debug_info["status"] = "NO_TEXT_DETECTED"
            debug_info["timings"]["total"] = time.perf_counter() - t_total_start
            return None, debug_info

        # --- Phase 4: OCR Box Parsing & Entity Extraction ---
        t0 = time.perf_counter()
        words = []
        raw_ocr = []
        for line in results[0]:
            box = line[0]
            text, conf = line[1]
            clean_text = text.strip()
            raw_ocr.append({
                "text": clean_text,
                "confidence": round(float(conf), 3),
                "box": box,
            })

            if float(conf) >= self.min_ocr_conf and clean_text:
                x_min = int(min(pt[0] for pt in box) / scale)
                x_max = int(max(pt[0] for pt in box) / scale)
                y_min = int(min(pt[1] for pt in box) / scale)
                y_max = int(max(pt[1] for pt in box) / scale)
                words.append({
                    "text": clean_text,
                    "confidence": round(float(conf), 3),
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                    "box": box,
                })

        debug_info["ocr_raw"] = raw_ocr
        debug_info["words"] = words

        if len(words) < 2:
            debug_info["status"] = f"INSUFFICIENT_WORDS: found {len(words)} word(s)"
            debug_info["timings"]["total"] = time.perf_counter() - t_total_start
            return None, debug_info

        words.sort(key=lambda w: w["x_min"])
        attacker_text = words[0]["text"]
        victim_text = words[-1]["text"]
        debug_info["attacker_text"] = attacker_text
        debug_info["victim_text"] = victim_text
        debug_info["timings"]["ocr_parse"] = time.perf_counter() - t0

        # --- Phase 5: YOLO Prediction ---
        t0 = time.perf_counter()
        detected_icons = []
        yolo_detections = []
        if self.icon_model is not None:
            try:
                yolo_res = self.icon_model.predict(
                    source=frame,
                    conf=self.yolo_conf,
                    imgsz=self.imgsz,
                    verbose=False,
                )[0]
                for box in yolo_res.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = self.icon_model.names[cls_id].lower()
                    conf = float(box.conf[0])
                    xyxy = [int(v) for v in box.xyxy[0].tolist()]
                    detected_icons.append(cls_name)
                    yolo_detections.append({
                        "class": cls_name,
                        "confidence": round(conf, 3),
                        "box": xyxy,
                    })
            except Exception as e:
                print(f"[Warning] YOLO inference error: {e}")
                detected_icons.append("obj")
        else:
            detected_icons.append("obj")
            yolo_detections.append({
                "class": "obj",
                "confidence": 1.0,
                "box": None,
                "source": "fallback_default",
            })

        debug_info["detected_icons"] = detected_icons
        debug_info["yolo_detections"] = yolo_detections
        debug_info["timings"]["yolo_infer"] = time.perf_counter() - t0

        # --- Phase 6: Event Assembly ---
        icon_mapping = {
            "playzone": Icon.PLAYZONE,
            "knock": Icon.KNOCK,
            "object": Icon.OBJECT,
            "obj": Icon.OBJECT,
            "zone": Icon.PLAYZONE,
        }

        icons = [
            icon_mapping[name.lower()]
            for name in detected_icons
            if name.lower() in icon_mapping
        ]
        if not icons:
            icons = [Icon.OBJECT]

        debug_info["icons"] = [i.value for i in icons]

        eventobject = Event(
            attacker=attacker_text,
            icons=icons,
            victim=victim_text,
        )
        debug_info["event"] = eventobject
        debug_info["status"] = "SUCCESS"
        debug_info["timings"]["total"] = time.perf_counter() - t_total_start

        return eventobject, debug_info

    def process(self, image_input: Any) -> Optional[Event]:
        event, _ = self.process_debug(image_input)
        return event
