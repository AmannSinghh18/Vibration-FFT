from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import numpy as np
from pypdf import PdfReader

from .batch import (
    _build_industrial_all_reference,
    _industrial_spectrum,
    _reference_image_sizes,
)
from .manifest import IndustrialImagePlot, SPECTRA_IMAGE_PLOTS
from .plotting import plot_industrial_spectrum, safe_stem
from .processing import Spectrum
from .uff import iter_uff_signals


@dataclass(frozen=True)
class BaseFrequency:
    family: str
    component: str
    name: str
    frequency_hz: float


@dataclass(frozen=True)
class MatchCandidate:
    base: BaseFrequency
    harmonic_order: int
    theoretical_frequency_hz: float
    difference_hz: float
    tolerance_hz: float


@dataclass(frozen=True)
class DetectedPeak:
    frequency_hz: float
    amplitude: float
    prominence: float
    bin_index: int


@dataclass(frozen=True)
class SidebandHit:
    center_frequency_hz: float
    sideband_frequency_hz: float
    side: str
    order: int
    spacing_hz: float
    spacing_name: str
    detected_spacing_hz: float
    difference_hz: float


GEAR_COMPONENTS = ("Input/Motor shaft", "2nd shaft", "Output shaft")
BEARING_COLUMNS = (
    ("FTF/Cage", "Cage"),
    ("BSF/Rolling element", "RE"),
    ("BPFO/Outer race", "OR"),
    ("BPFI/Inner race", "IR"),
)


def _numbers_from_line(line: str) -> list[float]:
    return [float(item) for item in re.findall(r"\d+(?:\.\d+)?", line)]


