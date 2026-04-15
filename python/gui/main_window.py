"""
main_window.py
Top-level window for fluidic_control_hw.
Assembles panels into the main layout.

Launch with fake pumps (no hardware needed):
    PYTHONPATH=python python python/gui/main_window.py --fake --pumps 0 1 2 3

Launch with real pumps:
    PYTHONPATH=python python python/gui/main_window.py --port /dev/ttyUSB0 --pumps 0 1 2
"""

import sys
import argparse
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

from core.pump_interface import PumpInterface
from gui.panels.pump_panel import PumpPanel
from gui.panels.sequence_panel import SequencePanel


class MainWindow(QWidget):

    def __init__(self, pump: PumpInterface, channels: dict) -> None:
        super().__init__()
        self._init_ui(pump, channels)

    def _init_ui(self, pump: PumpInterface, channels: dict) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # --- Pump panel ---
        self.pump_panel = PumpPanel(pump)
        layout.addWidget(self.pump_panel)

        # --- Sequence panel ---
        self.sequence_panel = SequencePanel(channels)
        layout.addWidget(self.sequence_panel)

        # Wire sequence panel signals to pump panel
        self.sequence_panel.channels_loaded.connect(
            self.pump_panel.set_contents_from_channels
        )
        self.sequence_panel.step_setpoints.connect(
            self.pump_panel.set_step_setpoints
        )

        # Wire pump Run button to start sequence if loaded
        self.pump_panel.run_pressed.connect(
            self.sequence_panel.start
        )
        # Stop button also stops sequence
        self.pump_panel.stopbtn.clicked.connect(
            self.sequence_panel._stop_sequence
        )

        self.setLayout(layout)
        self.setWindowTitle('Fluidic Control')
        self.show()

    def shutdown(self) -> None:
        self.pump_panel.shutdown()


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
        help='Serial port for real hardware'
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
        channels = {
            f'pump_{pid}': FakePump(pump_ids=[pid])
            for pid in args.pumps
        }

        print(f'Running with FakePump, IDs: {args.pumps}')
    else:
        from core.pumps.new_era import NewEraPump
        pump = NewEraPump(port=args.port, pump_ids=args.pumps)
        channels = {}
        print(f'Connected to NewEraPump on {args.port}, IDs: {args.pumps}')

    app = QApplication(sys.argv)
    win = MainWindow(pump, channels)
    ret = app.exec_()
    win.shutdown()
    sys.exit(ret)


if __name__ == '__main__':
    main()