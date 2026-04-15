"""
qscope_camera.py
Camera driver for Q-Scope USB digital microscopes (Euromex/AmScope).
Confirmed working with USB 2.0 Camera (generic UVC device).

Supported resolutions and framerates (confirmed on Mac via AVFoundation):
    800x600    @ 15 fps
    1024x768   @ 15 fps
    1280x720   @ 30 fps  (only mode with 30fps)
    1280x960   @ 15 fps
    1600x1200  @ 15 fps
    2048x1536  @ 15 fps
    2592x1944  @ 15 fps
    3264x2448  @ 15 fps  (8MP max resolution)

No proprietary SDK required — standard UVC on all platforms.
Controls (brightness, contrast etc) subject to platform UVC support.
On Mac, AVFoundation does not expose UVC property control for this device.
"""

import sys
import logging
from core.cameras.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)

QSCOPE_FORMATS = [
    {'width': 800,  'height': 600,  'fps': [15]},
    {'width': 1024, 'height': 768,  'fps': [15]},
    {'width': 1280, 'height': 720,  'fps': [30]},
    {'width': 1280, 'height': 960,  'fps': [15]},
    {'width': 1600, 'height': 1200, 'fps': [15]},
    {'width': 2048, 'height': 1536, 'fps': [15]},
    {'width': 2592, 'height': 1944, 'fps': [15]},
    {'width': 3264, 'height': 2448, 'fps': [15]},
]

# Default: 1280x720 @ 30fps — best balance of resolution and framerate
DEFAULT_WIDTH  = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS    = 30


class QScopeCamera(OpenCVCamera):
    """
    Q-Scope USB microscope driver.
    Pure UVC — no SDK required.
    Default resolution: 1280x720 @ 30fps.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__(
            device_index=device_index,
            width=width,
            height=height,
        )
        self._target_fps = fps

    def start(self) -> None:
        if sys.platform == 'darwin':
            self._set_avf_format(self._width, self._height, self._target_fps)
        super().start()

    def set_resolution_and_fps(
        self, width: int, height: int, fps: int
    ) -> None:
        """Change resolution and framerate, restarting camera if needed."""
        was_running = self.is_running
        if was_running:
            self.stop()
        self._width = width
        self._height = height
        self._target_fps = fps
        if was_running:
            self.start()

    def get_available_formats(self) -> list:
        return QSCOPE_FORMATS

    def _set_avf_format(
        self, width: int, height: int, fps: int
    ) -> None:
        """Set resolution and framerate via AVFoundation on Mac."""
        try:
            import AVFoundation as AVF
            devices = AVF.AVCaptureDevice.devicesWithMediaType_(
                AVF.AVMediaTypeVideo
            )
            device = None
            for d in devices:
                if 'USB 2.0' in d.localizedName():
                    device = d
                    break

            if device is None:
                logger.warning("QScope (USB 2.0 Camera) not found via AVFoundation")
                return

            formats = device.formats()
            target_format = None
            target_range = None

            for fmt in formats:
                desc = fmt.formatDescription()
                dims = AVF.CMVideoFormatDescriptionGetDimensions(desc)
                if dims.width == width and dims.height == height:
                    for r in fmt.videoSupportedFrameRateRanges():
                        if abs(r.maxFrameRate() - fps) < 1:
                            target_format = fmt
                            target_range = r
                            break
                if target_format:
                    break

            if target_format is None:
                logger.warning(
                    f"QScope format {width}x{height}@{fps}fps not found"
                )
                return

            success, err = device.lockForConfiguration_(None)
            if success:
                device.setActiveFormat_(target_format)
                duration = target_range.minFrameDuration()
                device.setActiveVideoMinFrameDuration_(duration)
                device.setActiveVideoMaxFrameDuration_(duration)
                device.unlockForConfiguration()
                logger.info(
                    f"QScope format set: {width}x{height}@{fps}fps"
                )
            else:
                logger.warning(f"Could not lock QScope for configuration: {err}")

        except Exception as e:
            logger.warning(f"AVFoundation format control failed: {e}")