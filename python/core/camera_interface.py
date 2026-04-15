"""
camera_interface.py
Abstract base class that every camera driver must implement.
All higher-level code (GUI, tests) depends only on this interface.
"""

from abc import ABC, abstractmethod
import numpy as np


class CameraInterface(ABC):
    """Abstract base class for all camera drivers."""

    @abstractmethod
    def start(self) -> None:
        """Open the camera and begin capturing."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop capturing and release the camera."""
        ...

    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """
        Return the latest frame as a numpy array (H, W, 3) BGR.
        Returns None if no frame is available.
        """
        ...

    @abstractmethod
    def capture_image(self, path: str) -> None:
        """Save current frame to disk at the given path."""
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """True if the camera is currently capturing."""
        ...