from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
VIS_DIR = ROOT / "Visuals"
ASSET_DIR = VIS_DIR / "assets"

W, H = 1800, 2200
BG = "#0b1020"
PANEL = "#121a2f"
PANEL_INNER = "#0c1324"
BORDER = "#31405f"
TEXT = "#edf2ff"
MUTED = "#a8b3cf"
ACCENT = "#4f46e5"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#f59e0b"
CYAN = "#06b6d4"

FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=None, width: int = 1, radius: int = 28) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def add_text(
    draw: ImageDraw.ImageDraw,
    xy,
    text: str,
    *,
    size: int = 26,
    fill: str = TEXT,
    bold: bool = False,
    spacing: int = 8,
) -> None:
    draw.multiline_text(xy, text, font=font(size, bold), fill=fill, spacing=spacing)


def paste_fit(canvas: Image.Image, image_path: Path, box, *, border: str = "#24304d") -> None:
    x1, y1, x2, y2 = box
    img = Image.open(image_path).convert("RGB")
    w = x2 - x1
    h = y2 - y1
    img.thumbnail((w, h), Image.Resampling.LANCZOS)
    px = x1 + (w - img.width) // 2
    py = y1 + (h - img.height) // 2
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=18, fill="#0a0f1a", outline=border, width=2)
    canvas.paste(img, (px, py))


def arrow(draw: ImageDraw.ImageDraw, p1, p2, *, color: str = MUTED, width: int = 6) -> None:
    x1, y1 = p1
    x2, y2 = p2
    draw.line([p1, p2], fill=color, width=width)
    if abs(x2 - x1) > abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        draw.polygon(
            [(x2, y2), (x2 - 22 * direction, y2 - 12), (x2 - 22 * direction, y2 + 12)],
            fill=color,
        )
    else:
        direction = 1 if y2 > y1 else -1
        draw.polygon(
            [(x2, y2), (x2 - 12, y2 - 22 * direction), (x2 + 12, y2 - 22 * direction)],
            fill=color,
        )


def step_tag(draw: ImageDraw.ImageDraw, box, label: str, fill: str) -> None:
    rounded(draw, box, fill=fill, radius=18)
    add_text(draw, (box[0] + 18, box[1] + 8), label, size=24, bold=True)


def info_panel(draw: ImageDraw.ImageDraw, box, title: str, body: str) -> None:
    rounded(draw, box, fill=PANEL_INNER, outline="#384766", width=2, radius=22)
    add_text(draw, (box[0] + 30, box[1] + 32), title, size=22, bold=True)
    add_text(draw, (box[0] + 30, box[1] + 84), body, size=21, fill=TEXT, spacing=10)