def load_defect_frequency_table(pdf_path: str | Path) -> list[BaseFrequency]:
    """Extract gearbox and bearing characteristic frequencies from the PDF table."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"defect frequency table not found: {path}")

    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    base_frequencies: list[BaseFrequency] = []

    for line in lines:
        lower = line.lower()
        if lower.startswith("rotation freq"):
            values = _numbers_from_line(line)
            for component, frequency in zip(GEAR_COMPONENTS, values[-3:]):
                base_frequencies.append(
                    BaseFrequency("gear", component, "Shaft rotation", frequency)
                )
        elif lower.startswith("wobbling freq"):
            values = _numbers_from_line(line)
            for component, frequency in zip(GEAR_COMPONENTS, values[-3:]):
                base_frequencies.append(
                    BaseFrequency("gear", component, "Wobbling", frequency)
                )

    standalone_values = [
        float(line)
        for line in lines
        if re.fullmatch(r"\d+(?:\.\d+)?", line) and float(line) > 100.0
    ]
    for name, frequency in zip(("GMF Stage 1", "GMF Stage 2"), standalone_values[:2]):
        base_frequencies.append(BaseFrequency("gear", "Gear mesh", name, frequency))

    current_bearing_component = ""
    for line in lines:
        lower = line.lower()
        if lower.startswith("bearing input shaft"):
            current_bearing_component = "Input shaft bearing"
            continue
        if lower.startswith("bearing 2nd shaft"):
            current_bearing_component = "2nd shaft bearing"
            continue
        if lower.startswith("bearing output shaft"):
            current_bearing_component = "Output shaft bearing"
            continue
        match = re.match(
            r"^(\d+(?:/\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$",
            line,
        )
        if match and current_bearing_component:
            bearing_id = match.group(1)
            values = [float(match.group(index)) for index in range(2, 6)]
            for (name, short_name), frequency in zip(BEARING_COLUMNS, values):
                base_frequencies.append(
                    BaseFrequency(
                        "bearing",
                        f"{current_bearing_component} {bearing_id}",
                        f"{short_name} {name}",
                        frequency,
                    )
                )

    if not base_frequencies:
        raise ValueError(f"no usable defect frequencies could be extracted from {path}")
    return base_frequencies


def _frequency_resolution(spectrum: Spectrum) -> float:
    if spectrum.frequency.size < 2:
        return 0.0
    return float(np.median(np.diff(spectrum.frequency)))


def comparison_tolerance_hz(theoretical_frequency_hz: float, resolution_hz: float) -> float:
    return max(2.0 * resolution_hz, 0.01 * theoretical_frequency_hz)


def _expanded_candidates(
    base_frequencies: Iterable[BaseFrequency],
    max_frequency_hz: float,
) -> list[tuple[BaseFrequency, int, float]]:
    candidates: list[tuple[BaseFrequency, int, float]] = []
    for base in base_frequencies:
        if base.frequency_hz <= 0:
            continue
        if base.family == "bearing":
            max_order = 10
        elif "GMF" in base.name:
            max_order = 5
        else:
            max_order = 10
        for order in range(1, max_order + 1):
            frequency = base.frequency_hz * order
            if frequency <= max_frequency_hz:
                candidates.append((base, order, frequency))
    return candidates


def detect_significant_peaks(
    spectrum: Spectrum,
    x_limit: tuple[float, float],
    *,
    minimum_frequency_hz: float = 0.5,
) -> list[DetectedPeak]:
    frequency = spectrum.frequency
    amplitude = spectrum.amplitude
    mask = (
        (frequency >= max(x_limit[0], minimum_frequency_hz))
        & (frequency <= x_limit[1])
        & np.isfinite(amplitude)
    )
    visible_indices = np.flatnonzero(mask)
    if visible_indices.size < 3:
        return []

    visible_amplitude = amplitude[visible_indices]
    noise_median = float(np.median(visible_amplitude))
    mad = float(np.median(np.abs(visible_amplitude - noise_median)))
    robust_sigma = 1.4826 * mad if mad > 0 else float(np.std(visible_amplitude))
    maximum = float(np.max(visible_amplitude))
    min_height = max(noise_median + 12.0 * robust_sigma, 0.07 * maximum)
    min_prominence = max(10.0 * robust_sigma, 0.06 * maximum)
    resolution = _frequency_resolution(spectrum)
    local_window_hz = max(2.0, 8.0 * resolution)
    local_window_bins = max(3, int(round(local_window_hz / resolution))) if resolution > 0 else 5

    local_peak_indices: list[int] = []
    for index in visible_indices[1:-1]:
        if amplitude[index] > amplitude[index - 1] and amplitude[index] >= amplitude[index + 1]:
            start = max(0, index - local_window_bins)
            end = min(amplitude.size, index + local_window_bins + 1)
            neighborhood = np.concatenate((amplitude[start:index], amplitude[index + 1 : end]))
            local_floor = float(np.median(neighborhood)) if neighborhood.size else noise_median
            prominence = float(amplitude[index] - local_floor)
            if amplitude[index] >= min_height and prominence >= min_prominence:
                local_peak_indices.append(index)

    peaks = [
        DetectedPeak(float(frequency[index]), float(amplitude[index]), 0.0, int(index))
        for index in local_peak_indices
    ]
    refined: list[DetectedPeak] = []
    for peak in peaks:
        start = max(0, peak.bin_index - local_window_bins)
        end = min(amplitude.size, peak.bin_index + local_window_bins + 1)
        neighborhood = np.concatenate(
            (amplitude[start : peak.bin_index], amplitude[peak.bin_index + 1 : end])
        )
        local_floor = float(np.median(neighborhood)) if neighborhood.size else noise_median
        refined.append(
            DetectedPeak(
                peak.frequency_hz,
                peak.amplitude,
                float(peak.amplitude - local_floor),
                peak.bin_index,
            )
        )

    min_distance_hz = max(2.0, 6.0 * resolution)
    selected: list[DetectedPeak] = []
    for peak in sorted(refined, key=lambda item: item.amplitude, reverse=True):
        if all(abs(peak.frequency_hz - kept.frequency_hz) >= min_distance_hz for kept in selected):
            selected.append(peak)
    selected = sorted(selected, key=lambda item: item.prominence, reverse=True)[:35]
    return sorted(selected, key=lambda item: item.frequency_hz)


def match_peak(
    peak: DetectedPeak,
    candidates: list[tuple[BaseFrequency, int, float]],
    resolution_hz: float,
    spectrum_unit: str,
) -> tuple[MatchCandidate | None, list[MatchCandidate]]:
    matches: list[MatchCandidate] = []
    for base, order, theoretical_frequency in candidates:
        tolerance = comparison_tolerance_hz(theoretical_frequency, resolution_hz)
        difference = abs(peak.frequency_hz - theoretical_frequency)
        if difference <= tolerance:
            matches.append(
                MatchCandidate(base, order, theoretical_frequency, difference, tolerance)
            )
    if not matches:
        return None, []

    def priority(candidate: MatchCandidate) -> tuple[float, int]:
        normalized_difference = candidate.difference_hz / candidate.tolerance_hz
        if spectrum_unit == "mm/s":
            family_rank = 0 if candidate.base.family == "gear" else 1
        else:
            family_rank = 0 if candidate.base.family == "bearing" else 1
        return normalized_difference, family_rank

    matches.sort(key=priority)
    return matches[0], matches


def _nearest_peak(
    target_frequency_hz: float,
    peaks: list[DetectedPeak],
    tolerance_hz: float,
) -> DetectedPeak | None:
    if not peaks:
        return None
    nearest = min(peaks, key=lambda peak: abs(peak.frequency_hz - target_frequency_hz))
    if abs(nearest.frequency_hz - target_frequency_hz) <= tolerance_hz:
        return nearest
    return None


def analyze_sidebands(
    center_peak: DetectedPeak,
    peaks: list[DetectedPeak],
    spacing_references: list[BaseFrequency],
    x_limit: tuple[float, float],
    resolution_hz: float,
) -> list[SidebandHit]:
    best_hits: list[SidebandHit] = []
    best_score: tuple[int, float] | None = None
    for spacing_ref in spacing_references:
        spacing = spacing_ref.frequency_hz
        if spacing <= 0:
            continue
        hits: list[SidebandHit] = []
        for order in range(1, 5):
            for side, sign in (("lower", -1), ("upper", 1)):
                target = center_peak.frequency_hz + sign * order * spacing
                if not x_limit[0] <= target <= x_limit[1]:
                    continue
                tolerance = comparison_tolerance_hz(target, resolution_hz)
                side_peak = _nearest_peak(target, peaks, tolerance)
                if side_peak is None or side_peak.frequency_hz == center_peak.frequency_hz:
                    continue
                if side_peak.amplitude < 0.35 * center_peak.amplitude:
                    continue
                detected_spacing = abs(side_peak.frequency_hz - center_peak.frequency_hz) / order
                hits.append(
                    SidebandHit(
                        center_peak.frequency_hz,
                        side_peak.frequency_hz,
                        side,
                        order,
                        spacing,
                        f"{spacing_ref.component} {spacing_ref.name}",
                        detected_spacing,
                        abs(detected_spacing - spacing),
                    )
                )
        if hits:
            average_error = float(np.mean([hit.difference_hz for hit in hits]))
            score = (len(hits), -average_error)
            if best_score is None or score > best_score:
                best_score = score
                best_hits = hits
    if len(best_hits) >= 2:
        return best_hits
    lower_upper = {hit.side for hit in best_hits if hit.order == 1}
    if lower_upper == {"lower", "upper"}:
        return best_hits
    return []


def _candidate_summary(candidates: list[MatchCandidate]) -> str:
    return "; ".join(
        f"{candidate.base.component} {candidate.base.name} H{candidate.harmonic_order} "
        f"{candidate.theoretical_frequency_hz:.3f} Hz"
        for candidate in candidates
    )


def _diagnostic_interpretation(
    unit: str,
    matched: MatchCandidate | None,
    sidebands: list[SidebandHit],
) -> str:
    if matched is None:
        return "Significant peak; no table match within tolerance. Trend and inspect if amplitude is high."
    attention = "primary" if (
        (unit == "mm/s" and matched.base.family == "gear")
        or (unit != "mm/s" and matched.base.family == "bearing")
    ) else "secondary"
    sideband_text = (
        f" Sidebands present with {sidebands[0].spacing_name} spacing."
        if sidebands
        else " No clear sideband family detected from significant peaks."
    )
    return (
        f"{matched.base.family.title()} characteristic match ({attention} attention for this spectrum type): "
        f"{matched.base.component} {matched.base.name} H{matched.harmonic_order}."
        + sideband_text
    )


def run_phase2_analysis(
    input_path: str | Path,
    output_path: str | Path,
    defect_table_pdf: str | Path,
    *,
    spectra_reference_path: str | Path | None = None,
    formats: tuple[str, ...] = ("pdf", "svg", "png"),
) -> dict[str, int]:
    output = Path(output_path)
    annotated_dir = output / "phase2_annotated_spectra"
    report_dir = output / "phase2_analysis"
    report_dir.mkdir(parents=True, exist_ok=True)

    base_frequencies = load_defect_frequency_table(defect_table_pdf)
    signals = list(iter_uff_signals(input_path))
    reference_sizes = _reference_image_sizes(spectra_reference_path)
    exact_image_by_source: dict[str, IndustrialImagePlot] = {
        reference.source: reference for reference in SPECTRA_IMAGE_PLOTS
    }

    frequency_rows: list[dict[str, object]] = []
    for frequency in base_frequencies:
        frequency_rows.append(
            {
                "family": frequency.family,
                "component": frequency.component,
                "name": frequency.name,
                "frequency_hz": f"{frequency.frequency_hz:.9g}",
            }
        )
    with (report_dir / "defect_frequency_table_extracted.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frequency_rows[0]))
        writer.writeheader()
        writer.writerows(frequency_rows)

    peak_rows: list[dict[str, object]] = []
    sideband_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    total_peaks = 0
    total_matches = 0
    total_sideband_hits = 0

    spacing_references = [
        frequency
        for frequency in base_frequencies
        if frequency.frequency_hz <= 100.0
    ]

    for signal in signals:
        exact_reference = exact_image_by_source.get(signal.source_name)
        industrial_reference = _build_industrial_all_reference(signal, exact_reference)
        spectrum = _industrial_spectrum(signal, industrial_reference)
        resolution = _frequency_resolution(spectrum)
        candidates = _expanded_candidates(base_frequencies, industrial_reference.x_limit[1])
        peaks = detect_significant_peaks(spectrum, industrial_reference.x_limit)
        matched_count = 0
        sideband_count = 0
        annotations: list[dict[str, object]] = []
        spectrum_peak_rows: list[dict[str, object]] = []

        match_data: list[tuple[DetectedPeak, MatchCandidate | None, list[MatchCandidate], list[SidebandHit]]] = []
        for peak in peaks:
            best_match, all_matches = match_peak(peak, candidates, resolution, spectrum.unit)
            sidebands = (
                analyze_sidebands(
                    peak,
                    peaks,
                    spacing_references,
                    industrial_reference.x_limit,
                    resolution,
                )
                if best_match is not None
                else []
            )
            match_data.append((peak, best_match, all_matches, sidebands))

        for peak, best_match, all_matches, sidebands in match_data:
            matched = best_match is not None
            if matched:
                matched_count += 1
            if sidebands:
                sideband_count += len(sidebands)
            component = best_match.base.component if best_match else ""
            matched_name = best_match.base.name if best_match else ""
            theoretical = best_match.theoretical_frequency_hz if best_match else ""
            difference = best_match.difference_hz if best_match else ""
            tolerance = best_match.tolerance_hz if best_match else ""
            harmonic_order = best_match.harmonic_order if best_match else ""
            sideband_summary = (
                f"{len(sidebands)} sideband(s), spacing {sidebands[0].detected_spacing_hz:.3f} Hz "
                f"~ {sidebands[0].spacing_name} ({sidebands[0].spacing_hz:.3f} Hz)"
                if sidebands
                else "No clear sideband pattern"
            )
            interpretation = _diagnostic_interpretation(spectrum.unit, best_match, sidebands)
            row = {
                "source": signal.source_name,
                "processing": industrial_reference.kind,
                "spectrum_unit": spectrum.unit,
                "fft_resolution_hz": f"{resolution:.9g}",
                "peak_frequency_hz": f"{peak.frequency_hz:.9g}",
                "peak_rms_amplitude": f"{peak.amplitude:.9g}",
                "peak_prominence": f"{peak.prominence:.9g}",
                "match_status": "Yes" if matched else "No",
                "matched_family": best_match.base.family if best_match else "",
                "component_identified": component,
                "matched_machine_frequency": matched_name,
                "harmonic_order": harmonic_order,
                "theoretical_frequency_hz": f"{theoretical:.9g}" if matched else "",
                "difference_hz": f"{difference:.9g}" if matched else "",
                "tolerance_hz": f"{tolerance:.9g}" if matched else "",
                "all_candidates_within_tolerance": _candidate_summary(all_matches),
                "sideband_analysis": sideband_summary,
                "diagnostic_interpretation": interpretation,
            }
            spectrum_peak_rows.append(row)
            peak_rows.append(row)
            label = f"{peak.frequency_hz:.2f}"
            if matched:
                label = f"{peak.frequency_hz:.2f} {matched_name}"
            annotations.append(
                {
                    "frequency": peak.frequency_hz,
                    "amplitude": peak.amplitude,
                    "label": label,
                    "matched": matched,
                    "role": "peak",
                }
            )
            for sideband in sidebands:
                side_peak = _nearest_peak(
                    sideband.sideband_frequency_hz,
                    peaks,
                    comparison_tolerance_hz(sideband.sideband_frequency_hz, resolution),
                )
                if side_peak is None:
                    continue
                annotations.append(
                    {
                        "frequency": side_peak.frequency_hz,
                        "amplitude": side_peak.amplitude,
                        "label": f"SB {sideband.detected_spacing_hz:.2f}",
                        "matched": True,
                        "role": "sideband",
                    }
                )
                sideband_rows.append(
                    {
                        "source": signal.source_name,
                        "center_frequency_hz": f"{sideband.center_frequency_hz:.9g}",
                        "sideband_frequency_hz": f"{sideband.sideband_frequency_hz:.9g}",
                        "side": sideband.side,
                        "order": sideband.order,
                        "detected_spacing_hz": f"{sideband.detected_spacing_hz:.9g}",
                        "theoretical_spacing_hz": f"{sideband.spacing_hz:.9g}",
                        "spacing_difference_hz": f"{sideband.difference_hz:.9g}",
                        "spacing_identified": sideband.spacing_name,
                    }
                )

        size_px = (
            reference_sizes.get(exact_reference.reference_image)
            if exact_reference is not None
            else None
        )
        plot_industrial_spectrum(
            spectrum,
            annotated_dir / safe_stem(signal.source_name),
            reference=industrial_reference,
            size_px=size_px,
            annotations=annotations,
            formats=formats,
        )
        total_peaks += len(peaks)
        total_matches += matched_count
        total_sideband_hits += sideband_count
        primary_matches = sum(
            1
            for row in spectrum_peak_rows
            if row["match_status"] == "Yes"
            and (
                (spectrum.unit == "mm/s" and row["matched_family"] == "gear")
                or (spectrum.unit != "mm/s" and row["matched_family"] == "bearing")
            )
        )
        summary_rows.append(
            {
                "source": signal.source_name,
                "processing": industrial_reference.kind,
                "spectrum_unit": spectrum.unit,
                "detected_peak_count": len(peaks),
                "matched_peak_count": matched_count,
                "primary_attention_match_count": primary_matches,
                "sideband_hit_count": sideband_count,
                "diagnostic_summary": (
                    f"{len(peaks)} significant peak(s), {matched_count} table match(es), "
                    f"{sideband_count} sideband hit(s)."
                ),
            }
        )

    if peak_rows:
        with (report_dir / "detected_peak_matches.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(peak_rows[0]))
            writer.writeheader()
            writer.writerows(peak_rows)
    if sideband_rows:
        with (report_dir / "sideband_analysis.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(sideband_rows[0]))
            writer.writeheader()
            writer.writerows(sideband_rows)
    if summary_rows:
        with (report_dir / "diagnostic_summary.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
            writer.writeheader()
            writer.writerows(summary_rows)

    methodology = (
        "Phase 2 methodology\n"
        "===================\n\n"
        "1. FFT spectra are calculated from UFF data before any defect-table comparison.\n"
        "2. Significant peaks are local maxima above a robust noise threshold: max(median + 12*MAD-derived sigma,\n"
        "   7% of visible-band maximum), with prominence at least max(10*MAD-derived sigma, 6% of maximum).\n"
        "   If more than 35 peaks pass these tests in one spectrum, the 35 highest-prominence peaks are reported.\n"
        "3. Frequency matching tolerance is max(2 FFT frequency bins, 1% of theoretical frequency).\n"
        "4. Gear and bearing harmonics are generated mathematically from the extracted table values only.\n"
        "5. Velocity spectra prioritize shaft/wobble/GMF matches; acceleration spectra prioritize bearing matches.\n"
        "6. Sidebands are searched from detected peaks around matched characteristic frequencies using table-derived\n"
        "   shaft, wobble, cage, and other low-frequency spacings; accepted sideband peaks must be at least 35%\n"
        "   of the center peak amplitude and form a repeatable/symmetric family.\n"
    )
    (report_dir / "methodology.txt").write_text(methodology, encoding="utf-8")

    return {
        "signals": len(signals),
        "annotated_plots": len(signals),
        "detected_peaks": total_peaks,
        "matched_peaks": total_matches,
        "sideband_hits": total_sideband_hits,
        "base_frequencies": len(base_frequencies),
    }
