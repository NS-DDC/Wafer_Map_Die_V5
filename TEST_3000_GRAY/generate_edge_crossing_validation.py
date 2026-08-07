"""Rebuild the 3000px TEST overlay and prove every circle-crossing EDGE box.

The input JPEG remains outside the repository because it is too large for
GitHub.  Only its 3000x3000 Gray derivative and these visual results are kept.
"""

from __future__ import annotations

from pathlib import Path
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_JPEG = Path("E:/mirero/Claude_V5") / "\uc6d0\ubcf8" / "Claude_V5" / "TEST" / "wafer_1.jpg"
OUT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT))
from USE_LATEST.use_gray_wafer_die_particle import build_die_map  # noqa: E402


def _legacy_center_based_edge(die: dict, dm: object) -> bool:
    """Reproduce the old bug: reject an edge box when its center is outside."""
    x1, y1, x2, y2 = die["rect_px"]
    cx, cy = die["center_px"]
    center_inside = (cx - dm.wafer_cx) ** 2 + (cy - dm.wafer_cy) ** 2 <= dm.edge_limit_r ** 2
    corner_outside = any(
        (px - dm.wafer_cx) ** 2 + (py - dm.wafer_cy) ** 2 > dm.edge_limit_r ** 2
        for px, py in ((x1, y1), (x2, y1), (x1, y2), (x2, y2))
    )
    return center_inside and corner_outside


def _draw_circle_and_corner(canvas: np.ndarray, dm: object) -> None:
    cv2.circle(canvas, (dm.wafer_cx, dm.wafer_cy), int(round(dm.edge_limit_r)), (255, 255, 0), 2)
    x0, y0 = int(round(dm.x0)), int(round(dm.y0))
    cv2.drawMarker(canvas, (x0, y0), (255, 0, 255), cv2.MARKER_CROSS, 18, 2)


def _write_preview(path: Path, image: np.ndarray) -> None:
    preview = cv2.resize(image, (1000, 1000), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), preview)


def main() -> None:
    raw = cv2.imdecode(np.fromfile(str(SOURCE_JPEG), np.uint8), cv2.IMREAD_COLOR)
    if raw is None:
        raise FileNotFoundError(f"Cannot decode source image: {SOURCE_JPEG}")
    gray = cv2.resize(cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY), (3000, 3000), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(OUT_DIR / "wafer_1_gray_3000.png"), gray)
    _write_preview(OUT_DIR / "wafer_1_gray_preview.png", cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

    dm = build_die_map(
        gray,
        grid_method="cross",
        min_pitch=30,
        max_pitch=70,
        notch_align=False,
        clip_partial_edge=False,
        edge_clip_margin_px=0,
        edge_mode="circle",
    )

    full = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    diagnostic = full.copy()
    new_edges = [die for die in dm.dies if die["is_edge_partial"]]
    old_indices = set()
    for die in dm.dies:
        x1, y1, x2, y2 = die["rect_px"]
        cv2.rectangle(full, (x1, y1), (x2, y2), (0, 220, 0), 1)
    for die in new_edges:
        x1, y1, x2, y2 = die["rect_px"]
        if _legacy_center_based_edge(die, dm):
            old_indices.add(die["index"])
        cv2.rectangle(full, (x1, y1), (x2, y2), (0, 0, 255), 1)

    # Yellow: boxes the former center-based code found. Red: actual EDGE boxes
    # it missed because their centers are outside the wafer circle.
    missing = []
    for die in new_edges:
        x1, y1, x2, y2 = die["rect_px"]
        color = (0, 255, 255) if die["index"] in old_indices else (0, 0, 255)
        cv2.rectangle(diagnostic, (x1, y1), (x2, y2), color, 1)
        if die["index"] not in old_indices:
            missing.append(die)

    _draw_circle_and_corner(full, dm)
    _draw_circle_and_corner(diagnostic, dm)
    cv2.imwrite(str(OUT_DIR / "wafer_1_cross_overlay_3000.png"), full)
    cv2.imwrite(str(OUT_DIR / "wafer_1_edge_gap_diagnostic_3000.png"), diagnostic)
    _write_preview(OUT_DIR / "wafer_1_cross_overlay_preview.png", full)
    _write_preview(OUT_DIR / "wafer_1_edge_gap_diagnostic_preview.png", diagnostic)

    print({
        "wafer": (dm.wafer_cx, dm.wafer_cy, dm.wafer_r),
        "pitch": (round(dm.pitch_x, 3), round(dm.pitch_y, 3)),
        "corner": (dm.x0, dm.y0),
        "dies_including_partial": len(dm.dies),
        "edge_circle_crossing": len(new_edges),
        "legacy_center_based_edge": len(old_indices),
        "previously_missing_edge": len(missing),
    })


if __name__ == "__main__":
    main()
