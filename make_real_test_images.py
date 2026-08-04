from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Tuple
from urllib.request import urlretrieve

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "Test_Images"
SOURCE_DIR = TEST_DIR / "sources"
SIZE = 3072


SOURCES: Dict[str, Dict[str, str]] = {
    "MIPS_R3000A_die.jpg": {
        "url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/MIPS%20R3000A%20die.JPG",
        "page": "https://commons.wikimedia.org/wiki/File:MIPS_R3000A_die.JPG",
        "license": "CC BY 3.0",
    },
    "Performance_PIPER_die.jpg": {
        "url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Performance%20PIPER%20die.JPG",
        "page": "https://commons.wikimedia.org/wiki/File:Performance_PIPER_die.JPG",
        "license": "CC BY 3.0",
    },
    "CASIO_fx92_2D_die.jpg": {
        "url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/CASIO%20fx-92%20Coll%C3%A8ge%202D%20integrated%20circuit.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:CASIO_fx-92_Coll%C3%A8ge_2D_integrated_circuit.jpg",
        "license": "CC BY-SA 3.0",
    },
    "Exposed_150mm_wafer.jpg": {
        "url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Exposed%20150mm%206%22%20wafer%20with%20hundreds%20of%20chips.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Exposed_150mm_6%22_wafer_with_hundreds_of_chips.jpg",
        "license": "CC BY-SA 4.0",
    },
}


def ensure_sources() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for name, meta in SOURCES.items():
        dst = SOURCE_DIR / name
        if dst.exists():
            continue
        print(f"download: {name}")
        urlretrieve(meta["url"], dst)


