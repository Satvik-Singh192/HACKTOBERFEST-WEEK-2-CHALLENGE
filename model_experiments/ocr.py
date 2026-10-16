import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Pre-load PyTorch DLLs on Windows to avoid DLL load conflicts with PaddlePaddle
try:
    venv_site = Path(sys.executable).parent.parent / "Lib" / "site-packages"
    torch_lib = venv_site / "torch" / "lib"
    if torch_lib.is_dir() and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(torch_lib))
    import torch
except Exception:
    pass

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_onednn_fuse_conv_bn"] = "0"

import cv2
import numpy as np
import paddle
import paddle.inference

try:
    paddle.set_flags({"FLAGS_use_mkldnn": False})
except Exception:
    pass

# Paddle 3.0+ enables OneDNN by default on CPU, which has a known bug with fused_conv2d in MobileNetV3.
# Wrapping create_predictor ensures OneDNN and MKLDNN are always disabled for crash-free execution.
_orig_create_predictor = paddle.inference.create_predictor

def _safe_create_predictor(config):
    try:
        config.disable_onednn()
        config.disable_mkldnn()
    except Exception:
        pass
    return _orig_create_predictor(config)

paddle.inference.create_predictor = _safe_create_predictor

from paddleocr import PaddleOCR


class SingleRowKillfeedOCR:
    def __init__(self, min_ocr_conf: float = 0.75):
        self.min_ocr_conf = min_ocr_conf

        # Check for local workspace model weights
        local_paddle = Path(__file__).resolve().parent.parent / ".paddleocr"
        det_dir = None
        rec_dir = None
        cls_dir = None
        if local_paddle.is_dir():
            d = local_paddle / "whl" / "det" / "en" / "en_PP-OCRv3_det_infer"
            r = local_paddle / "whl" / "rec" / "en" / "en_PP-OCRv4_rec_infer"
            c = local_paddle / "whl" / "cls" / "ch_ppocr_mobile_v2.0_cls_infer"
            if d.is_dir():
                det_dir = str(d)
            if r.is_dir():
                rec_dir = str(r)
            if c.is_dir():
                cls_dir = str(c)

        # PaddleOCR configured for sensitive extraction of small HUD fonts with OneDNN disabled to avoid fused_conv2d crash on Windows
        ocr_kwargs = {
            "use_angle_cls": False,
            "lang": "en",
            "show_log": False,
            "enable_mkldnn": False,
            "use_gpu": False,
            "det_db_thresh": 0.2,       # Catches low-contrast text edges
            "det_db_box_thresh": 0.3,   # Preserves smaller character bounding boxes
            "det_db_unclip_ratio": 1.8, # Avoids clipping thin letter edges
        }
        if det_dir:
            ocr_kwargs["det_model_dir"] = det_dir
        if rec_dir:
            ocr_kwargs["rec_model_dir"] = rec_dir
        if cls_dir:
            ocr_kwargs["cls_model_dir"] = cls_dir

        self.ocr = PaddleOCR(**ocr_kwargs)

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

    def extract(self, img_bgr: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Extracts attacker (leftmost text), victim (rightmost text), 
        and the middle icon coordinate bounds without any roster dependency.
        """
        h, w = img_bgr.shape[:2]
        processed_img, scale = self.preprocess(img_bgr, scale=2.0)

        # Run OCR inference
        results = self.ocr.ocr(processed_img, cls=False)
        if not results or not results[0]:
            return None

        detected_entities = []
        for line in results[0]:
            box, (text, conf) = line
            clean_text = text.strip()

            # Strict confidence threshold filter
            if float(conf) < self.min_ocr_conf or not clean_text:
                continue

            # Re-scale bounding box coordinates back to original image dimensions
            x_min = int(min(pt[0] for pt in box) / scale)
            x_max = int(max(pt[0] for pt in box) / scale)

            detected_entities.append({
                "text": clean_text,
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
                "text": attacker["text"],
                "confidence": attacker["confidence"]
            },
            "victim": {
                "text": victim["text"],
                "confidence": victim["confidence"]
            },
            "icon_x_bounds": (attacker["x_max"], victim["x_min"]),
            "avg_confidence": round((attacker["confidence"] + victim["confidence"]) / 2, 2)
        }
