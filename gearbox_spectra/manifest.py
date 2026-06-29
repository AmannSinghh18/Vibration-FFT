from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Marker:
    frequency: float
    label: str


@dataclass(frozen=True)
class ReferencePlot:
    figure: int
    source: str
    kind: str
    title: str
    x_limit: tuple[float, float]
    y_limit: tuple[float, float]
    x_tick: float
    y_tick: float
    rpm: int
    markers: tuple[Marker, ...] = ()


@dataclass(frozen=True)
class IndustrialImagePlot:
    reference_image: str
    source: str
    kind: str
    header: str
    x_limit: tuple[float, float]
    y_limit: tuple[float, float]
    x_tick: float
    y_tick: float
    rpm: int
    default_size_px: tuple[int, int]
    annotations: tuple[str, ...] = ()


REFERENCE_PLOTS: tuple[ReferencePlot, ...] = (
    ReferencePlot(
        18, "timesignal (10).uff", "velocity_native",
        "Vibration velocity spectrum, input shaft, measurement point (Lifting side)",
        (0, 1500), (0, 5), 100, 0.5, 990,
        (
            Marker(145.86, "Gmf_St2"),
            Marker(291.72, "Gmf_St2 H#2"),
            Marker(462.00, "Gmf_St1"),
            Marker(924.00, "Gmf_St1 H#2"),
        ),
    ),
    ReferencePlot(
        20, "timesignal (26).uff", "velocity_from_acceleration",
        "Vibration velocity spectrum, intermediate shaft, measurement point (Lifting side)",
        (0, 800), (0, 5), 50, 0.5, 992,
        (
            Marker(146.15, "Gmf_St2"),
            Marker(292.30, "Gmf_St2 H#2"),
            Marker(462.92, "Gmf_St1"),
        ),
    ),
    ReferencePlot(
        22, "timesignal (32).uff", "velocity_from_acceleration",
        "Vibration velocity spectrum, output shaft, measurement point (Lifting side)",
        (0, 800), (0, 5), 50, 0.5, 992,
    ),
    ReferencePlot(
        24, "timesignal (4).uff", "envelope",
        "Envelope spectrum, input shaft, measurement point (Lifting side)",
        (0, 1500), (0, 8), 100, 1, 990,
        tuple(
            Marker(125.40 * harmonic, "BPO Brg 150/151" if harmonic == 1 else f"BPO H#{harmonic}")
            for harmonic in range(1, 10)
            if 125.40 * harmonic <= 1500
        ),
    ),
    ReferencePlot(
        26, "timesignal (30).uff", "envelope",
        "Envelope spectrum, intermediate shaft, measurement point (Lifting side)",
        (0, 1500), (0, 8), 100, 1, 992,
        (Marker(8.10, "Marker 8.10 Hz"),),
    ),
    ReferencePlot(
        28, "timesignal (51).uff", "envelope",
        "Envelope spectrum, output shaft, measurement point (Lifting side)",
        (0, 400), (0, 8), 20, 1, 992,
        (Marker(8.13, "Marker 8.13 Hz"),),
    ),
    ReferencePlot(
        30, "timesignal (2).uff", "acceleration",
        "Acceleration spectrum, input shaft, measurement point (Lifting side)",
        (0, 10000), (0, 9), 1000, 1, 992,
    ),
    ReferencePlot(
        32, "timesignal (28).uff", "acceleration",
        "Acceleration spectrum, intermediate shaft, measurement point (Lifting side)",
        (0, 10000), (0, 9), 1000, 1, 992,
    ),
    ReferencePlot(
        34, "timesignal (49).uff", "acceleration",
        "Acceleration spectrum, output shaft, measurement point (Lifting side)",
        (0, 10000), (0, 6), 1000, 1, 992,
    ),
)


