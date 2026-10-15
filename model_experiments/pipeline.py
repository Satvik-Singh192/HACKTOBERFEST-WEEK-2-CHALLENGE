from typing import Any, Dict, Optional
import time
import cv2
import numpy as np
from ultralytics import YOLO
from backend.events import Event
from backend.events import Event, Icon

# Import preprocessing & OCR engine directly from your existing ocr.py
from .ocr import SingleRowKillfeedOCR

class KillfeedPipeline:
    def __init__(
        self,
        yolo_weights_path: str = r"D:\Attendance_ml\runs\detect\train\weights\best.pt",
        min_ocr_conf: float = 0.50,
        yolo_conf: float = 0.25,
        imgsz: int = 352,
    ):
        self.min_ocr_conf = min_ocr_conf
        self.yolo_conf = yolo_conf
        self.imgsz = imgsz

        # Use your ocr instance from ocr.py
        self.ocr_engine = SingleRowKillfeedOCR(min_ocr_conf=min_ocr_conf)
        self.icon_model = YOLO(yolo_weights_path)

    def process(self, image_input: Any) -> Optional[Dict[str, str]]:
        t_total_start = time.perf_counter()

        # --- Phase 1: Image Load ---
        t0 = time.perf_counter()
        if isinstance(image_input, str):
            frame = cv2.imread(image_input)
            if frame is None:
                print(f"[ERROR] Could not load image from: {image_input}")
                return None
        else:
            frame = image_input
        t_load = time.perf_counter() - t0

        # --- Phase 2: OCR Preprocessing ---
        t0 = time.perf_counter()
        ocr_input, scale = self.ocr_engine.preprocess(frame, scale=2.0)
        t_preprocess = time.perf_counter() - t0

        # --- Phase 3: OCR Inference ---
        t0 = time.perf_counter()
        results = self.ocr_engine.ocr.ocr(ocr_input, cls=False)
        t_ocr_infer = time.perf_counter() - t0

        # --- Phase 4: OCR Box Parsing & Entity Extraction ---
        t0 = time.perf_counter()
        if not results or not results[0]:
            print("[OCR] No text detected.")
            return None

        words = []
        for line in results[0]:
            box = line[0]
            text, conf = line[1]
            clean_text = text.strip()

            if float(conf) >= self.min_ocr_conf and clean_text:
                x_min = int(min(pt[0] for pt in box) / scale)
                x_max = int(max(pt[0] for pt in box) / scale)
                words.append(
                    {"text": clean_text, "x_min": x_min, "x_max": x_max}
                )

        if len(words) < 2:
            print(
                f"[OCR] Only found {len(words)} word(s): {[w['text'] for w in words]}"
            )
            return None

        words.sort(key=lambda w: w["x_min"])
        attacker_text = words[0]["text"]
        victim_text = words[-1]["text"]
        x_left = words[0]["x_max"]
        x_right = words[-1]["x_min"]
        t_ocr_parse = time.perf_counter() - t0

        # --- Phase 5: YOLO Prediction ---
        t0 = time.perf_counter()
        yolo_res = self.icon_model.predict(
            source=frame,
            conf=self.yolo_conf,
            imgsz=self.imgsz,
            verbose=False,
        )[0]
        t_yolo_infer = time.perf_counter() - t0

        # --- Phase 6: Spatial Association & Resolution ---
        t0 = time.perf_counter()
        detected_icons = []
        for box in yolo_res.boxes:
            cls_id = int(box.cls[0])
            cls_name = self.icon_model.names[cls_id].lower()
            detected_icons.append(cls_name)
            #changed to list 

        # middle_classes = [
        #     icon["class"]
        #     for icon in detected_icons
        #     if x_left <= icon["x_center"] <= x_right
        # ]

        # if "knock" in middle_classes:
        #     resolved_icon = "knock"
        # elif "playzone" in middle_classes:
        #     resolved_icon = "playzone"
        # else:
        #     resolved_icon = "object"
        t_postprocess = time.perf_counter() - t0

        t_total = time.perf_counter() - t_total_start


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

        eventobject = Event(
            attacker=attacker_text,
            icons=icons,
            victim=victim_text,
        )

        return eventobject
