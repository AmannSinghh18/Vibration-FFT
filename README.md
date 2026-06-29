# Gearbox UFF Spectrum Visualization

This project reads Universal File Format dataset-58 time signals and produces
Hann-windowed, single-sided RMS spectra. It accepts the supplied ZIP archive,
an extracted directory, or one `.uff` file.

## Installation

Python 3.10 or newer is recommended.

```powershell
python -m pip install -r requirements.txt
```

## Generate the graphs

```powershell
python generate_spectra.py `
  --input "UFF Files Bearing defect.zip" `
  --output output
```

The command auto-detects `Spectra.zip` or an extracted `Spectra` folder in the
current directory. You can also pass it explicitly:

```powershell
python generate_spectra.py `
  --input "UFF Files Bearing defect.zip" `
  --spectra-reference "Spectra.zip" `
  --output output
```

The default command writes:

- `output/generic`: native-unit spectra for all 57 UFF signals.
- `output/reference_matched`: Figures 18, 20, 22, 24, 26, 28, 30, 32, and 34.
- `output/spectra_image_matched`: 19 widescreen industrial-style plots matched
  to `Spectra.zip` references (`Uff.jpg` through `Uff(18).jpg`) using the
  correct timestamp-based UFF mapping.
- `output/spectrum_summary.csv`: source metadata, signal RMS, and dominant peaks.
- `output/missing_pressing_side.txt`: the nine PDF figures whose source UFF
  records are absent.

The PDF/reference plots are exported as PDF, SVG, and PNG. The
`spectra_image_matched` PNGs preserve the exact pixel dimensions of the
corresponding JPG references from `Spectra.zip`. Restrict formats when needed:

```powershell
python generate_spectra.py --input "UFF Files Bearing defect" `
  --output output --formats png
```

## Processing

- The mean is removed from every signal.
- A Hann window is applied.
- FFT amplitudes are corrected for window coherent gain and converted to
  single-sided RMS values.
- Acceleration spectra used for velocity plots are divided by `2*pi*f` and
  converted from m/s to mm/s.
- The envelope records are already demodulated signals, so no second Hilbert
  envelope is applied.

The PDF-matched mapping is recorded in `reference_manifest.json`. The
Spectra.zip image-matched mapping is encoded in `gearbox_spectra/manifest.py`
because it also stores the visual headers, axis ranges, RPM labels, and the
timestamp-based UFF/image pairings.

## Tests

The tests use Python's built-in `unittest` runner:

```powershell
$env:PYTHONDONTWRITEBYTECODE=1
python -m unittest discover -s tests -v
```

They validate real UFF metadata, all 57 input records, synthetic RMS FFT
scaling, acceleration-to-velocity conversion, envelope marker amplitudes, and
PNG dimensions.

## Important dataset limitation

The supplied files align with the report's nine Lifting-side timestamps. No
UFF records align with the nine Pressing-side timestamps, so those graphs are
reported as unavailable rather than reconstructed from unrelated signals.
