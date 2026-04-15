"""
qscope_camera.py
Camera driver for QScope cameras.
Connection type TBD — currently stubbed as OpenCV UVC.
Update this driver once QScope connection method is confirmed.
"""

from core.cameras.opencv_camera import OpenCVCamera


class QScopeCamera(OpenCVCamera):
    """
    QScope camera driver.
    Currently inherits OpenCV UVC capture.
    Will be updated once QScope SDK/connection type is confirmed.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 1280,
        height: int = 960,
    ) -> None:
        super().__init__(
            device_index=device_index,
            width=width,
            height=height,
        )