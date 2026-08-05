from __future__ import annotations

"""Test only the generated inputs kept under testWafer/ and save overlays."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wafer_die_map_v5_refined import build_die_map


ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "testWafer"
VIS_DIR = ROOT / "Visuals"
IMAGE_PATHS = (
    TEST_DIR / "wafer_1_3000_gray.png",
    TEST_DIR / "wafer_1_horizontal_street_3000.png",
)
SUMMARY_PATH = TEST_DIR / "testwafer_validation.json"


def horizontal_street_contrast(gray: np.ndarray, die_map: Any) -> float:
    """Measure how much detected horizontal grid lines stand out from nearby die rows."""
    h, w = gray.shape
    center_x1, center_x2 = int(w * 0.25), int(w * 0.75)
    row_mean = gray[:, center_x1:center_x2].mean(axis=1)
    pitch = max(4, int(round(die_map.pitch_y)))
    line_rows = []
    for y in np.arange(die_map.y0, h, pitch):
        if 3 <= y < h - 3:
            line_rows.append(int(y))
    for y in np.arange(die_map.y0 - pitch, -1, -pitch):
        if 3 <= y < h - 3:
            line_rows.append(int(y))
    if not line_rows:
        return 0.0

    deltas = []
    offset = max(3, pitch // 4)
    for y in line_rows:
        street = float(row_mean[max(0, y - 1):min(h, y + 2)].mean())
        body = float((row_mean[max(0, y - offset - 1):max(1, y - offset + 2)].mean() +
                      row_mean[min(h - 1, y + offset - 1):min(h, y + offset + 2)].mean()) / 2.0)
        deltas.append(street - body)
    return float(np.median(deltas))


def render_overlay(image_path: Path, die_map: Any) -> Path:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Could not read: {image_path}")
    for die in die_map.dies:
        x1, y1, x2, y2 = die["rect_px"]
        color = (30, 30, 230) if die["is_edge"] else (40, 205, 40)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
    cv2.circle(image, (die_map.wafer_cx, die_map.wafer_cy), die_map.wafer_r, (0, 190, 255), 2)
    cv2.drawMarker(image, (die_map.x0, die_map.y0), (255, 80, 255), cv2.MARKER_CROSS, 22, 2)
    out_path = TEST_DIR / f"{image_path.stem}_overlay.png"
    if not cv2.imwrite(str(out_path), image, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
        raise RuntimeError(f"Could not write: {out_path}")
    return out_path


def evaluate(image_path: Path) -> dict[str, Any]:
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(image_path)
    die_map = build_die_map(
        str(image_path),
        grid_method="std",
        notch_align=False,
        angle_align_method="none",
        clean=True,
        edge_mode="both",
    )
    overlay_path = render_overlay(image_path, die_map)
    return {
        "image": image_path.name,
        "overlay": overlay_path.name,
        "num_dies": die_map.num_dies,
        "edge_dies": sum(bool(die["is_edge"]) for die in die_map.dies),
        "pitch_x_px": round(float(die_map.pitch_x), 3),
        "pitch_y_px": round(float(die_map.pitch_y), 3),
        "grid_origin_px": [int(die_map.x0), int(die_map.y0)],
        "grid_origin_shift_px": list(die_map.grid_origin_shift_px),
        "wafer_center_px": [int(die_map.wafer_cx), int(die_map.wafer_cy)],
        "wafer_radius_px": int(die_map.wafer_r),
        "edge_clip_margin_px": int(die_map.edge_clip_margin_px),
        "horizontal_street_contrast": round(horizontal_street_contrast(gray, die_map), 3),
    }


def main() -> None:
    missing = [str(path) for path in IMAGE_PATHS if not path.exists()]
    if missing:
        raise FileNotFoundError("Run make_testwafer_horizontal_pattern.py first: " + ", ".join(missing))
    results = [evaluate(path) for path in IMAGE_PATHS]
    by_name = {item["image"]: item for item in results}
    reference = by_name[IMAGE_PATHS[0].name]
    horizontal = by_name[IMAGE_PATHS[1].name]
    pitch_tolerance = 2.0
    checks = {
        "both_images_detected": all(item["num_dies"] > 500 for item in results),
        "horizontal_pitch_stable": abs(horizontal["pitch_y_px"] - reference["pitch_y_px"]) <= pitch_tolerance,
        "horizontal_street_is_clearer": horizontal["horizontal_street_contrast"] > reference["horizontal_street_contrast"],
    }
    summary = {
        "test_scope": "testWafer folder only",
        "results": results,
        "pitch_y_difference_px": round(abs(horizontal["pitch_y_px"] - reference["pitch_y_px"]), 3),
        "horizontal_contrast_gain": round(
            horizontal["horizontal_street_contrast"] - reference["horizontal_street_contrast"], 3),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_checks_passed"]:
        raise SystemExit("testWafer validation failed")


if __name__ == "__main__":
    main()
