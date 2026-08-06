from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np

from .manifest import IndustrialImagePlot, Marker
from .processing import Spectrum


FIGURE_SIZE_INCHES = (6.5, 2.0)
PNG_DPI = 300
PNG_PIXEL_SIZE = (1950, 600)
AXES_RECT = (16 / 468, 24 / 144, 436 / 468, 100 / 144)


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")


def plot_spectrum(
    spectrum: Spectrum,
    output_base: Path,
    *,
    title: str,
    x_limit: tuple[float, float] | None = None,
    y_limit: tuple[float, float] | None = None,
    x_tick: float | None = None,
    y_tick: float | None = None,
    markers: tuple[Marker, ...] = (),
    rpm: int | None = None,
    formats: tuple[str, ...] = ("pdf", "svg", "png"),
) -> list[Path]:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 5.8,
            "axes.linewidth": 0.45,
            "xtick.major.width": 0.4,
            "ytick.major.width": 0.4,
            "xtick.major.size": 2.0,
            "ytick.major.size": 2.0,
        }
    )
    figure = plt.figure(figsize=FIGURE_SIZE_INCHES)
    axis = figure.add_axes(AXES_RECT)

    axis.plot(spectrum.frequency, spectrum.amplitude, color="#0000ff", linewidth=0.48)
    axis.set_title(title, fontsize=6.5, pad=3)
    axis.set_xlabel("f [Hz]", fontsize=6)
    quantity_symbol = "v" if "mm/s" in spectrum.unit else "a"
    axis.set_ylabel(f"{quantity_symbol} rms [{spectrum.unit}]", fontsize=6)
    axis.grid(True, color="#777777", linestyle=(0, (1, 2)), linewidth=0.35, alpha=0.8)
    axis.tick_params(labelsize=5.5, pad=1.5)

    if x_limit is None:
        x_limit = (0.0, float(spectrum.frequency[-1]))
    if y_limit is None:
        visible = spectrum.amplitude[
            (spectrum.frequency >= x_limit[0]) & (spectrum.frequency <= x_limit[1])
        ]
        maximum = float(np.max(visible)) if visible.size else 1.0
        y_limit = (0.0, maximum * 1.08 if maximum > 0 else 1.0)
    axis.set_xlim(*x_limit)
    axis.set_ylim(*y_limit)

    if x_tick:
        axis.xaxis.set_major_locator(MultipleLocator(x_tick))
    if y_tick:
        axis.yaxis.set_major_locator(MultipleLocator(y_tick))

    for marker_index, marker in enumerate(markers):
        if not x_limit[0] <= marker.frequency <= x_limit[1]:
            continue
        axis.axvline(
            marker.frequency,
            color="#ff0000",
            linewidth=0.55,
            linestyle=(0, (6, 2)),
            alpha=0.95,
        )
        label_y = y_limit[1] * (0.88 - 0.10 * (marker_index % 2))
        axis.text(
            marker.frequency,
            label_y,
            marker.label,
            color="#cc0000",
            fontsize=4.7,
            rotation=90,
            va="top",
            ha="right",
            clip_on=True,
        )

    if rpm:
        axis.text(
            0.995,
            0.965,
            f"RPM : {rpm} ({rpm / 60:.2f} Hz)",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=5.3,
            color="black",
        )

    output_base.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for extension in formats:
        target = output_base.with_suffix(f".{extension}")
        if extension == "png":
            figure.savefig(target, dpi=PNG_DPI, facecolor="white")
        else:
            figure.savefig(target, facecolor="white")
        written.append(target)
    plt.close(figure)
    return written


