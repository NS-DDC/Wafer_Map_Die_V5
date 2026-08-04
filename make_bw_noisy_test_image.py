from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "Test_Images"
SOURCE_DIR = TEST_DIR / "sources"
OUT_PATH = TEST_DIR / "bw_noisy_top_p090_3000.png"
SIZE = 3000


def load_source() -> np.ndarray:
    path = SOURCE_DIR / "Performance_PIPER_die.jpg"
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return img


def crop_box(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    h, w = img.shape[:2]
    x1 = max(0, min(w, x1))
    x2 = max(0, min(w, x2))
    y1 = max(0, min(h, y1))
    y2 = max(0, min(h, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("invalid crop")
    return img[y1:y2, x1:x2].copy()


def square_center_crop(img: np.ndarray, scale: float = 0.90) -> np.ndarray:
    h, w = img.shape[:2]
    size = int(min(h, w) * scale)
    x1 = (w - size) // 2
    y1 = (h - size) // 2
    return crop_box(img, x1, y1, x1 + size, y1 + size)


def build_gray_texture() -> np.ndarray:
    src = square_center_crop(load_source(), scale=0.90)
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return gray


def full_die_inside_circle(
    die_x1: int,
    die_y1: int,
    die_x2: int,
    die_y2: int,
    cx: int,
    cy: int,
    radius: int,
) -> bool:
    r2 = radius * radius
    corners = (
        (die_x1, die_y1),
        (die_x2, die_y1),
        (die_x1, die_y2),
        (die_x2, die_y2),
    )
    return all((px - cx) ** 2 + (py - cy) ** 2 <= r2 for px, py in corners)


def add_street_noise(gray: np.ndarray, wafer_mask: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = gray.astype(np.int16)

    # Global gaussian-like intensity wobble.
    global_noise = rng.normal(0.0, 11.0, gray.shape).astype(np.int16)
    out += global_noise

    # Salt-and-pepper speckles concentrated on street / wafer area.
    speckle = rng.random(gray.shape)
    out[(speckle < 0.018) & wafer_mask] = 255
    out[(speckle > 0.982) & wafer_mask] = 0

    # Random scratch lines across the wafer.
    h, w = gray.shape
    for _ in range(160):
        x1 = int(rng.integers(0, w))
        y1 = int(rng.integers(0, h))
        x2 = int(np.clip(x1 + rng.integers(-160, 160), 0, w - 1))
        y2 = int(np.clip(y1 + rng.integers(-160, 160), 0, h - 1))
        color = int(rng.integers(35, 225))
        thickness = int(rng.integers(1, 3))
        cv2.line(out, (x1, y1), (x2, y2), color, thickness=thickness, lineType=cv2.LINE_AA)

    # Blotchy islands between dies.
    for _ in range(120):
        cx = int(rng.integers(0, w))
        cy = int(rng.integers(0, h))
        rx = int(rng.integers(8, 26))
        ry = int(rng.integers(8, 26))
        color = int(rng.integers(48, 208))
        cv2.ellipse(out, (cx, cy), (rx, ry), 0, 0, 360, color, -1, lineType=cv2.LINE_AA)

    out = np.clip(out, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(out, (3, 3), 0)


def create_bw_wafer(
    texture: np.ndarray,
    *,
    out_size: int = SIZE,
    pitch: int = 90,
    gap_px: int = 1,
    rotation_deg: float = -1.10,
    seed: int = 77,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    cx = out_size // 2
    cy = out_size // 2
    radius = int(out_size * 0.455)
    gap_px = max(1, int(gap_px))
    die_side = pitch - gap_px
    left_gap = gap_px // 2

    gray = np.zeros((out_size, out_size), dtype=np.uint8)
    yy, xx = np.mgrid[:out_size, :out_size]
    wafer_mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius
    gray[wafer_mask] = 78

    cols = math.ceil((2 * radius) / pitch) + 4
    rows = math.ceil((2 * radius) / pitch) + 4
    start_x = cx - (cols // 2) * pitch
    start_y = cy - (rows // 2) * pitch

    tile = cv2.resize(texture, (die_side, die_side), interpolation=cv2.INTER_AREA)

    for row in range(rows):
        for col in range(cols):
            cell_x1 = start_x + col * pitch
            cell_y1 = start_y + row * pitch
            die_x1 = cell_x1 + left_gap
            die_y1 = cell_y1 + left_gap
            die_x2 = die_x1 + die_side
            die_y2 = die_y1 + die_side

            if die_x2 <= 0 or die_y2 <= 0 or die_x1 >= out_size or die_y1 >= out_size:
                continue
            if not full_die_inside_circle(die_x1, die_y1, die_x2, die_y2, cx, cy, radius - 2):
                continue

            patch = tile.astype(np.float32)
            patch *= rng.uniform(0.95, 1.05)
            patch += rng.normal(0.0, 4.0, patch.shape)
            patch = np.clip(patch, 0, 255).astype(np.uint8)
            if rng.random() < 0.03:
                dot_x = int(rng.integers(max(2, die_side // 5), max(3, die_side - die_side // 5)))
                dot_y = int(rng.integers(max(2, die_side // 5), max(3, die_side - die_side // 5)))
                cv2.circle(patch, (dot_x, dot_y), max(2, die_side // 14), int(rng.integers(0, 32)), -1)
            gray[die_y1:die_y2, die_x1:die_x2] = patch

    gray = add_street_noise(gray, wafer_mask, seed + 101)
    cv2.circle(gray, (cx, cy), radius, 180, thickness=5, lineType=cv2.LINE_AA)

    if abs(rotation_deg) > 1e-9:
        m = cv2.getRotationMatrix2D((cx, cy), rotation_deg, 1.0)
        gray = cv2.warpAffine(
            gray,
            m,
            (out_size, out_size),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
    return gray


def main() -> None:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    gray_texture = build_gray_texture()
    gray = create_bw_wafer(gray_texture)
    cv2.imwrite(str(OUT_PATH), gray)
    print(f"wrote: {OUT_PATH.name}")


if __name__ == "__main__":
    main()
