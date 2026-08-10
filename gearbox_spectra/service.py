from __future__ import annotations

from pathlib import Path
from typing import Any

from .batch import _build_industrial_all_reference, _industrial_spectrum
from .phase2 import (
    _candidate_summary,
    _diagnostic_interpretation,
    _expanded_candidates,
    _frequency_resolution,
    _nearest_peak,
    analyze_sidebands,
    comparison_tolerance_hz,
    detect_significant_peaks,
    load_defect_frequency_table,
    match_peak,
)
from .manifest import SPECTRA_IMAGE_PLOTS
from .processing import Spectrum
from .uff import UFFError, _decode_uff, parse_dataset_58


def _display_unit(unit: str) -> str:
    return "m/s²" if "m/s" in unit and "Â" in unit else unit


def _reference_metadata(reference: Any) -> dict[str, Any]:
    return {
        "kind": reference.kind,
        "header": reference.header,
        "x_limit": list(reference.x_limit),
        "y_limit": list(reference.y_limit),
        "x_tick": reference.x_tick,
        "y_tick": reference.y_tick,
        "rpm": reference.rpm,
        "reference_image": reference.reference_image,
    }


def _json_spectrum(spectrum: Spectrum) -> dict[str, Any]:
    return {
        "frequencies": spectrum.frequency.tolist(),
        "amplitudes": spectrum.amplitude.tolist(),
        "unit": _display_unit(spectrum.unit),
    }


def _parse_upload(raw: bytes, filename: str):
    if not filename.lower().endswith(".uff"):
        raise UFFError("Only .uff files can be analyzed.")
    if not raw:
        raise UFFError("The uploaded UFF file is empty.")
    return parse_dataset_58(_decode_uff(raw), source_name=Path(filename).name)


def _build_reference(signal):
    exact = next((item for item in SPECTRA_IMAGE_PLOTS if item.source == signal.source_name), None)
    return _build_industrial_all_reference(signal, exact)


def build_phase1_result(raw: bytes, filename: str) -> dict[str, Any]:
    signal = _parse_upload(raw, filename)
    reference = _build_reference(signal)
    spectrum = _industrial_spectrum(signal, reference)
    return {
        "filename": signal.source_name,
        "phase": 1,
        "spectrum": _json_spectrum(spectrum),
        "metadata": {
            "title": signal.title,
            "timestamp": signal.timestamp,
            "sample_count": signal.sample_count,
            "sample_interval_s": signal.sample_interval,
            "sample_rate_hz": signal.sample_rate,
            "quantity": signal.quantity,
            "source_unit": _display_unit(signal.unit),
            "processing": reference.kind,
            "reference": _reference_metadata(reference),
        },
    }


def build_phase2_result(
    raw: bytes,
    filename: str,
    defect_table_pdf: str | Path,
    *,
    sideband_analysis: bool = False,
) -> dict[str, Any]:
    signal = _parse_upload(raw, filename)
    reference = _build_reference(signal)
    spectrum = _industrial_spectrum(signal, reference)
    frequencies = load_defect_frequency_table(defect_table_pdf)
    resolution = _frequency_resolution(spectrum)
    candidates = _expanded_candidates(frequencies, reference.x_limit[1])
    peaks = detect_significant_peaks(spectrum, reference.x_limit)
    spacing_references = [item for item in frequencies if item.frequency_hz <= 100.0]

    peak_results: list[dict[str, Any]] = []
    sideband_results: list[dict[str, Any]] = []
    for peak in peaks:
        best, all_matches = match_peak(peak, candidates, resolution, spectrum.unit)
        sidebands = []
        if best is not None and sideband_analysis:
            sidebands = analyze_sidebands(
                peak, peaks, spacing_references, reference.x_limit, resolution
            )
        row: dict[str, Any] = {
            "frequency_hz": peak.frequency_hz,
            "amplitude": peak.amplitude,
            "prominence": peak.prominence,
            "bin_index": peak.bin_index,
            "match_status": best is not None,
            "matched_family": best.base.family if best else None,
            "component": best.base.component if best else None,
            "characteristic": best.base.name if best else None,
            "harmonic_order": best.harmonic_order if best else None,
            "theoretical_frequency_hz": best.theoretical_frequency_hz if best else None,
            "difference_hz": best.difference_hz if best else None,
            "tolerance_hz": best.tolerance_hz if best else None,
            "all_candidates_within_tolerance": _candidate_summary(all_matches),
            "sidebands": [],
            "diagnostic_interpretation": _diagnostic_interpretation(spectrum.unit, best, sidebands),
        }
        for sideband in sidebands:
            side_peak = _nearest_peak(
                sideband.sideband_frequency_hz,
                peaks,
                comparison_tolerance_hz(sideband.sideband_frequency_hz, resolution),
            )
            item = {
                "frequency_hz": sideband.sideband_frequency_hz,
                "amplitude": side_peak.amplitude if side_peak else None,
                "side": sideband.side,
                "order": sideband.order,
                "spacing_hz": sideband.spacing_hz,
                "spacing_name": sideband.spacing_name,
                "detected_spacing_hz": sideband.detected_spacing_hz,
                "difference_hz": sideband.difference_hz,
            }
            row["sidebands"].append(item)
            sideband_results.append({"center_frequency_hz": peak.frequency_hz, **item})
        peak_results.append(row)

    return {
        "filename": signal.source_name,
        "phase": 2,
        "spectrum": _json_spectrum(spectrum),
        "metadata": {
            "title": signal.title,
            "timestamp": signal.timestamp,
            "sample_count": signal.sample_count,
            "sample_interval_s": signal.sample_interval,
            "sample_rate_hz": signal.sample_rate,
            "quantity": signal.quantity,
            "source_unit": _display_unit(signal.unit),
            "processing": reference.kind,
            "reference": _reference_metadata(reference),
            "fft_resolution_hz": resolution,
            "comparison_tolerance": "max(2 FFT bins, 1% of theoretical frequency)",
            "base_frequency_count": len(frequencies),
        },
        "analysis": {
            "peak_detection": True,
            "characteristic_matching": True,
            "sideband_analysis": sideband_analysis,
            "peaks": peak_results,
            "sidebands": sideband_results,
            "counts": {
                "detected_peaks": len(peak_results),
                "matched_peaks": sum(1 for item in peak_results if item["match_status"]),
                "sideband_hits": len(sideband_results),
            },
        },
    }
