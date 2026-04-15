"""
fake_pump.py
In-memory fake implementation of PumpInterface for development and testing.
No hardware required. Simulates realistic pump state.

Usage:
    pump = FakePump(pump_ids=[0, 1, 2, 3])
    pump.set_rates({0: 500.0, 1: -200.0})
    pump.run_all()
    print(pump.get_rates([0, 1]))
"""

import logging
from typing import Dict, List

from core.pump_interface import PumpInterface

logger = logging.getLogger(__name__)

# Rate at which prime() runs, in µL/hr
PRIME_RATE_UL_HR = 10_000.0

# Default syringe diameter in mm (1 mL BD syringe)
DEFAULT_DIAMETER_MM = 4.699


class FakePump(PumpInterface):
    """
    Fake syringe pump driver. Stores all state in memory and logs
    every command that would be sent to real hardware.
    """

    def __init__(self, pump_ids: List[int]) -> None:
        """
        Args:
            pump_ids: list of integer pump IDs to simulate, e.g. [0, 1, 2, 3]
        """
        self._pump_ids = list(pump_ids)
        self._running = False

        # State per pump ID
        self._rates: Dict[int, float] = {p: 0.0 for p in pump_ids}
        self._diameters: Dict[int, float] = {
            p: DEFAULT_DIAMETER_MM for p in pump_ids
        }

        logger.info(f"FakePump initialised with pump IDs: {self._pump_ids}")

    # ------------------------------------------------------------------
    # PumpInterface implementation
    # ------------------------------------------------------------------

    def find_pumps(self) -> List[int]:
        logger.info(f"find_pumps -> {self._pump_ids}")
        return list(self._pump_ids)

    def run_all(self) -> None:
        self._running = True
        logger.info(
            f"run_all | current rates: "
            f"{self._format_rates(self._pump_ids)}"
        )

    def stop_all(self) -> None:
        self._running = False
        for p in self._pump_ids:
            self._rates[p] = 0.0
        logger.info("stop_all | all pumps stopped, rates zeroed")

    def stop_pump(self, pump_id: int) -> None:
        self._check_id(pump_id)
        self._rates[pump_id] = 0.0
        logger.info(f"stop_pump | pump {pump_id} stopped")

    def set_rates(self, rates: Dict[int, float]) -> None:
        for pump_id, rate in rates.items():
            self._check_id(pump_id)
            self._rates[pump_id] = rate
            direction = "INF" if rate >= 0 else "WDR"
            logger.info(
                f"set_rates | pump {pump_id} -> "
                f"{abs(rate):.2f} µL/hr {direction}"
            )

    def get_rates(self, pump_ids: List[int]) -> Dict[int, float]:
        result = {}
        for pump_id in pump_ids:
            self._check_id(pump_id)
            result[pump_id] = self._rates[pump_id]
        logger.info(f"get_rates | {self._format_rates(pump_ids)}")
        return result

    def set_diameter(self, pump_id: int, diameter_mm: float) -> None:
        self._check_id(pump_id)
        self._diameters[pump_id] = diameter_mm
        logger.info(f"set_diameter | pump {pump_id} -> {diameter_mm} mm")

    def get_diameter(self, pump_id: int) -> float:
        self._check_id(pump_id)
        diameter = self._diameters[pump_id]
        logger.info(f"get_diameter | pump {pump_id} -> {diameter} mm")
        return diameter

    def prime(self, pump_id: int) -> None:
        self._check_id(pump_id)
        self._rates[pump_id] = PRIME_RATE_UL_HR
        self._running = True
        logger.info(
            f"prime | pump {pump_id} -> {PRIME_RATE_UL_HR:.0f} µL/hr INF"
        )

    # ------------------------------------------------------------------
    # Extra helpers (not part of interface — useful for tests)
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def pump_ids(self) -> List[int]:
        return list(self._pump_ids)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_id(self, pump_id: int) -> None:
        if pump_id not in self._pump_ids:
            raise ValueError(
                f"Pump ID {pump_id} not found. "
                f"Available IDs: {self._pump_ids}"
            )

    def _format_rates(self, pump_ids: List[int]) -> str:
        return ", ".join(
            f"p{p}={self._rates[p]:.1f} µL/hr" for p in pump_ids
        )