def plot_industrial_spectrum(
    spectrum: Spectrum,
    output_base: Path,
    *,
    reference: IndustrialImagePlot,
    size_px: tuple[int, int] | None = None,
    annotations: Sequence[Mapping[str, object]] = (),
    formats: tuple[str, ...] = ("png",),
) -> list[Path]:
    """Plot a widescreen spectrum matching the supplied Spectra.zip JPG style."""
    if size_px is None:
        size_px = reference.default_size_px
    width_px, height_px = size_px
    dpi = 100

    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 10.0,
            "axes.linewidth": 0.7,
            "xtick.major.width": 0.65,
            "ytick.major.width": 0.65,
            "xtick.major.size": 4.0,
            "ytick.major.size": 4.0,
        }
    )
    figure = plt.figure(
        figsize=(width_px / dpi, height_px / dpi),
        dpi=dpi,
        facecolor="white",
    )
    axis = figure.add_axes((0.035, 0.145, 0.955, 0.775))

    axis.plot(spectrum.frequency, spectrum.amplitude, color="#0000cc", linewidth=0.35)
    axis.set_xlim(*reference.x_limit)
    axis.set_ylim(*reference.y_limit)
    axis.xaxis.set_major_locator(MultipleLocator(reference.x_tick))
    axis.yaxis.set_major_locator(MultipleLocator(reference.y_tick))
    axis.grid(True, color="#8a8a8a", linestyle=(0, (1, 2)), linewidth=0.55, alpha=0.9)
    axis.tick_params(labelsize=16, pad=2)

    for spine in axis.spines.values():
        spine.set_color("black")
        spine.set_linewidth(0.7)

    label_unit = "mm/s" if "mm/s" in spectrum.unit else "m/s²"
    label_symbol = "v" if label_unit == "mm/s" else "a"
    figure.text(
        0.001,
        0.995,
        f"{label_symbol} rms [{label_unit}]",
        ha="left",
        va="top",
        fontsize=17,
        color="black",
    )
    figure.text(
        0.081,
        0.996,
        reference.header,
        ha="left",
        va="top",
        fontsize=13.2,
        color="black",
        bbox={"facecolor": "white", "edgecolor": "black", "linewidth": 0.9, "pad": 2.0},
    )
    figure.text(
        0.985,
        0.02,
        "f [Hz]",
        ha="right",
        va="bottom",
        fontsize=16,
        color="black",
    )
    axis.text(
        0.998,
        0.98,
        f"RPM : {reference.rpm} ({reference.rpm / 60:.2f}Hz)",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=16,
        color="black",
    )
    if reference.annotations:
        axis.text(
            0.80,
            0.93,
            "\n".join(reference.annotations),
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=10,
            color="black",
        )

    y_span = reference.y_limit[1] - reference.y_limit[0]
    label_levels = (0.92, 0.82, 0.72, 0.62)
    for annotation_index, annotation in enumerate(annotations):
        frequency = float(annotation["frequency"])
        amplitude = float(annotation["amplitude"])
        if not reference.x_limit[0] <= frequency <= reference.x_limit[1]:
            continue
        role = str(annotation.get("role", "peak"))
        if role == "sideband":
            color = "#ff8c00"
            linestyle = (0, (2, 2))
            marker = "o"
        elif annotation.get("matched"):
            color = "#cc0000"
            linestyle = (0, (5, 2))
            marker = "^"
        else:
            color = "#008000"
            linestyle = (0, (1, 3))
            marker = "^"
        axis.axvline(
            frequency,
            color=color,
            linewidth=0.55,
            linestyle=linestyle,
            alpha=0.8,
        )
        axis.plot(
            [frequency],
            [min(amplitude, reference.y_limit[1])],
            marker=marker,
            markersize=3.0,
            color=color,
            markeredgewidth=0,
            clip_on=True,
        )
        label = str(annotation.get("label", f"{frequency:.2f} Hz"))
        label_y = reference.y_limit[0] + y_span * label_levels[
            annotation_index % len(label_levels)
        ]
        axis.text(
            frequency,
            label_y,
            label,
            color=color,
            fontsize=6.2,
            rotation=90,
            va="top",
            ha="right",
            clip_on=True,
        )

    output_base.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for extension in formats:
        target = output_base.with_suffix(f".{extension}")
        if extension == "png":
            figure.savefig(target, dpi=dpi, facecolor="white")
        else:
            figure.savefig(target, facecolor="white")
        written.append(target)
    plt.close(figure)
    return written
