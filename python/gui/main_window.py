"""
main_window.py
PyQt5 GUI for fluidic_control_hw.
Accepts any PumpInterface implementation — real hardware or fake.

Launch with real pumps:
    python -m python.gui.main_window --port COM3 --pumps 0 1 2

Launch with fake pumps (no hardware needed):
    python -m python.gui.main_window --fake --pumps 0 1 2 3
"""

import sys
import argparse
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import (
    QShortcut, QLineEdit, QApplication, QWidget,
    QGridLayout, QPushButton, QLabel, QComboBox
)

from core.pump_interface import PumpInterface

SYRINGES = {
    '1 ml BD':  '4.699',
    '3 ml BD':  '8.585',
    '5 ml BD':  '11.99',
    '10 ml BD': '14.50',
}


class PumpControl(QWidget):

    def __init__(self, pump: PumpInterface) -> None:
        super().__init__()
        self._pump = pump
        self._pumps = pump.find_pumps()
        self.initUI()

    def initUI(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(5)

        # --- Top buttons ---
        self.runbtn = QPushButton('Run/Update', self)
        self.runbtn.setCheckable(True)
        self.runbtn.clicked.connect(self.run_update)
        grid.addWidget(self.runbtn, 1, 2)

        self.stopbtn = QPushButton('Stop', self)
        self.stopbtn.setCheckable(True)
        self.stopbtn.clicked.connect(self.stop_all)
        grid.addWidget(self.stopbtn, 1, 3)

        # --- Column headers ---
        grid.addWidget(QLabel('Pump number'),      2, 0)
        grid.addWidget(QLabel('Syringe'),          2, 1)
        grid.addWidget(QLabel('Contents'),         2, 2)
        grid.addWidget(QLabel('Flow rate'),        2, 3)
        grid.addWidget(QLabel('Current flow rate'),2, 4)

        # --- Per-pump rows ---
        self.mapper      = QtCore.QSignalMapper(self)
        self.primemapper = QtCore.QSignalMapper(self)
        self.currflow    = {}
        self.rates       = {}
        self.prime_btns  = {}

        for i, pump_id in enumerate(self._pumps):
            row = 3 + i

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

            self.currflow[pump_id] = QLabel(self)
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

        # --- Status and command bars ---
        self.curr_state = 'Stopped'
        self.statusbar = QLabel(self)
        self.statusbar.setText('Status: Stopped')
        grid.addWidget(self.statusbar, 1, 4)

        self.commandbar = QLabel(self)
        grid.addWidget(self.commandbar, row + 1, 0, 1, 4)

        # --- Prime state tracking ---
        self.prime_state = set()

        # --- Initialise ---
        self._pump.stop_all()
        [self.update_syringe(p) for p in self._pumps]
        self.commandbar.setText('')
        [self.currflow[p].setText('0 ul/hr') for p in self._pumps]

        # --- Keyboard shortcut ---
        QShortcut(QtGui.QKeySequence('Space'), self, self.stop_all)

        self.setLayout(grid)
        self.setWindowTitle('Pump control')
        self.show()

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

        # Parse rates from text fields
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

    def update_syringe(self, pump_id: int) -> None:
        if self.curr_state == 'Stopped':
            dia = float(SYRINGES[
                str(self.mapper.mapping(pump_id).currentText())
            ])
            self._pump.set_diameter(pump_id, dia)
            actual_dia = self._pump.get_diameter(pump_id)
            self.commandbar.setText(
                f'Last command: pump {pump_id} diameter set to '
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

    def shutdown(self) -> None:
        self.stop_all()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description='Fluidic control GUI')
    parser.add_argument(
        '--fake', action='store_true',
        help='Use fake pump (no hardware required)'
    )
    parser.add_argument(
        '--port', type=str, default='COM1',
        help='Serial port for real hardware (e.g. COM3 or /dev/ttyUSB0)'
    )
    parser.add_argument(
        '--pumps', type=int, nargs='+', default=[0, 1, 2, 3],
        help='Pump IDs to use (default: 0 1 2 3)'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.fake:
        from core.pumps.fake_pump import FakePump
        pump = FakePump(pump_ids=args.pumps)
        print(f'Running with FakePump, IDs: {args.pumps}')
    else:
        from core.pumps.new_era import NewEraPump
        pump = NewEraPump(port=args.port, pump_ids=args.pumps)
        print(f'Connected to NewEraPump on {args.port}, IDs: {args.pumps}')

    app = QApplication(sys.argv)
    ex = PumpControl(pump)
    ret = app.exec_()
    ex.shutdown()
    sys.exit(ret)


if __name__ == '__main__':
    main()