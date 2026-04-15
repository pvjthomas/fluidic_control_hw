"""
pump_interface.py
Abstract base class that every syringe pump driver must implement.
All higher-level code (GUI, sequence runner, tests) depends only on this
interface, never on a concrete driver.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class PumpInterface(ABC):
    """Abstract base class for all syringe pump drivers."""

    @abstractmethod
    def find_pumps(self) -> List[int]:
        """Scan the connection and return a list of pump IDs found."""
        ...

    @abstractmethod
    def run_all(self) -> None:
        """Start all pumps at their current rates."""
        ...

    @abstractmethod
    def stop_all(self) -> None:
        """Stop all pumps immediately."""
        ...

    @abstractmethod
    def stop_pump(self, pump_id: int) -> None:
        """Stop a single pump by ID."""
        ...

    @abstractmethod
    def set_rates(self, rates: Dict[int, float]) -> None:
        """
        Set flow rates for one or more pumps.
        rates: dict mapping pump_id -> flow rate in µL/hr.
               Positive = infuse, negative = withdraw.
        """
        ...

    @abstractmethod
    def get_rates(self, pump_ids: List[int]) -> Dict[int, float]:
        """
        Read current flow rates from pumps.
        Returns dict mapping pump_id -> flow rate in µL/hr.
        """
        ...

    @abstractmethod
    def set_diameter(self, pump_id: int, diameter_mm: float) -> None:
        """Set the syringe diameter for a pump in millimetres."""
        ...

    @abstractmethod
    def get_diameter(self, pump_id: int) -> float:
        """Read the syringe diameter for a pump in millimetres."""
        ...

    @abstractmethod
    def prime(self, pump_id: int) -> None:
        """Prime a pump at a fast fixed rate (implementation defines the rate)."""
        ...
