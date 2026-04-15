"""
camera_panel.py
PyQt5 panel for live camera feed.
Camera type and index are selectable from the GUI.
Panel is collapsible — click Camera >> to expand, << to collapse.
Settings open in a floating dialog.
"""

import logging
import os
import sys
import time

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QSizePolicy,
    QComboBox, QSpinBox, QWidget, QSlider, QCheckBox,
    QDialog, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap

from core.camera_interface import CameraInterface

logger = logging.getLogger(__name__)

DEFAULT_SAVE_DIR = os.path.expanduser('~/Pictures/fluidic_control')
CAMERA_TYPES = ['Dino-Lite', 'QScope', 'Generic USB', 'Fake']


# ------------------------------------------------------------------
# Helper: make a labelled slider
# ------------------------------------------------------------------

def make_slider(
    parent,
    label: str,
    min_val: int,
    max_val: int,
    default: int
) -> dict:
    """
    Create a labelled horizontal slider.
    Returns dict with keys: layout, slider, label.
    parent is the object whose _on_slider_changed will be called.
    """
    layout = QHBoxLayout()

    lbl = QLabel(f'{label}:')
    lbl.setFixedWidth(100)
    layout.addWidget(lbl)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(default)
    layout.addWidget(slider)

    val_lbl = QLabel(str(default))
    val_lbl.setFixedWidth(40)
    layout.addWidget(val_lbl)

    slider.valueChanged.connect(
        lambda v, l=val_lbl, n=label: parent._on_slider_changed(n, v, l)
    )

    return {'layout': layout, 'slider': slider, 'label': val_lbl}


# ------------------------------------------------------------------
# Settings dialog
# ------------------------------------------------------------------

