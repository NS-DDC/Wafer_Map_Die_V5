from __future__ import annotations

"""Render a Korean validation board for the testWafer-only experiment."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "testWafer"
VIS_DIR = ROOT / "Visuals"
SUMMARY_PATH = TEST_DIR / "testwafer_validation.json"
OUT_PATH = VIS_DIR / "testwafer_horizontal_pattern_validation.png"
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

BG = "#08111f"
PANEL = "#101e31"
PANEL_ALT = "#0c1828"
TEXT = "#f4f7fb"
MUTED = "#afc0d8"
GREEN = "#34d399"
CYAN = "#38bdf8"
ORANGE = "#fbbf24"
RED = "#fb7185"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, *, size: int,
         fill: str = TEXT, bold: bool = False, spacing: int = 8) -> None:
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, spacing=spacing)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=24, fill=PANEL, outline="#27415f", width=2)


def paste_crop(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    crop_w, crop_h = int(width * 0.44), int(height * 0.26)
    left = (width - crop_w) // 2
    top = (height - crop_h) // 2
    image = image.crop((left, top, left + crop_w, top + crop_h))
    target_w, target_h = box[2] - box[0], box[3] - box[1]
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    px = box[0] + (target_w - image.width) // 2
    py = box[1] + (target_h - image.height) // 2
    canvas.paste(image, (px, py))


def paste_fit(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(path).convert("RGB")
    target_w, target_h = box[2] - box[0], box[3] - box[1]
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    px = box[0] + (target_w - image.width) // 2
    py = box[1] + (target_h - image.height) // 2
    canvas.paste(image, (px, py))


def main() -> None:
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError("Run evaluate_testwafer_images.py first.")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    reference, horizontal = summary["results"]

    VIS_DIR.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (2000, 1500), BG)
    draw = ImageDraw.Draw(canvas)

    text(draw, (64, 42), "testWafer 전용 검증: 가로 Street Pattern 강화", size=45, bold=True)
    text(
        draw,
        (66, 108),
        "동일한 wafer_1 기반으로 가로 street만 선명하게 만든 뒤, die grid / EDGE clip 판정이 유지되는지 확인",
        size=24,
        fill=MUTED,
    )

    panel(draw, (48, 176, 976, 720))
    text(draw, (80, 208), "A. 실제 이미지 축소본 (가로 간격이 상대적으로 약함)", size=28, bold=True, fill=CYAN)
    paste_crop(canvas, TEST_DIR / reference["image"], (80, 272, 944, 672))

    panel(draw, (1024, 176, 1952, 720))
    text(draw, (1056, 208), "B. 생성 이미지 (실제 row grid에 맞춘 가로 street 강화)", size=28, bold=True, fill=ORANGE)
    paste_crop(canvas, TEST_DIR / horizontal["image"], (1056, 272, 1920, 672))

    panel(draw, (48, 768, 976, 1432))
    text(draw, (80, 800), "A 판정 Overlay: 초록=내부 die / 빨강=EDGE clip", size=27, bold=True)
    paste_fit(canvas, TEST_DIR / reference["overlay"], (100, 860, 924, 1384))

    panel(draw, (1024, 768, 1952, 1432))
    text(draw, (1056, 800), "검증 결과", size=30, bold=True, fill=GREEN)
    text(
        draw,
        (1058, 866),
        f"검출 pitch: X {reference['pitch_x_px']:.0f}px / Y {reference['pitch_y_px']:.0f}px\n"
        f"강화 후 Y pitch: {horizontal['pitch_y_px']:.0f}px  (차이 {summary['pitch_y_difference_px']:.1f}px)\n"
        f"가로 street 대비: {reference['horizontal_street_contrast']:.1f} → "
        f"{horizontal['horizontal_street_contrast']:.1f}  (+{summary['horizontal_contrast_gain']:.1f})\n"
        f"검출 die 수: {reference['num_dies']} → {horizontal['num_dies']}\n"
        f"EDGE die 수: {reference['edge_dies']} → {horizontal['edge_dies']}\n"
        f"EDGE clip margin: {reference['edge_clip_margin_px']}px",
        size=26,
        fill=TEXT,
        spacing=12,
    )
    status = "PASS: 모든 검증 조건 통과" if summary["all_checks_passed"] else "FAIL: 검증 조건 재확인 필요"
    status_color = GREEN if summary["all_checks_passed"] else RED
    draw.rounded_rectangle((1058, 1272, 1918, 1378), radius=18, fill="#122b28")
    text(draw, (1090, 1304), status, size=30, bold=True, fill=status_color)

    canvas.save(OUT_PATH, optimize=True)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
