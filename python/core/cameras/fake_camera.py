"""
fake_camera.py
In-memory fake camera for development and testing.
Generates synthetic frames with a timestamp and frame counter.
No hardware required.

Usage:
    cam = FakeCamera(width=640, height=480)
    cam.start()
    frame = cam.get_frame()  # numpy array (H, W, 3)
    cam.stop()
"""

import logging
import time
import numpy as np
import cv2

from core.camera_interface import CameraInterface

logger = logging.getLogger(__name__)


class FakeCamera(CameraInterface):
    """
    Fake camera that generates synthetic frames.
    Each frame shows a gradient background with a timestamp
    and frame counter so you can verify the feed is live.
    """

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self._width = width
        self._height = height
        self._running = False
        self._frame_count = 0

    def start(self) -> None:
        self._running = True
        self._frame_count = 0
        logger.info(
            f"FakeCamera started ({self._width}x{self._height})"
        )

    def stop(self) -> None:
        self._running = False
        logger.info("FakeCamera stopped")

    def get_frame(self) -> np.ndarray:
        if not self._running:
            return None

        self._frame_count += 1

        # Generate a simple gradient background
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        for x in range(self._width):
            intensity = int(x / self._width * 180)
            frame[:, x] = (intensity, 80, 180 - intensity)

        # Draw a moving circle so it's obvious the feed is live
        t = time.time()
        cx = int((np.sin(t) * 0.3 + 0.5) * self._width)
        cy = int((np.cos(t * 0.7) * 0.3 + 0.5) * self._height)
        cv2.circle(frame, (cx, cy), 30, (255, 255, 255), -1)

        # Overlay timestamp and frame count
        timestamp = time.strftime('%H:%M:%S')
        cv2.putText(
            frame,
            f'FAKE  {timestamp}  frame {self._frame_count}',
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (255, 255, 255), 2
        )

        return frame

    def capture_image(self, path: str) -> None:
        frame = self.get_frame()
        if frame is not None:
            cv2.imwrite(path, frame)
            logger.info(f"FakeCamera: saved frame to {path}")

    @property
    def is_running(self) -> bool:
        return self._running