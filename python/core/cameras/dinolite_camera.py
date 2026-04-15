"""
dinolite_camera.py
Camera driver for Dino-Lite USB microscopes.
Tested with AM4113T-GFBW (1.3MP, UVC compatible, Mac/Win/Linux).
Uses OpenCV VideoCapture — no SDK required for frame capture.
Advanced controls (LED, FLC) require DNX64 SDK — Windows only.
"""

from core.cameras.opencv_camera import OpenCVCamera


class DinoLiteCamera(OpenCVCamera):
    """
    Dino-Lite camera driver.
    AM4113T native resolution: 1280x1024.
    Inherits OpenCV UVC capture.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 1280,
        height: int = 1024,
    ) -> None:
        super().__init__(
            device_index=device_index,
            width=width,
            height=height,
        )

    # DNX64 SDK methods (Windows only) — to be added when SDK available:
    # def set_led(self, on: bool) -> None: ...
    # def set_flc(self, intensity: int) -> None: ...
    # def get_magnification(self) -> float: ...