class CameraSettingsDialog(QDialog):
    """Floating, non-blocking camera settings dialog."""

    def __init__(self, panel: 'CameraPanel') -> None:
        super().__init__(panel)
        self._panel = panel
        self.setWindowTitle('Camera Settings')
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint |
            Qt.WindowCloseButtonHint
        )
        self.setModal(False)
        self._formats = []
        self._init_ui()
        self.resize(360, 420)

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        tabs = QTabWidget()

        # ----------------------------------------------------------
        # Tab 1: Image controls
        # ----------------------------------------------------------
        image_tab = QWidget()
        image_layout = QVBoxLayout()
        image_layout.setSpacing(6)

        self.contrast_slider  = make_slider(self, 'Contrast',  0, 255, 128)
        self.saturation_slider = make_slider(self, 'Saturation', 0, 255, 128)
        self.gain_slider      = make_slider(self, 'Gain',      0, 255, 0)
        self.sharpness_slider = make_slider(self, 'Sharpness', 0, 255, 128)

        for s in [self.contrast_slider, self.saturation_slider,
                  self.gain_slider, self.sharpness_slider]:
            image_layout.addLayout(s['layout'])

        self.auto_wb_chk = QCheckBox('Auto White Balance')
        self.auto_wb_chk.setChecked(True)
        self.auto_wb_chk.stateChanged.connect(self._on_auto_wb_changed)
        image_layout.addWidget(self.auto_wb_chk)

        self.wb_slider = make_slider(self, 'White Balance', 2000, 7500, 4500)
        self.wb_slider['slider'].setEnabled(False)
        image_layout.addLayout(self.wb_slider['layout'])

        mac_note = QLabel(
            'Note: UVC property control not supported on macOS.'
            if sys.platform == 'darwin' else ''
        )
        mac_note.setStyleSheet('color: orange; font-size: 10px;')
        mac_note.setWordWrap(True)
        image_layout.addWidget(mac_note)

        image_layout.addStretch()
        image_tab.setLayout(image_layout)
        tabs.addTab(image_tab, 'Image')

        # ----------------------------------------------------------
        # Tab 2: Resolution / FPS
        # ----------------------------------------------------------
        res_tab = QWidget()
        res_layout = QVBoxLayout()
        res_layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel('Resolution:'))
        self.resolution_combo = QComboBox()
        self.resolution_combo.currentIndexChanged.connect(
            self._on_resolution_changed
        )
        row1.addWidget(self.resolution_combo)
        res_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('FPS:'))
        self.fps_combo = QComboBox()
        row2.addWidget(self.fps_combo)
        res_layout.addLayout(row2)

        self.apply_res_btn = QPushButton('Apply Resolution / FPS')
        self.apply_res_btn.clicked.connect(self._apply_format)
        res_layout.addWidget(self.apply_res_btn)

        res_layout.addStretch()
        res_tab.setLayout(res_layout)
        tabs.addTab(res_tab, 'Resolution / FPS')

        # ----------------------------------------------------------
        # Tab 3: Dino-Lite specific (LED etc)
        # ----------------------------------------------------------
        dino_tab = QWidget()
        dino_layout = QVBoxLayout()
        dino_layout.setSpacing(6)

        led_note = QLabel('LED controls require DNX64 SDK (Windows only).')
        led_note.setStyleSheet('color: gray; font-size: 10px;')
        led_note.setWordWrap(True)
        dino_layout.addWidget(led_note)

        led_row = QHBoxLayout()
        led_on_btn = QPushButton('LED On')
        led_on_btn.clicked.connect(lambda: self._panel._set_led(True))
        led_off_btn = QPushButton('LED Off')
        led_off_btn.clicked.connect(lambda: self._panel._set_led(False))
        led_row.addWidget(led_on_btn)
        led_row.addWidget(led_off_btn)
        dino_layout.addLayout(led_row)

        self.intensity_slider = make_slider(self, 'LED Intensity', 0, 100, 100)
        self.intensity_slider['slider'].valueChanged.connect(
            lambda v: self._panel._set_led_intensity(v)
        )
        dino_layout.addLayout(self.intensity_slider['layout'])

        dino_layout.addStretch()
        dino_tab.setLayout(dino_layout)
        tabs.addTab(dino_tab, 'Dino-Lite')

        layout.addWidget(tabs)
        self.setLayout(layout)

    def refresh_formats(self) -> None:
        """Reload format list based on currently selected camera type."""
        camera_type = self._panel.camera_type_combo.currentText()
        self.resolution_combo.blockSignals(True)
        self.resolution_combo.clear()

        if camera_type == 'Dino-Lite':
            from core.cameras.dinolite_camera import DINOLITE_FORMATS
            self._formats = DINOLITE_FORMATS
            default_index = 6  # 1280x1024
        elif camera_type == 'QScope':
            from core.cameras.qscope_camera import QSCOPE_FORMATS
            self._formats = QSCOPE_FORMATS
            default_index = 2  # 1280x720 @ 30fps
        else:
            self._formats = []
            self.resolution_combo.blockSignals(False)
            return

        for fmt in self._formats:
            self.resolution_combo.addItem(
                f"{fmt['width']}x{fmt['height']}"
            )
        self.resolution_combo.blockSignals(False)
        self.resolution_combo.setCurrentIndex(default_index)
        self._update_fps_combo(default_index)

    def _update_fps_combo(self, format_index: int) -> None:
        self.fps_combo.clear()
        if not self._formats or format_index >= len(self._formats):
            return
        for fps in self._formats[format_index]['fps']:
            self.fps_combo.addItem(f'{fps} fps', fps)

    def _on_resolution_changed(self, index: int) -> None:
        self._update_fps_combo(index)

    def _apply_format(self) -> None:
        cam = self._panel._camera
        if not cam:
            return
        if not self._formats:
            return
        fmt = self._formats[self.resolution_combo.currentIndex()]
        fps = self.fps_combo.currentData()
        if hasattr(cam, 'set_resolution_and_fps'):
            cam.set_resolution_and_fps(fmt['width'], fmt['height'], fps)
            self._panel.status_label.setText(
                f"Format: {fmt['width']}x{fmt['height']}@{fps}fps"
            )

    def _on_auto_wb_changed(self, state: int) -> None:
        auto = state == Qt.Checked
        self.wb_slider['slider'].setEnabled(not auto)
        self._panel._set_cv2_prop('White Balance', None, auto_wb=auto)

    def _on_slider_changed(self, name: str, value: int, label: QLabel) -> None:
        label.setText(str(value))
        self._panel._set_cv2_prop(name, value)


# ------------------------------------------------------------------
# Camera panel
# ------------------------------------------------------------------