SPECTRA_IMAGE_PLOTS: tuple[IndustrialImagePlot, ...] = (
    IndustrialImagePlot(
        "Uff.jpg", "timesignal.uff", "velocity_native",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_1 Inp. Shaft, motor side vert.\1002 T _SV3,2kHz0,25Hz20s\Spectrum 06-Mar-26 3:19:31 PM",
        (0, 2000), (0, 4), 200, 0.5, 992, (1920, 546),
    ),
    IndustrialImagePlot(
        "Uff(1).jpg", "timesignal (1).uff", "velocity_from_acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_1 Inp. Shaft, motor side vert.\1004 T _SV0,8kHz0,03Hz27s\Spectrum 06-Mar-26 3:20:12 PM",
        (0, 800), (0, 4), 50, 0.5, 992, (1920, 548),
    ),
    IndustrialImagePlot(
        "Uff(2).jpg", "timesignal (2).uff", "acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_1 Inp. Shaft, motor side vert.\1010 T _SA12,8kHz1Hz0s\Spectrum 06-Mar-26 3:18:58 PM",
        (0, 10000), (0, 12), 1000, 2, 992, (1920, 547),
    ),
    IndustrialImagePlot(
        "Uff(3).jpg", "timesignal (3).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_1 Inp. Shaft, motor side vert.\1012 T _EA1,5kHz0,5-10kHz\Spectrum 06-Mar-26 3:18:00 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 549),
    ),
    IndustrialImagePlot(
        "Uff(4).jpg", "timesignal (4).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_1 Inp. Shaft, motor side vert.\1018 T _EA1,5kHz2,5-10kHz\Spectrum 06-Mar-26 3:18:39 PM",
        (0, 1500), (0, 10), 100, 1, 990, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(5).jpg", "timesignal (5).uff", "velocity_native",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_2 Inp. Shaft, output side vert.\1002 T _SV3,2kHz0,25Hz20s\Spectrum 06-Mar-26 3:24:18 PM",
        (0, 2000), (0, 4), 200, 0.5, 992, (1920, 526),
    ),
    IndustrialImagePlot(
        "Uff(6).jpg", "timesignal (6).uff", "velocity_from_acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_2 Inp. Shaft, output side vert.\1004 T _SV0,8kHz0,03Hz27s\Spectrum 06-Mar-26 3:24:57 PM",
        (0, 800), (0, 4), 50, 0.5, 992, (1920, 526),
    ),
    IndustrialImagePlot(
        "Uff(7).jpg", "timesignal (7).uff", "acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_2 Inp. Shaft, output side vert.\1010 T _SA12,8kHz1Hz0s\Spectrum 06-Mar-26 3:23:47 PM",
        (0, 10000), (0, 12), 1000, 2, 992, (1920, 527),
    ),
    IndustrialImagePlot(
        "Uff(8).jpg", "timesignal (8).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_2 Inp. Shaft, output side vert.\1012 T _EA1,5kHz0,5-10kHz\Spectrum 06-Mar-26 3:23:30 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(9).jpg", "timesignal (9).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_2 Inp. Shaft, output side vert.\1018 T _EA1,5kHz2,5-10kHz\Spectrum 06-Mar-26 3:22:48 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(10).jpg", "timesignal (10).uff", "velocity_native",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_3 Inp. Shaft, motor side hor.\1002 T _SV3,2kHz0,25Hz20s\Spectrum 06-Mar-26 3:28:00 PM",
        (0, 2000), (0, 4), 200, 0.5, 990, (1920, 527),
    ),
    IndustrialImagePlot(
        "Uff(11).jpg", "timesignal (11).uff", "velocity_from_acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_3 Inp. Shaft, motor side hor.\1004 T _SV0,8kHz0,03Hz27s\Spectrum 06-Mar-26 3:28:59 PM",
        (0, 800), (0, 4), 50, 0.5, 992, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(12).jpg", "timesignal (13).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_3 Inp. Shaft, motor side hor.\1012 T _EA1,5kHz0,5-10kHz\Spectrum 06-Mar-26 3:27:30 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(13).jpg", "timesignal (14).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_3 Inp. Shaft, motor side hor.\1018 T _EA1,5kHz2,5-10kHz\Spectrum 06-Mar-26 3:26:48 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
    ),
    IndustrialImagePlot(
        "Uff(14).jpg", "timesignal (15).uff", "velocity_native",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_4 Inp. Shaft, output side hor.\1002 T _SV3,2kHz0,25Hz20s\Spectrum 06-Mar-26 3:31:58 PM",
        (0, 2000), (0, 4), 200, 0.5, 992, (1920, 527),
    ),
    IndustrialImagePlot(
        "Uff(15).jpg", "timesignal (16).uff", "velocity_from_acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_4 Inp. Shaft, output side hor.\1004 T _SV0,8kHz0,03Hz27s\Spectrum 06-Mar-26 3:32:36 PM",
        (0, 800), (0, 4), 50, 0.5, 992, (1920, 528),
    ),
    IndustrialImagePlot(
        "Uff(16).jpg", "timesignal (17).uff", "acceleration",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_4 Inp. Shaft, output side hor.\1010 T _SA12,8kHz1Hz0s\Spectrum 06-Mar-26 3:31:28 PM",
        (0, 10000), (0, 12), 1000, 2, 992, (1920, 527),
    ),
    IndustrialImagePlot(
        "Uff(17).jpg", "timesignal (18).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_4 Inp. Shaft, output side hor.\1012 T _EA1,5kHz0,5-10kHz\Spectrum 06-Mar-26 3:30:27 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
        ("M(x) : 80.70 Hz (4.88 Orders)", "M(y) : 4.833 m/s²"),
    ),
    IndustrialImagePlot(
        "Uff(18).jpg", "timesignal (19).uff", "envelope",
        r"Ball Mill Lifting Side\H2SH-19; 3002378204-1000VA_4 Inp. Shaft, output side hor.\1018 T _EA1,5kHz2,5-10kHz\Spectrum 06-Mar-26 3:31:09 PM",
        (0, 1500), (0, 10), 100, 1, 992, (1920, 529),
    ),
)


MISSING_PRESSING_SIDE = (
    "Fig. 19: velocity spectrum, input shaft, Pressing side",
    "Fig. 21: velocity spectrum, intermediate shaft, Pressing side",
    "Fig. 23: velocity spectrum, output shaft, Pressing side",
    "Fig. 25: envelope spectrum, input shaft, Pressing side",
    "Fig. 27: envelope spectrum, intermediate shaft, Pressing side",
    "Fig. 29: envelope spectrum, output shaft, Pressing side",
    "Fig. 31: acceleration spectrum, input shaft, Pressing side",
    "Fig. 33: acceleration spectrum, intermediate shaft, Pressing side",
    "Fig. 35: acceleration spectrum, output shaft, Pressing side",
)
