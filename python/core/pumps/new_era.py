"""
new_era.py
PumpInterface implementation for New Era syringe pumps.
Supports NE-500, NE-1000, NE-1010, NE-1600, NE-4000 and compatible models.

Serial protocol: ASCII commands over RS-232/USB at 19200 baud.

Usage:
    pump = NewEraPump(port='COM3', pump_ids=[0, 1, 2])
    pump.run_all()
    pump.set_rates({0: 500.0, 1: -200.0})
    pump.stop_all()
"""

import logging
from typing import Dict, List

import serial

from core.pump_interface import PumpInterface

logger = logging.getLogger(__name__)

# Default serial settings for New Era pumps
DEFAULT_BAUD = 19200
DEFAULT_TIMEOUT = 1.0  # seconds

# Rate threshold above which mL/hr is used instead of µL/hr
RATE_THRESHOLD_UL_HR = 5000.0


class NewEraPump(PumpInterface):
    """
    Driver for New Era syringe pumps communicating over serial.
    One instance manages all pumps on the serial network.
    """

    def __init__(
        self,
        port: str,
        pump_ids: List[int],
        baud: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Args:
            port:     Serial port name, e.g. 'COM3' or '/dev/ttyUSB0'
            pump_ids: List of pump IDs expected on the network
            baud:     Baud rate (default 19200)
            timeout:  Serial read timeout in seconds
        """
        self._port = port
        self._pump_ids = list(pump_ids)
        self._ser = serial.Serial(port, baud, timeout=timeout)
        self._running = False
        logger.info(
            f"NewEraPump connected on {port} at {baud} baud, "
            f"pump IDs: {self._pump_ids}"
        )

    def close(self) -> None:
        """Close the serial connection."""
        if self._ser.isOpen():
            self._ser.close()
            logger.info("Serial connection closed")

    # ------------------------------------------------------------------
    # PumpInterface implementation
    # ------------------------------------------------------------------

    def find_pumps(self, tot_range: int = 10) -> List[int]:
        """Scan addresses 0-9 and return IDs that respond."""
        pumps = []
        for i in range(tot_range):
            self._ser.write(str.encode('%iADR\x0D' % i))
            output = self._ser.readline()
            if len(output) > 0:
                pumps.append(i)
        logger.info(f"find_pumps -> {pumps}")
        return pumps

    def run_all(self) -> None:
        cmd = b'*RUN\x0D'
        self._ser.write(cmd)
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from run_all not understood")
        else:
            self._running = True
            logger.info("run_all")

    def stop_all(self) -> None:
        cmd = '*STP\x0D'
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from stop_all not understood")
        else:
            self._running = False
            logger.info("stop_all")

    def stop_pump(self, pump_id: int) -> None:
        self._check_id(pump_id)

        cmd = '%iSTP\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from stop_pump not understood")

        cmd = '%iRAT0UH\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from stop_pump not understood")
        else:
            logger.info(f"stop_pump | pump {pump_id}")

    def set_rates(self, rates: Dict[int, float]) -> None:
        cmd = ''
        for pump_id, fr in rates.items():
            self._check_id(pump_id)
            fr = float(fr)

            # Set direction
            direction = 'INF' if fr >= 0 else 'WDR'
            frcmd = '%iDIR%s\x0D' % (pump_id, direction)
            self._ser.write(str.encode(frcmd))
            output = self._ser.readline()
            if b'?' in output:
                logger.error(
                    f"{frcmd.strip()} from set_rates not understood"
                )

            # Build rate command — use MH (mL/hr) above threshold
            fr = abs(fr)
            if fr < RATE_THRESHOLD_UL_HR:
                cmd += str(pump_id) + 'RAT' + str(fr)[:5] + 'UH*'
            else:
                cmd += str(pump_id) + 'RAT' + str(fr / 1000.0)[:5] + 'MH*'

        cmd += '\x0D'
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from set_rates not understood")
        else:
            logger.info(f"set_rates | {rates}")

    def get_rates(self, pump_ids: List[int]) -> Dict[int, float]:
        rates = {}
        for pump_id in pump_ids:
            self._check_id(pump_id)
            rates[pump_id] = self._get_rate(pump_id)
        logger.info(f"get_rates | {rates}")
        return rates

    def set_diameter(self, pump_id: int, diameter_mm: float) -> None:
        self._check_id(pump_id)
        cmd = '%iDIA%s\x0D' % (pump_id, diameter_mm)
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from set_diameter not understood")
        else:
            logger.info(f"set_diameter | pump {pump_id} -> {diameter_mm} mm")

    def get_diameter(self, pump_id: int) -> float:
        self._check_id(pump_id)
        cmd = '%iDIA\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from get_diameter not understood")
        dia = float(output[4:-1])
        logger.info(f"get_diameter | pump {pump_id} -> {dia} mm")
        return dia

    def prime(self, pump_id: int) -> None:
        self._check_id(pump_id)

        cmd = '%iRAT10.0MH\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from prime not understood")

        cmd = '%iRUN\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from prime not understood")
        else:
            self._running = True
            logger.info(f"prime | pump {pump_id}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_rate(self, pump_id: int) -> float:
        """Read the current flow rate for a single pump. Returns µL/hr."""
        cmd = f"{pump_id}RAT\x0D"
        self._ser.write(str.encode(cmd, encoding='ASCII'))
        output = self._ser.readline()

        # Detect withdraw direction
        sign = -1.0 if output.decode()[3] == 'W' else 1.0

        # Re-query to get the rate value cleanly
        cmd = '%iRAT\x0D' % pump_id
        self._ser.write(str.encode(cmd))
        output = self._ser.readline()
        if b'?' in output:
            logger.error(f"{cmd.strip()} from get_rate not understood")
            return 0.0

        units = output[-3:-1]
        if units == b'MH':
            rate = float(output[4:-3]) * 1000.0  # convert mL/hr -> µL/hr
        elif units == b'UH':
            rate = float(output[4:-3])
        else:
            logger.error(f"get_rate | unrecognised units: {units}")
            return 0.0

        return sign * rate

    def _check_id(self, pump_id: int) -> None:
        if pump_id not in self._pump_ids:
            raise ValueError(
                f"Pump ID {pump_id} not found. "
                f"Available IDs: {self._pump_ids}"
            )