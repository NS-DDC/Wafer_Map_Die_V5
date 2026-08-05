from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

import wafer_die_map_v5 as base


WaferDieMap = base.WaferDieMap

DEFAULT_REFINE_GRID_ORIGIN = True
DEFAULT_STREET_AWARE_CROP = True
DEFAULT_EDGE_CLIP_MARGIN_PX = -1  # <0 => auto from pitch

__all__ = list(base.__all__) + ["build_die_map", "locate_die"]


def _norm_profile(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    lo = float(values.min())
    hi = float(values.max())
    if hi - lo < 1e-6:
        return np.zeros_like(values, dtype=np.float32)
    return (values - lo) / (hi - lo)


def _local_street_score_profiles(image_roi: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """High score means 'more likely street / margin than die body'."""
    if image_roi.ndim == 3:
        gray_roi = cv2.cvtColor(image_roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray_roi = image_roi.astype(np.float32)
    gray_roi = cv2.GaussianBlur(gray_roi, (3, 3), 0)

    col_mean = gray_roi.mean(axis=0)
    row_mean = gray_roi.mean(axis=1)
    col_std = gray_roi.std(axis=0)
    row_std = gray_roi.std(axis=1)

    col_score = 0.62 * _norm_profile(col_mean) + 0.38 * _norm_profile(float(col_std.max()) - col_std)
    row_score = 0.62 * _norm_profile(row_mean) + 0.38 * _norm_profile(float(row_std.max()) - row_std)
    return col_score.astype(np.float32), row_score.astype(np.float32)


def _refine_band_center(profile: np.ndarray, approx_idx: float, search_radius: int) -> float:
    if profile.size == 0:
        return float(approx_idx)
    search_radius = max(4, int(search_radius))
    lo = max(0, int(round(approx_idx)) - search_radius)
    hi = min(len(profile), int(round(approx_idx)) + search_radius + 1)
    if hi <= lo + 1:
        return float(np.clip(approx_idx, 0, len(profile) - 1))

    seg = profile[lo:hi].astype(np.float32)
    peak_val = float(seg.max())
    base_level = float(np.percentile(seg, 45))
    thr = max(base_level + (peak_val - base_level) * 0.18,
              float(np.percentile(seg, 60)))
    if peak_val <= base_level + 1e-6:
        return float(np.clip(approx_idx, 0, len(profile) - 1))

    mask = seg >= thr
    runs: List[Tuple[int, int]] = []
    start = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    if not runs:
        return float(np.clip(approx_idx, 0, len(profile) - 1))

    best_run: Optional[Tuple[int, int]] = None
    best_key: Optional[Tuple[float, int, float]] = None
    for start, end in runs:
        abs_start = lo + start
        abs_end = lo + end
        if abs_start <= approx_idx <= abs_end:
            dist = 0.0
        else:
            dist = min(abs(approx_idx - abs_start), abs(approx_idx - abs_end))
        width = abs_end - abs_start + 1
        strength = float(seg[start:end + 1].mean())
        key = (dist, -width, -strength)
        if best_key is None or key < best_key:
            best_key = key
            best_run = (start, end)

    assert best_run is not None
    start, end = best_run
    return float((lo + start + lo + end) / 2.0)


def _edge_half_width(profile: np.ndarray, side: str, max_width: int) -> int:
    if profile.size < 6:
        return 0
    max_width = max(1, min(int(max_width), len(profile) // 2 - 1))
    if max_width <= 0:
        return 0

    smooth = base._smooth_projection(profile.astype(np.float32), max(3, min(13, max_width // 2 * 2 + 1)))
    if side in ("left", "top"):
        edge_seg = smooth[:max_width]
    elif side in ("right", "bottom"):
        edge_seg = smooth[-max_width:][::-1]
    else:
        raise ValueError(f"Unknown side: {side!r}")

    inner = smooth[max_width:len(smooth) - max_width] if len(smooth) > max_width * 2 + 4 else smooth
    base_level = float(np.percentile(inner, 50))
    peak = float(edge_seg.max())
    if peak <= base_level + 0.03:
        return 0

    thr = base_level + (peak - base_level) * 0.52
    width = 0
    for value in edge_seg:
        if float(value) < thr:
            break
        width += 1
    return int(width)


def _estimate_body_geometry(image_bgr: np.ndarray,
                            nominal_rect: Tuple[int, int, int, int],
                            max_trim_ratio: float = 0.30
                            ) -> Tuple[Tuple[int, int, int, int], Tuple[int, int], Tuple[int, int, int, int]]:
    """Trim street margins from a pitch-sized cell and return die-body geometry."""
    x1, y1, x2, y2 = nominal_rect
    H, W = image_bgr.shape[:2]
    ix1, iy1 = max(0, x1), max(0, y1)
    ix2, iy2 = min(W, x2), min(H, y2)
    if ix2 <= ix1 + 4 or iy2 <= iy1 + 4:
        cx = int(round((x1 + x2) / 2.0))
        cy = int(round((y1 + y2) / 2.0))
        return nominal_rect, (cx, cy), (0, 0, 0, 0)

    roi = image_bgr[iy1:iy2, ix1:ix2]
    col_score, row_score = _local_street_score_profiles(roi)
    max_trim_x = max(1, int(round((ix2 - ix1) * max_trim_ratio)))
    max_trim_y = max(1, int(round((iy2 - iy1) * max_trim_ratio)))

    left = _edge_half_width(col_score, "left", max_trim_x)
    right = _edge_half_width(col_score, "right", max_trim_x)
    top = _edge_half_width(row_score, "top", max_trim_y)
    bottom = _edge_half_width(row_score, "bottom", max_trim_y)

    body_x1 = min(ix2 - 2, ix1 + left)
    body_x2 = max(body_x1 + 2, ix2 - right)
    body_y1 = min(iy2 - 2, iy1 + top)
    body_y2 = max(body_y1 + 2, iy2 - bottom)

    cx = int(round((body_x1 + body_x2) / 2.0))
    cy = int(round((body_y1 + body_y2) / 2.0))
    return (body_x1, body_y1, body_x2, body_y2), (cx, cy), (left, top, right, bottom)


def _refine_grid_origin(image_bgr: np.ndarray,
                        x0: int, y0: int,
                        pitch_x: float, pitch_y: float
                        ) -> Tuple[int, int]:
    H, W = image_bgr.shape[:2]
    half_x = max(12, int(round(pitch_x * 1.2)))
    half_y = max(12, int(round(pitch_y * 1.2)))
    rx1 = max(0, x0 - half_x)
    rx2 = min(W, x0 + half_x + 1)
    ry1 = max(0, y0 - half_y)
    ry2 = min(H, y0 + half_y + 1)
    roi = image_bgr[ry1:ry2, rx1:rx2]
    if roi.size == 0:
        return x0, y0

    col_score, row_score = _local_street_score_profiles(roi)
    local_x = _refine_band_center(col_score, x0 - rx1, max(8, int(round(pitch_x * 0.55))))
    local_y = _refine_band_center(row_score, y0 - ry1, max(8, int(round(pitch_y * 0.55))))
    return int(round(rx1 + local_x)), int(round(ry1 + local_y))


def build_die_map(image: Union[str, Path, np.ndarray],
                  *,
                  grid_method: str = base.DEFAULT_GRID_METHOD,
                  pixel_per_unit: int = base.DEFAULT_PIXEL_PER_UNIT,
                  include_edge: bool = True,
                  edge_margin: float = base.DEFAULT_EDGE_MARGIN,
                  die_template_path: Optional[str] = None,
                  with_crops: bool = False,
                  border_mode: str = "pad",
                  offset_x: int = base.DEFAULT_OFFSET_X,
                  offset_y: int = base.DEFAULT_OFFSET_Y,
                  margin_x: int = base.DEFAULT_MARGIN_X,
                  margin_y: int = base.DEFAULT_MARGIN_Y,
                  refine_grid_origin: bool = DEFAULT_REFINE_GRID_ORIGIN,
                  street_aware_crop: bool = DEFAULT_STREET_AWARE_CROP,
                  edge_clip_margin_px: int = DEFAULT_EDGE_CLIP_MARGIN_PX,
                  notch_align: bool = base.DEFAULT_NOTCH_ALIGN,
                  notch_ref_deg: float = base.DEFAULT_NOTCH_REF_DEG,
                  angle_align_method: str = base.DEFAULT_ANGLE_ALIGN_METHOD,
                  edge_mode: str = base.DEFAULT_EDGE_MODE,
                  clean: bool = base.DEFAULT_CLEAN_WAFER,
                  notch_sector_deg: float = base.DEFAULT_NOTCH_SECTOR_DEG,
                  verify_angle: bool = True,
                  verify_tol_deg: float = base.DEFAULT_VERIFY_TOL_DEG) -> WaferDieMap:
    """Refined wrapper around WaferDieMap V5.

    Main differences from the base version:
    - `center_px` follows the die body center after trimming visible street margins.
    - `rect_px` follows the die body rect, while `nominal_rect_px` preserves the pitch-sized cell.
    - `edge_clip_margin_px` expands EDGE classification by shrinking the effective wafer radius.
    """
    img = base._load_bgr(image)
    if clean:
        img = base.clean_wafer(img, in_place=not isinstance(image, np.ndarray))

    rotation_deg = 0.0
    angle_confidence = 1.0
    angle_agree = True
    align_method = angle_align_method.lower().replace("-", "_").strip()
    if notch_align:
        if align_method in ("die_render", "die", "render", "grid_render"):
            img, rotation_deg, info = base.align_wafer_by_die_render(
                img, grid_method=grid_method, return_info=True)
            angle_confidence = float(info.get("confidence", 1.0))
            angle_agree = bool(info.get("agree", False))
        elif align_method == "notch":
            img, rotation_deg = base.align_wafer_by_notch(img, notch_ref_deg=notch_ref_deg)
        elif align_method in ("vertical_line", "longest_vertical_line", "line"):
            img, rotation_deg = base.align_wafer_by_vertical_line(img)
        elif align_method in ("none", "off", "false"):
            pass
        else:
            raise ValueError(
                "angle_align_method must be 'die_render', 'notch', "
                "'vertical_line', or 'none'.")

    H, W = img.shape[:2]
    wafer_cx, wafer_cy, wafer_r = base.detect_wafer(img)

    notch_center_px = None
    notch_resid = 0.0
    nres = base.detect_notch(
        img, wafer_cx, wafer_cy, wafer_r,
        notch_ref_deg=notch_ref_deg, sector_deg=notch_sector_deg)
    if nres is not None:
        notch_resid, notch_center_px = nres

    die_grid_angle_resid = 0.0
    angle_verified = False
    if verify_angle:
        die_grid_angle_resid = base.measure_die_grid_angle(img, wafer_cx, wafer_cy, wafer_r)
        if align_method == "notch":
            angle_verified = bool(abs(die_grid_angle_resid - notch_resid) <= verify_tol_deg
                                  and abs(die_grid_angle_resid) <= verify_tol_deg)
        else:
            angle_verified = bool(abs(die_grid_angle_resid) <= verify_tol_deg)

    die_template_bgr = None
    if die_template_path is not None:
        die_template_bgr = cv2.imread(str(die_template_path), cv2.IMREAD_COLOR)
        if die_template_bgr is None:
            raise FileNotFoundError(str(die_template_path))

    try:
        pitch_x, pitch_y, x0, y0 = base.detect_grid(
            img, wafer_cx, wafer_cy, wafer_r,
            method=grid_method, die_template_bgr=die_template_bgr)
    except RuntimeError:
        fallback_method = "std" if str(grid_method).lower() == "corner" else "corner"
        pitch_x, pitch_y, x0, y0 = base.detect_grid(
            img, wafer_cx, wafer_cy, wafer_r,
            method=fallback_method, die_template_bgr=die_template_bgr)
    x0_raw, y0_raw = x0, y0
    if refine_grid_origin:
        x0, y0 = _refine_grid_origin(img, x0, y0, pitch_x, pitch_y)

    nominal_die_w = int(round(pitch_x))
    nominal_die_h = int(round(pitch_y))
    if edge_clip_margin_px < 0:
        edge_clip_margin_px = max(2, int(round(min(nominal_die_w, nominal_die_h) * 0.10)))
    else:
        edge_clip_margin_px = max(0, int(edge_clip_margin_px))

    max_ix = int(np.ceil(wafer_r / pitch_x)) + 2
    max_iy = int(np.ceil(wafer_r / pitch_y)) + 2
    margin = edge_margin if include_edge else 0.98
    r_lim = max(0.0, wafer_r * margin - float(edge_clip_margin_px))
    r_lim_sq = r_lim ** 2

    dies: List[Dict[str, Any]] = []
    dies_by_index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    body_widths: List[int] = []
    body_heights: List[int] = []

    for iy in range(-max_iy, max_iy + 1):
        for ix in range(-max_ix, max_ix + 1):
            cx_nom = int(round(x0 + ix * pitch_x + pitch_x / 2))
            cy_nom = int(round(y0 - iy * pitch_y - pitch_y / 2))
            dx = cx_nom - wafer_cx
            dy = cy_nom - wafer_cy
            if dx * dx + dy * dy > r_lim_sq:
                continue

            nominal_rect = (
                cx_nom - nominal_die_w // 2,
                cy_nom - nominal_die_h // 2,
                cx_nom - nominal_die_w // 2 + nominal_die_w,
                cy_nom - nominal_die_h // 2 + nominal_die_h,
            )
            if street_aware_crop:
                body_rect, (cx_use, cy_use), street_trim_px = _estimate_body_geometry(img, nominal_rect)
            else:
                body_rect = nominal_rect
                cx_use, cy_use = cx_nom, cy_nom
                street_trim_px = (0, 0, 0, 0)

            body_w = max(1, body_rect[2] - body_rect[0])
            body_h = max(1, body_rect[3] - body_rect[1])
            crop_rect = base._crop_rect(cx_use, cy_use, body_w, body_h,
                                        offset_x, offset_y, margin_x, margin_y)

            entry: Dict[str, Any] = {
                "index": (ix, iy),
                "nominal_center_px": (cx_nom, cy_nom),
                "center_px": (cx_use, cy_use),
                "nominal_rect_px": nominal_rect,
                "rect_px": body_rect,
                "street_trim_px": street_trim_px,
                "crop_rect_px": crop_rect,
                "real_coord": (
                    (cx_use - wafer_cx) / pixel_per_unit,
                    (wafer_cy - cy_use) / pixel_per_unit,
                ),
                "is_edge_partial": base._rect_crosses_circle(
                    nominal_rect[0], nominal_rect[1], nominal_rect[2], nominal_rect[3],
                    wafer_cx, wafer_cy, max(0, wafer_r - edge_clip_margin_px)),
                "is_edge_ring": False,
                "is_edge": False,
            }

            if with_crops:
                crop = base.crop_die(
                    img, cx_use, cy_use, body_w, body_h,
                    offset_x=offset_x, offset_y=offset_y,
                    margin_x=margin_x, margin_y=margin_y,
                    border_mode=border_mode)
                if crop is None:
                    continue
                entry["image"] = crop

            body_widths.append(body_w)
            body_heights.append(body_h)
            dies.append(entry)
            dies_by_index[(ix, iy)] = entry

    emode = base._normalize_edge_mode(edge_mode)
    present = set(dies_by_index.keys())
    for d in dies:
        dix, diy = d["index"]
        ring = any((dix + dxn, diy + dyn) not in present
                   for dxn in (-1, 0, 1) for dyn in (-1, 0, 1)
                   if not (dxn == 0 and dyn == 0))
        d["is_edge_ring"] = bool(ring)
        d["is_edge"] = base._resolve_edge_flag(d["is_edge_partial"], d["is_edge_ring"], emode)

    die_w = int(round(np.median(body_widths))) if body_widths else nominal_die_w
    die_h = int(round(np.median(body_heights))) if body_heights else nominal_die_h
    quadrant_report = base.validate_quadrant_edges(dies, wafer_cx, wafer_cy, wafer_r)

    die_map = WaferDieMap(
        wafer_cx=wafer_cx,
        wafer_cy=wafer_cy,
        wafer_r=wafer_r,
        pitch_x=pitch_x,
        pitch_y=pitch_y,
        x0=x0,
        y0=y0,
        die_w=die_w,
        die_h=die_h,
        pixel_per_unit=pixel_per_unit,
        dies=dies,
        dies_by_index=dies_by_index,
        image_shape=(H, W),
        rotation_deg=rotation_deg,
        aligned_image=img,
        notch_center_px=notch_center_px,
        die_grid_angle_resid=die_grid_angle_resid,
        angle_verified=angle_verified,
        angle_confidence=angle_confidence,
        angle_agree=angle_agree,
        edge_mode=emode,
        quadrant_report=quadrant_report,
    )
    die_map.nominal_die_w = nominal_die_w
    die_map.nominal_die_h = nominal_die_h
    die_map.refined_grid_origin = bool(refine_grid_origin)
    die_map.street_aware_crop = bool(street_aware_crop)
    die_map.edge_clip_margin_px = int(edge_clip_margin_px)
    die_map.grid_origin_shift_px = (int(x0 - x0_raw), int(y0 - y0_raw))
    return die_map


def locate_die(die_map: WaferDieMap,
               point: Optional[Tuple[float, float]] = None,
               bbox: Optional[Tuple[float, float, float, float]] = None,
               *,
               offset_x: int = base.DEFAULT_OFFSET_X,
               offset_y: int = base.DEFAULT_OFFSET_Y,
               margin_x: int = base.DEFAULT_MARGIN_X,
               margin_y: int = base.DEFAULT_MARGIN_Y
               ) -> Dict[str, Any]:
    if (point is None) == (bbox is None):
        raise ValueError("point 또는 bbox 중 하나만 지정해야 합니다.")

    if bbox is not None:
        x1, y1, x2, y2 = bbox
        qx = (float(x1) + float(x2)) / 2.0
        qy = (float(y1) + float(y2)) / 2.0
        input_type = "bbox"
    else:
        qx, qy = float(point[0]), float(point[1])
        input_type = "point"

    ix = int(math.floor((qx - die_map.x0) / die_map.pitch_x))
    iy = int(math.floor((die_map.y0 - qy) / die_map.pitch_y))

    entry = die_map.get_die(ix, iy)
    nominal_die_w = int(getattr(die_map, "nominal_die_w", die_map.die_w))
    nominal_die_h = int(getattr(die_map, "nominal_die_h", die_map.die_h))
    edge_clip_margin_px = int(getattr(die_map, "edge_clip_margin_px", 0))
    street_aware_crop = bool(getattr(die_map, "street_aware_crop", False))

    if entry is not None:
        cx_nom, cy_nom = entry.get("nominal_center_px", entry["center_px"])
        cx_d, cy_d = entry["center_px"]
        nominal_rect = entry.get("nominal_rect_px", entry["rect_px"])
        body_rect = entry["rect_px"]
        street_trim_px = entry.get("street_trim_px", (0, 0, 0, 0))
        is_edge_partial = bool(entry.get("is_edge_partial", entry.get("is_edge", False)))
        is_edge_ring = bool(entry.get("is_edge_ring", False))
    else:
        cx_nom = int(round(die_map.x0 + ix * die_map.pitch_x + die_map.pitch_x / 2))
        cy_nom = int(round(die_map.y0 - iy * die_map.pitch_y - die_map.pitch_y / 2))
        nominal_rect = (
            cx_nom - nominal_die_w // 2,
            cy_nom - nominal_die_h // 2,
            cx_nom - nominal_die_w // 2 + nominal_die_w,
            cy_nom - nominal_die_h // 2 + nominal_die_h,
        )
        if street_aware_crop and die_map.aligned_image is not None:
            body_rect, (cx_d, cy_d), street_trim_px = _estimate_body_geometry(die_map.aligned_image, nominal_rect)
        else:
            body_rect = nominal_rect
            cx_d, cy_d = cx_nom, cy_nom
            street_trim_px = (0, 0, 0, 0)
        is_edge_partial = base._rect_crosses_circle(
            nominal_rect[0], nominal_rect[1], nominal_rect[2], nominal_rect[3],
            die_map.wafer_cx, die_map.wafer_cy, max(0, die_map.wafer_r - edge_clip_margin_px))
        is_edge_ring = any(
            (ix + dxn, iy + dyn) not in die_map.dies_by_index
            for dxn in (-1, 0, 1) for dyn in (-1, 0, 1)
            if not (dxn == 0 and dyn == 0))

    body_w = max(1, body_rect[2] - body_rect[0])
    body_h = max(1, body_rect[3] - body_rect[1])
    crop_rect = base._crop_rect(cx_d, cy_d, body_w, body_h, offset_x, offset_y, margin_x, margin_y)
    emode = base._normalize_edge_mode(getattr(die_map, "edge_mode", base.DEFAULT_EDGE_MODE))
    is_edge = base._resolve_edge_flag(is_edge_partial, is_edge_ring, emode)

    rx = (qx - die_map.wafer_cx) / die_map.pixel_per_unit
    ry = (die_map.wafer_cy - qy) / die_map.pixel_per_unit
    drx = (cx_d - die_map.wafer_cx) / die_map.pixel_per_unit
    dry = (die_map.wafer_cy - cy_d) / die_map.pixel_per_unit
    in_wafer = ((qx - die_map.wafer_cx) ** 2 + (qy - die_map.wafer_cy) ** 2
                <= die_map.wafer_r ** 2)

    return {
        "input_type": input_type,
        "query_px": (qx, qy),
        "die_index": (ix, iy),
        "die_center_px": (cx_d, cy_d),
        "die_nominal_center_px": (cx_nom, cy_nom),
        "die_rect_px": body_rect,
        "die_nominal_rect_px": nominal_rect,
        "street_trim_px": street_trim_px,
        "crop_rect_px": crop_rect,
        "real_coord": (rx, ry),
        "real_distance": math.hypot(rx, ry),
        "die_real_coord": (drx, dry),
        "wafer_center_px": (die_map.wafer_cx, die_map.wafer_cy),
        "corner_px": (die_map.x0, die_map.y0),
        "grid_origin_shift_px": tuple(getattr(die_map, "grid_origin_shift_px", (0, 0))),
        "is_edge": is_edge,
        "is_edge_partial": is_edge_partial,
        "is_edge_ring": is_edge_ring,
        "edge_mode": emode,
        "in_wafer": bool(in_wafer),
    }
