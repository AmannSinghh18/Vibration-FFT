from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
import zipfile

import numpy as np

from .manifest import (
    MISSING_PRESSING_SIDE,
    REFERENCE_PLOTS,
    SPECTRA_IMAGE_PLOTS,
    IndustrialImagePlot,
    ReferencePlot,
)
from .plotting import plot_industrial_spectrum, plot_spectrum, safe_stem
from .processing import (
    Spectrum,
    acceleration_to_velocity_spectrum,
    dominant_peak,
    rms_spectrum,
)
from .uff import UFFSignal, iter_uff_signals


def _native_spectrum(signal: UFFSignal) -> Spectrum:
    return rms_spectrum(signal.values, signal.sample_rate, signal.unit)


def _reference_spectrum(signal: UFFSignal, reference: ReferencePlot) -> Spectrum:
    native = _native_spectrum(signal)
    if reference.kind == "velocity_from_acceleration":
        return acceleration_to_velocity_spectrum(native)
    if reference.kind == "velocity_native":
        return Spectrum(native.frequency, native.amplitude, "mm/s")
    if reference.kind in {"envelope", "acceleration"}:
        return Spectrum(native.frequency, native.amplitude, "m/s²")
    raise ValueError(f"unsupported reference processing kind: {reference.kind}")


def _industrial_spectrum(signal: UFFSignal, reference: IndustrialImagePlot) -> Spectrum:
    native = _native_spectrum(signal)
    if reference.kind == "velocity_from_acceleration":
        return acceleration_to_velocity_spectrum(native)
    if reference.kind == "velocity_native":
        return Spectrum(native.frequency, native.amplitude, "mm/s")
    if reference.kind in {"envelope", "acceleration"}:
        return Spectrum(native.frequency, native.amplitude, "m/s²")
    raise ValueError(f"unsupported industrial processing kind: {reference.kind}")


def _generic_limits(spectrum: Spectrum) -> tuple[tuple[float, float], tuple[float, float]]:
    maximum_frequency = min(float(spectrum.frequency[-1]), 10_000.0)
    mask = spectrum.frequency <= maximum_frequency
    maximum_amplitude = float(np.max(spectrum.amplitude[mask]))
    return (0.0, maximum_frequency), (0.0, maximum_amplitude * 1.08 or 1.0)


def _reference_image_sizes(reference_path: str | Path | None) -> dict[str, tuple[int, int]]:
    if reference_path is None:
        return {}
    path = Path(reference_path)
    if not path.exists():
        return {}

    from PIL import Image

    sizes: dict[str, tuple[int, int]] = {}
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                with Image.open(BytesIO(archive.read(name))) as image:
                    sizes[Path(name).name] = image.size
        return sizes

    if path.is_dir():
        for image_path in path.rglob("*"):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            with Image.open(image_path) as image:
                sizes[image_path.name] = image.size
        return sizes

    return sizes


