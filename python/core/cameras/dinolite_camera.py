"""
dinolite_camera.py
Camera driver for Dino-Lite USB microscopes.
Tested with AM4113T-GFBW.

Platform support:
    Mac/Linux:  Live view via OpenCV. Resolution and framerate
                controllable via AVFoundation (Mac only).
                Advanced controls (LED, FLC, AMR) require DNX64 SDK
                which is Windows only.
    Windows:    Full control via DNX64 SDK when installed.
"""

import sys
import logging
from core.cameras.opencv_camera import OpenCVCamera

logger = logging.getLogger(__name__)

_ON_WINDOWS = sys.platform == 'win32'
_ON_MAC = sys.platform == 'darwin'
_DNX64 = None

# Available formats on AM4113T-GFBW
DINOLITE_FORMATS = [
    {'width': 160,  'height': 120,  'fps': [30, 25, 20, 15, 10, 5]},
    {'width': 176,  'height': 144,  'fps': [30, 25, 20, 15, 10, 5]},
    {'width': 320,  'height': 240,  'fps': [30, 25, 20, 15, 10, 5]},
    {'width': 352,  'height': 288,  'fps': [30, 25, 20, 15, 10, 5]},
    {'width': 640,  'height': 480,  'fps': [30, 25, 20, 15, 10, 5]},
    {'width': 1280, 'height': 960,  'fps': [9, 5]},
    {'width': 1280, 'height': 1024, 'fps': [9, 5]},
]


def _load_sdk():
    global _DNX64
    if _DNX64 is not None:
        return _DNX64
    if not _ON_WINDOWS:
        return None
    try:
        import os
        sdk_path = os.environ.get('DINOLITE_SDK_PATH', '')
        if sdk_path:
            sys.path.insert(0, sdk_path)
        from DNX64 import DNX64
        _DNX64 = DNX64()
        logger.info("DNX64 SDK loaded successfully")
        return _DNX64
    except ImportError:
        logger.warning("DNX64 SDK not found.")
        return None


def _sdk_not_available_error(method):
    return NotImplementedError(
        f"DinoLiteCamera.{method}() requires DNX64 SDK (Windows only). "
        f"Current platform: {sys.platform}."
    )


def _get_avf_device():
    """Find the Dino-Lite AVCaptureDevice on Mac."""
    try:
        import AVFoundation as AVF
        devices = AVF.AVCaptureDevice.devicesWithMediaType_(
            AVF.AVMediaTypeVideo
        )
        for d in devices:
            if 'Dino' in d.localizedName():
                return d
    except ImportError:
        pass
    return None


class DinoLiteCamera(OpenCVCamera):
    """
    Dino-Lite camera driver.
    Resolution and framerate controllable on Mac via AVFoundation.
    Advanced controls require DNX64 SDK on Windows.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 1280,
        height: int = 1024,
        fps: int = 9,
    ) -> None:
        super().__init__(
            device_index=device_index,
            width=width,
            height=height,
        )
        self._target_fps = fps
        self._sdk = None

    def start(self) -> None:
        # Set format via AVFoundation before OpenCV opens the device
        if _ON_MAC:
            self._set_avf_format(self._width, self._height, self._target_fps)
        super().start()
        self._sdk = _load_sdk()

    def set_resolution_and_fps(self, width: int, height: int, fps: int) -> None:
        """
        Change resolution and framerate.
        Restarts the camera if already running.
        """
        was_running = self.is_running
        if was_running:
            self.stop()
        self._width = width
        self._height = height
        self._target_fps = fps
        if was_running:
            self.start()

    def get_available_formats(self) -> list:
        """Return list of available formats for this camera."""
        return DINOLITE_FORMATS

    # ------------------------------------------------------------------
    # AVFoundation format control (Mac only)
    # ------------------------------------------------------------------

    def _set_avf_format(
        self, width: int, height: int, fps: int
    ) -> None:
        """Set resolution and framerate via AVFoundation."""
        try:
            import AVFoundation as AVF
            device = _get_avf_device()
            if device is None:
                logger.warning("Dino-Lite not found via AVFoundation")
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
                    f"Format {width}x{height}@{fps}fps not found "
                    f"on Dino-Lite"
                )
                return

            err = device.lockForConfiguration_(None)
            if err:
                device.setActiveFormat_(target_format)
                duration = target_range.minFrameDuration()
                device.setActiveVideoMinFrameDuration_(duration)
                device.setActiveVideoMaxFrameDuration_(duration)
                device.unlockForConfiguration()
                logger.info(
                    f"AVFoundation format set: {width}x{height}@{fps}fps"
                )

        except Exception as e:
            logger.warning(f"AVFoundation format control failed: {e}")

    # ------------------------------------------------------------------
    # LED control (Windows DNX64 SDK only)
    # ------------------------------------------------------------------

    def set_led(self, on: bool) -> None:
        if not self._sdk:
            raise _sdk_not_available_error('set_led')
        self._sdk.SetLEDState(self._device_index, 1 if on else 0)
        logger.info(f"LED {'on' if on else 'off'}")

    def set_flc(
        self,
        top: bool = True,
        bottom: bool = True,
        left: bool = True,
        right: bool = True
    ) -> None:
        if not self._sdk:
            raise _sdk_not_available_error('set_flc')
        mask = (
            (8 if top else 0) |
            (4 if bottom else 0) |
            (2 if left else 0) |
            (1 if right else 0)
        )
        self._sdk.SetFLCMode(self._device_index, mask)
        logger.info(f"FLC mask:{mask:#04b}")

    def set_led_intensity(self, intensity: int) -> None:
        if not self._sdk:
            raise _sdk_not_available_error('set_led_intensity')
        intensity = max(0, min(100, intensity))
        self._sdk.SetLEDIntensity(self._device_index, intensity)
        logger.info(f"LED intensity: {intensity}%")

    # ------------------------------------------------------------------
    # Magnification (Windows DNX64 SDK only)
    # ------------------------------------------------------------------

    def get_magnification(self) -> float:
        if not self._sdk:
            raise _sdk_not_available_error('get_magnification')
        return float(self._sdk.GetMagnification(self._device_index))

    # ------------------------------------------------------------------
    # MicroTouch (Windows DNX64 SDK only)
    # ------------------------------------------------------------------

    def is_microtouch_pressed(self) -> bool:
        if not self._sdk:
            raise _sdk_not_available_error('is_microtouch_pressed')
        return bool(self._sdk.GetMicroTouch(self._device_index))

    # ------------------------------------------------------------------
    # AXI (Windows DNX64 SDK only)
    # ------------------------------------------------------------------

    def set_axi(self, on: bool) -> None:
        if not self._sdk:
            raise _sdk_not_available_error('set_axi')
        self._sdk.SetAXI(self._device_index, 1 if on else 0)
        logger.info(f"AXI: {'on' if on else 'off'}")