def build_generator_board() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    add_text(draw, (70, 48), "상세 로직 1: 흑백 고노이즈 Wafer 생성기", size=46, bold=True)
    add_text(draw, (72, 106), "대상 파일: paste_ready_generate_bw_noisy_wafer.py", size=24, fill=MUTED)
    rounded(draw, (50, 150, 1750, 2140), fill="#0f162b", outline="#26314e", width=2, radius=34)

    rounded(draw, (80, 190, 840, 760), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 214, 266, 258), "STEP 1", ACCENT)
    add_text(draw, (292, 214), "소스 die -> 반복 가능한 타일 텍스처", size=28, bold=True)
    add_text(
        draw,
        (104, 282),
        "먼저 die 사진에서 쓸 만한 중심 영역만 crop 합니다.\n"
        "그 다음 grayscale, equalizeHist, resize(256x256), blur 를 거쳐\n"
        "여러 번 붙여도 어색하지 않은 texture 로 바꿉니다.",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "source_die_crop.png", (110, 390, 430, 710))
    paste_fit(img, ASSET_DIR / "source_die_gray_texture.png", (490, 390, 810, 710))
    add_text(draw, (142, 724), "예시 A. 원본 die crop", size=22, fill="#d9e3ff")
    add_text(draw, (494, 724), "예시 B. 생성용 gray texture", size=22, fill="#d9e3ff")
    arrow(draw, (440, 550), (480, 550), color=CYAN)

    rounded(draw, (910, 190, 1720, 760), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (934, 214, 1096, 258), "STEP 2", ACCENT)
    add_text(draw, (1122, 214), "Wafer 위에 die 를 촘촘하게 배치", size=28, bold=True)
    add_text(
        draw,
        (934, 282),
        "핵심 규칙\n"
        "- out_size = 3000\n"
        "- pitch = 90\n"
        "- gap = 1 px\n"
        "- die_side = pitch - gap\n"
        "- full_die_inside_circle(...) 인 경우만 사용",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "wafer_pre_noise_zoom.png", (980, 430, 1650, 720))
    add_text(
        draw,
        (988, 730),
        "노이즈 전 확대 예시: 간격은 거의 1px 이고, 가장자리 partial die 는 제외됨",
        size=21,
        fill="#d9e3ff",
    )
    arrow(draw, (840, 475), (910, 475))
    arrow(draw, (840, 610), (910, 610))

    rounded(draw, (80, 820, 1720, 1390), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 844, 266, 888), "STEP 3", RED)
    add_text(draw, (292, 844), "배치가 끝난 뒤 street 노이즈를 강하게 추가", size=28, bold=True)
    add_text(
        draw,
        (104, 910),
        "add_street_noise() 에서 wafer/street 영역에 여러 종류의 방해 요소를 누적합니다.\n"
        "즉, die 패턴은 유지하되 경계 읽기는 어렵게 만드는 단계입니다.",
        size=24,
        fill=MUTED,
    )
    add_text(
        draw,
        (104, 992),
        "- Global gaussian wobble\n"
        "- Salt & pepper speckles\n"
        "- Scratch line\n"
        "- Blotchy islands",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "wafer_pre_noise_zoom.png", (120, 1030, 620, 1340))
    paste_fit(img, ASSET_DIR / "wafer_post_noise_zoom.png", (720, 1030, 1220, 1340))
    add_text(draw, (222, 1350), "Before noise", size=24, fill="#d9e3ff", bold=True)
    add_text(draw, (838, 1350), "After noise", size=24, fill="#d9e3ff", bold=True)
    arrow(draw, (630, 1185), (705, 1185), color=YELLOW)
    info_panel(
        draw,
        (1280, 1020, 1680, 1345),
        "눈으로 보면 바뀌는 점",
        "- street 밝기가 균일하지 않음\n"
        "- 긁힘, 얼룩, 점 같은 요소가 생김\n"
        "- die 경계가 전보다 덜 또렷해짐\n"
        "- 완전 랜덤이 아니라 wafer 같은 질감 유지",
    )

    rounded(draw, (80, 1450, 1720, 2060), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 1474, 266, 1518), "STEP 4", GREEN)
    add_text(draw, (292, 1474), "외곽선 추가 -> 회전 -> 최종 PNG 저장", size=28, bold=True)
    add_text(
        draw,
        (104, 1540),
        "마지막에 wafer outline 을 그리고 rotation_deg = -1.10 을 적용합니다.\n"
        "이 결과가 검출기 스트레스 테스트용 grayscale wafer 이미지가 됩니다.",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "wafer_post_noise_full.png", (120, 1630, 760, 2010))
    info_panel(
        draw,
        (860, 1610, 1670, 2015),
        "최종 출력 특징",
        "1. 3000 x 3000 grayscale\n"
        "2. 위에서 본 2D wafer 형태\n"
        "3. Die 간격은 약 1 px\n"
        "4. 가장자리에 partial die 없음\n"
        "5. 내부와 street 에 강한 노이즈 포함\n"
        "6. seed 값으로 재현 가능",
    )

    img.save(VIS_DIR / "bw_noisy_generation_logic_korean.png")


