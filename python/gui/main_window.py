"""
main_window.py
Top-level window for fluidic_control_hw.
Assembles panels into the main layout.

Launch with fake pumps (no hardware needed):
    PYTHONPATH=python python python/gui/main_window.py --fake-pump --pumps 0 1 2 3

Launch with real pumps:
    PYTHONPATH=python python python/gui/main_window.py --port /dev/ttyUSB0 --pumps 0 1 2
"""

import sys
import argparse
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout

from core.pump_interface import PumpInterface
from gui.panels.pump_panel import PumpPanel
from gui.panels.sequence_panel import SequencePanel
from gui.panels.camera_panel import CameraPanel


class MainWindow(QWidget):

    def __init__(
        self,
        pump: PumpInterface,
        channels: dict,
    ) -> None:
        super().__init__()
        self._init_ui(pump, channels)

    def _init_ui(
        self,
        pump: PumpInterface,
        channels: dict,
    ) -> None:
        # --- Main horizontal layout ---
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)

        # --- Left side: pump + sequence stacked vertically ---
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        self.pump_panel = PumpPanel(pump)
        left_layout.addWidget(self.pump_panel)

        self.sequence_panel = SequencePanel(channels)
        left_layout.addWidget(self.sequence_panel)

        left_layout.addStretch()
        main_layout.addLayout(left_layout)

        # --- Right side: camera panel (manages itself) ---
        self.camera_panel = CameraPanel()
        main_layout.addWidget(self.camera_panel)

        # --- Signal wiring ---
        self.sequence_panel.channels_loaded.connect(
            self.pump_panel.set_contents_from_channels
        )
        self.sequence_panel.step_setpoints.connect(
            self.pump_panel.apply_setpoints
        )
        self.pump_panel.run_pressed.connect(
            self.sequence_panel.start
        )
        self.sequence_panel.sequence_ended.connect(
            self.pump_panel.trigger_stop
        )
        self.sequence_panel.protocol_active.connect(
            self.pump_panel.set_protocol_active
        )
        self.pump_panel.state_changed.connect(
            self.sequence_panel.on_pump_state_changed
        )

        self.setLayout(main_layout)
        self.setWindowTitle('Fluidic Control')
        self.show()

    def shutdown(self) -> None:
        self.pump_panel.shutdown()
        self.camera_panel.shutdown()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description='Fluidic control GUI')
    parser.add_argument(
        '--fake-pump', action='store_true',
        help='Use fake pump (no hardware required)'
    )
    parser.add_argument(
        '--fake', action='store_true',
        help='Shorthand for --fake-pump'
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

    use_fake_pump = args.fake or args.fake_pump

    # --- Pump ---
    if use_fake_pump:
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