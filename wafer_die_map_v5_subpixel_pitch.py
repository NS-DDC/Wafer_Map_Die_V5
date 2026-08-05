from __future__ import annotations

"""Sub-pixel lattice wrapper for WaferDieMap V5.

This module keeps pitch as a float for the complete lattice calculation.
Pixel rounding happens only when a raster rectangle is emitted.  Adjacent die
boundaries are snapped from the same float boundary, so a fractional pitch
cannot accumulate a far-edge drift.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

import wafer_die_map_v5 as base
import wafer_die_map_v5_refined as refined


WaferDieMap = base.WaferDieMap
__all__ = list(base.__all__) + ["build_die_map", "locate_die", "fit_subpixel_lattice"]


def _round_pixel(value: float) -> int:
    """Use one explicit half-up conversion only at the image boundary."""
    return int(math.floor(float(value) + 0.5))


def _fit_axis(profile: np.ndarray, origin: float, pitch: float, *, direction: float,
              center: float, radius: float, fit_radius_ratio: float) -> Tuple[float, float, int]:
    """Fit observed street centers to ``origin + index * direction * pitch``."""
    if pitch <= 1.0:
        return float(origin), float(pitch), 0

    max_index = int(math.ceil(radius / pitch)) + 2
    search_radius = max(3, int(round(pitch * 0.34)))
    samples: List[Tuple[int, float]] = []
    fit_radius = radius * fit_radius_ratio
    for index in range(-max_index, max_index + 1):
        predicted = origin + direction * index * pitch
        if not (search_radius <= predicted < len(profile) - search_radius):
            continue
        if abs(predicted - center) > fit_radius:
            continue
        observed = refined._refine_band_center(profile, predicted, search_radius)
        samples.append((index, observed))

    if len(samples) < 5:
        return float(origin), float(pitch), len(samples)

    indexes = np.asarray([item[0] for item in samples], dtype=np.float64)
    observed = np.asarray([item[1] for item in samples], dtype=np.float64)
    keep = np.ones(len(samples), dtype=bool)
    intercept = float(origin)
    slope = direction * float(pitch)
    for _ in range(3):
        if keep.sum() < 5:
            break
        slope, intercept = np.polyfit(indexes[keep], observed[keep], 1)
        residual = observed - (slope * indexes + intercept)
        median = float(np.median(residual[keep]))
        mad = float(np.median(np.abs(residual[keep] - median)))
        tolerance = max(0.8, 3.0 * 1.4826 * mad)
        keep = np.abs(residual - median) <= tolerance

    fitted_pitch = abs(float(slope))
    # A nearby false street must not replace the detected lattice wholesale.
    # Sub-pixel correction is expected to be much smaller than a whole die.
    # Reject a nearby texture period instead of allowing it to bend the grid.
    if keep.sum() < 5 or not (pitch * 0.985 <= fitted_pitch <= pitch * 1.015):
        return float(origin), float(pitch), int(keep.sum())
    return float(intercept), fitted_pitch, int(keep.sum())


def fit_subpixel_lattice(image_bgr: np.ndarray, x0: float, y0: float,
                          pitch_x: float, pitch_y: float,
                          wafer_cx: int, wafer_cy: int, wafer_r: int,
                          *, fit_radius_ratio: float = 0.72) -> Dict[str, float]:
    """Refine x/y pitch and grid origin from many observed street centers."""
    col_score, row_score = refined._local_street_score_profiles(image_bgr)
    x0_fit, pitch_x_fit, x_samples = _fit_axis(
        col_score, float(x0), float(pitch_x), direction=1.0,
        center=float(wafer_cx), radius=float(wafer_r), fit_radius_ratio=fit_radius_ratio)
    y0_fit, pitch_y_fit, y_samples = _fit_axis(
        row_score, float(y0), float(pitch_y), direction=-1.0,
        center=float(wafer_cy), radius=float(wafer_r), fit_radius_ratio=fit_radius_ratio)
    return {
        "x0": x0_fit,
        "y0": y0_fit,
        "pitch_x": pitch_x_fit,
        "pitch_y": pitch_y_fit,
        "x_samples": float(x_samples),
        "y_samples": float(y_samples),
    }


def _rebuild_die_map(seed: WaferDieMap, *, x0: float, y0: float,
                     pitch_x: float, pitch_y: float, pixel_per_unit: int,
                     include_edge: bool, edge_margin: float, with_crops: bool,
                     border_mode: str, offset_x: int, offset_y: int,
                     margin_x: int, margin_y: int, street_aware_crop: bool,
                     edge_mode: str) -> WaferDieMap:
    """Emit one-shot snapped rectangles from the fitted float lattice."""
    image = seed.aligned_image
    if image is None:
        raise RuntimeError("Sub-pixel rebuild requires the aligned wafer image.")
    height, width = image.shape[:2]
    nominal_die_w = _round_pixel(pitch_x)
    nominal_die_h = _round_pixel(pitch_y)
    edge_clip_margin_px = int(getattr(seed, "edge_clip_margin_px", 0))
    max_ix = int(np.ceil(seed.wafer_r / pitch_x)) + 2
    max_iy = int(np.ceil(seed.wafer_r / pitch_y)) + 2
    margin = edge_margin if include_edge else 0.98
    effective_radius = max(0.0, seed.wafer_r * margin - edge_clip_margin_px)
    effective_radius_sq = effective_radius ** 2

    dies: List[Dict[str, Any]] = []
    dies_by_index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    body_widths: List[int] = []
    body_heights: List[int] = []
    for iy in range(-max_iy, max_iy + 1):
        top_float = y0 - (iy + 1) * pitch_y
        bottom_float = y0 - iy * pitch_y
        for ix in range(-max_ix, max_ix + 1):
            left_float = x0 + ix * pitch_x
            right_float = x0 + (ix + 1) * pitch_x
            cx_float = (left_float + right_float) / 2.0
            cy_float = (top_float + bottom_float) / 2.0
            dx = cx_float - seed.wafer_cx
            dy = cy_float - seed.wafer_cy
            if dx * dx + dy * dy > effective_radius_sq:
                continue

            nominal_rect = (
                _round_pixel(left_float),
                _round_pixel(top_float),
                _round_pixel(right_float),
                _round_pixel(bottom_float),
            )
            if nominal_rect[2] <= nominal_rect[0] or nominal_rect[3] <= nominal_rect[1]:
                continue
            nominal_center = (_round_pixel(cx_float), _round_pixel(cy_float))
            if street_aware_crop:
                body_rect, center_px, street_trim_px = refined._estimate_body_geometry(image, nominal_rect)
            else:
                body_rect = nominal_rect
                center_px = nominal_center
                street_trim_px = (0, 0, 0, 0)
            body_w = max(1, body_rect[2] - body_rect[0])
            body_h = max(1, body_rect[3] - body_rect[1])
            cx_use, cy_use = center_px
            crop_rect = base._crop_rect(cx_use, cy_use, body_w, body_h,
                                        offset_x, offset_y, margin_x, margin_y)
            entry: Dict[str, Any] = {
                "index": (ix, iy),
                "nominal_center_float_px": (cx_float, cy_float),
                "nominal_center_px": nominal_center,
                "center_px": center_px,
                "nominal_rect_px": nominal_rect,
                "rect_px": body_rect,
                "street_trim_px": street_trim_px,
                "crop_rect_px": crop_rect,
                "real_coord": (
                    (cx_use - seed.wafer_cx) / pixel_per_unit,
                    (seed.wafer_cy - cy_use) / pixel_per_unit,
                ),
                "is_edge_partial": base._rect_crosses_circle(
                    *nominal_rect, seed.wafer_cx, seed.wafer_cy,
                    max(0, seed.wafer_r - edge_clip_margin_px)),
                "is_edge_ring": False,
                "is_edge": False,
            }
            if with_crops:
                crop = base.crop_die(image, cx_use, cy_use, body_w, body_h,
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
    present = set(dies_by_index)
    for entry in dies:
        ix, iy = entry["index"]
        entry["is_edge_ring"] = any(
            (ix + dx, iy + dy) not in present
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0))
        entry["is_edge"] = base._resolve_edge_flag(
            entry["is_edge_partial"], entry["is_edge_ring"], emode)

    die_map = WaferDieMap(
        wafer_cx=seed.wafer_cx, wafer_cy=seed.wafer_cy, wafer_r=seed.wafer_r,
        pitch_x=float(pitch_x), pitch_y=float(pitch_y), x0=float(x0), y0=float(y0),
        die_w=int(round(np.median(body_widths))) if body_widths else nominal_die_w,
        die_h=int(round(np.median(body_heights))) if body_heights else nominal_die_h,
        pixel_per_unit=pixel_per_unit, dies=dies, dies_by_index=dies_by_index,
        image_shape=(height, width), rotation_deg=seed.rotation_deg,
        aligned_image=image, notch_center_px=seed.notch_center_px,
        die_grid_angle_resid=seed.die_grid_angle_resid,
        angle_verified=seed.angle_verified, angle_confidence=seed.angle_confidence,
        angle_agree=seed.angle_agree, edge_mode=emode,
        quadrant_report=base.validate_quadrant_edges(dies, seed.wafer_cx, seed.wafer_cy, seed.wafer_r),
    )
    die_map.nominal_die_w = nominal_die_w
    die_map.nominal_die_h = nominal_die_h
    die_map.refined_grid_origin = bool(getattr(seed, "refined_grid_origin", True))
    die_map.street_aware_crop = street_aware_crop
    die_map.edge_clip_margin_px = edge_clip_margin_px
    return die_map


def build_die_map(image: Union[str, np.ndarray], *,
                  subpixel_pitch: bool = True, fit_radius_ratio: float = 0.72,
                  pixel_per_unit: int = base.DEFAULT_PIXEL_PER_UNIT,
                  include_edge: bool = True, edge_margin: float = base.DEFAULT_EDGE_MARGIN,
                  with_crops: bool = False, border_mode: str = "pad",
                  offset_x: int = base.DEFAULT_OFFSET_X, offset_y: int = base.DEFAULT_OFFSET_Y,
                  margin_x: int = base.DEFAULT_MARGIN_X, margin_y: int = base.DEFAULT_MARGIN_Y,
                  street_aware_crop: bool = refined.DEFAULT_STREET_AWARE_CROP,
                  edge_mode: str = base.DEFAULT_EDGE_MODE, **kwargs: Any) -> WaferDieMap:
    """Build a map using a globally fitted float pitch and one-shot pixel snapping."""
    seed = refined.build_die_map(
        image, pixel_per_unit=pixel_per_unit, include_edge=include_edge,
        edge_margin=edge_margin, with_crops=False, border_mode=border_mode,
        offset_x=offset_x, offset_y=offset_y, margin_x=margin_x, margin_y=margin_y,
        street_aware_crop=street_aware_crop, edge_mode=edge_mode, **kwargs)
    if not subpixel_pitch or seed.aligned_image is None:
        return seed

    fit = fit_subpixel_lattice(
        seed.aligned_image, seed.x0, seed.y0, seed.pitch_x, seed.pitch_y,
        seed.wafer_cx, seed.wafer_cy, seed.wafer_r, fit_radius_ratio=fit_radius_ratio)
    die_map = _rebuild_die_map(
        seed, x0=fit["x0"], y0=fit["y0"], pitch_x=fit["pitch_x"], pitch_y=fit["pitch_y"],
        pixel_per_unit=pixel_per_unit, include_edge=include_edge, edge_margin=edge_margin,
        with_crops=with_crops, border_mode=border_mode, offset_x=offset_x, offset_y=offset_y,
        margin_x=margin_x, margin_y=margin_y, street_aware_crop=street_aware_crop,
        edge_mode=edge_mode)
    die_map.grid_origin_shift_px = (fit["x0"] - seed.x0, fit["y0"] - seed.y0)
    die_map.subpixel_pitch_fit = {
        "initial_pitch_x": float(seed.pitch_x), "initial_pitch_y": float(seed.pitch_y),
        "fitted_pitch_x": fit["pitch_x"], "fitted_pitch_y": fit["pitch_y"],
        "x_samples": int(fit["x_samples"]), "y_samples": int(fit["y_samples"]),
    }
    return die_map


def locate_die(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Use the refined locator; it already divides by the float map pitch."""
    return refined.locate_die(*args, **kwargs)
