"""
opencv_camera.py
Real camera implementation using OpenCV VideoCapture.
Works with any UVC camera including Dino-Lite on Mac/Linux/Windows.

Usage:
    cam = OpenCVCamera(device_index=0)
    cam.start()
    frame = cam.get_frame()
    cam.stop()
"""

import logging
import cv2
import numpy as np

from core.camera_interface import CameraInterface

logger = logging.getLogger(__name__)


class OpenCVCamera(CameraInterface):
    """
    Camera driver using OpenCV VideoCapture.
    Works with any UVC-compatible camera.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 1280,
        height: int = 960,
    ) -> None:
        """
        Args:
            device_index: camera index (0 = first camera, 1 = second, etc.)
            width:        requested frame width in pixels
            height:       requested frame height in pixels
        """
        self._device_index = device_index
        self._width = width
        self._height = height
        self._cap = None
        self._running = False

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {self._device_index}. "
                f"Check that the camera is connected and not in use."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._running = True
        logger.info(
            f"OpenCVCamera started on index {self._device_index} "
            f"({self._width}x{self._height})"
        )

    def stop(self) -> None:
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("OpenCVCamera stopped")

    def get_frame(self) -> np.ndarray:
        if not self._running or self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            logger.warning("OpenCVCamera: failed to read frame")
            return None
        return frame

    def capture_image(self, path: str) -> None:
        frame = self.get_frame()
        if frame is not None:
            cv2.imwrite(path, frame)
            logger.info(f"OpenCVCamera: saved frame to {path}")
        else:
            logger.warning("OpenCVCamera: no frame to capture")

    @property
    def is_running(self) -> bool:
        return self._running