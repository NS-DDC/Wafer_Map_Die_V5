from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cv2

from wafer_die_map_v5_refined import _refine_grid_origin


ROOT = Path(__file__).resolve().parent
VIS_DIR = ROOT / "Visuals"
SAMPLE_PATH = ROOT.parent / "Sample_Point.png"
OVERLAY_PATH = ROOT / "Test_Images" / "bw_noisy_top_p090_3000_overlay_refined.png"

FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

BG = "#0b1020"
PANEL = "#11182b"
PANEL_ALT = "#0d1424"
TEXT = "#eef2ff"
MUTED = "#aab5d0"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#f59e0b"
CYAN = "#06b6d4"
WHITE = "#f8fafc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def rounded(draw: ImageDraw.ImageDraw, box, *, fill: str, outline: str | None = None,
            width: int = 1, radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def add_text(draw: ImageDraw.ImageDraw, xy, text: str, *, size: int = 24,
             fill: str = TEXT, bold: bool = False, spacing: int = 8) -> None:
    draw.multiline_text(xy, text, font=font(size, bold), fill=fill, spacing=spacing)


def paste_fit(canvas: Image.Image, image_path: Path, box) -> None:
    x1, y1, x2, y2 = box
    img = Image.open(image_path).convert("RGB")
    target_w = x2 - x1
    target_h = y2 - y1
    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    px = x1 + (target_w - img.width) // 2
    py = y1 + (target_h - img.height) // 2
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=20, fill="#0a0f1a", outline="#31405f", width=2)
    canvas.paste(img, (px, py))


def cross(draw: ImageDraw.ImageDraw, x: int, y: int, color: str, label: str) -> None:
    r = 12
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="#081019", width=2)
    draw.line((x - 28, y, x + 28, y), fill=color, width=3)
    draw.line((x, y - 28, x, y + 28), fill=color, width=3)
    add_text(draw, (x + 18, y - 42), label, size=22, fill=color, bold=True)


def build_visual() -> Path:
    VIS_DIR.mkdir(parents=True, exist_ok=True)

    sample_cv = cv2.imread(str(SAMPLE_PATH))
    refined_x, refined_y = _refine_grid_origin(sample_cv, 336, 396, 90, 90)
    current_x, current_y = 336, 396
    shift_x = refined_x - current_x
    shift_y = refined_y - current_y

    canvas = Image.new("RGB", (2000, 1500), BG)
    draw = ImageDraw.Draw(canvas)

    add_text(draw, (60, 42), "Wafer Center / Street Center 보정 로직", size=44, bold=True)
    add_text(
        draw,
        (62, 104),
        "샘플 그림 기준으로 현재 포인트(검정)에서 원하는 포인트(초록) 쪽으로 이동시키는 이유와 실제 반영 로직",
        size=24,
        fill=MUTED,
    )

    rounded(draw, (40, 160, 980, 840), fill=PANEL, outline="#2e3d5f", width=2, radius=30)
    add_text(draw, (72, 192), "1. 사용자가 그린 샘플", size=30, bold=True)
    add_text(draw, (72, 236), "빨강 = die, 흰색 = street, 검정 = 현재 치우친 포인트, 초록 = 원하는 포인트", size=22, fill=MUTED)
    paste_fit(canvas, SAMPLE_PATH, (72, 290, 948, 808))

    rounded(draw, (1020, 160, 1960, 840), fill=PANEL, outline="#2e3d5f", width=2, radius=30)
    add_text(draw, (1052, 192), "2. 보정 결과", size=30, bold=True)
    add_text(draw, (1052, 236), "street 전체 폭의 중심을 다시 잡아 x0, y0 를 보정", size=22, fill=MUTED)

    sample_pil = Image.open(SAMPLE_PATH).convert("RGB")
    overlay = sample_pil.copy()
    od = ImageDraw.Draw(overlay)
    cross(od, current_x, current_y, RED, "현재")
    cross(od, refined_x, refined_y, GREEN, "보정")
    od.line((0, refined_y, overlay.width, refined_y), fill=GREEN, width=2)
    od.line((refined_x, 0, refined_x, overlay.height), fill=GREEN, width=2)
    od.line((0, current_y, overlay.width, current_y), fill=RED, width=2)
    od.line((current_x, 0, current_x, overlay.height), fill=RED, width=2)
    tmp = VIS_DIR / "_tmp_sample_overlay.png"
    overlay.save(tmp)
    paste_fit(canvas, tmp, (1052, 290, 1928, 808))
    tmp.unlink(missing_ok=True)

    add_text(
        draw,
        (1070, 728),
        f"입력 추정값: ({current_x}, {current_y})\n"
        f"보정 결과: ({refined_x}, {refined_y})\n"
        f"이동량: ({shift_x}, {shift_y}) px",
        size=24,
        fill=WHITE,
        bold=True,
    )

    rounded(draw, (40, 890, 640, 1430), fill=PANEL_ALT, outline="#2e3d5f", width=2, radius=28)
    add_text(draw, (72, 924), "방식 1. 실제 street 중심 재탐색", size=28, bold=True, fill=CYAN)
    add_text(
        draw,
        (72, 986),
        "- detect_grid() 가 준 초기 x0, y0 를 그대로 믿지 않음\n"
        "- 중심 근처 ROI 에서 세로/가로 street score profile 생성\n"
        "- 가장 가까운 street band 전체 폭을 찾고 중심으로 재보정\n"
        "- 이번 샘플에서는 y 축이 아래로 밀린 값을 위로 26 px 보정",
        size=23,
        fill=TEXT,
    )

    rounded(draw, (700, 890, 1300, 1430), fill=PANEL_ALT, outline="#2e3d5f", width=2, radius=28)
    add_text(draw, (732, 924), "방식 2. Street-aware crop", size=28, bold=True, fill=YELLOW)
    add_text(
        draw,
        (732, 986),
        "- pitch 크기 셀 전체를 die 로 쓰지 않음\n"
        "- 셀 가장자리의 street 두께를 추정해 실제 die body 만 남김\n"
        "- 결과적으로 center_px / rect_px 가 die body 기준으로 바뀜\n"
        "- nominal_rect_px 는 유지해서 원래 셀 기준도 같이 확인 가능",
        size=23,
        fill=TEXT,
    )

    rounded(draw, (1360, 890, 1960, 1430), fill=PANEL_ALT, outline="#2e3d5f", width=2, radius=28)
    add_text(draw, (1392, 924), "방식 3. EDGE clip 확대", size=28, bold=True, fill=GREEN)
    add_text(
        draw,
        (1392, 986),
        "- wafer 반경을 edge_clip_margin_px 만큼 안쪽으로 축소\n"
        "- partial die / 경계 애매한 die 를 더 공격적으로 제외\n"
        "- refined 모듈에서는 include_edge 와 무관하게 margin 적용\n"
        "- edge 쪽 false positive 를 줄이는 목적",
        size=20,
        fill=TEXT,
    )

    if OVERLAY_PATH.exists():
        rounded(draw, (1460, 1160, 1920, 1400), fill="#09111e", outline="#31405f", width=2, radius=18)
        paste_fit(canvas, OVERLAY_PATH, (1480, 1180, 1900, 1380))
        add_text(draw, (1490, 1386), "실제 noisy wafer 예시 overlay", size=18, fill=MUTED)

    out = VIS_DIR / "refined_center_logic_sample.png"
    canvas.save(out)
    return out


if __name__ == "__main__":
    path = build_visual()
    print(path)
