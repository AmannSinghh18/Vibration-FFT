from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import re
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


STANDARD_INDUSTRIAL_SIZE_PX = (1920, 529)
IST_OFFSET = timedelta(hours=5, minutes=30)


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


def _signal_number(source_name: str) -> int:
    match = re.search(r"\((\d+)\)", source_name)
    return int(match.group(1)) if match else 0


def _format_report_timestamp(timestamp: str) -> str:
    parts = [int(item) for item in re.findall(r"\d+", timestamp)]
    if len(parts) < 6:
        return timestamp.strip()
    day, month, year, hour, minute, second = parts[:6]
    report_time = datetime(year, month, day, hour, minute, second) + IST_OFFSET
    hour_12 = report_time.hour % 12 or 12
    return f"{report_time:%d-%b-%y} {hour_12}:{report_time:%M:%S} {report_time:%p}"


def _infer_industrial_kind(signal: UFFSignal) -> str:
    source_number = _signal_number(signal.source_name)
    if signal.quantity.lower() == "velocity" or signal.unit == "mm/s":
        return "velocity_native"
    if signal.sample_rate > 10_000:
        return "acceleration"
    if 3_000 <= signal.sample_rate <= 4_000:
        return "envelope"
    if 900 <= signal.sample_rate <= 1_100:
        return "velocity_from_acceleration"
    if 1_900 <= signal.sample_rate <= 2_100:
        if source_number in {36, 41, 46, 51, 56}:
            return "envelope"
        return "velocity_from_acceleration"
    return "acceleration"


def _infer_industrial_limits(
    signal: UFFSignal,
    kind: str,
) -> tuple[tuple[float, float], tuple[float, float], float, float]:
    if kind == "velocity_native":
        return (0, 2000), (0, 4), 200, 0.5
    if kind == "velocity_from_acceleration":
        if signal.sample_rate <= 1_100:
            return (0, 400), (0, 4), 50, 0.5
        return (0, 800), (0, 4), 50, 0.5
    if kind == "acceleration":
        return (0, 10000), (0, 12), 1000, 2
    if kind == "envelope":
        if signal.sample_rate <= 2_100:
            return (0, 400), (0, 8), 50, 1
        return (0, 1500), (0, 10), 100, 1
    return (0, min(signal.sample_rate / 2, 10_000)), (0, 10), 100, 1


def _infer_acquisition_label(signal: UFFSignal, kind: str) -> str:
    source_number = _signal_number(signal.source_name)
    if kind == "velocity_native":
        return r"1002 T _SV3,2kHz0,25Hz20s"
    if kind == "velocity_from_acceleration":
        if signal.sample_rate <= 1_100:
            return r"1006 T _SV0,4kHz0,06Hz16s"
        return r"1004 T _SV0,8kHz0,03Hz27s"
    if kind == "acceleration":
        return r"1010 T _SA12,8kHz1Hz0s"
    if kind == "envelope":
        high_band_numbers = {4, 9, 14, 19, 24, 30, 36, 41, 46, 51, 56}
        if source_number in high_band_numbers:
            return r"1018 T _EA1,5kHz2,5-10kHz"
        return r"1012 T _EA1,5kHz0,5-10kHz"
    return r"1000 T _Spectrum"


def _build_industrial_all_reference(
    signal: UFFSignal,
    exact_reference: IndustrialImagePlot | None,
) -> IndustrialImagePlot:
    if exact_reference is not None:
        return exact_reference

    kind = _infer_industrial_kind(signal)
    x_limit, y_limit, x_tick, y_tick = _infer_industrial_limits(signal, kind)
    report_timestamp = _format_report_timestamp(signal.timestamp)
    source_label = Path(signal.source_name).stem
    acquisition = _infer_acquisition_label(signal, kind)
    header = (
        rf"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_"
        rf"{source_label} inferred measurement\{acquisition}\Spectrum {report_timestamp}"
    )
    return IndustrialImagePlot(
        reference_image=signal.source_name,
        source=signal.source_name,
        kind=kind,
        header=header,
        x_limit=x_limit,
        y_limit=y_limit,
        x_tick=x_tick,
        y_tick=y_tick,
        rpm=992,
        default_size_px=STANDARD_INDUSTRIAL_SIZE_PX,
    )


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
    spectra_all_dir = output / "spectra_all_57"
    reference_sizes = _reference_image_sizes(spectra_reference_path)
    exact_image_by_source = {
        reference.source: reference for reference in SPECTRA_IMAGE_PLOTS
    }
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

    generated_spectra_all = 0
    for signal in signals:
        exact_reference = exact_image_by_source.get(signal.source_name)
        industrial_reference = _build_industrial_all_reference(
            signal,
            exact_reference,
        )
        spectrum = _industrial_spectrum(signal, industrial_reference)
        peak_frequency, peak_amplitude = dominant_peak(
            spectrum, 0.01, industrial_reference.x_limit[1]
        )
        size_px = (
            reference_sizes.get(exact_reference.reference_image)
            if exact_reference is not None
            else None
        )
        plot_industrial_spectrum(
            spectrum,
            spectra_all_dir / safe_stem(signal.source_name),
            reference=industrial_reference,
            size_px=size_px,
            formats=formats,
        )
        rows.append(
            {
                "category": "spectra_all_57",
                "figure": "",
                "source": signal.source_name,
                "processing": industrial_reference.kind,
                "sample_count": signal.sample_count,
                "sample_rate_hz": f"{signal.sample_rate:.9g}",
                "signal_rms": f"{np.sqrt(np.mean((signal.values - np.mean(signal.values)) ** 2)):.9g}",
                "spectrum_unit": spectrum.unit,
                "peak_frequency_hz": f"{peak_frequency:.9g}",
                "peak_rms_amplitude": f"{peak_amplitude:.9g}",
            }
        )
        generated_spectra_all += 1

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
        "spectra_all_57_plots": generated_spectra_all,
        "skipped_spectra_image_plots": len(skipped_spectra_images),
        "missing_reference_plots": len(MISSING_PRESSING_SIDE),
    }
