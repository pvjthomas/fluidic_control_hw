"""
camera_panel.py
PyQt5 panel for live camera feed.
Camera type and index are selectable from the GUI.
Panel is collapsible — click Camera >> to expand, << to collapse.
"""

import logging
import os
import time
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QSizePolicy,
    QComboBox, QSpinBox, QWidget, QSlider, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap

from core.camera_interface import CameraInterface

logger = logging.getLogger(__name__)

FRAME_INTERVAL_MS = 33
DEFAULT_SAVE_DIR = os.path.expanduser('~/Pictures/fluidic_control')
CAMERA_TYPES = ['Dino-Lite', 'QScope', 'Generic USB', 'Fake']


class CameraPanel(QGroupBox):
    """Collapsible panel with live camera feed and camera selection."""

    def __init__(self) -> None:
        super().__init__('')
        self._camera = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)
        self._frame_count = 0
        self._expanded = False
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout()
        outer_layout.setSpacing(6)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # --- Toggle button (always visible) ---
        toggle_layout = QHBoxLayout()
        self.toggle_btn = QPushButton('Camera  ▶▶')
        self.toggle_btn.setFixedWidth(150)
        self.toggle_btn.clicked.connect(self._toggle)
        toggle_layout.addWidget(self.toggle_btn)
        toggle_layout.addStretch()
        outer_layout.addLayout(toggle_layout)

        # --- Collapsible content widget ---
        self.content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Camera type and index selector
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel('Camera:'))
        self.camera_type_combo = QComboBox()
        for t in CAMERA_TYPES:
            self.camera_type_combo.addItem(t)
        select_layout.addWidget(self.camera_type_combo)
        select_layout.addWidget(QLabel('Index:'))
        self.camera_index_spin = QSpinBox()
        self.camera_index_spin.setRange(0, 9)
        self.camera_index_spin.setValue(0)
        self.camera_index_spin.setFixedWidth(50)
        select_layout.addWidget(self.camera_index_spin)
        select_layout.addStretch()
        content_layout.addLayout(select_layout)

        # Live view
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(640, 480)
        self.view.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.view.setStyleSheet('background-color: black; color: gray;')
        self.view.setText('Camera not started')
        content_layout.addWidget(self.view)

        # Start / Stop / Capture buttons
        ctrl_layout = QHBoxLayout()
        self.start_btn = QPushButton('Start Camera')
        self.start_btn.clicked.connect(self._start_camera)
        ctrl_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton('Stop Camera')
        self.stop_btn.clicked.connect(self._stop_camera)
        self.stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self.stop_btn)

        self.capture_btn = QPushButton('Capture Image')
        self.capture_btn.clicked.connect(self._capture_image)
        self.capture_btn.setEnabled(False)
        ctrl_layout.addWidget(self.capture_btn)
        content_layout.addLayout(ctrl_layout)

        # Essential controls
        self.auto_exposure_chk = QCheckBox('Auto Exposure')
        self.auto_exposure_chk.setChecked(True)
        self.auto_exposure_chk.stateChanged.connect(
            self._on_auto_exposure_changed
        )
        content_layout.addWidget(self.auto_exposure_chk)

        self.exposure_slider = self._make_slider('Exposure', -13, -1, -6)
        content_layout.addLayout(self.exposure_slider['layout'])
        self.exposure_slider['slider'].setEnabled(False)

        self.brightness_slider = self._make_slider('Brightness', 0, 255, 128)
        content_layout.addLayout(self.brightness_slider['layout'])

        # More controls toggle
        self.more_btn = QPushButton('More Controls  ▼')
        self.more_btn.setCheckable(True)
        self.more_btn.clicked.connect(self._toggle_more_controls)
        content_layout.addWidget(self.more_btn)

        # Expanded controls (hidden by default)
        self.more_controls = QWidget()
        more_layout = QVBoxLayout()
        more_layout.setContentsMargins(0, 0, 0, 0)
        more_layout.setSpacing(4)

        self.contrast_slider = self._make_slider('Contrast', 0, 255, 128)
        more_layout.addLayout(self.contrast_slider['layout'])

        self.saturation_slider = self._make_slider('Saturation', 0, 255, 128)
        more_layout.addLayout(self.saturation_slider['layout'])

        self.gain_slider = self._make_slider('Gain', 0, 255, 0)
        more_layout.addLayout(self.gain_slider['layout'])

        self.sharpness_slider = self._make_slider('Sharpness', 0, 255, 128)
        more_layout.addLayout(self.sharpness_slider['layout'])

        self.auto_wb_chk = QCheckBox('Auto White Balance')
        self.auto_wb_chk.setChecked(True)
        self.auto_wb_chk.stateChanged.connect(self._on_auto_wb_changed)
        more_layout.addWidget(self.auto_wb_chk)

        self.wb_slider = self._make_slider('White Balance', 2000, 7500, 4500)
        more_layout.addLayout(self.wb_slider['layout'])
        self.wb_slider['slider'].setEnabled(False)

        self.more_controls.setLayout(more_layout)
        self.more_controls.hide()
        content_layout.addWidget(self.more_controls)

        # Status label
        self.status_label = QLabel('Stopped')
        self.status_label.setStyleSheet('color: gray; font-size: 10px;')
        content_layout.addWidget(self.status_label)

        # Apply layout to content widget
        self.content.setLayout(content_layout)
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
        camera_type = self.camera_type_combo.currentText()
        index = self.camera_index_spin.value()

        if camera_type == 'Fake':
            from core.cameras.fake_camera import FakeCamera
            return FakeCamera()
        elif camera_type == 'Dino-Lite':
            from core.cameras.dinolite_camera import DinoLiteCamera
            return DinoLiteCamera(device_index=index)
        elif camera_type == 'QScope':
            from core.cameras.qscope_camera import QScopeCamera
            return QScopeCamera(device_index=index)
        else:
            from core.cameras.opencv_camera import OpenCVCamera
            return OpenCVCamera(device_index=index)

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
        self._timer.start(FRAME_INTERVAL_MS)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.capture_btn.setEnabled(True)
        self.camera_type_combo.setEnabled(False)
        self.camera_index_spin.setEnabled(False)
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
        self.view.setText('Camera stopped')
        self.view.setStyleSheet('background-color: black; color: gray;')
        self.status_label.setText('Stopped')
        self.status_label.setStyleSheet('color: gray; font-size: 10px;')

    def _capture_image(self) -> None:
        if not self._camera:
            return
        os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(
            DEFAULT_SAVE_DIR, f'capture_{timestamp}.png'
        )
        self._camera.capture_image(path)
        self.status_label.setText(f'Saved: {path}')

    # ------------------------------------------------------------------
    # Slider helpers
    # ------------------------------------------------------------------

    def _make_slider(
        self, label: str, min_val: int, max_val: int, default: int
    ) -> dict:
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
            lambda v, l=val_lbl, n=label: self._on_slider_changed(n, v, l)
        )
        return {'layout': layout, 'slider': slider, 'label': val_lbl}

    def _toggle_more_controls(self) -> None:
        if self.more_btn.isChecked():
            self.more_controls.show()
            self.more_btn.setText('More Controls  ▲')
        else:
            self.more_controls.hide()
            self.more_btn.setText('More Controls  ▼')

    def _on_auto_exposure_changed(self, state: int) -> None:
        auto = state == Qt.Checked
        self.exposure_slider['slider'].setEnabled(not auto)
        if self._camera and self._camera.is_running:
            import cv2
            if hasattr(self._camera, '_cap') and self._camera._cap:
                self._camera._cap.set(
                    cv2.CAP_PROP_AUTO_EXPOSURE,
                    0.75 if auto else 0.25
                )

    def _on_auto_wb_changed(self, state: int) -> None:
        auto = state == Qt.Checked
        self.wb_slider['slider'].setEnabled(not auto)
        if self._camera and self._camera.is_running:
            import cv2
            if hasattr(self._camera, '_cap') and self._camera._cap:
                self._camera._cap.set(
                    cv2.CAP_PROP_AUTO_WB,
                    1.0 if auto else 0.0
                )

    def _on_slider_changed(
        self, name: str, value: int, label: QLabel
    ) -> None:
        label.setText(str(value))
        if not (self._camera and self._camera.is_running):
            return
        if not hasattr(self._camera, '_cap') or not self._camera._cap:
            return
        import cv2
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
        if prop is not None:
            self._camera._cap.set(prop, value)

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
        bytes_per_line = ch * w
        qt_image = QImage(
            rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
        )
        pixmap = QPixmap.fromImage(qt_image)
        pixmap = pixmap.scaled(
            self.view.width(),
            self.view.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.view.setPixmap(pixmap)
        self.status_label.setText(
            f'Running — frame {self._frame_count}'
        )

    def shutdown(self) -> None:
        if self._camera and self._camera.is_running:
            self._stop_camera()