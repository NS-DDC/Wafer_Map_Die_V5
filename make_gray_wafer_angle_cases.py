from __future__ import annotations

"""Create positive 0.1 to 1.0 degree rotation cases from Gray_Wafer/Gray.png."""

import json
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parent
GRAY_DIR = ROOT / "Gray_Wafer"
SOURCE_PATH = GRAY_DIR / "Gray.png"
CASE_DIR = GRAY_DIR / "angle_cases"
MANIFEST_PATH = GRAY_DIR / "gray_angle_cases_manifest.json"
ANGLES_DEG = tuple(round(step / 10.0, 1) for step in range(1, 11))


def case_name(angle_deg: float) -> str:
    angle_label = f"{angle_deg:.1f}".replace(".", "_")
    return f"gray_rot_p{angle_label}deg.png"


def rotate_keep_size(image, angle_deg: float):
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle_deg, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )


def main() -> None:
    source = cv2.imread(str(SOURCE_PATH), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(SOURCE_PATH)

    CASE_DIR.mkdir(parents=True, exist_ok=True)
    cases = []
    for angle_deg in ANGLES_DEG:
        out_path = CASE_DIR / case_name(angle_deg)
        rotated = rotate_keep_size(source, angle_deg)
        if not cv2.imwrite(str(out_path), rotated, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
            raise RuntimeError(f"Could not write: {out_path}")
        cases.append({"input_rotation_deg": angle_deg, "image": out_path.name})

    manifest = {
        "source": SOURCE_PATH.name,
        "rotation_direction": "positive / counter-clockwise in OpenCV",
        "cases": cases,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
