from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from gearbox_spectra.manifest import REFERENCE_PLOTS, SPECTRA_IMAGE_PLOTS
from gearbox_spectra.plotting import (
    PNG_PIXEL_SIZE,
    plot_industrial_spectrum,
    plot_spectrum,
)
from gearbox_spectra.processing import (
    acceleration_to_velocity_spectrum,
    rms_spectrum,
)
from gearbox_spectra.uff import iter_uff_signals, parse_dataset_58


WORKSPACE = Path(__file__).resolve().parents[1]
DATA_DIR = WORKSPACE / "UFF Files Bearing defect"


class UFFTests(unittest.TestCase):
    def test_real_dataset_58_metadata_and_values(self) -> None:
        signal = parse_dataset_58(
            (DATA_DIR / "timesignal (2).uff").read_text(encoding="latin1"),
            "timesignal (2).uff",
        )
        self.assertEqual(signal.sample_count, 32768)
        self.assertAlmostEqual(signal.sample_rate, 32767.9765, places=2)
        self.assertEqual(signal.quantity, "Acceleration")
        self.assertEqual(signal.unit, "m/s²")
        self.assertEqual(signal.values.size, signal.sample_count)

    def test_folder_contains_all_signals(self) -> None:
        signals = list(iter_uff_signals(DATA_DIR))
        self.assertEqual(len(signals), 57)
        self.assertEqual(signals[0].source_name, "timesignal.uff")
        self.assertEqual(signals[-1].source_name, "timesignal (56).uff")

    def test_zip_units_are_normalized(self) -> None:
        signals = list(iter_uff_signals(WORKSPACE / "UFF Files Bearing defect.zip"))
        acceleration = next(item for item in signals if item.quantity == "Acceleration")
        self.assertEqual(acceleration.unit, "m/s²")


class ProcessingTests(unittest.TestCase):
    def test_hann_single_sided_rms_amplitude(self) -> None:
        sample_rate = 1024.0
        count = 4096
        frequency = 128.0
        expected_rms = 3.0
        time = np.arange(count) / sample_rate
        values = np.sqrt(2.0) * expected_rms * np.sin(2 * np.pi * frequency * time)
        spectrum = rms_spectrum(values, sample_rate, "m/s²")
        index = int(np.argmin(np.abs(spectrum.frequency - frequency)))
        self.assertAlmostEqual(spectrum.amplitude[index], expected_rms, places=3)

    def test_acceleration_to_velocity(self) -> None:
        sample_rate = 1024.0
        count = 4096
        frequency = 64.0
        expected_velocity_mm_s = 2.0
        acceleration_rms = (
            2 * np.pi * frequency * expected_velocity_mm_s / 1000.0
        )
        time = np.arange(count) / sample_rate
        values = (
            np.sqrt(2.0)
            * acceleration_rms
            * np.sin(2 * np.pi * frequency * time)
        )
        acceleration = rms_spectrum(values, sample_rate, "m/s²")
        velocity = acceleration_to_velocity_spectrum(acceleration)
        index = int(np.argmin(np.abs(velocity.frequency - frequency)))
        self.assertAlmostEqual(
            velocity.amplitude[index], expected_velocity_mm_s, places=3
        )

    def test_reference_envelope_markers_are_close(self) -> None:
        references = {item.figure: item for item in REFERENCE_PLOTS}
        expected = {
            26: ("timesignal (30).uff", 8.10, 1.946, 0.20),
            28: ("timesignal (51).uff", 8.13, 3.445, 0.08),
        }
        for figure, (filename, frequency, amplitude, tolerance) in expected.items():
            signal = next(
                item for item in iter_uff_signals(DATA_DIR) if item.source_name == filename
            )
            spectrum = rms_spectrum(signal.values, signal.sample_rate, "m/s²")
            index = int(np.argmin(np.abs(spectrum.frequency - frequency)))
            relative_error = abs(spectrum.amplitude[index] - amplitude) / amplitude
            self.assertLess(
                relative_error,
                tolerance,
                msg=f"Fig. {figure} marker amplitude differs too much",
            )
            self.assertEqual(references[figure].source, filename)


class PlotTests(unittest.TestCase):
    def test_png_dimensions(self) -> None:
        spectrum = rms_spectrum(np.sin(np.linspace(0, 100, 2048)), 1024, "m/s²")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "dimension_check"
            plot_spectrum(
                spectrum,
                base,
                title="Dimension check",
                formats=("png",),
            )
            with Image.open(base.with_suffix(".png")) as image:
                self.assertEqual(image.size, PNG_PIXEL_SIZE)

    def test_spectra_image_reference_mapping_and_dimensions(self) -> None:
        references = {item.reference_image: item for item in SPECTRA_IMAGE_PLOTS}
        self.assertEqual(references["Uff(12).jpg"].source, "timesignal (13).uff")
        self.assertEqual(references["Uff(18).jpg"].source, "timesignal (19).uff")

        signal = next(
            item
            for item in iter_uff_signals(DATA_DIR)
            if item.source_name == references["Uff(17).jpg"].source
        )
        spectrum = rms_spectrum(signal.values, signal.sample_rate, "m/s²")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "Uff(17)"
            plot_industrial_spectrum(
                spectrum,
                base,
                reference=references["Uff(17).jpg"],
                formats=("png",),
            )
            with Image.open(base.with_suffix(".png")) as image:
                self.assertEqual(image.size, (1920, 529))


if __name__ == "__main__":
    unittest.main()
