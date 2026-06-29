from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterator
import zipfile

import numpy as np


class UFFError(ValueError):
    """Raised when a UFF dataset cannot be parsed safely."""


@dataclass(frozen=True)
class UFFSignal:
    source_name: str
    title: str
    timestamp: str
    sample_count: int
    sample_interval: float
    sample_rate: float
    quantity: str
    unit: str
    values: np.ndarray


def _clean_text(text: str) -> str:
    return (
        text.replace("\x00", "")
        .replace("Â²", "²")
        .replace("�", "²")
        .strip()
    )


def _decode_uff(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin1")


def parse_dataset_58(text: str, source_name: str = "<memory>") -> UFFSignal:
    """Parse the first universal-file dataset 58 contained in *text*."""
    lines = text.splitlines()
    block: list[str] | None = None

    for index, line in enumerate(lines):
        if line.strip() != "-1":
            continue
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines) or lines[next_index].strip() != "58":
            continue
        end = next_index + 1
        while end < len(lines) and lines[end].strip() != "-1":
            end += 1
        block = lines[next_index + 1 : end]
        break

    if block is None:
        raise UFFError(f"{source_name}: dataset 58 was not found")
    if len(block) < 12:
        raise UFFError(f"{source_name}: dataset 58 header is incomplete")

    descriptor = block[6].split()
    if len(descriptor) < 5:
        raise UFFError(f"{source_name}: invalid dataset 58 data descriptor")

    try:
        sample_count = int(descriptor[1])
        sample_interval = float(descriptor[4])
    except ValueError as exc:
        raise UFFError(f"{source_name}: invalid sample count or interval") from exc

    if sample_count <= 0 or sample_interval <= 0:
        raise UFFError(f"{source_name}: sample count and interval must be positive")

    ordinate = _clean_text(block[8])
    quantity_match = re.search(
        r"\b(Acceleration|Velocity|Displacement|Force|Pressure)\b",
        ordinate,
        flags=re.IGNORECASE,
    )
    quantity = quantity_match.group(1).title() if quantity_match else "Unknown"
    unit = ordinate[35:].strip() if len(ordinate) > 35 else ""
    if not unit:
        tokens = ordinate.split()
        unit = tokens[-1] if tokens else ""
    unit = _clean_text(unit).replace("m/s2", "m/s²")

    numeric_text = " ".join(block[11:])
    values = np.fromstring(numeric_text, sep=" ", dtype=float)
    if values.size < sample_count:
        raise UFFError(
            f"{source_name}: expected {sample_count} values, found {values.size}"
        )
    if values.size > sample_count:
        values = values[:sample_count]

    return UFFSignal(
        source_name=source_name,
        title=_clean_text(block[0]),
        timestamp=_clean_text(block[2]),
        sample_count=sample_count,
        sample_interval=sample_interval,
        sample_rate=1.0 / sample_interval,
        quantity=quantity,
        unit=unit,
        values=values,
    )


def _natural_key(name: str) -> tuple[int, str]:
    match = re.search(r"\((\d+)\)", Path(name).name)
    return (int(match.group(1)) if match else 0, name.lower())


def iter_uff_signals(input_path: str | Path) -> Iterator[UFFSignal]:
    """Yield dataset-58 signals from a ZIP archive, UFF file, or directory."""
    path = Path(input_path)
    if not path.exists():
        raise UFFError(f"input does not exist: {path}")

    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                (name for name in archive.namelist() if name.lower().endswith(".uff")),
                key=_natural_key,
            )
            if not names:
                raise UFFError(f"{path}: archive contains no UFF files")
            for name in names:
                raw = archive.read(name)
                yield parse_dataset_58(_decode_uff(raw), source_name=Path(name).name)
        return

    if path.is_file() and path.suffix.lower() == ".uff":
        yield parse_dataset_58(path.read_text(encoding="latin1"), path.name)
        return

    if path.is_dir():
        files = sorted(path.rglob("*.uff"), key=lambda item: _natural_key(str(item)))
        if not files:
            raise UFFError(f"{path}: directory contains no UFF files")
        for file_path in files:
            yield parse_dataset_58(
                file_path.read_text(encoding="latin1"), source_name=file_path.name
            )
        return

    raise UFFError(f"unsupported input type: {path}")
