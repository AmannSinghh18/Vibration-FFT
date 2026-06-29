# Gearbox UFF Spectrum Visualization

## Summary

Build a Python batch tool that reads the ZIP or extracted UFF folder, processes all 57 signals, and recreates the nine PDF-matched lifting-side spectra. The nine pressing-side plots will be documented as unavailable because their source records are absent.

## Implementation

- Create a dataset-58 UFF parser that reads signal values, sample interval, units, timestamp, and point count.
- Apply mean removal, Hann windowing, and single-sided RMS FFT scaling.
- Generate:
  - Native velocity spectra from velocity signals.
  - Acceleration spectra from 32.768 kHz signals.
  - Envelope spectra from the supplied demodulated signals.
  - Velocity spectra from acceleration using frequency-domain integration.
- Add a manifest mapping the nine reference figures to their exact UFF files, titles, axis limits, RPM, gear-mesh/bearing markers, and harmonics.
- Produce generic native-unit spectra for every remaining UFF file, using filenames and timestamps where measurement labels are unavailable.
- Match the PDF styling: Arial fonts, blue spectrum, red markers, dotted grid, thin black frame, RMS units, and reference axis ranges.
- Use a 468×144-point vector canvas with an approximately 436×100-point plotting frame. Export resolution-independent PDF/SVG and 1950×600 PNG files at 300 DPI.
- Provide a CLI such as:
  - `python generate_spectra.py --input "UFF Files Bearing defect.zip" --output output`
  - Support ZIP files and extracted directories.
- Include configuration, dependency file, README, and clear diagnostics for malformed or unsupported UFF records.

## Reference Outputs

Recreate PDF Figures 18, 20, 22, 24, 26, 28, 30, 32, and 34 with their original frequency and amplitude ranges. Organize generic and reference-matched outputs into separate directories and generate a CSV summary of peaks and RMS values.

## Test Plan

- Verify UFF point counts, sampling rates, timestamps, and units.
- Validate FFT frequency and RMS amplitude using synthetic sine signals.
- Validate acceleration-to-velocity conversion.
- Confirm reference envelope markers near 8.10 Hz/1.946 m/s² and 8.13 Hz/3.445 m/s².
- Confirm vector dimensions, PNG pixel dimensions, fonts, labels, and axis limits.
- Run a batch smoke test across all 57 files.

## Assumptions

- The PDF is vector-based and has no intrinsic DPI; exact physical dimensions are preserved in PDF/SVG, while PNG defaults to 300 DPI.
- Low-rate envelope records are already demodulated and require FFT processing rather than another Hilbert-envelope stage.
- Missing pressing-side records will be reported, not fabricated.
