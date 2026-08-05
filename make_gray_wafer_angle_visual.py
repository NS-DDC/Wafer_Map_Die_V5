from __future__ import annotations

"""Create a Korean visual board for Gray_Wafer angle-correction validation."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
GRAY_DIR = ROOT / "Gray_Wafer"
VIS_DIR = ROOT / "Visuals"
SUMMARY_PATH = GRAY_DIR / "gray_angle_validation.json"
OUT_PATH = VIS_DIR / "gray_wafer_angle_validation.png"
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

BG = "#08111f"
PANEL = "#101e31"
TEXT = "#f4f7fb"
MUTED = "#afc0d8"
CYAN = "#38bdf8"
GREEN = "#34d399"
ORANGE = "#fbbf24"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, *, size: int,
         fill: str = TEXT, bold: bool = False, spacing: int = 7) -> None:
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, spacing=spacing)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=24, fill=PANEL, outline="#27415f", width=2)


def paste_fit(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(path).convert("RGB")
    target_w, target_h = box[2] - box[0], box[3] - box[1]
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    px = box[0] + (target_w - image.width) // 2
    py = box[1] + (target_h - image.height) // 2
    canvas.paste(image, (px, py))


def main() -> None:
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError("Run evaluate_gray_wafer_angles.py first.")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    by_angle = {float(item["input_rotation_deg"]): item for item in summary["results"]}

    VIS_DIR.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (2000, 1500), BG)
    draw = ImageDraw.Draw(canvas)
    text(draw, (62, 42), "Gray_Wafer Angle Correction 검증", size=46, bold=True)
    text(draw, (64, 110), "0.1도부터 1.0도까지 회전한 실제 Gray wafer에서 die-render 보정 성능을 확인", size=24, fill=MUTED)

    panel(draw, (46, 174, 690, 842))
    text(draw, (78, 206), "기준 Gray wafer", size=30, bold=True, fill=CYAN)
    paste_fit(canvas, GRAY_DIR / "Gray.png", (90, 276, 646, 798))

    panel(draw, (730, 174, 1954, 842))
    text(draw, (764, 206), "각도별 보정 결과", size=30, bold=True, fill=GREEN)
    text(draw, (766, 274), "입력      적용 보정      잔여 각도      결과", size=24, bold=True, fill=MUTED)
    y = 330
    for angle in sorted(by_angle):
        item = by_angle[angle]
        status = "PASS" if item["passed"] else "FAIL"
        color = GREEN if item["passed"] else "#fb7185"
        text(
            draw,
            (766, y),
            f"+{angle:.1f}°        {item['applied_correction_deg']:+.4f}°        "
            f"{item['residual_grid_angle_deg']:+.4f}°        {status}",
            size=24,
            fill=color if not item["passed"] else TEXT,
        )
        y += 40
    text(draw, (766, 750), "판정 기준: 잔여 각도 <= 0.12°, 보정 오차 <= 0.12°", size=21, fill=ORANGE)

    selected = (0.1, 0.5, 1.0)
    x_positions = (46, 700, 1354)
    for angle, x in zip(selected, x_positions):
        item = by_angle[angle]
        panel(draw, (x, 890, x + 600, 1446))
        text(draw, (x + 28, 922), f"+{angle:.1f}° 입력 후 보정 overlay", size=25, bold=True)
        overlay = GRAY_DIR / item["aligned_overlay"]
        paste_fit(canvas, overlay, (x + 34, 984, x + 566, 1408))

    canvas.save(OUT_PATH, optimize=True)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
