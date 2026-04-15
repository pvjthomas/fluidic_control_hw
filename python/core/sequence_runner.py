"""
sequence_runner.py
Loads and executes a step-based protocol from a CSV or XLSX file.
Runs independently of the GUI — can be used in scripts or tests.

Protocol file format:
    Required columns: step_name, duration_s
    Channel columns:  one per channel, named after the channel
                      e.g. 'oil', 'buffer', 'pressure_1'
    Empty cells:      interpreted as "no change" for that channel

Usage:
    channels = {
        'oil':    FakePump(pump_ids=[0]),   # or NewEraPump(...)
        'buffer': FakePump(pump_ids=[1]),
    }
    runner = SequenceRunner(channels)
    runner.load('protocol.csv')
    runner.start()
"""

import csv
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

class Step:
    """One row in the protocol file."""

    def __init__(
        self,
        name: str,
        duration_s: float,
        setpoints: Dict[str, float],
    ) -> None:
        self.name = name
        self.duration_s = duration_s
        self.setpoints = setpoints  # channel_name -> value

    def __repr__(self) -> str:
        return (
            f"Step(name={self.name!r}, "
            f"duration_s={self.duration_s}, "
            f"setpoints={self.setpoints})"
        )


# ------------------------------------------------------------------
# Protocol file loading
# ------------------------------------------------------------------

def _parse_float(value: str) -> Optional[float]:
    """Return float or None if empty/invalid."""
    v = str(value).strip()
    if v == '' or v.lower() == 'none':
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _load_csv(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    """Return (headers, rows) from a CSV file."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return list(headers), rows


def _load_xlsx(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    """Return (headers, rows) from an XLSX file."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "openpyxl is required to load .xlsx files. "
            "Install it with: pip install openpyxl"
        )
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h) for h in next(rows_iter)]
    rows = []
    for row in rows_iter:
        rows.append({headers[i]: (str(v) if v is not None else '')
                     for i, v in enumerate(row)})
    wb.close()
    return headers, rows