def load(name: str) -> np.ndarray:
    img = cv2.imread(str(SOURCE_DIR / name), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(name)
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


def square_center_crop(img: np.ndarray, scale: float = 0.88) -> np.ndarray:
    h, w = img.shape[:2]
    size = int(min(h, w) * scale)
    x1 = (w - size) // 2
    y1 = (h - size) // 2
    return crop_box(img, x1, y1, x1 + size, y1 + size)


def prep_texture(img: np.ndarray, out_size: int, color_boost: float = 1.0) -> np.ndarray:
    tex = cv2.resize(img, (out_size, out_size), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(tex, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= color_boost
    hsv[..., 2] *= 1.01
    hsv[..., 1:] = np.clip(hsv[..., 1:], 0, 255)
    tex = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return cv2.GaussianBlur(tex, (3, 3), 0)


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


def add_between_die_noise(
    canvas: np.ndarray,
    street_mask: np.ndarray,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = canvas.astype(np.int16)

    pixel_jitter = rng.normal(0.0, 8.0, out.shape).astype(np.int16)
    out[street_mask] += pixel_jitter[street_mask]

    speckle = rng.random(street_mask.shape)
    bright_mask = street_mask & (speckle < 0.012)
    dark_mask = street_mask & (speckle > 0.988)
    out[bright_mask] += 22
    out[dark_mask] -= 28

    h, w = street_mask.shape
    for _ in range(220):
        x1 = int(rng.integers(0, w))
        y1 = int(rng.integers(0, h))
        x2 = int(np.clip(x1 + rng.integers(-28, 29), 0, w - 1))
        y2 = int(np.clip(y1 + rng.integers(-28, 29), 0, h - 1))
        color = tuple(int(v) for v in rng.integers(88, 196, size=3))
        thickness = int(rng.integers(1, 2))
        line_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.line(line_mask, (x1, y1), (x2, y2), 255, thickness=thickness, lineType=cv2.LINE_AA)
        keep = (line_mask > 0) & street_mask
        out[keep] = np.array(color, dtype=np.int16)

    for _ in range(140):
        cx = int(rng.integers(0, w))
        cy = int(rng.integers(0, h))
        rx = int(rng.integers(1, 4))
        ry = int(rng.integers(1, 4))
        blob_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(blob_mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1, lineType=cv2.LINE_AA)
        keep = (blob_mask > 0) & street_mask
        delta = int(rng.integers(-26, 27))
        out[keep] += delta

    out = np.clip(out, 0, 255).astype(np.uint8)
    return out


def create_flat_wafer(
    texture: np.ndarray,
    *,
    out_size: int,
    pitch: int,
    gap_px: int,
    street_bgr: Tuple[int, int, int],
    wafer_bgr: Tuple[int, int, int],
    outline_bgr: Tuple[int, int, int],
    rotation_deg: float,
    seed: int,
    defect_prob: float = 0.015,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    canvas = np.zeros((out_size, out_size, 3), dtype=np.uint8)
    die_mask = np.zeros((out_size, out_size), dtype=bool)

    cx = out_size // 2
    cy = out_size // 2
    radius = int(out_size * 0.455)
    gap_px = max(1, int(gap_px))
    die_side = pitch - gap_px
    left_gap = gap_px // 2
    tile = cv2.resize(texture, (die_side, die_side), interpolation=cv2.INTER_AREA)

    yy, xx = np.mgrid[:out_size, :out_size]
    wafer_mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius
    canvas[wafer_mask] = wafer_bgr

    cols = math.ceil((2 * radius) / pitch) + 4
    rows = math.ceil((2 * radius) / pitch) + 4
    start_x = cx - (cols // 2) * pitch
    start_y = cy - (rows // 2) * pitch

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

            canvas[cell_y1:cell_y1 + pitch, cell_x1:cell_x1 + pitch] = street_bgr

            patch = tile.astype(np.float32)
            patch *= rng.uniform(0.97, 1.03)
            patch = np.clip(patch, 0, 255).astype(np.uint8)
            if rng.random() < defect_prob:
                dot_x = int(rng.integers(max(2, die_side // 5), max(3, die_side - die_side // 5)))
                dot_y = int(rng.integers(max(2, die_side // 5), max(3, die_side - die_side // 5)))
                cv2.circle(patch, (dot_x, dot_y), max(2, die_side // 14), (16, 16, 16), -1)

            canvas[die_y1:die_y2, die_x1:die_x2] = patch
            die_mask[die_y1:die_y2, die_x1:die_x2] = True

    street_mask = wafer_mask & (~die_mask)
    canvas = add_between_die_noise(canvas, street_mask, seed + 101)

    cv2.circle(canvas, (cx, cy), radius, outline_bgr, thickness=6, lineType=cv2.LINE_AA)

    if abs(rotation_deg) > 1e-9:
        m = cv2.getRotationMatrix2D((cx, cy), rotation_deg, 1.0)
        canvas = cv2.warpAffine(
            canvas,
            m,
            (out_size, out_size),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
    return canvas


def build_textures() -> Dict[str, np.ndarray]:
    mips = prep_texture(square_center_crop(load("MIPS_R3000A_die.jpg"), scale=0.90), 256, color_boost=1.03)
    piper = prep_texture(square_center_crop(load("Performance_PIPER_die.jpg"), scale=0.90), 256, color_boost=1.04)
    casio = prep_texture(crop_box(load("CASIO_fx92_2D_die.jpg"), 820, 640, 6400, 6220), 256, color_boost=1.02)
    exposed = prep_texture(crop_box(load("Exposed_150mm_wafer.jpg"), 2400, 1500, 3000, 2100), 256, color_boost=0.98)

    return {
        "real_mips_top_p084.png": mips,
        "real_piper_top_p088.png": piper,
        "real_casio_top_p092.png": casio,
        "real_exposed_top_p078.png": exposed,
    }


def write_sources_md() -> None:
    lines = [
        "# Real Test Image Sources",
        "",
        "These source images were downloaded from Wikimedia Commons and used to build the generated 2D top-view wafer samples in this folder.",
        "",
    ]
    for name, meta in SOURCES.items():
        lines.extend(
            [
                f"## {name}",
                "",
                f"- File page: {meta['page']}",
                f"- Download URL: {meta['url']}",
                f"- License: {meta['license']}",
                "",
            ]
        )
    (TEST_DIR / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_sources()
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    textures = build_textures()
    configs = {
        "real_mips_top_p084.png": dict(pitch=84, gap_px=1, street_bgr=(126, 170, 142), wafer_bgr=(58, 58, 58), outline_bgr=(178, 178, 178), rotation_deg=-1.25, seed=11),
        "real_piper_top_p088.png": dict(pitch=88, gap_px=1, street_bgr=(150, 200, 164), wafer_bgr=(60, 60, 60), outline_bgr=(182, 182, 182), rotation_deg=1.55, seed=19),
        "real_casio_top_p092.png": dict(pitch=92, gap_px=1, street_bgr=(136, 176, 196), wafer_bgr=(54, 54, 54), outline_bgr=(180, 180, 180), rotation_deg=-0.95, seed=29),
        "real_exposed_top_p078.png": dict(pitch=78, gap_px=1, street_bgr=(164, 186, 128), wafer_bgr=(56, 56, 56), outline_bgr=(184, 184, 184), rotation_deg=0.85, seed=37),
    }

    for name, texture in textures.items():
        out = create_flat_wafer(texture, out_size=SIZE, **configs[name])
        cv2.imwrite(str(TEST_DIR / name), out)
        print(f"wrote: {name}")

    write_sources_md()


if __name__ == "__main__":
    main()
