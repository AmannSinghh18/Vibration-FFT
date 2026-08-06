from __future__ import annotations

import argparse
from pathlib import Path
import sys

from gearbox_spectra.batch import generate_batch
from gearbox_spectra.phase2 import run_phase2_analysis
from gearbox_spectra.uff import UFFError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate gearbox spectra from dataset-58 UFF time signals."
    )
    parser.add_argument("--input", required=True, help="UFF ZIP archive, file, or folder")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument(
        "--formats",
        default="pdf,svg,png",
        help="Comma-separated output formats selected from pdf, svg, png",
    )
    parser.add_argument(
        "--spectra-reference",
        default=None,
        help=(
            "Optional Spectra.zip file or extracted Spectra folder used for "
            "image-matched output dimensions. Defaults to auto-detecting "
            "Spectra.zip or Spectra beside the command."
        ),
    )
    parser.add_argument(
        "--phase2",
        action="store_true",
        help="Run industrial vibration analysis: peak detection, matching, sidebands, and annotated plots.",
    )
    parser.add_argument(
        "--defect-table",
        default="defect frequency calculation.pdf",
        help="PDF containing gearbox and bearing characteristic frequency tables.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    formats = tuple(
        item.strip().lower() for item in args.formats.split(",") if item.strip()
    )
    unsupported = set(formats) - {"pdf", "svg", "png"}
    if not formats or unsupported:
        print(
            f"error: formats must be selected from pdf, svg, png; got {args.formats!r}",
            file=sys.stderr,
        )
        return 2

    spectra_reference = Path(args.spectra_reference) if args.spectra_reference else None
    if spectra_reference is None:
        for candidate in (Path("Spectra.zip"), Path("Spectra")):
            if candidate.exists():
                spectra_reference = candidate
                break

    try:
        result = generate_batch(
            Path(args.input),
            Path(args.output),
            formats=formats,
            spectra_reference_path=spectra_reference,
        )
    except (UFFError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        "Generated "
        f"{result['generic_plots']} generic and {result['reference_plots']} "
        f"PDF-matched spectra from {result['signals']} UFF signals."
    )
    print(
        f"Generated {result['spectra_image_plots']} Spectra.zip image-matched "
        f"plots; skipped {result['skipped_spectra_image_plots']}."
    )
    print(
        f"Generated {result['spectra_all_57_plots']} industrial-style spectra "
        "for all UFF time-signal files."
    )
    print(
        f"{result['missing_reference_plots']} Pressing-side reference figures "
        "are documented as unavailable."
    )

    if args.phase2:
        try:
            phase2_result = run_phase2_analysis(
                Path(args.input),
                Path(args.output),
                Path(args.defect_table),
                spectra_reference_path=spectra_reference,
                formats=formats,
            )
        except (UFFError, OSError, ValueError) as exc:
            print(f"error: phase 2 failed: {exc}", file=sys.stderr)
            return 1
        print(
            "Phase 2 complete: "
            f"{phase2_result['detected_peaks']} significant peaks, "
            f"{phase2_result['matched_peaks']} matched peaks, "
            f"{phase2_result['sideband_hits']} sideband hits across "
            f"{phase2_result['signals']} spectra."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
