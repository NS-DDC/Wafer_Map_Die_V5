from __future__ import annotations

from pathlib import Path

import wafer_die_map_v5_refined as refined


ROOT = Path(__file__).resolve().parent
TEST_IMAGES = [
    ROOT / "Test_Images" / "real_mips_top_p084.png",
    ROOT / "Test_Images" / "real_piper_top_p088.png",
    ROOT / "Test_Images" / "real_casio_top_p092.png",
    ROOT / "Test_Images" / "real_exposed_top_p078.png",
    ROOT / "Test_Images" / "bw_noisy_top_p090_3000.png",
]


def main() -> None:
    print("[Refined Center / Edge Clip Evaluation]")
    for image_path in TEST_IMAGES:
        if not image_path.exists():
            print(f"- {image_path.name}: missing")
            continue

        dm = refined.build_die_map(
            str(image_path),
            include_edge=False,
            clean=False,
        )
        sample = dm.get_die(0, 0) or dm.dies[len(dm.dies) // 2]
        center_shift = (
            sample["center_px"][0] - sample.get("nominal_center_px", sample["center_px"])[0],
            sample["center_px"][1] - sample.get("nominal_center_px", sample["center_px"])[1],
        )
        print(f"- {image_path.name}")
        print(f"  dies={len(dm.dies)} pitch=({dm.pitch_x:.2f}, {dm.pitch_y:.2f})")
        print(f"  origin=({dm.x0}, {dm.y0}) origin_shift={getattr(dm, 'grid_origin_shift_px', (0, 0))}")
        print(f"  die_size=({dm.die_w}, {dm.die_h}) nominal=({dm.nominal_die_w}, {dm.nominal_die_h})")
        print(f"  edge_clip_margin_px={dm.edge_clip_margin_px}")
        print(f"  sample_trim_px={sample.get('street_trim_px', (0, 0, 0, 0))}")
        print(f"  sample_center_shift_px={center_shift}")


if __name__ == "__main__":
    main()
