"""Regression check for use_manual_grid_wafer_map.py using manual float inputs."""

from pathlib import Path

import cv2

from use_manual_grid_wafer_map import build_die_map, locate_die


CASES = {
    "111.png": {"corner": (625.25, 593.75), "pitch": (76.125, 67.50)},
    "2222.png": {"corner": (627.25, 592.50), "pitch": (76.125, 67.50)},
}


def main() -> None:
    root = Path(__file__).resolve().parent / "Gray_Wafer"
    for filename, manual in CASES.items():
        image = cv2.imread(str(root / filename), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(root / filename)
        dm = build_die_map(
            image,
            corner_point=manual["corner"],
            pitch=manual["pitch"],
            edge_clip_margin_px=8.0,
            edge_index_margin_px=20.0,
            edge_mode="both",
        )
        assert (dm.x0, dm.y0) == manual["corner"]
        assert (dm.pitch_x, dm.pitch_y) == manual["pitch"]
        assert dm.edge_indices == dm.edge_index_report["selected"]
        assert dm.edge_index_report["margin"]
        probe = dm.dies[0]
        located = locate_die(dm, point=probe["center_px"])
        assert located["die_index"] == probe["index"]
        assert located["is_edge"] == probe["is_edge"]
        print({
            "image": filename,
            "wafer_center_radius": (dm.wafer_cx, dm.wafer_cy, dm.wafer_r),
            "corner": (dm.x0, dm.y0),
            "pitch": (dm.pitch_x, dm.pitch_y),
            "dies": dm.num_dies,
            "edge_counts": {key: len(value) for key, value in dm.edge_index_report.items()},
        })


if __name__ == "__main__":
    main()
