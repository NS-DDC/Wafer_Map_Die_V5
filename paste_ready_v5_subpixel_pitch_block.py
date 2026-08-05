"""Copy-paste replacement for the V5 pitch-to-die loop.

Usage
-----
In ``wafer_die_map_v5.py`` replace the block that starts with::

    die_w = int(round(pitch_x))

and ends immediately before ``# 3b) EDGE`` with the contents between
``START REPLACEMENT`` and ``END REPLACEMENT`` below.  No import changes are
needed.  All existing build_die_map parameters remain untouched.
"""


REPLACEMENT_BLOCK = r'''
    # ===== START REPLACEMENT: sub-pixel pitch lattice =====
    # Keep pitch/origin as floats.  Only final image boundaries are snapped.
    SUBPIXEL_FIT_RADIUS_RATIO = 0.72
    SUBPIXEL_MAX_PITCH_CHANGE_RATIO = 0.015

    def _round_pixel(value: float) -> int:
        return int(math.floor(float(value) + 0.5))

    def _norm_profile(values: np.ndarray) -> np.ndarray:
        values = values.astype(np.float32)
        lo = float(values.min())
        hi = float(values.max())
        if hi - lo < 1e-6:
            return np.zeros_like(values, dtype=np.float32)
        return (values - lo) / (hi - lo)

    def _street_score_profiles(image_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        col_mean, row_mean = gray.mean(axis=0), gray.mean(axis=1)
        col_std, row_std = gray.std(axis=0), gray.std(axis=1)
        col_score = 0.62 * _norm_profile(col_mean) + 0.38 * _norm_profile(float(col_std.max()) - col_std)
        row_score = 0.62 * _norm_profile(row_mean) + 0.38 * _norm_profile(float(row_std.max()) - row_std)
        return col_score.astype(np.float32), row_score.astype(np.float32)

    def _street_center(profile: np.ndarray, predicted: float, radius: int) -> float:
        lo = max(0, int(round(predicted)) - radius)
        hi = min(len(profile), int(round(predicted)) + radius + 1)
        segment = profile[lo:hi].astype(np.float32)
        if len(segment) < 3:
            return float(predicted)
        peak = float(segment.max())
        base_level = float(np.percentile(segment, 45))
        if peak <= base_level + 1e-6:
            return float(predicted)
        threshold = max(base_level + (peak - base_level) * 0.18,
                        float(np.percentile(segment, 60)))
        above = segment >= threshold
        runs = []
        start = None
        for pos, is_on in enumerate(above):
            if is_on and start is None:
                start = pos
            elif not is_on and start is not None:
                runs.append((start, pos - 1))
                start = None
        if start is not None:
            runs.append((start, len(above) - 1))
        if not runs:
            return float(predicted)
        best = min(
            runs,
            key=lambda run: (
                0.0 if lo + run[0] <= predicted <= lo + run[1]
                else min(abs(predicted - (lo + run[0])), abs(predicted - (lo + run[1]))),
                -(run[1] - run[0] + 1),
            ),
        )
        return float((lo + best[0] + lo + best[1]) / 2.0)

    def _fit_axis(profile: np.ndarray, origin: float, pitch: float, direction: float,
                  center: float) -> Tuple[float, float]:
        max_index = int(math.ceil(wafer_r / pitch)) + 2
        search_radius = max(3, int(round(pitch * 0.34)))
        samples = []
        for index in range(-max_index, max_index + 1):
            predicted = origin + direction * index * pitch
            if not (search_radius <= predicted < len(profile) - search_radius):
                continue
            if abs(predicted - center) > wafer_r * SUBPIXEL_FIT_RADIUS_RATIO:
                continue
            samples.append((index, _street_center(profile, predicted, search_radius)))
        if len(samples) < 5:
            return float(origin), float(pitch)

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
            keep = np.abs(residual - median) <= max(0.8, 3.0 * 1.4826 * mad)

        fitted_pitch = abs(float(slope))
        lower = pitch * (1.0 - SUBPIXEL_MAX_PITCH_CHANGE_RATIO)
        upper = pitch * (1.0 + SUBPIXEL_MAX_PITCH_CHANGE_RATIO)
        if keep.sum() < 5 or not (lower <= fitted_pitch <= upper):
            return float(origin), float(pitch)
        return float(intercept), fitted_pitch

    col_score, row_score = _street_score_profiles(img)
    x0, pitch_x = _fit_axis(col_score, float(x0), float(pitch_x), 1.0, float(wafer_cx))
    y0, pitch_y = _fit_axis(row_score, float(y0), float(pitch_y), -1.0, float(wafer_cy))

    max_ix = int(np.ceil(wafer_r / pitch_x)) + 2
    max_iy = int(np.ceil(wafer_r / pitch_y)) + 2
    margin = edge_margin if include_edge else 0.98
    r_lim_sq = (wafer_r * margin) ** 2

    dies: List[Dict[str, Any]] = []
    dies_by_index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    nominal_widths: List[int] = []
    nominal_heights: List[int] = []

    for iy in range(-max_iy, max_iy + 1):
        top_float = y0 - (iy + 1) * pitch_y
        bottom_float = y0 - iy * pitch_y
        for ix in range(-max_ix, max_ix + 1):
            left_float = x0 + ix * pitch_x
            right_float = x0 + (ix + 1) * pitch_x
            cx_float = (left_float + right_float) / 2.0
            cy_float = (top_float + bottom_float) / 2.0
            dx = cx_float - wafer_cx
            dy = cy_float - wafer_cy
            if dx * dx + dy * dy > r_lim_sq:
                continue

            # Shared float boundaries guarantee neighboring dies tile exactly.
            x_a, x_b = _round_pixel(left_float), _round_pixel(right_float)
            y_a, y_b = _round_pixel(top_float), _round_pixel(bottom_float)
            if x_b <= x_a or y_b <= y_a:
                continue
            cell_w, cell_h = x_b - x_a, y_b - y_a
            cx_d, cy_d = x_a + cell_w // 2, y_a + cell_h // 2
            crop_rect = _crop_rect(cx_d, cy_d, cell_w, cell_h,
                                   offset_x, offset_y, margin_x, margin_y)

            entry: Dict[str, Any] = {
                "index": (ix, iy),
                "nominal_center_float_px": (cx_float, cy_float),
                "center_px": (cx_d, cy_d),
                "rect_px": (x_a, y_a, x_b, y_b),
                "crop_rect_px": crop_rect,
                "real_coord": ((cx_d - wafer_cx) / pixel_per_unit,
                               (wafer_cy - cy_d) / pixel_per_unit),
                "is_edge_partial": _rect_crosses_circle(
                    x_a, y_a, x_b, y_b, wafer_cx, wafer_cy, wafer_r),
                "is_edge_ring": False,
                "is_edge": False,
            }
            if with_crops:
                crop = crop_die(img, cx_d, cy_d, cell_w, cell_h,
                                offset_x=offset_x, offset_y=offset_y,
                                margin_x=margin_x, margin_y=margin_y,
                                border_mode=border_mode)
                if crop is None:
                    continue
                entry["image"] = crop
            nominal_widths.append(cell_w)
            nominal_heights.append(cell_h)
            dies.append(entry)
            dies_by_index[(ix, iy)] = entry

    # WaferDieMap keeps these legacy fields as representative crop dimensions.
    die_w = int(round(np.median(nominal_widths))) if nominal_widths else int(round(pitch_x))
    die_h = int(round(np.median(nominal_heights))) if nominal_heights else int(round(pitch_y))
    # ===== END REPLACEMENT =====
'''