class CameraPanel(QGroupBox):
    """Collapsible panel with live camera feed and camera selection."""

    def __init__(self) -> None:
        super().__init__('')
        self._camera = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)
        self._frame_count = 0
        self._expanded = False
        self._settings_dialog = None
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout()
        outer_layout.setSpacing(6)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # Toggle button — always visible
        toggle_row = QHBoxLayout()
        self.toggle_btn = QPushButton('Camera  ▶▶')
        self.toggle_btn.setFixedWidth(150)
        self.toggle_btn.clicked.connect(self._toggle)
        toggle_row.addWidget(self.toggle_btn)
        toggle_row.addStretch()
        outer_layout.addLayout(toggle_row)

        # Collapsible content
        self.content = QWidget()
        cl = QVBoxLayout()
        cl.setSpacing(6)
        cl.setContentsMargins(0, 0, 0, 0)

        # Camera type and index
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel('Camera:'))
        self.camera_type_combo = QComboBox()
        for t in CAMERA_TYPES:
            self.camera_type_combo.addItem(t)
        sel_row.addWidget(self.camera_type_combo)
        sel_row.addWidget(QLabel('Index:'))
        self.camera_index_spin = QSpinBox()
        self.camera_index_spin.setRange(0, 9)
        self.camera_index_spin.setFixedWidth(50)
        sel_row.addWidget(self.camera_index_spin)
        sel_row.addStretch()
        cl.addLayout(sel_row)

        # Live view
        self.view = QLabel('Camera not started')
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(640, 480)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setStyleSheet('background-color: black; color: gray;')
        cl.addWidget(self.view)

        # Buttons row
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton('Start Camera')
        self.start_btn.clicked.connect(self._start_camera)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton('Stop Camera')
        self.stop_btn.clicked.connect(self._stop_camera)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.capture_btn = QPushButton('Capture Image')
        self.capture_btn.clicked.connect(self._capture_image)
        self.capture_btn.setEnabled(False)
        btn_row.addWidget(self.capture_btn)
        cl.addLayout(btn_row)

        # Essential controls: auto exposure + exposure on one line
        self.brightness_slider = make_slider(self, 'Brightness', 0, 255, 128)
        ae_row = QHBoxLayout()
        self.auto_exposure_chk = QCheckBox('Auto Exposure')
        self.auto_exposure_chk.setChecked(True)
        self.auto_exposure_chk.stateChanged.connect(
            self._on_auto_exposure_changed
        )
        ae_row.addWidget(self.auto_exposure_chk)
        self.exposure_slider = make_slider(self, 'Exposure', -13, -1, -6)
        self.exposure_slider['slider'].setEnabled(False)
        ae_row.addLayout(self.exposure_slider['layout'])
        cl.addLayout(ae_row)

        cl.addLayout(self.brightness_slider['layout'])

        # Display rate
        disp_row = QHBoxLayout()
        disp_row.addWidget(QLabel('Display rate:'))
        self.display_rate_combo = QComboBox()
        for lbl, ms in [
            ('30 fps', 33), ('15 fps', 67), ('10 fps', 100),
            ('5 fps', 200), ('2 fps', 500), ('1 fps', 1000),
        ]:
            self.display_rate_combo.addItem(lbl, ms)
        self.display_rate_combo.setCurrentIndex(2)  # 10 fps default
        self.display_rate_combo.currentIndexChanged.connect(
            self._on_display_rate_changed
        )
        disp_row.addWidget(self.display_rate_combo)
        disp_row.addStretch()
        cl.addLayout(disp_row)

        # Settings button
        self.settings_btn = QPushButton('⚙ Camera Settings')
        self.settings_btn.clicked.connect(self._open_settings)
        cl.addWidget(self.settings_btn)

        # Status label
        self.status_label = QLabel('Stopped')
        self.status_label.setStyleSheet('color: gray; font-size: 10px;')
        cl.addWidget(self.status_label)

        self.content.setLayout(cl)
        self.content.hide()
        outer_layout.addWidget(self.content)
        self.setLayout(outer_layout)

    # ------------------------------------------------------------------
    # Collapse / expand
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self) -> None:
        self._expanded = True
        self.content.show()
        self.toggle_btn.setText('Camera  ◀◀')

    def _collapse(self) -> None:
        if self._camera is not None:
            self.status_label.setText('Stop camera before collapsing')
            return
        self._expanded = False
        self.content.hide()
        self.toggle_btn.setText('Camera  ▶▶')

    # ------------------------------------------------------------------
    # Camera control
    # ------------------------------------------------------------------

    def _make_camera(self) -> CameraInterface:
        t = self.camera_type_combo.currentText()
        idx = self.camera_index_spin.value()
        if t == 'Fake':
            from core.cameras.fake_camera import FakeCamera
            return FakeCamera()
        elif t == 'Dino-Lite':
            from core.cameras.dinolite_camera import DinoLiteCamera
            return DinoLiteCamera(device_index=idx)
        elif t == 'QScope':
            from core.cameras.qscope_camera import QScopeCamera
            return QScopeCamera(device_index=idx)
        else:
            from core.cameras.opencv_camera import OpenCVCamera
            return OpenCVCamera(device_index=idx)

    def _start_camera(self) -> None:
        try:
            self._camera = self._make_camera()
            self._camera.start()
        except Exception as e:
            self.status_label.setText(f'Error: {e}')
            logger.error(f"Camera start failed: {e}")
            self._camera = None
            return

        self._frame_count = 0
        ms = self.display_rate_combo.currentData()
        self._timer.start(ms)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.capture_btn.setEnabled(True)
        self.camera_type_combo.setEnabled(False)
        self.camera_index_spin.setEnabled(False)

        if sys.platform == 'darwin':
            self.exposure_slider['slider'].setEnabled(False)
            self.auto_exposure_chk.setEnabled(False)
            self.brightness_slider['slider'].setEnabled(False)
            self.status_label.setText(
                'Running — UVC controls not supported on macOS'
            )
            self.status_label.setStyleSheet('color: orange; font-size: 10px;')
        else:
            self.status_label.setText('Running')
            self.status_label.setStyleSheet('color: green; font-size: 10px;')

    def _stop_camera(self) -> None:
        self._timer.stop()
        if self._camera:
            self._camera.stop()
            self._camera = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.camera_type_combo.setEnabled(True)
        self.camera_index_spin.setEnabled(True)
        self.auto_exposure_chk.setEnabled(True)
        self.exposure_slider['slider'].setEnabled(False)
        self.brightness_slider['slider'].setEnabled(True)
        self.view.setText('Camera stopped')
        self.view.setStyleSheet('background-color: black; color: gray;')
        self.status_label.setText('Stopped')
        self.status_label.setStyleSheet('color: gray; font-size: 10px;')

    def _capture_image(self) -> None:
        if not self._camera:
            return
        os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(DEFAULT_SAVE_DIR, f'capture_{timestamp}.png')
        self._camera.capture_image(path)
        self.status_label.setText(f'Saved: {path}')

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        if self._settings_dialog is None or \
                not self._settings_dialog.isVisible():
            self._settings_dialog = CameraSettingsDialog(self)
            self._settings_dialog.refresh_formats()
        self._settings_dialog.show()
        self._settings_dialog.raise_()

    # ------------------------------------------------------------------
    # LED control (Dino-Lite, Windows only)
    # ------------------------------------------------------------------

    def _set_led(self, on: bool) -> None:
        if not self._camera:
            return
        try:
            self._camera.set_led(on)
        except (NotImplementedError, AttributeError) as e:
            self.status_label.setText(str(e)[:80])

    def _set_led_intensity(self, value: int) -> None:
        if not self._camera:
            return
        try:
            self._camera.set_led_intensity(value)
        except (NotImplementedError, AttributeError) as e:
            self.status_label.setText(str(e)[:80])

    # ------------------------------------------------------------------
    # CV2 property control
    # ------------------------------------------------------------------

    def _set_cv2_prop(
        self, name: str, value, auto_wb: bool = None
    ) -> None:
        """Send a property to the camera's cv2 cap if available."""
        if not self._camera:
            return
        if not hasattr(self._camera, '_cap') or not self._camera._cap:
            return
        try:
            import cv2
            if auto_wb is not None:
                self._camera._cap.set(
                    cv2.CAP_PROP_AUTO_WB, 1.0 if auto_wb else 0.0
                )
                return
            prop_map = {
                'Exposure':      cv2.CAP_PROP_EXPOSURE,
                'Brightness':    cv2.CAP_PROP_BRIGHTNESS,
                'Contrast':      cv2.CAP_PROP_CONTRAST,
                'Saturation':    cv2.CAP_PROP_SATURATION,
                'Gain':          cv2.CAP_PROP_GAIN,
                'Sharpness':     cv2.CAP_PROP_SHARPNESS,
                'White Balance': cv2.CAP_PROP_WB_TEMPERATURE,
            }
            prop = prop_map.get(name)
            if prop is not None and value is not None:
                self._camera._cap.set(prop, value)
        except Exception as e:
            logger.warning(f"CV2 property set failed: {e}")

    # ------------------------------------------------------------------
    # Essential control slots
    # ------------------------------------------------------------------

    def _on_auto_exposure_changed(self, state: int) -> None:
        auto = state == Qt.Checked
        self.exposure_slider['slider'].setEnabled(not auto)
        self._set_cv2_prop(
            'Exposure', None,
            auto_wb=None
        )
        try:
            import cv2
            if hasattr(self._camera, '_cap') and self._camera._cap:
                self._camera._cap.set(
                    cv2.CAP_PROP_AUTO_EXPOSURE,
                    0.75 if auto else 0.25
                )
        except Exception:
            pass

    def _on_display_rate_changed(self, index: int) -> None:
        ms = self.display_rate_combo.itemData(index)
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def _on_slider_changed(
        self, name: str, value: int, label: QLabel
    ) -> None:
        label.setText(str(value))
        self._set_cv2_prop(name, value)

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------

    def _update_frame(self) -> None:
        if not self._camera:
            return
        frame = self._camera.get_frame()
        if frame is None:
            return

        self._frame_count += 1
        rgb = frame[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        qt_image = QImage(
            rgb.data, w, h, ch * w, QImage.Format_RGB888
        )
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.view.width(),
            self.view.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.view.setPixmap(pixmap)
        self.status_label.setText(f'Running — frame {self._frame_count}')

    def shutdown(self) -> None:
        if self._camera and self._camera.is_running:
            self._stop_camera()