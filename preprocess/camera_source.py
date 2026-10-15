"""Live camera frame source for OBS Virtual Camera capture."""

from __future__ import annotations

import time
from typing import Iterator
import cv2
import numpy as np

from .pipeline import FramePacket


class OBSCameraSource:
    """Read live frames from OBS Virtual Camera or local video capture device."""

    def __init__(
        self,
        camera_index: int = 0,
        target_fps: int = 30,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        self.camera_index = camera_index
        self.target_fps = target_fps
        self.width = width
        self.height = height

    def frames(self) -> Iterator[FramePacket]:
        print(f"Connecting to OBS Virtual Camera at device index {self.camera_index}...")

        # Use DirectShow backend on Windows for lowest latency & fastest capture
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        # Request native 1080p resolution and target frame rate
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        if not cap.isOpened():
            cap.release()
            raise RuntimeError(
                f"Cannot open camera at index {self.camera_index}.\n"
                "Please make sure OBS Studio is running and 'Start Virtual Camera' is clicked in the Controls dock."
            )

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)

        print("OBS Virtual Camera connected successfully!")
        print(f"Resolution: {actual_w}x{actual_h}")
        print(f"FPS: {actual_fps:.2f}\n")

        frame_idx = 0
        start_time = time.time()

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.005)
                    continue

                # Ensure dimensions match expected 1080p canvas
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(
                        frame,
                        (self.width, self.height),
                        interpolation=cv2.INTER_LINEAR,
                    )

                yield FramePacket(
                    frame_index=frame_idx,
                    timestamp_seconds=time.time() - start_time,
                    frame_bgr=frame,
                )
                frame_idx += 1

        except KeyboardInterrupt:
            print("\nStopping OBS Virtual Camera capture...")
        finally:
            cap.release()
            print("OBS Virtual Camera device released.")


def list_available_cameras(max_probe: int = 4) -> list[int]:
    """Check camera indices 0 through max_probe to find connected capture devices."""
    available = []
    for idx in range(max_probe):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            available.append(idx)
            cap.release()
    return available
