from __future__ import annotations

"""Validate adjustable edge-only particle inspection on Gray wafer inputs."""

import json
from pathlib import Path

import cv2
import numpy as np

from use_gray_wafer_die_particle import (
    build_die_map,
    inspect_particles_in_wafer_ring,
    render_particle_diagnostic_overlay,
    render_particle_overlay,
)


ROOT = Path(__file__).resolve().parent
GRAY_DIR = ROOT / "Gray_Wafer"
INPUTS = ("111.png", "2222.png")
PARTICLE_REFERENCE = GRAY_DIR / "Paticle" / "22.png"
RESULT_DIR = GRAY_DIR / "edge_particle_results"
SUMMARY_PATH = GRAY_DIR / "edge_particle_validation.json"

# These are intentionally ordinary call parameters, not hidden constants.
RING_PARAMS = {
    "ring_inner_margin_px": 75,
    "ring_outer_margin_px": 10,
    "ring_guard_px": 2,
    "die_exclusion_margin_px": 2,
    "white_threshold": 220,
    "min_area_px": 20,
    "max_area_px": 300,
    "max_aspect_ratio": 2.5,
    "min_fill_ratio": 0.45,
    "min_local_contrast": 45.0,
}


def _synthetic_reference_check(image: np.ndarray) -> dict:
    """Place a scaled reference blob in a valid edge-only pixel region."""
    reference = cv2.imread(str(PARTICLE_REFERENCE), cv2.IMREAD_GRAYSCALE)
    if reference is None:
        raise FileNotFoundError(str(PARTICLE_REFERENCE))
    reference = cv2.resize(reference, (13, 11), interpolation=cv2.INTER_AREA)

    probe_dm = build_die_map(image, grid_method="std", notch_align=False, edge_mode="both")
    probe = inspect_particles_in_wafer_ring(probe_dm, **RING_PARAMS)
    valid = cv2.erode(probe["inspection_mask"], np.ones(reference.shape, dtype=np.uint8))
    locations = np.argwhere(valid > 0)
    if len(locations) == 0:
        raise RuntimeError("No valid particle injection location in edge inspection mask")
    y, x = (int(value) for value in locations[np.argmin(locations[:, 0])])

    synthetic = image.copy()
    half_h, half_w = reference.shape[0] // 2, reference.shape[1] // 2
    target = synthetic[y - half_h:y - half_h + reference.shape[0],
                       x - half_w:x - half_w + reference.shape[1]]
    target[:] = np.maximum(target, reference)
    synthetic_dm = build_die_map(synthetic, grid_method="std", notch_align=False, edge_mode="both")
    detected = inspect_particles_in_wafer_ring(synthetic_dm, **RING_PARAMS)
    first = detected["particles"][0] if detected["particles"] else None
    return {
        "injected_center_px": [x, y],
        "detected_count": len(detected["particles"]),
        "first_detected_center_px": list(first["center_px"]) if first else None,
        "passed": len(detected["particles"]) == 1 and first is not None,
    }


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    source_for_reference_check = None
    for name in INPUTS:
        image = cv2.imread(str(GRAY_DIR / name), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(name)
        die_map = build_die_map(image, grid_method="std", notch_align=False, edge_mode="both")
        inspection = inspect_particles_in_wafer_ring(
            die_map, include_debug_components=True, **RING_PARAMS)
        overlay_path = RESULT_DIR / f"{Path(name).stem}_edge_particles.png"
        diagnostic_path = RESULT_DIR / f"{Path(name).stem}_edge_particle_diagnostic.png"
        if not cv2.imwrite(str(overlay_path), render_particle_overlay(die_map, inspection)):
            raise RuntimeError(f"Could not write: {overlay_path}")
        if not cv2.imwrite(str(diagnostic_path), render_particle_diagnostic_overlay(die_map, inspection)):
            raise RuntimeError(f"Could not write: {diagnostic_path}")
        results.append({
            "image": name,
            "input_shape": list(image.shape),
            "input_channels": 1,
            "num_dies": die_map.num_dies,
            "pitch_px": [round(float(die_map.pitch_x), 3), round(float(die_map.pitch_y), 3)],
            "inspection_pixels": int(inspection["inspection_mask"].sum()),
            "mask_summary": inspection["mask_summary"],
            "debug_component_counts": {
                "die_excluded": len(inspection["debug_components"]["die_excluded"]),
                "rejected": len(inspection["debug_components"]["rejected"]),
            },
            "particle_count": len(inspection["particles"]),
            "particles": inspection["particles"],
            "overlay": str(overlay_path.relative_to(GRAY_DIR)),
            "diagnostic_overlay": str(diagnostic_path.relative_to(GRAY_DIR)),
        })
        source_for_reference_check = image

    assert source_for_reference_check is not None
    reference_check = _synthetic_reference_check(source_for_reference_check)
    summary = {
        "test_scope": "Gray_Wafer/111.png and Gray_Wafer/2222.png",
        "parameters": RING_PARAMS,
        "results": results,
        "reference_particle_injection": reference_check,
        "all_checks_passed": all(item["input_channels"] == 1 for item in results)
        and reference_check["passed"],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_checks_passed"]:
        raise SystemExit("Gray wafer-ring particle validation failed")


if __name__ == "__main__":
    main()
