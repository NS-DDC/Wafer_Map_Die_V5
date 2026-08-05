from __future__ import annotations

"""Create reproducible 3,000 px test inputs from testWafer/wafer_1.jpg.

The second image keeps the source die texture but makes the horizontal streets
more visible.  This gives the detector a controlled weak-row / strong-row
comparison without adding unrelated images to the test set.
"""

import json
from pathlib import Path

import cv2
import numpy as np

from wafer_die_map_v5_refined import build_die_map


ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "testWafer"
SOURCE_PATH = TEST_DIR / "wafer_1.jpg"
REFERENCE_PATH = TEST_DIR / "wafer_1_3000_gray.png"
HORIZONTAL_PATH = TEST_DIR / "wafer_1_horizontal_street_3000.png"
METADATA_PATH = TEST_DIR / "wafer_1_horizontal_street_3000.json"
OUT_SIZE = 3000


def detect_row_grid(gray: np.ndarray) -> tuple[float, float]:
    """Use the real image grid, not a texture harmonic, as the street guide."""
    die_map = build_die_map(
        cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
        grid_method="std",
        notch_align=False,
        angle_align_method="none",
        clean=True,
        edge_mode="both",
    )
    pitch_y = float(die_map.pitch_y)
    phase_y = float(die_map.y0 % max(1, int(round(pitch_y))))
    return pitch_y, phase_y


def enhance_horizontal_streets(gray: np.ndarray, pitch: float, phase: float) -> np.ndarray:
    """Brighten a narrow, softly tapered band at each detected horizontal street."""
    h, w = gray.shape
    rows = np.arange(h, dtype=np.float32)
    period = max(1.0, pitch)
    distance = np.abs(((rows - phase + period / 2.0) % period) - period / 2.0)
    band = np.clip(1.0 - distance / 2.1, 0.0, 1.0) ** 1.6

    # Avoid changing the black background outside the physical wafer.
    wafer_mask = (gray > 12).astype(np.float32)
    strength = 46.0 * band[:, None] * wafer_mask
    out = np.clip(gray.astype(np.float32) + strength, 0, 255).astype(np.uint8)
    return out


def main() -> None:
    if SOURCE_PATH.exists():
        source = cv2.imread(str(SOURCE_PATH), cv2.IMREAD_GRAYSCALE)
        if source is None:
            raise RuntimeError(f"Could not read: {SOURCE_PATH}")
        reference = cv2.resize(source, (OUT_SIZE, OUT_SIZE), interpolation=cv2.INTER_AREA)
        source_name = SOURCE_PATH.name
    elif REFERENCE_PATH.exists():
        # GitHub intentionally excludes the 52 MB original.  The committed
        # 3,000 px reference remains enough to reproduce the enhanced image.
        reference = cv2.imread(str(REFERENCE_PATH), cv2.IMREAD_GRAYSCALE)
        if reference is None:
            raise RuntimeError(f"Could not read: {REFERENCE_PATH}")
        source_name = REFERENCE_PATH.name
    else:
        raise FileNotFoundError(f"Missing both {SOURCE_PATH.name} and {REFERENCE_PATH.name}")
    pitch_y, phase_y = detect_row_grid(reference)
    horizontal = enhance_horizontal_streets(reference, pitch_y, phase_y)

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(REFERENCE_PATH), reference, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
        raise RuntimeError(f"Could not write: {REFERENCE_PATH}")
    if not cv2.imwrite(str(HORIZONTAL_PATH), horizontal, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
        raise RuntimeError(f"Could not write: {HORIZONTAL_PATH}")

    metadata = {
        "source": source_name,
        "reference": REFERENCE_PATH.name,
        "horizontal_pattern": HORIZONTAL_PATH.name,
        "size_px": OUT_SIZE,
        "estimated_horizontal_pitch_px": round(pitch_y, 3),
        "estimated_horizontal_phase_px": round(phase_y, 3),
        "street_band_half_width_px": 2.1,
        "street_brightness_boost": 46,
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
