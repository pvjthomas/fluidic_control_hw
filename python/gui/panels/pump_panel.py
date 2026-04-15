"""
pump_panel.py
PyQt5 panel for syringe pump control.
Displays one row per pump with syringe selector, contents label,
flow rate input, current flow rate display, and prime button.
"""

from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QPushButton,
    QLabel, QComboBox, QLineEdit, QShortcut
)

from core.pump_interface import PumpInterface
from PyQt5.QtCore import pyqtSignal

    
SYRINGES = {
    '1 ml BD':  '4.699',
    '3 ml BD':  '8.585',
    '5 ml BD':  '11.99',
    '10 ml BD': '14.50',
}


class PumpPanel(QWidget):
    """Panel displaying controls for all connected pumps."""
    run_pressed = pyqtSignal()

    def __init__(self, pump: PumpInterface) -> None:
        super().__init__()
        self._pump = pump
        self._pumps = pump.find_pumps()
        self._init_ui()

    def _init_ui(self) -> None:
        self._grid = QGridLayout()
        grid = self._grid
        grid.setSpacing(5)

        # --- Top buttons ---
        self.runbtn = QPushButton('Run/Update', self)
        self.runbtn.setCheckable(True)
        self.runbtn.clicked.connect(self.run_update)
        grid.addWidget(self.runbtn, 0, 2)

        self.stopbtn = QPushButton('Stop', self)
        self.stopbtn.setCheckable(True)
        self.stopbtn.clicked.connect(self.stop_all)
        grid.addWidget(self.stopbtn, 0, 3)

        self.statusbar = QLabel('Status: Stopped', self)
        grid.addWidget(self.statusbar, 0, 4)

        # --- Column headers ---
        grid.addWidget(QLabel('Pump'),             1, 0)
        grid.addWidget(QLabel('Syringe'),          1, 1)
        grid.addWidget(QLabel('Contents'),         1, 2)
        grid.addWidget(QLabel('Flow rate'),        1, 3)
        grid.addWidget(QLabel('Current flow rate'),1, 4)

        # --- Per-pump rows ---
        self.mapper      = QtCore.QSignalMapper(self)
        self.primemapper = QtCore.QSignalMapper(self)
        self.currflow    = {}
        self.rates       = {}
        self.prime_btns  = {}
        self.prime_state = set()
        self.curr_state  = 'Stopped'

        for i, pump_id in enumerate(self._pumps):
            row = 2 + i

            lbl = QLabel('Pump %i' % pump_id)
            lbl.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(lbl, row, 0)

            combo = QComboBox(self)
            [combo.addItem(s) for s in sorted(SYRINGES)]
            self.mapper.setMapping(combo, pump_id)
            combo.activated.connect(self.mapper.map)
            grid.addWidget(combo, row, 1)

            grid.addWidget(QLineEdit(), row, 2)

            self.rates[pump_id] = QLineEdit(self)
            grid.addWidget(self.rates[pump_id], row, 3)

            self.currflow[pump_id] = QLabel('0 ul/hr', self)
            self.currflow[pump_id].setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(self.currflow[pump_id], row, 4)

            btn = QPushButton('Prime', self)
            btn.setCheckable(True)
            self.primemapper.setMapping(btn, pump_id)
            btn.clicked.connect(self.primemapper.map)
            grid.addWidget(btn, row, 5)
            self.prime_btns[pump_id] = btn

        self.mapper.mapped.connect(self.update_syringe)
        self.primemapper.mapped.connect(self.prime_pumps)

        # --- Command bar ---
        last_row = 2 + len(self._pumps)
        self.commandbar = QLabel('', self)
        grid.addWidget(self.commandbar, last_row, 0, 1, 5)

        # --- Keyboard shortcut ---
        QShortcut(QtGui.QKeySequence('Space'), self, self.stop_all)

        # --- Initialise state ---
        self._pump.stop_all()
        [self.update_syringe(p) for p in self._pumps]
        self.commandbar.setText('')

        self.setLayout(grid)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def stop_all(self) -> None:
        self.runbtn.setChecked(0)
        self.stopbtn.setChecked(1)
        self._pump.stop_all()
        self.curr_state = 'Stopped'
        self.statusbar.setText('Status: Stopped')
        self.commandbar.setText('Last command: stop all pumps')
        [self.currflow[p].setText('0 ul/hr') for p in self.rates]
        self.prime_state = set()
        [self.prime_btns[p].setChecked(0) for p in self.rates]

    def run_update(self) -> None:
        self.runbtn.setChecked(1)
        self.stopbtn.setChecked(0)

        rates = {}
        for pump_id in self.rates:
            text = self.rates[pump_id].text().strip()
            try:
                rates[pump_id] = float(text)
            except ValueError:
                rates[pump_id] = 0.0
                self.rates[pump_id].setText('0')

        if self.curr_state == 'Running':
            self._pump.stop_all()
            self._pump.set_rates(rates)
            self._pump.run_all()
        else:
            self._pump.set_rates(rates)
            self._pump.run_all()
            self.curr_state = 'Running'
            self.statusbar.setText('Status: Running')

        actual = self._pump.get_rates(list(rates.keys()))
        self.commandbar.setText(
            'Last command: run/update ' +
            ', '.join(f'p{p}={actual[p]:.1f}' for p in actual)
        )
        [self.currflow[p].setText(f'{actual[p]:.1f} ul/hr')
         for p in actual]
        self.run_pressed.emit()

    def update_syringe(self, pump_id: int) -> None:
        if self.curr_state == 'Stopped':
            dia = float(SYRINGES[
                str(self.mapper.mapping(pump_id).currentText())
            ])
            self._pump.set_diameter(pump_id, dia)
            actual_dia = self._pump.get_diameter(pump_id)
            self.commandbar.setText(
                f'Last command: pump {pump_id} diameter -> '
                f'{actual_dia:.3f} mm'
            )
        else:
            self.commandbar.setText("Can't change syringe while running")

    def prime_pumps(self, pump_id: int) -> None:
        if self.curr_state == 'Stopped':
            if pump_id not in self.prime_state:
                self._pump.prime(pump_id)
                self.commandbar.setText(
                    f'Last command: priming pump {pump_id}'
                )
                self.statusbar.setText('Status: Priming')
                self.prime_state.add(pump_id)
            else:
                self._pump.stop_pump(pump_id)
                self.commandbar.setText(
                    f'Last command: stopped pump {pump_id}'
                )
                self.prime_state.remove(pump_id)
                if len(self.prime_state) == 0:
                    self.statusbar.setText('Status: Stopped')

            actual = self._pump.get_rates(list(self.rates.keys()))
            self.currflow[pump_id].setText(
                f'{actual[pump_id]:.1f} ul/hr'
            )
        else:
            self.commandbar.setText("Can't prime while running")
            self.prime_btns[pump_id].setChecked(0)

    def set_contents_from_channels(self, channel_names: list) -> None:
        """Pre-fill Contents fields from protocol channel names."""
        for i, pump_id in enumerate(self._pumps):
            if i < len(channel_names):
                # Find the contents QLineEdit for this row
                # It's the unnamed QLineEdit in column 2
                item = self._grid.itemAtPosition(2 + i, 2)
                if item and item.widget():
                    item.widget().setText(channel_names[i])
  
    def set_step_setpoints(self, setpoints: dict) -> None:
        """Update flow rate fields from sequence step setpoints."""
        channel_names = list(setpoints.keys())
        for i, pump_id in enumerate(self._pumps):
            if i < len(channel_names):
                name = channel_names[i]
                value = setpoints[name]
                self.rates[pump_id].setText(str(int(value)))

    def shutdown(self) -> None:
        self.stop_all()