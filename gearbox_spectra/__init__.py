"""Gearbox UFF spectrum generation tools."""

from .processing import Spectrum, acceleration_to_velocity_spectrum, rms_spectrum
from .uff import UFFError, UFFSignal, iter_uff_signals, parse_dataset_58

__all__ = [
    "Spectrum",
    "UFFError",
    "UFFSignal",
    "acceleration_to_velocity_spectrum",
    "iter_uff_signals",
    "parse_dataset_58",
    "rms_spectrum",
]
