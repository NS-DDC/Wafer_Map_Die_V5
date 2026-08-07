"""
Manual-grid Wafer Die Map (standalone, Python 3.9+).

Use this module when the calling application measures the grid itself.
Only the wafer circle is detected from the supplied image.  The caller supplies
the shared grid corner and pitch as floats; this module never re-detects,
rounds, or accumulates the pitch while calculating grid boundaries.

Required packages: numpy, opencv-python
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

__all__ = [
    "WaferDieMap",
    "detect_wafer_center",
    "build_die_map",
    "locate_die",
    "crop_die",
    "render_die_map_overlay",
]


DEFAULT_PIXEL_PER_UNIT = 32.0
DEFAULT_EDGE_MARGIN = 1.0
DEFAULT_CLIP_PARTIAL_EDGE = True
DEFAULT_EDGE_MODE = "both"


def _as_bgr(image: np.ndarray) -> np.ndarray:
    """Normalize Gray/BGR/BGRA input to BGR without changing coordinates."""
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("image must be a non-empty numpy array.")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim != 3:
        raise ValueError("image must have shape (H,W), (H,W,1), (H,W,3), or (H,W,4).")
    if image.shape[2] == 1:
        return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 3:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    raise ValueError("image channel count must be 1, 3, or 4.")


def detect_wafer_center(image: np.ndarray, *, bg_threshold: int = 20) -> Dict[str, int]:
    """Detect the largest non-background wafer contour.

    Returns
    -------
    dict
        ``{"wafer_cx": int, "wafer_cy": int, "wafer_r": int}``

        - ``wafer_cx``, ``wafer_cy``: image-pixel wafer center.
        - ``wafer_r``: wafer radius in image pixels.

    This is the only image-analysis step used by :func:`build_die_map`.
    The function does not inspect or modify the caller's corner/pitch values.
    """
    bgr = _as_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, int(bg_threshold), 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("Wafer region not found. Check bg_threshold or input image.")
    (cx, cy), radius = cv2.minEnclosingCircle(max(contours, key=cv2.contourArea))
    return {"wafer_cx": int(round(cx)), "wafer_cy": int(round(cy)), "wafer_r": int(round(radius))}


def _normalize_edge_mode(edge_mode: str) -> str:
    mode = str(edge_mode).lower().strip()
    aliases = {
        "circle": "circle", "partial": "circle", "disc": "circle",
        "ring": "ring", "neighbor": "ring", "outer": "ring",
        "margin": "margin", "band": "margin", "distance": "margin",
        "both": "both", "or": "both", "all": "both", "union": "both",
    }
    if mode not in aliases:
        raise ValueError("edge_mode must be 'circle', 'ring', 'margin', or 'both'.")
    return aliases[mode]


def _edge_flag(is_partial: bool, is_ring: bool, is_margin: bool, mode: str) -> bool:
    if mode == "circle":
        return bool(is_partial)
    if mode == "ring":
        return bool(is_ring)
    if mode == "margin":
        return bool(is_margin)
    return bool(is_partial or is_ring or is_margin)


def _rect_circle_clearance(x1: float, y1: float, x2: float, y2: float,
                           cx: float, cy: float, radius: float) -> float:
    """Positive: complete die is inside. Negative: a die corner crosses the circle."""
    farthest = max(math.hypot(x - cx, y - cy)
                   for x, y in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)))
    return float(radius - farthest)


def _rect_intersects_circle(x1: float, y1: float, x2: float, y2: float,
                            cx: float, cy: float, radius: float) -> bool:
    """Whether any portion of an axis-aligned die rectangle lies in the wafer."""
    left, right = sorted((float(x1), float(x2)))
    top, bottom = sorted((float(y1), float(y2)))
    nearest_x = min(max(float(cx), left), right)
    nearest_y = min(max(float(cy), top), bottom)
    return (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2 <= float(radius) ** 2


def _rect_crosses_circle(x1: float, y1: float, x2: float, y2: float,
                         cx: float, cy: float, radius: float) -> bool:
    """Whether the wafer circle crosses the rectangle boundary.

    It includes boxes whose centers sit outside the circle but whose area still
    intersects it; those boxes are valid EDGE boxes.
    """
    left, right = sorted((float(x1), float(x2)))
    top, bottom = sorted((float(y1), float(y2)))
    farthest = max(math.hypot(x - cx, y - cy)
                   for x, y in ((left, top), (right, top),
                                (left, bottom), (right, bottom)))
    if left <= cx <= right and top <= cy <= bottom:
        nearest = min(cx - left, right - cx, cy - top, bottom - cy)
    else:
        nearest_x = min(max(cx, left), right)
        nearest_y = min(max(cy, top), bottom)
        nearest = math.hypot(nearest_x - cx, nearest_y - cy)
    return nearest <= float(radius) <= farthest


def _crop_rect(cx: float, cy: float, die_w: float, die_h: float,
               offset_x: float, offset_y: float,
               margin_x: float, margin_y: float) -> Tuple[int, int, int, int]:
    return (
        int(round(cx + offset_x - die_w / 2.0 - margin_x)),
        int(round(cy + offset_y - die_h / 2.0 - margin_y)),
        int(round(cx + offset_x + die_w / 2.0 + margin_x)),
        int(round(cy + offset_y + die_h / 2.0 + margin_y)),
    )


def crop_die(image: np.ndarray, center_x: float, center_y: float,
             die_w: float, die_h: float, *, offset_x: float = 0.0,
             offset_y: float = 0.0, margin_x: float = 0.0,
             margin_y: float = 0.0, border_mode: str = "pad") -> np.ndarray:
    """Crop one die and return a numpy image array.

    ``pad`` returns the requested crop size and fills image-outside pixels with
    zeros. ``crop`` returns only the image-overlapping region, so its shape can
    be smaller. This helper returns the crop array itself, not a Die map entry.
    """
    x1, y1, x2, y2 = _crop_rect(center_x, center_y, die_w, die_h,
                                 offset_x, offset_y, margin_x, margin_y)
    height, width = image.shape[:2]
    if border_mode not in ("pad", "crop"):
        raise ValueError("border_mode must be 'pad' or 'crop'.")
    if border_mode == "crop":
        return image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)].copy()
    out_h, out_w = max(0, y2 - y1), max(0, x2 - x1)
    if image.ndim == 2:
        out = np.zeros((out_h, out_w), dtype=image.dtype)
    else:
        out = np.zeros((out_h, out_w, image.shape[2]), dtype=image.dtype)
    sx1, sy1, sx2, sy2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    if sx2 > sx1 and sy2 > sy1:
        out[sy1 - y1:sy2 - y1, sx1 - x1:sx2 - x1] = image[sy1:sy2, sx1:sx2]
    return out


@dataclass
class WaferDieMap:
    """Output of build_die_map().

    ``corner_point`` is the shared grid corner `(x0, y0)`.  Die `(0, 0)` is
    the upper-right die from that corner. Its center is
    `(x0 + pitch_x / 2, y0 - pitch_y / 2)`.

    Important returned fields
    -------------------------
    ``wafer_cx``, ``wafer_cy``, ``wafer_r``
        Wafer center/radius detected from the input image in pixels.
    ``x0``, ``y0``, ``pitch_x``, ``pitch_y``
        The exact float values supplied by the caller. They are never shifted,
        re-detected, or rounded for grid calculation.
    ``dies`` / ``dies_by_index`` / ``get_die(ix, iy)``
        All retained die entries and index-based lookup access.
    ``edge_indices`` / ``edge_index_report``
        Selected edge index list and reason-specific index lists.
    ``aligned_image``
        BGR-normalized original image. This manual-grid module never rotates it.

    Each item in ``dies`` is a dict with:
    ``index``, ``center_px``, ``rect_px``, ``crop_rect_px``, ``real_coord``,
    ``is_edge_partial``, ``is_edge_ring``, ``edge_distance_px``,
    ``is_edge_margin``, and ``is_edge``. If ``with_crops=True`` was used,
    the item additionally contains ``image``.
    """
    wafer_cx: int
    wafer_cy: int
    wafer_r: int
    pitch_x: float
    pitch_y: float
    x0: float
    y0: float
    die_w: float
    die_h: float
    pixel_per_unit: float
    dies: List[Dict[str, Any]] = field(default_factory=list)
    dies_by_index: Dict[Tuple[int, int], Dict[str, Any]] = field(default_factory=dict)
    image_shape: Tuple[int, int] = (0, 0)
    aligned_image: Optional[np.ndarray] = field(default=None, repr=False)
    rotation_deg: float = 0.0
    edge_mode: str = DEFAULT_EDGE_MODE
    edge_clip_margin_px: float = 0.0
    edge_index_margin_px: float = 0.0
    edge_limit_r: float = 0.0
    quadrant_report: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_dies(self) -> int:
        """Number of die entries retained in this map."""
        return len(self.dies)

    def get_die(self, ix: int, iy: int) -> Optional[Dict[str, Any]]:
        """Return one die entry by `(ix, iy)`, or None when not in the map."""
        return self.dies_by_index.get((int(ix), int(iy)))

    @property
    def edge_indices(self) -> List[Tuple[int, int]]:
        """Indices selected by the current edge_mode."""
        return [tuple(d["index"]) for d in self.dies if bool(d.get("is_edge"))]

    @property
    def edge_index_report(self) -> Dict[str, List[Tuple[int, int]]]:
        """Indices split into selected, partial, grid-ring, and margin reasons."""
        return {
            "selected": self.edge_indices,
            "partial": [tuple(d["index"]) for d in self.dies if d["is_edge_partial"]],
            "ring": [tuple(d["index"]) for d in self.dies if d["is_edge_ring"]],
            "margin": [tuple(d["index"]) for d in self.dies if d["is_edge_margin"]],
        }


def _quadrant_report(dies: List[Dict[str, Any]], cx: int, cy: int, radius: int) -> Dict[str, Any]:
    per: Dict[str, Dict[str, Any]] = {}
    for key, x_sign, y_sign in (("TR", 1, -1), ("TL", -1, -1), ("BR", 1, 1), ("BL", -1, 1)):
        distances = [math.hypot(d["center_px"][0] - cx, d["center_px"][1] - cy)
                     for d in dies
                     if (d["center_px"][0] - cx) * x_sign >= 0 and (d["center_px"][1] - cy) * y_sign >= 0]
        per[key] = {"n_dies": len(distances), "coverage": round(max(distances) / radius, 4) if distances else 0.0}
    coverage = [value["coverage"] for value in per.values()]
    return {"per_quadrant": per, "coverage_spread": round(max(coverage) - min(coverage), 4),
            "balanced": bool(min(coverage) > 0.8 and max(coverage) - min(coverage) <= 0.08)}


def build_die_map(image: np.ndarray, corner_point: Tuple[float, float],
                  pitch: Tuple[float, float], *, pixel_per_unit: float = DEFAULT_PIXEL_PER_UNIT,
                  include_edge: bool = True, edge_margin: float = DEFAULT_EDGE_MARGIN,
                  clip_partial_edge: bool = DEFAULT_CLIP_PARTIAL_EDGE,
                  edge_clip_margin_px: float = -1.0, edge_index_margin_px: float = 0.0,
                  edge_mode: str = DEFAULT_EDGE_MODE, with_crops: bool = False,
                  border_mode: str = "pad", offset_x: float = 0.0, offset_y: float = 0.0,
                  margin_x: float = 0.0, margin_y: float = 0.0,
                  bg_threshold: int = 20) -> WaferDieMap:
    """Create a die map from caller-provided float grid parameters.

    Parameters
    ----------
    image:
        Original Gray/BGR/BGRA numpy image. Used only for wafer-center detection
        and optional die crops. No grid, pitch, corner, or angle detection occurs.
    corner_point:
        Float `(x0, y0)` shared grid corner. It is not rounded or shifted.
    pitch:
        Float `(pitch_x, pitch_y)`. Each cell boundary is independently computed
        from these floats, so there is no cumulative rounding drift.

    Returns
    -------
    WaferDieMap
        ``dm.wafer_cx``, ``dm.wafer_cy``, ``dm.wafer_r`` are detected from
        the image. ``dm.x0``, ``dm.y0``, ``dm.pitch_x``, and ``dm.pitch_y``
        preserve the supplied float values exactly.

        ``dm.dies`` is a list of die dictionaries. A die dictionary contains:
        - ``index``: `(ix, iy)` grid index; right is `ix+`, upward is `iy+`.
        - ``center_px``: float die-center `(cx, cy)` in image pixels.
        - ``rect_px``: rounded `(x1, y1, x2, y2)` die rectangle for drawing.
        - ``crop_rect_px``: rectangle after requested crop offset/margin.
        - ``real_coord``: die-center coordinate relative to wafer center.
        - ``is_edge_partial``, ``is_edge_ring``, ``is_edge_margin``,
          ``edge_distance_px``, and final ``is_edge`` flags.
        - ``image``: only present if ``with_crops=True``.

        ``dm.edge_indices`` returns selected `(ix, iy)` indices using the
        current ``edge_mode``. ``dm.edge_index_report`` separately returns
        ``selected``, ``partial``, ``ring``, and ``margin`` index lists.
    """
    bgr = _as_bgr(image)
    try:
        x0, y0 = float(corner_point[0]), float(corner_point[1])
        pitch_x, pitch_y = float(pitch[0]), float(pitch[1])
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("corner_point and pitch must each contain two float values.") from exc
    if not all(math.isfinite(v) for v in (x0, y0, pitch_x, pitch_y)) or pitch_x <= 0 or pitch_y <= 0:
        raise ValueError("corner_point must be finite and pitch_x/pitch_y must be finite positive floats.")
    if not math.isfinite(float(pixel_per_unit)) or float(pixel_per_unit) <= 0:
        raise ValueError("pixel_per_unit must be a positive number.")

    wafer = detect_wafer_center(bgr, bg_threshold=bg_threshold)
    wcx, wcy, wafer_r = wafer["wafer_cx"], wafer["wafer_cy"], wafer["wafer_r"]
    mode = _normalize_edge_mode(edge_mode)
    edge_clip_margin_px = float(edge_clip_margin_px)
    if edge_clip_margin_px < 0:
        edge_clip_margin_px = max(2.0, min(pitch_x, pitch_y) * 0.10)
    edge_clip_margin_px = max(0.0, edge_clip_margin_px)
    edge_index_margin_px = max(0.0, float(edge_index_margin_px))
    center_limit_r = wafer_r * (float(edge_margin) if include_edge else 0.98) - edge_clip_margin_px
    if center_limit_r <= 0:
        raise ValueError("edge_margin and edge_clip_margin_px leave no valid wafer area.")

    max_ix = int(math.ceil(wafer_r / pitch_x)) + 2
    max_iy = int(math.ceil(wafer_r / pitch_y)) + 2
    dies: List[Dict[str, Any]] = []
    by_index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for iy in range(-max_iy, max_iy + 1):
        for ix in range(-max_ix, max_ix + 1):
            # These boundaries use the supplied float pitch independently.
            left_f, right_f = x0 + ix * pitch_x, x0 + (ix + 1) * pitch_x
            top_f, bottom_f = y0 - (iy + 1) * pitch_y, y0 - iy * pitch_y
            center_x, center_y = (left_f + right_f) / 2.0, (top_f + bottom_f) / 2.0
            # Keep true circle-crossing boxes even if their centers are outside.
            if not _rect_intersects_circle(left_f, top_f, right_f, bottom_f,
                                           wcx, wcy, center_limit_r):
                continue
            clearance = _rect_circle_clearance(left_f, top_f, right_f, bottom_f,
                                                wcx, wcy, center_limit_r)
            if clip_partial_edge and _rect_crosses_circle(
                    left_f, top_f, right_f, bottom_f, wcx, wcy, center_limit_r):
                continue
            rect = (int(round(left_f)), int(round(top_f)), int(round(right_f)), int(round(bottom_f)))
            crop_rect = _crop_rect(center_x, center_y, pitch_x, pitch_y,
                                   offset_x, offset_y, margin_x, margin_y)
            entry: Dict[str, Any] = {
                "index": (ix, iy),
                "center_px": (center_x, center_y),
                "rect_px": rect,
                "crop_rect_px": crop_rect,
                "real_coord": ((center_x - wcx) / float(pixel_per_unit), (wcy - center_y) / float(pixel_per_unit)),
                "is_edge_partial": _rect_crosses_circle(
                    left_f, top_f, right_f, bottom_f, wcx, wcy, center_limit_r),
                "is_edge_ring": False,
                "edge_distance_px": round(clearance, 4),
                "is_edge_margin": bool(0.0 <= clearance <= edge_index_margin_px),
                "is_edge": False,
            }
            if with_crops:
                entry["image"] = crop_die(bgr, center_x, center_y, pitch_x, pitch_y,
                                           offset_x=offset_x, offset_y=offset_y,
                                           margin_x=margin_x, margin_y=margin_y,
                                           border_mode=border_mode)
            dies.append(entry)
            by_index[(ix, iy)] = entry

    present = set(by_index)
    for entry in dies:
        ix, iy = entry["index"]
        entry["is_edge_ring"] = any(
            (ix + dx, iy + dy) not in present
            for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
        entry["is_edge"] = _edge_flag(entry["is_edge_partial"], entry["is_edge_ring"],
                                       entry["is_edge_margin"], mode)

    return WaferDieMap(
        wafer_cx=wcx, wafer_cy=wcy, wafer_r=wafer_r,
        pitch_x=pitch_x, pitch_y=pitch_y, x0=x0, y0=y0, die_w=pitch_x, die_h=pitch_y,
        pixel_per_unit=float(pixel_per_unit), dies=dies, dies_by_index=by_index,
        image_shape=bgr.shape[:2], aligned_image=bgr, edge_mode=mode,
        edge_clip_margin_px=edge_clip_margin_px, edge_index_margin_px=edge_index_margin_px,
        edge_limit_r=center_limit_r, quadrant_report=_quadrant_report(dies, wcx, wcy, wafer_r),
    )


def locate_die(die_map: WaferDieMap, point: Optional[Tuple[float, float]] = None,
               bbox: Optional[Tuple[float, float, float, float]] = None, *,
               offset_x: float = 0.0, offset_y: float = 0.0,
               margin_x: float = 0.0, margin_y: float = 0.0) -> Dict[str, Any]:
    """Map a point or BBox to the manual float grid and return die metadata.

    Use exactly one input: ``point=(x, y)`` or ``bbox=(x1, y1, x2, y2)``.
    A BBox is mapped using its center. A grid index is returned even when the
    queried location was clipped out of ``dm.dies`` at the wafer edge.

    Returns
    -------
    dict
        ``input_type``: ``"point"`` or ``"bbox"``.
        ``query_px``: actual queried `(x, y)`; BBox center for BBox input.
        ``die_index``: manual-grid `(ix, iy)` containing the queried point.
        ``die_center_px`` / ``die_rect_px``: computed die center and rectangle.
        ``crop_rect_px``: crop rectangle after requested offset/margin.
        ``real_coord`` / ``real_distance``: query coordinate and distance
        relative to the wafer center in ``pixel_per_unit`` units.
        ``die_real_coord``: die-center coordinate in the same real units.
        ``wafer_center_px`` / ``corner_px``: detected wafer center and the
        caller-provided float grid corner.
        ``is_edge``, ``is_edge_partial``, ``is_edge_ring``,
        ``is_edge_margin``, ``edge_distance_px``, ``edge_mode``: edge result.
        ``in_wafer``: whether the query coordinate is within the original
        detected wafer circle.
    """
    if (point is None) == (bbox is None):
        raise ValueError("Specify exactly one of point or bbox.")
    if bbox is not None:
        x1, y1, x2, y2 = map(float, bbox)
        qx, qy, input_type = (x1 + x2) / 2.0, (y1 + y2) / 2.0, "bbox"
    else:
        qx, qy, input_type = float(point[0]), float(point[1]), "point"
    ix = int(math.floor((qx - die_map.x0) / die_map.pitch_x))
    iy = int(math.floor((die_map.y0 - qy) / die_map.pitch_y))
    left, right = die_map.x0 + ix * die_map.pitch_x, die_map.x0 + (ix + 1) * die_map.pitch_x
    top, bottom = die_map.y0 - (iy + 1) * die_map.pitch_y, die_map.y0 - iy * die_map.pitch_y
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    entry = die_map.get_die(ix, iy)
    clearance = _rect_circle_clearance(left, top, right, bottom,
                                        die_map.wafer_cx, die_map.wafer_cy, die_map.edge_limit_r)
    partial = (bool(entry["is_edge_partial"]) if entry else _rect_crosses_circle(
        left, top, right, bottom, die_map.wafer_cx, die_map.wafer_cy,
        die_map.edge_limit_r))
    ring = bool(entry["is_edge_ring"]) if entry else any(
        (ix + dx, iy + dy) not in die_map.dies_by_index
        for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
    margin = bool(entry["is_edge_margin"]) if entry else bool(0.0 <= clearance <= die_map.edge_index_margin_px)
    return {
        "input_type": input_type,
        "query_px": (qx, qy),
        "die_index": (ix, iy),
        "die_center_px": (center_x, center_y),
        "die_rect_px": (int(round(left)), int(round(top)), int(round(right)), int(round(bottom))),
        "crop_rect_px": _crop_rect(center_x, center_y, die_map.pitch_x, die_map.pitch_y,
                                     offset_x, offset_y, margin_x, margin_y),
        "real_coord": ((qx - die_map.wafer_cx) / die_map.pixel_per_unit,
                       (die_map.wafer_cy - qy) / die_map.pixel_per_unit),
        "real_distance": math.hypot(qx - die_map.wafer_cx, qy - die_map.wafer_cy) / die_map.pixel_per_unit,
        "die_real_coord": ((center_x - die_map.wafer_cx) / die_map.pixel_per_unit,
                           (die_map.wafer_cy - center_y) / die_map.pixel_per_unit),
        "wafer_center_px": (die_map.wafer_cx, die_map.wafer_cy),
        "corner_px": (die_map.x0, die_map.y0),
        "is_edge": _edge_flag(partial, ring, margin, die_map.edge_mode),
        "is_edge_partial": partial,
        "is_edge_ring": ring,
        "edge_distance_px": round(float(entry["edge_distance_px"]) if entry else clearance, 4),
        "is_edge_margin": margin,
        "edge_mode": die_map.edge_mode,
        "in_wafer": bool(math.hypot(qx - die_map.wafer_cx, qy - die_map.wafer_cy) <= die_map.wafer_r),
    }


def render_die_map_overlay(image: np.ndarray, die_map: WaferDieMap) -> np.ndarray:
    """Return a BGR overlay image without writing a file.

    Regular dies are green, current ``is_edge`` dies are red, the effective
    edge circle is cyan, and the detected wafer center is magenta. Save the
    returned ``np.ndarray`` with ``cv2.imwrite(...)`` when needed.
    """
    overlay = _as_bgr(image).copy()
    for die in die_map.dies:
        x1, y1, x2, y2 = die["rect_px"]
        color = (0, 0, 255) if die["is_edge"] else (0, 220, 0)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
    cv2.circle(overlay, (die_map.wafer_cx, die_map.wafer_cy), int(round(die_map.edge_limit_r)), (255, 255, 0), 1)
    cv2.circle(overlay, (die_map.wafer_cx, die_map.wafer_cy), 3, (255, 0, 255), -1)
    return overlay
