from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Spectrum:
    frequency: np.ndarray
    amplitude: np.ndarray
    unit: str


def rms_spectrum(
    values: np.ndarray,
    sample_rate: float,
    unit: str,
    *,
    remove_mean: bool = True,
) -> Spectrum:
    """Return a Hann-windowed, single-sided RMS amplitude spectrum."""
    signal = np.asarray(values, dtype=float)
    if signal.ndim != 1 or signal.size < 2:
        raise ValueError("spectrum input must be a one-dimensional signal")
    if sample_rate <= 0:
        raise ValueError("sample rate must be positive")

    if remove_mean:
        signal = signal - np.mean(signal)
    window = np.hanning(signal.size)
    coherent_sum = float(np.sum(window))
    if coherent_sum == 0:
        raise ValueError("signal is too short for a Hann window")

    transformed = np.fft.rfft(signal * window)
    amplitude = np.abs(transformed) * np.sqrt(2.0) / coherent_sum
    amplitude[0] = np.abs(transformed[0]) / coherent_sum
    if signal.size % 2 == 0:
        amplitude[-1] = np.abs(transformed[-1]) / coherent_sum

    frequency = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate)
    return Spectrum(frequency=frequency, amplitude=amplitude, unit=unit)


def acceleration_to_velocity_spectrum(
    acceleration: Spectrum, *, output_unit: str = "mm/s"
) -> Spectrum:
    """Integrate an acceleration RMS spectrum in the frequency domain."""
    frequency = acceleration.frequency
    amplitude = np.zeros_like(acceleration.amplitude)
    nonzero = frequency > 0
    amplitude[nonzero] = (
        acceleration.amplitude[nonzero] / (2.0 * np.pi * frequency[nonzero])
    )
    if output_unit == "mm/s":
        amplitude *= 1000.0
    elif output_unit != "m/s":
        raise ValueError(f"unsupported velocity output unit: {output_unit}")
    return Spectrum(frequency=frequency, amplitude=amplitude, unit=output_unit)


def dominant_peak(
    spectrum: Spectrum, minimum_frequency: float = 0.0, maximum_frequency: float | None = None
) -> tuple[float, float]:
    mask = spectrum.frequency >= minimum_frequency
    if maximum_frequency is not None:
        mask &= spectrum.frequency <= maximum_frequency
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return 0.0, 0.0
    index = indices[int(np.argmax(spectrum.amplitude[indices]))]
    return float(spectrum.frequency[index]), float(spectrum.amplitude[index])
