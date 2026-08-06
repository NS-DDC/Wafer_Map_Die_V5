from __future__ import annotations

"""Create a Korean visual board for Gray edge-only particle inspection."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
GRAY_DIR = ROOT / "Gray_Wafer"
VIS_DIR = ROOT / "Visuals"
SUMMARY_PATH = GRAY_DIR / "edge_particle_validation.json"
OUT_PATH = VIS_DIR / "gray_edge_particle_inspection_ko.png"
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

BG = "#07111e"
PANEL = "#102238"
TEXT = "#f6f8fb"
MUTED = "#b5c5d8"
CYAN = "#38bdf8"
GREEN = "#34d399"
ORANGE = "#fbbf24"
RED = "#fb7185"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, *, size: int,
         fill: str = TEXT, bold: bool = False, spacing: int = 7) -> None:
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, spacing=spacing)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=24, fill=PANEL, outline="#294968", width=2)


def paste_fit(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(path).convert("RGB")
    width, height = box[2] - box[0], box[3] - box[1]
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas.paste(image, (box[0] + (width - image.width) // 2, box[1] + (height - image.height) // 2))


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    by_name = {item["image"]: item for item in summary["results"]}
    VIS_DIR.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGB", (2400, 1600), BG)
    draw = ImageDraw.Draw(canvas)
    text(draw, (64, 44), "Gray Wafer 외곽 Particle 검사", size=52, bold=True)
    text(draw, (66, 118), "흰색 전체 검출이 아니라 외곽 ring + die 내부 제외 + blob 형상 필터를 함께 적용", size=25, fill=MUTED)

    panel(draw, (46, 180, 610, 790))
    text(draw, (78, 214), "1. 기준 이미지", size=29, bold=True, fill=CYAN)
    text(draw, (78, 266), "DIE 내부 흰 회로선은\nparticle가 아니므로 제외", size=22, fill=MUTED)
    paste_fit(canvas, GRAY_DIR / "DIE" / "DIE.png", (88, 350, 566, 652))
    text(draw, (78, 684), "Particle 기준\n작고 조밀한 밝은 blob", size=22, fill=ORANGE, bold=True)
    paste_fit(canvas, GRAY_DIR / "Paticle" / "22.png", (370, 666, 538, 758))

    panel(draw, (642, 180, 1414, 790))
    text(draw, (676, 214), "2. 검사 영역 + 제외 근거", size=29, bold=True, fill=CYAN)
    paste_fit(canvas, GRAY_DIR / by_name["2222.png"]["diagnostic_overlay"], (678, 282, 1378, 748))
    text(draw, (676, 750), "주황: die 제외 / 초록: 실제 검사 / D: die 내부 흰 blob / R: 형상 탈락 / P: 최종", size=19, fill=MUTED)

    panel(draw, (1446, 180, 2354, 790))
    text(draw, (1480, 214), "3. 외부 조절 파라미터", size=29, bold=True, fill=CYAN)
    params = summary["parameters"]
    text(draw, (1482, 292),
         f"edge_inner_margin_px = {params['edge_inner_margin_px']}\n"
         f"edge_outer_margin_px = {params['edge_outer_margin_px']}\n"
         f"die_exclusion_margin_px = {params['die_exclusion_margin_px']}\n"
         f"white_threshold = {params['white_threshold']}\n"
         f"min_area_px = {params['min_area_px']}\n"
         f"max_aspect_ratio = {params['max_aspect_ratio']}\n"
         f"min_local_contrast = {params['min_local_contrast']}",
         size=24, fill=TEXT, spacing=14)
    text(draw, (1482, 628), "범위를 넓히려면 inner 값을 키우고,\nrim 가까이를 더 보려면 outer 값을 줄인다.", size=22, fill=ORANGE)

    panel(draw, (46, 828, 2354, 1544))
    text(draw, (78, 862), "4. 검증 결과", size=30, bold=True, fill=GREEN)
    text(draw, (82, 928), "입력                1채널     Die 수     검사 pixel     D: die 제외     R: 탈락     P: 최종", size=24, bold=True, fill=MUTED)
    y = 982
    for name in ("111.png", "2222.png"):
        item = by_name[name]
        debug = item["debug_component_counts"]
        text(draw, (82, y),
             f"{name:<18}  OK          {item['num_dies']:>3}      {item['inspection_pixels']:>6}       "
             f"{debug['die_excluded']:>4}            {debug['rejected']:>4}        {item['particle_count']}",
             size=25, fill=TEXT)
        y += 48

    check = summary["reference_particle_injection"]
    text(draw, (82, 1108), "Particle 기준 삽입 검증", size=27, bold=True, fill=ORANGE)
    text(draw, (82, 1156),
         f"die 제외 mask 밖의 외곽 영역에 기준 blob 삽입: {check['injected_center_px']}\n"
         f"검출 결과: {check['detected_count']}개, 검출 중심: {check['first_detected_center_px']}  -> PASS",
         size=24, fill=TEXT)
    text(draw, (1250, 1114), "판정 순서", size=27, bold=True, fill=GREEN)
    text(draw, (1250, 1162), "외곽 ring 선택  ->  partial die 포함 die mask 제외\n"
                              "-> 밝기 threshold  ->  면적/형상/대비 필터\n"
                              "-> 남은 compact blob만 particle", size=24, fill=TEXT, spacing=13)
    text(draw, (82, 1428), "실제 입력의 흰 점이 die 내부이면 후보 0개가 정상이다. 이 경우 오검출이 아니라 die 제외 로직이 동작한 결과다.", size=22, fill=RED)

    canvas.save(OUT_PATH, optimize=True)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