def generate_batch(
    input_path: str | Path,
    output_path: str | Path,
    *,
    formats: tuple[str, ...] = ("pdf", "svg", "png"),
    spectra_reference_path: str | Path | None = None,
) -> dict[str, int]:
    output = Path(output_path)
    signals = list(iter_uff_signals(input_path))
    by_name = {signal.source_name: signal for signal in signals}
    generic_dir = output / "generic"
    reference_dir = output / "reference_matched"
    spectra_image_dir = output / "spectra_image_matched"
    reference_sizes = _reference_image_sizes(spectra_reference_path)
    rows: list[dict[str, object]] = []

    for signal in signals:
        spectrum = _native_spectrum(signal)
        x_limit, y_limit = _generic_limits(spectrum)
        peak_frequency, peak_amplitude = dominant_peak(spectrum, 0.01, x_limit[1])
        plot_spectrum(
            spectrum,
            generic_dir / safe_stem(signal.source_name),
            title=f"{signal.source_name} | {signal.timestamp} | Native {signal.quantity}",
            x_limit=x_limit,
            y_limit=y_limit,
            formats=formats,
        )
        rows.append(
            {
                "category": "generic",
                "figure": "",
                "source": signal.source_name,
                "processing": "native",
                "sample_count": signal.sample_count,
                "sample_rate_hz": f"{signal.sample_rate:.9g}",
                "signal_rms": f"{np.sqrt(np.mean((signal.values - np.mean(signal.values)) ** 2)):.9g}",
                "spectrum_unit": spectrum.unit,
                "peak_frequency_hz": f"{peak_frequency:.9g}",
                "peak_rms_amplitude": f"{peak_amplitude:.9g}",
            }
        )

    generated_references = 0
    for reference in REFERENCE_PLOTS:
        signal = by_name.get(reference.source)
        if signal is None:
            continue
        spectrum = _reference_spectrum(signal, reference)
        peak_frequency, peak_amplitude = dominant_peak(
            spectrum, 0.01, reference.x_limit[1]
        )
        plot_spectrum(
            spectrum,
            reference_dir / f"fig_{reference.figure:02d}",
            title=f"Fig. {reference.figure}: {reference.title}",
            x_limit=reference.x_limit,
            y_limit=reference.y_limit,
            x_tick=reference.x_tick,
            y_tick=reference.y_tick,
            markers=reference.markers,
            rpm=reference.rpm,
            formats=formats,
        )
        rows.append(
            {
                "category": "reference",
                "figure": reference.figure,
                "source": signal.source_name,
                "processing": reference.kind,
                "sample_count": signal.sample_count,
                "sample_rate_hz": f"{signal.sample_rate:.9g}",
                "signal_rms": f"{np.sqrt(np.mean((signal.values - np.mean(signal.values)) ** 2)):.9g}",
                "spectrum_unit": spectrum.unit,
                "peak_frequency_hz": f"{peak_frequency:.9g}",
                "peak_rms_amplitude": f"{peak_amplitude:.9g}",
            }
        )
        generated_references += 1

    generated_spectra_images = 0
    skipped_spectra_images: list[str] = []
    for image_reference in SPECTRA_IMAGE_PLOTS:
        signal = by_name.get(image_reference.source)
        if signal is None:
            skipped_spectra_images.append(
                f"{image_reference.reference_image}: missing {image_reference.source}"
            )
            continue
        spectrum = _industrial_spectrum(signal, image_reference)
        peak_frequency, peak_amplitude = dominant_peak(
            spectrum, 0.01, image_reference.x_limit[1]
        )
        plot_industrial_spectrum(
            spectrum,
            spectra_image_dir / Path(image_reference.reference_image).stem,
            reference=image_reference,
            size_px=reference_sizes.get(image_reference.reference_image),
            formats=formats,
        )
        rows.append(
            {
                "category": "spectra_image_reference",
                "figure": image_reference.reference_image,
                "source": signal.source_name,
                "processing": image_reference.kind,
                "sample_count": signal.sample_count,
                "sample_rate_hz": f"{signal.sample_rate:.9g}",
                "signal_rms": f"{np.sqrt(np.mean((signal.values - np.mean(signal.values)) ** 2)):.9g}",
                "spectrum_unit": spectrum.unit,
                "peak_frequency_hz": f"{peak_frequency:.9g}",
                "peak_rms_amplitude": f"{peak_amplitude:.9g}",
            }
        )
        generated_spectra_images += 1

    output.mkdir(parents=True, exist_ok=True)
    with (output / "spectrum_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    missing_text = (
        "The supplied archive has no UFF records matching these Pressing-side "
        "report timestamps. These figures were not fabricated:\n\n"
        + "\n".join(f"- {item}" for item in MISSING_PRESSING_SIDE)
        + "\n"
    )
    (output / "missing_pressing_side.txt").write_text(missing_text, encoding="utf-8")
    if skipped_spectra_images:
        (output / "skipped_spectra_images.txt").write_text(
            "\n".join(skipped_spectra_images) + "\n",
            encoding="utf-8",
        )

    return {
        "signals": len(signals),
        "generic_plots": len(signals),
        "reference_plots": generated_references,
        "spectra_image_plots": generated_spectra_images,
        "skipped_spectra_image_plots": len(skipped_spectra_images),
        "missing_reference_plots": len(MISSING_PRESSING_SIDE),
    }
