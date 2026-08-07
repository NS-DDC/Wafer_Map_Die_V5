"""Regression test: a wide vertical noise stripe must not become a grid cross."""

from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from USE_LATEST.use_gray_wafer_die_particle import detect_thin_cross_grid


def main() -> None:
    height = width = 3000
    wafer_cx = wafer_cy = 1500
    wafer_r = 1330
    expected_pitch_x, expected_pitch_y = 47, 53
    expected_x0, expected_y0 = 1498, 1490

    yy, xx = np.ogrid[:height, :width]
    wafer_mask = (xx - wafer_cx) ** 2 + (yy - wafer_cy) ** 2 <= wafer_r ** 2
    image = np.zeros((height, width), np.uint8)
    image[wafer_mask] = 45
    for x in np.arange(expected_x0 - 40 * expected_pitch_x,
                       expected_x0 + 41 * expected_pitch_x, expected_pitch_x):
        if 0 <= x < width:
            image[:, max(0, x - 1):min(width, x + 1)] = 125
    for y in np.arange(expected_y0 - 40 * expected_pitch_y,
                       expected_y0 + 41 * expected_pitch_y, expected_pitch_y):
        if 0 <= y < height:
            image[max(0, y - 1):min(height, y + 1), :] = 125

    # This stripe is deliberately bright, broad, and close to the center, but
    # it has no matching phase at +/- pitch.  It must not be the chosen x0.
    image[:, 1513:1529] = 235
    noise = np.random.default_rng(20260807).normal(0, 5, (height, width))
    image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    image[~wafer_mask] = 0

    pitch_x, pitch_y, x0, y0 = detect_thin_cross_grid(
        image, wafer_cx, wafer_cy, wafer_r, min_pitch=30, max_pitch=70)
    assert abs(pitch_x - expected_pitch_x) <= 2, (pitch_x, expected_pitch_x)
    assert abs(pitch_y - expected_pitch_y) <= 2, (pitch_y, expected_pitch_y)
    assert abs(x0 - expected_x0) <= 3, (x0, expected_x0)
    assert abs(y0 - expected_y0) <= 3, (y0, expected_y0)
    print({
        "expected": (expected_pitch_x, expected_pitch_y, expected_x0, expected_y0),
        "detected": (round(pitch_x, 3), round(pitch_y, 3), x0, y0),
    })


if __name__ == "__main__":
    main()
