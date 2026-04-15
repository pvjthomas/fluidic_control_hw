"""
sequence_panel.py
PyQt5 panel for sequence/protocol playback.
Loads a CSV or XLSX protocol file and provides playback controls.

Controls:
    Load File        — open file dialog to select protocol
    Prev / Next      — jump to previous or next step
    Back X / Fwd X  — seek backward or forward by X seconds
    X field          — editable seek increment (default 10s)
    Pause/Resume     — freeze/unfreeze the step timer
    Stop             — stop sequence and zero all channels
"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QLineEdit, QProgressBar,
    QFileDialog, QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

from core.sequence_runner import SequenceRunner, Step

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Worker thread — runs SequenceRunner._run_loop() off the GUI thread
# ------------------------------------------------------------------

class SequenceWorker(QThread):
    """Runs the sequence loop in a background thread."""

    # Signals emitted to update the GUI
    step_started  = pyqtSignal(int, object)   # index, Step
    step_ended    = pyqtSignal(int, object)   # index, Step
    tick          = pyqtSignal(int, float, float)  # index, elapsed, remaining
    sequence_done = pyqtSignal()
    log_message   = pyqtSignal(str)

    def __init__(self, runner: SequenceRunner) -> None:
        super().__init__()
        self._runner = runner

        # Wire runner callbacks to Qt signals
        self._runner.on_step_start  = self.step_started.emit
        self._runner.on_step_end    = self.step_ended.emit
        self._runner.on_tick        = self.tick.emit
        self._runner.on_sequence_end = self.sequence_done.emit
        self._runner.on_log         = self.log_message.emit

    def run(self) -> None:
        self._runner.start()


# ------------------------------------------------------------------
# Sequence panel widget
# ------------------------------------------------------------------

class SequencePanel(QGroupBox):
    """Panel for loading and playing back a protocol file."""
    # Emitted when a protocol is loaded — carries list of channel names
    channels_loaded = pyqtSignal(list)
    step_setpoints  = pyqtSignal(dict)
    sequence_ended   = pyqtSignal()
    protocol_active  = pyqtSignal(bool)

    def __init__(self, channels: dict) -> None:
        """
        Args:
            channels: dict mapping channel name -> instrument instance
                      e.g. {'oil': FakePump([0]), 'buffer': FakePump([1])}
        """
        super().__init__('Protocol Sequence')
        self._channels = channels
        self._runner = SequenceRunner(channels)
        self._worker = None
        self._step_count = 0
        self._protocol_loaded = False
        self._total_elapsed = 0.0

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        # --- Row 1: Load file ---
        load_layout = QHBoxLayout()
        self.load_btn = QPushButton('Load Protocol File')
        self.load_btn.clicked.connect(self._load_or_erase)
        self.file_label = QLabel('No file loaded')
        self.file_label.setStyleSheet('color: gray;')
        load_layout.addWidget(self.load_btn)
        load_layout.addWidget(self.file_label, stretch=1)
        main_layout.addLayout(load_layout)

        # --- Row 2: Step info ---
        self.step_label = QLabel('Step — / —')
        self.step_label.setFont(QFont('Courier New', 11))
        self.step_name_label = QLabel('')
        self.step_name_label.setStyleSheet('font-weight: bold;')
        step_info_layout = QHBoxLayout()
        step_info_layout.addWidget(self.step_label)
        step_info_layout.addWidget(self.step_name_label, stretch=1)
        main_layout.addLayout(step_info_layout)

        # --- Row 3: Time display ---
        time_layout = QHBoxLayout()
        self.total_time_label = QLabel('Time: 00:00')
        self.total_time_label.setFont(QFont('Courier New', 11))
        self.step_time_label = QLabel('Step Time: 00:00')
        self.step_time_label.setFont(QFont('Courier New', 11))
        time_layout.addWidget(self.total_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.step_time_label)
        main_layout.addLayout(time_layout)

        # --- Row 4: Playback buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.prev_btn = QPushButton('◀◀ Prev')
        self.prev_btn.clicked.connect(self._prev_step)
        btn_layout.addWidget(self.prev_btn)

        self.back_btn = QPushButton('◀ Back X')
        self.back_btn.clicked.connect(self._seek_backward)
        btn_layout.addWidget(self.back_btn)

        self.x_field = QLineEdit('10')
        self.x_field.setFixedWidth(50)
        self.x_field.setAlignment(Qt.AlignCenter)
        self.x_field.setToolTip('Seek increment in seconds')
        btn_layout.addWidget(QLabel('X (s):'))
        btn_layout.addWidget(self.x_field)

        self.fwd_btn = QPushButton('Fwd X ▶')
        self.fwd_btn.clicked.connect(self._seek_forward)
        btn_layout.addWidget(self.fwd_btn)

        self.next_btn = QPushButton('Next ▶▶')
        self.next_btn.clicked.connect(self._next_step)
        btn_layout.addWidget(self.next_btn)

        main_layout.addLayout(btn_layout)

        # --- Row 5: Pause / Stop ---
        ctrl_layout = QHBoxLayout()

        self.pause_btn = QPushButton('Pause')
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self._pause_resume)
        ctrl_layout.addWidget(self.pause_btn)


        main_layout.addLayout(ctrl_layout)

        # --- Row 6: Log bar ---
        self.log_label = QLabel('')
        self.log_label.setStyleSheet('color: gray; font-size: 10px;')
        main_layout.addWidget(self.log_label)

        self.setLayout(main_layout)
        self._set_controls_enabled(False)

        # --- Row 7: Protocol table ---
        self.protocol_table = QTableWidget()
        self.protocol_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.protocol_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.protocol_table.setAlternatingRowColors(True)
        self.protocol_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.protocol_table.setMinimumHeight(150)
        self.protocol_table.hide()  # hidden until file loaded
        main_layout.addWidget(self.protocol_table)


    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------
    def _load_or_erase(self) -> None:
            if self._protocol_loaded:
                self._erase_protocol()
            else:
                self._load_file()

    def _erase_protocol(self) -> None:
            """Stop sequence only, leave pumps at current state."""
            if self._worker and self._worker.isRunning():
                self._runner.stop()
                self._worker.wait()

            # Reset state
            self._protocol_loaded = False
            self.protocol_active.emit(False)
            self._step_count = 0
            self._total_elapsed = 0.0

            # Reset UI only
            self.load_btn.setText('Load Protocol File')
            self.file_label.setText('No file loaded')
            self.file_label.setStyleSheet('color: gray;')
            self.step_label.setText('Step — / —')
            self.step_name_label.setText('')
            self.total_time_label.setText('Time: 00:00')
            self.step_time_label.setText('Step Time: 00:00')
            self.log_label.setText('')
            self.protocol_table.hide()
            self.protocol_table.clearContents()
            self.protocol_table.setRowCount(0)
            self._set_controls_enabled(False)
            self.pause_btn.setChecked(False)
            self.pause_btn.setText('Pause')

            # Clear contents labels only — don't touch rates or pump state
            self.channels_loaded.emit([])
            
    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Load Protocol File',
            '',
            'Protocol files (*.csv *.xlsx);;All files (*.*)'
        )
        if not path:
            return

        # Load without channel validation first — map by position
        try:
            from core.sequence_runner import _load_csv, _load_xlsx
            from pathlib import Path
            p = Path(path)
            suffix = p.suffix.lower()
            if suffix not in ('.csv', '.xlsx', '.xls'):
                raise ValueError(f"Unsupported file format: {suffix}")
            if suffix == '.csv':
                headers, rows = _load_csv(p)
            else:
                headers, rows = _load_xlsx(p)
        except Exception as e:
            QMessageBox.critical(self, 'Protocol Error', str(e))
            return

        # Extract channel column names in order
        reserved = {'step_name', 'duration_s', 'end_action'}
        channel_names = [h for h in headers if h not in reserved]

        # Remap runner channels by position
        channel_keys = list(self._channels.keys())
        new_channels = {}
        for i, name in enumerate(channel_names):
            if i < len(channel_keys):
                new_channels[name] = self._channels[channel_keys[i]]
        self._runner = SequenceRunner(new_channels)

        # Now validate and load
        try:
            steps = self._runner.load(path)
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.critical(self, 'Protocol Error', str(e))
            print(f"LOAD ERROR: {e}")
            return

        self._step_count = len(steps)
        self._protocol_loaded = True
        self.protocol_active.emit(True)


        # Update UI
        self.load_btn.setText('Erase Protocol')
        self.file_label.setText(path.split('/')[-1])
        self.file_label.setStyleSheet('color: green;')
        self._update_step_display(0, steps[0])
        self.log_label.setText(
            f'Loaded {self._step_count} steps. Press Run to start.'
        )
        self._set_controls_enabled(True)

        # Populate table and show first step setpoints
        self._populate_table(steps, channel_names)
        self.channels_loaded.emit(channel_names)
        self._populate_setpoints(steps[0].setpoints)
    

    def _start_sequence(self) -> None:
            self._total_elapsed = 0.0
            self._worker = SequenceWorker(self._runner)
            self._worker.step_started.connect(self._on_step_started)
            self._worker.step_ended.connect(self._on_step_ended)
            self._worker.tick.connect(self._on_tick)
            self._worker.sequence_done.connect(self._on_sequence_done)
            self._worker.log_message.connect(self._on_log)
            self._worker.start()
            self.protocol_active.emit(True)
    
    def start(self) -> None:
        """Called by main window when Run is pressed."""
        if self._step_count > 0 and not (
            self._worker and self._worker.isRunning()
        ):
            self._start_sequence()
    # ------------------------------------------------------------------
    # Sequence control
    # ------------------------------------------------------------------

    def _prev_step(self) -> None:
        self._runner.previous_step()

    def _next_step(self) -> None:
        self._runner.next_step()

    def _seek_forward(self) -> None:
        self._runner.seek_forward(self._get_x())

    def _seek_backward(self) -> None:
        self._runner.seek_backward(self._get_x())

    def _pause_resume(self) -> None:
        if self.pause_btn.isChecked():
            self._runner.pause()
            self.pause_btn.setText('Resume')
        else:
            self._runner.resume()
            self.pause_btn.setText('Pause')

    def _stop_sequence(self) -> None:
        if self._worker and self._worker.isRunning():
            self._runner.stop()
            self._worker.wait()
        self._set_controls_enabled(False)
        self.step_label.setText('Step — / —')
        self.step_name_label.setText('')
        self.log_label.setText('Sequence stopped.')

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_step_started(self, index: int, step: Step) -> None:
        self._update_step_display(index, step)
        self._populate_setpoints(step.setpoints)
        self._highlight_row(index)

    def _on_step_ended(self, index: int, step: Step) -> None:
        pass  # tick handles progress updates

    def _on_tick(self, index: int, elapsed: float, remaining: float) -> None:
        self._total_elapsed += SequenceRunner.TICK_INTERVAL
        self.step_time_label.setText(
            f'Step Time: {self._fmt_time(elapsed)}'
        )
        self.total_time_label.setText(
            f'Time: {self._fmt_time(self._total_elapsed)}'
        )

    @pyqtSlot()
    def _on_sequence_done(self) -> None:
            self.log_label.setText('Sequence complete.')
            self._set_controls_enabled(False)
            self.sequence_ended.emit()
            self.protocol_active.emit(False)
        
    def on_pump_state_changed(self, state: str) -> None:
        """Disable Load button when running with no protocol loaded."""
        if not self._protocol_loaded:
            self.load_btn.setEnabled(state == 'Stopped')

    @pyqtSlot(str)
    def _on_log(self, message: str) -> None:
        self.log_label.setText(message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_x(self) -> float:
        try:
            return float(self.x_field.text().strip())
        except ValueError:
            self.x_field.setText('10')
            return 10.0
            

    def _update_step_display(self, index: int, step: Step) -> None:
        self.step_label.setText(
            f'Step {index + 1} / {self._step_count}'
        )
        self.step_name_label.setText(step.name)
    def _populate_setpoints(self, setpoints: dict) -> None:
            """Emit setpoints so pump panel can update flow rate fields."""
            self.step_setpoints.emit(setpoints)

    def _fmt_time(self, seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f'{m:02d}:{s:02d}'

    def _populate_table(self, steps, channel_names: list) -> None:
            """Fill the protocol table with step data."""
            columns = ['Step', 'Duration (s)'] + channel_names
            self.protocol_table.setColumnCount(len(columns))
            self.protocol_table.setHorizontalHeaderLabels(columns)
            self.protocol_table.setRowCount(len(steps))

            for row, step in enumerate(steps):
                self.protocol_table.setItem(
                    row, 0, QTableWidgetItem(step.name)
                )
                self.protocol_table.setItem(
                    row, 1, QTableWidgetItem(str(step.duration_s))
                )
                for col, name in enumerate(channel_names):
                    value = step.setpoints.get(name, '')
                    text = str(int(value)) if value != '' else ''
                    self.protocol_table.setItem(
                        row, col + 2, QTableWidgetItem(text)
                    )

            self.protocol_table.show()
            self._highlight_row(0)

    def _highlight_row(self, index: int) -> None:
            """Highlight the active step row in the table."""
            from PyQt5.QtGui import QColor
            for row in range(self.protocol_table.rowCount()):
                color = QColor('#2d6a4f') if row == index else QColor()
                for col in range(self.protocol_table.columnCount()):
                    item = self.protocol_table.item(row, col)
                    if item:
                        item.setBackground(color)
            self.protocol_table.scrollToItem(
                self.protocol_table.item(index, 0)
            )

    def _set_controls_enabled(self, enabled: bool) -> None:
        for btn in (
            self.prev_btn, self.next_btn,
            self.back_btn, self.fwd_btn,
            self.pause_btn
        ):
            btn.setEnabled(enabled)