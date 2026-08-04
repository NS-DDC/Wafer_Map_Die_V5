from __future__ import annotations

import json
from pathlib import Path

import cv2

from wafer_die_map_v5 import build_die_map


ROOT = Path(__file__).resolve().parent
IMAGE_PATH = ROOT / "Test_Images" / "bw_noisy_top_p090_3000.png"
OVERLAY_PATH = ROOT / "Test_Images" / "bw_noisy_top_p090_3000_overlay.png"


def render_overlay(image_path: Path, die_map) -> None:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return
    for die in die_map.dies:
        x1, y1, x2, y2 = die["rect_px"]
        color = (0, 0, 255) if die["is_edge"] else (0, 255, 0)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
    cv2.circle(img, (die_map.wafer_cx, die_map.wafer_cy), die_map.wafer_r, (255, 180, 0), 2)
    cv2.imwrite(str(OVERLAY_PATH), img)


def main() -> None:
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(
            f"{IMAGE_PATH.name} not found. Run make_bw_noisy_test_image.py first."
        )

    die_map = build_die_map(
        str(IMAGE_PATH),
        grid_method="std",
        angle_align_method="die_render",
        clean=True,
    )
    render_overlay(IMAGE_PATH, die_map)

    result = {
        "image": IMAGE_PATH.name,
        "num_dies": die_map.num_dies,
        "pitch_x": round(die_map.pitch_x, 3),
        "pitch_y": round(die_map.pitch_y, 3),
        "rotation_deg": round(die_map.rotation_deg, 4),
        "angle_confidence": round(die_map.angle_confidence, 3),
        "angle_agree": bool(die_map.angle_agree),
        "wafer_center": [die_map.wafer_cx, die_map.wafer_cy],
        "wafer_r": die_map.wafer_r,
        "overlay": OVERLAY_PATH.name,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