def load_protocol(path: str, channel_names: List[str]) -> List[Step]:
    """
    Load and validate a protocol file.

    Args:
        path:          Path to .csv or .xlsx file
        channel_names: List of known channel names from config

    Returns:
        List of Step objects

    Raises:
        ValueError: if the file has validation errors
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in ('.csv', '.xlsx', '.xls'):
        raise ValueError(f"Unsupported file format: {suffix}")

    if not p.exists():
        raise FileNotFoundError(f"Protocol file not found: {path}")

    if suffix == '.csv':
        headers, rows = _load_csv(p)
    elif suffix in ('.xlsx', '.xls'):
        headers, rows = _load_xlsx(p)

    # --- Validate required columns ---
    errors = []
    if 'step_name' not in headers:
        errors.append("Missing required column: 'step_name'")
    if 'duration_s' not in headers:
        errors.append("Missing required column: 'duration_s'")

    # --- Validate channel columns ---
    channel_cols = [h for h in headers
                    if h not in ('step_name', 'duration_s', 'end_action')]
    unknown = [c for c in channel_cols if c not in channel_names]
    if unknown:
        errors.append(f"Unknown channel column(s): {unknown}. "
                      f"Known channels: {channel_names}")

    if errors:
        raise ValueError("Protocol file errors:\n" + "\n".join(errors))

    # --- Parse rows into Steps ---
    steps = []
    for i, row in enumerate(rows, start=2):  # row 2 = first data row
        name = str(row.get('step_name', '')).strip()
        if not name:
            errors.append(f"Row {i}: empty step_name")
            continue

        duration = _parse_float(row.get('duration_s', ''))
        if duration is None:
            errors.append(f"Row {i} ({name!r}): invalid duration_s")
            continue
        if duration < 0:
            errors.append(f"Row {i} ({name!r}): duration_s must be >= 0")
            continue

        setpoints = {}
        for ch in channel_cols:
            val = _parse_float(row.get(ch, ''))
            if val is not None:
                setpoints[ch] = val

        steps.append(Step(name=name, duration_s=duration,
                          setpoints=setpoints))

    if errors:
        raise ValueError("Protocol file errors:\n" + "\n".join(errors))

    if not steps:
        raise ValueError("Protocol file contains no valid steps")

    logger.info(f"Loaded {len(steps)} steps from {path}")
    return steps


# ------------------------------------------------------------------
# Sequence runner
# ------------------------------------------------------------------

class SequenceRunner:
    """
    Executes a protocol sequence against a set of named channels.
    Each channel is a PumpInterface or PressureControllerInterface.
    Runs in the calling thread — call from a QThread in the GUI.

    Callbacks (all optional, called on events):
        on_step_start(step_index, step)
        on_step_end(step_index, step)
        on_tick(step_index, elapsed_s, remaining_s)
        on_sequence_end()
        on_log(message)
    """

    TICK_INTERVAL = 0.1  # seconds between timer updates

    def __init__(self, channels: Dict[str, Any]) -> None:
        """
        Args:
            channels: dict mapping channel name -> instrument instance
                      e.g. {'oil': FakePump([0]), 'buffer': FakePump([1])}
        """
        self._channels = channels
        self._steps: List[Step] = []
        self._current_index: int = 0
        self._elapsed: float = 0.0
        self._running: bool = False
        self._paused: bool = False

        # Callbacks
        self.on_step_start: Optional[Callable] = None
        self.on_step_end: Optional[Callable] = None
        self.on_tick: Optional[Callable] = None
        self.on_sequence_end: Optional[Callable] = None
        self.on_log: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str) -> List[Step]:
        """Load and validate a protocol file."""
        self._steps = load_protocol(path, list(self._channels.keys()))
        self._current_index = 0
        self._elapsed = 0.0
        return self._steps

    def start(self) -> None:
        """Start executing the sequence from the beginning."""
        if not self._steps:
            raise RuntimeError("No protocol loaded. Call load() first.")
        self._current_index = 0
        self._elapsed = 0.0
        self._running = True
        self._paused = False
        self._log(f"Sequence started ({len(self._steps)} steps)")
        self._run_loop()

    def pause(self) -> None:
        self._paused = True
        self._log("Paused")

    def resume(self) -> None:
        self._paused = False
        self._log("Resumed")

    def next_step(self) -> None:
        """Jump to the next step immediately."""
        if self._current_index < len(self._steps) - 1:
            self._log(f"Manual: next step")
            self._current_index += 1
            self._elapsed = 0.0
            self._apply_step(self._steps[self._current_index])

    def previous_step(self) -> None:
        """Jump to the previous step and restart its timer."""
        if self._current_index > 0:
            self._log(f"Manual: previous step")
            self._current_index -= 1
            self._elapsed = 0.0
            self._apply_step(self._steps[self._current_index])

    def seek_forward(self, seconds: float) -> None:
        """Seek forward by seconds; advances step if needed."""
        step = self._steps[self._current_index]
        remaining = step.duration_s - self._elapsed
        if seconds >= remaining:
            self._log(f"Fwd {seconds}s: advancing to next step")
            self.next_step()
        else:
            self._elapsed += seconds
            self._log(f"Fwd {seconds}s: now {self._elapsed:.1f}s "
                      f"into step {self._current_index}")

    def seek_backward(self, seconds: float) -> None:
        """Seek backward by seconds; clamps to start of current step."""
        new_elapsed = self._elapsed - seconds
        if new_elapsed < 0:
            new_elapsed = 0.0
        self._elapsed = new_elapsed
        self._log(f"Back {seconds}s: now {self._elapsed:.1f}s "
                  f"into step {self._current_index}")

    def stop(self) -> None:
        """Stop the sequence and zero all channels."""
        self._running = False
        self._stop_all_channels()
        self._log("Sequence stopped")

    @property
    def current_step(self) -> Optional[Step]:
        if not self._steps:
            return None
        return self._steps[self._current_index]

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def step_count(self) -> int:
        return len(self._steps)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main execution loop. Blocking — run in a thread from the GUI."""
        self._apply_step(self._steps[self._current_index])

        while self._running:
            time.sleep(self.TICK_INTERVAL)

            if self._paused:
                continue

            self._elapsed += self.TICK_INTERVAL
            step = self._steps[self._current_index]
            remaining = step.duration_s - self._elapsed

            if self.on_tick:
                self.on_tick(self._current_index, self._elapsed, remaining)

            if self._elapsed >= step.duration_s:
                self._log(
                    f"Step {self._current_index} '{step.name}' complete"
                )
                if self.on_step_end:
                    self.on_step_end(self._current_index, step)

                if self._current_index < len(self._steps) - 1:
                    self._current_index += 1
                    self._elapsed = 0.0
                    self._apply_step(self._steps[self._current_index])
                else:
                    # Last step finished
                    self._running = False
                    self._stop_all_channels()
                    self._log("Sequence complete")
                    if self.on_sequence_end:
                        self.on_sequence_end()

    def _apply_step(self, step: Step) -> None:
        """Send setpoints to all channels listed in this step."""
        self._log(
            f"Step {self._current_index} '{step.name}' "
            f"({step.duration_s}s) — {step.setpoints}"
        )
        if self.on_step_start:
            self.on_step_start(self._current_index, step)

        for channel_name, value in step.setpoints.items():
            instrument = self._channels.get(channel_name)
            if instrument is None:
                logger.warning(f"Channel '{channel_name}' not found")
                continue
            self._set_channel(channel_name, instrument, value)

    def _set_channel(
        self, name: str, instrument: Any, value: float
    ) -> None:
        """Send a setpoint to one channel, handling pump vs pressure."""
        from core.pump_interface import PumpInterface
        try:
            from core.pressure_controller_interface import (
                PressureControllerInterface
            )
            has_prc = True
        except ImportError:
            has_prc = False

        try:
            if isinstance(instrument, PumpInterface):
                # PumpInterface: pump_id is always 0 for single-channel use
                pump_ids = instrument.find_pumps()
                instrument.set_rates({pid: value for pid in pump_ids})
                instrument.run_all()
            elif has_prc and isinstance(instrument, PressureControllerInterface):
                # Set all channels to this value
                for ch in range(instrument.channel_count):
                    instrument.set_pressure(ch, value)
            else:
                logger.warning(
                    f"Channel '{name}': unknown instrument type "
                    f"{type(instrument)}"
                )
        except Exception as e:
            logger.error(f"Channel '{name}': failed to set {value} — {e}")

    def _stop_all_channels(self) -> None:
        """Zero all channels."""
        from core.pump_interface import PumpInterface
        for name, instrument in self._channels.items():
            try:
                if isinstance(instrument, PumpInterface):
                    instrument.stop_all()
                else:
                    logger.warning(
                        f"Channel '{name}': stop not implemented "
                        f"for {type(instrument)}"
                    )
            except Exception as e:
                logger.error(f"Channel '{name}': stop failed — {e}")

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.on_log:
            self.on_log(message)