from __future__ import annotations

"""Validate die-render angle correction for the Gray_Wafer rotation suite."""

import json
from pathlib import Path
from typing import Any

import cv2

from wafer_die_map_v5_refined import build_die_map


ROOT = Path(__file__).resolve().parent
GRAY_DIR = ROOT / "Gray_Wafer"
CASE_DIR = GRAY_DIR / "angle_cases"
MANIFEST_PATH = GRAY_DIR / "gray_angle_cases_manifest.json"
RESULT_PATH = GRAY_DIR / "gray_angle_validation.json"
OVERLAY_DIR = GRAY_DIR / "angle_overlays"
OVERLAY_ANGLES = {0.1, 0.5, 1.0}
RESIDUAL_TOLERANCE_DEG = 0.12
CORRECTION_TOLERANCE_DEG = 0.12


def render_overlay(image, die_map: Any, out_path: Path) -> None:
    canvas = image.copy()
    for die in die_map.dies:
        x1, y1, x2, y2 = die["rect_px"]
        color = (35, 35, 225) if die["is_edge"] else (45, 205, 55)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 1)
    cv2.circle(canvas, (die_map.wafer_cx, die_map.wafer_cy), die_map.wafer_r, (0, 190, 255), 2)
    cv2.drawMarker(canvas, (die_map.x0, die_map.y0), (255, 80, 255), cv2.MARKER_CROSS, 18, 2)
    if not cv2.imwrite(str(out_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise RuntimeError(f"Could not write: {out_path}")


def evaluate_case(image_path: Path, input_rotation_deg: float) -> dict[str, Any]:
    die_map = build_die_map(
        str(image_path),
        grid_method="std",
        notch_align=True,
        angle_align_method="die_render",
        clean=True,
        edge_mode="both",
    )
    correction_deg = float(die_map.rotation_deg)
    residual_deg = float(die_map.die_grid_angle_resid)
    correction_error = abs(correction_deg + input_rotation_deg)

    result = {
        "image": image_path.name,
        "input_rotation_deg": input_rotation_deg,
        "applied_correction_deg": round(correction_deg, 4),
        "correction_error_deg": round(correction_error, 4),
        "residual_grid_angle_deg": round(residual_deg, 4),
        "angle_confidence": round(float(die_map.angle_confidence), 3),
        "angle_agree": bool(die_map.angle_agree),
        "angle_verified": bool(die_map.angle_verified),
        "num_dies": die_map.num_dies,
        "edge_dies": sum(bool(die["is_edge"]) for die in die_map.dies),
        "pitch_x_px": round(float(die_map.pitch_x), 3),
        "pitch_y_px": round(float(die_map.pitch_y), 3),
        "passed": abs(residual_deg) <= RESIDUAL_TOLERANCE_DEG
        and correction_error <= CORRECTION_TOLERANCE_DEG
        and bool(die_map.angle_verified),
    }
    if input_rotation_deg in OVERLAY_ANGLES:
        OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
        overlay_path = OVERLAY_DIR / image_path.with_suffix(".jpg").name
        render_overlay(die_map.aligned_image, die_map, overlay_path)
        result["aligned_overlay"] = str(overlay_path.relative_to(GRAY_DIR))
    return result


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError("Run make_gray_wafer_angle_cases.py first.")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results = [
        evaluate_case(CASE_DIR / item["image"], float(item["input_rotation_deg"]))
        for item in manifest["cases"]
    ]
    checks = {
        "all_cases_passed": all(item["passed"] for item in results),
        "all_angles_verified": all(item["angle_verified"] for item in results),
        "stable_grid_pitch": len({(item["pitch_x_px"], item["pitch_y_px"]) for item in results}) == 1,
    }
    summary = {
        "test_scope": "Gray_Wafer/angle_cases only",
        "residual_tolerance_deg": RESIDUAL_TOLERANCE_DEG,
        "correction_tolerance_deg": CORRECTION_TOLERANCE_DEG,
        "results": results,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "note": "At 0.1 deg the default correction gate may choose no rotation; it still passes when residual grid angle stays within tolerance.",
    }
    RESULT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_checks_passed"]:
        raise SystemExit("Gray_Wafer angle validation failed")


if __name__ == "__main__":
    main()