def build_evaluator_board() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    add_text(draw, (70, 48), "상세 로직 2: 흑백 고노이즈 Wafer 판정기", size=46, bold=True)
    add_text(draw, (72, 106), "대상 파일: use_gray_wafer_die_particle.py", size=24, fill=MUTED)
    rounded(draw, (50, 150, 1750, 2140), fill="#0f162b", outline="#26314e", width=2, radius=34)

    rounded(draw, (80, 190, 840, 920), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 214, 266, 258), "STEP 1", ACCENT)
    add_text(draw, (292, 214), "Noisy wafer 이미지를 build_die_map() 에 넣음", size=28, bold=True)
    add_text(
        draw,
        (104, 282),
        "평가기 스크립트는 wafer PNG 를 읽은 뒤, 내부에 포함된\n"
        "wafer_die_map_v5 엔진을 바로 호출합니다.",
        size=24,
        fill=MUTED,
    )
    add_text(
        draw,
        (104, 350),
        "기본 설정\n"
        "- grid_method = std\n"
        "- angle_align_method = die_render\n"
        "- clean = True",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "eval_input_full.png", (120, 470, 800, 880))

    rounded(draw, (910, 190, 1720, 920), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (934, 214, 1096, 258), "STEP 2", ACCENT)
    add_text(draw, (1122, 214), "Wafer / pitch / angle 을 추정", size=28, bold=True)
    add_text(
        draw,
        (934, 282),
        "내부 핵심 흐름\n"
        "- detect_wafer(): wafer 원형 검출\n"
        "- detect_grid(method=\"std\"): pitch 추정\n"
        "- align_wafer_by_die_render(): 회전 각도 복원\n"
        "- build_die_map(): 전체 die box 생성",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "eval_input_zoom_center.png", (970, 470, 1330, 840))
    info_panel(
        draw,
        (1360, 470, 1680, 840),
        "엔진이 보는 단서",
        "- 반복되는 die 주기\n"
        "- 일정한 grid 방향성\n"
        "- 노이즈가 있어도 남아 있는 반복 패턴\n"
        "- 이 반복성이 pitch 계산의 핵심 근거",
    )

    rounded(draw, (80, 980, 1720, 1560), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 1004, 266, 1048), "STEP 3", RED)
    add_text(draw, (292, 1004), "각 die 를 inner / edge 로 분류하고 overlay 생성", size=28, bold=True)
    add_text(
        draw,
        (104, 1070),
        "Overlay 의미\n"
        "- Green box: inner die\n"
        "- Red box: edge die\n"
        "- Cyan circle: wafer 경계 추정값",
        size=24,
        fill=MUTED,
    )
    paste_fit(img, ASSET_DIR / "eval_overlay_zoom_center.png", (120, 1180, 620, 1510))
    paste_fit(img, ASSET_DIR / "eval_overlay_zoom_edge.png", (760, 1140, 1400, 1510))
    info_panel(
        draw,
        (1440, 1140, 1680, 1510),
        "왜 edge die 가 중요한가",
        "- wafer rim 에 닿는 영역\n"
        "- 분석에서 따로 제외 가능\n"
        "- 가장자리 불안정 영역을 분리할 때 유용",
    )

    rounded(draw, (80, 1620, 1720, 2060), fill=PANEL, outline=BORDER, width=2)
    step_tag(draw, (104, 1644, 266, 1688), "STEP 4", GREEN)
    add_text(draw, (292, 1644), "JSON 요약 + overlay PNG 출력", size=28, bold=True)
    paste_fit(img, ASSET_DIR / "eval_overlay_full.png", (120, 1720, 720, 2020))
    info_panel(
        draw,
        (810, 1710, 1680, 2020),
        "최근 검증 결과",
        "image: bw_noisy_top_p090_3000.png\n"
        "num_dies: 749\n"
        "pitch_x / pitch_y: 90.0 / 90.0\n"
        "rotation_deg: 1.1003\n"
        "angle_confidence: 0.97\n"
        "angle_agree: true\n"
        "wafer_center: [1481, 1500]\n"
        "wafer_r: 1394",
    )

    img.save(VIS_DIR / "bw_noisy_evaluation_logic_korean.png")


def main() -> None:
    build_generator_board()
    build_evaluator_board()
    print("wrote korean visual boards")


if __name__ == "__main__":
    main()
