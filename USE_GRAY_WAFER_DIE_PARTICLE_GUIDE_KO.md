# `use_gray_wafer_die_particle.py` 전체 기능 가이드

## 사용할 최신 파일

실제 검사 프로그램에 넣을 최신 단일 파일은 [`use_gray_wafer_die_particle.py`](use_gray_wafer_die_particle.py)이다.

- 다른 프로젝트 파일을 import하지 않는 독립형 파일이다.
- 필요한 외부 패키지는 `numpy`, `opencv-python`뿐이다.
- 함수에는 파일 경로가 아니라 OpenCV 이미지 배열을 직접 넣을 수 있다. Gray 1채널 `(H, W)` / `(H, W, 1)`, BGR, BGRA를 모두 받을 수 있으며 내부에서 안전하게 BGR로 정규화한다.
- 이전 파일명 `paste_ready_evaluate_bw_noisy_wafer.py` 대신 이 파일을 복사해 사용한다.

## 전체 처리 흐름

![Gray wafer 외곽 particle 검사 로직](Visuals/gray_edge_particle_inspection_ko.png)

1. 입력 이미지를 BGR로 정규화하고 wafer 원판 밖의 노이즈를 제거한다.
2. die grid의 projection/FFT 정보를 이용해 회전 각도를 측정하고 필요하면 보정한다.
3. wafer 중심, 반지름, notch 중심, die pitch와 grid 원점 `(x0, y0)`을 찾는다.
4. 모든 die 경계를 **float pitch**로 계산한 다음 화면 좌표로 한 번만 반올림한다. 누적 반올림으로 멀리 있는 die가 점점 밀리는 문제를 막는다.
5. 각 die 중심은 좌우/상하의 공유 경계 중점으로 계산한다. 따라서 die 안의 밝은 가로/세로 회로 패턴이 중심을 이동시키지 않는다.
6. `clip_partial_edge=True`이면 wafer 원에 조금이라도 걸치는 die를 제외한다. edge safety margin은 기본적으로 작은 pitch의 10%다.
7. 필요 시 wafer 외곽 ring에서만 particle을 찾고, partial die를 포함한 모든 die 내부는 먼저 마스킹한다.

## 1. Die Map 생성

```python
import cv2
from use_gray_wafer_die_particle import build_die_map, locate_die

# 호출부는 경로가 아니라 읽어 둔 1채널 이미지 배열을 전달합니다.
image = cv2.imread("Gray_Wafer/2222.png", cv2.IMREAD_GRAYSCALE)
if image is None:
    raise FileNotFoundError("Gray_Wafer/2222.png")

die_map = build_die_map(
    image,
    grid_method="std",
    notch_align=False,
    clip_partial_edge=True,
    edge_mode="both",
)

print(die_map.num_dies)
print(die_map.pitch_x, die_map.pitch_y)
print(die_map.wafer_cx, die_map.wafer_cy, die_map.wafer_r)

# 점 또는 검출 BBox가 어느 die에 있는지 조회합니다.
found = locate_die(die_map, point=(600, 500))
# found = locate_die(die_map, bbox=(580, 480, 620, 520))
print(found["die_index"], found["die_center_px"], found["is_edge"])
```

### `build_die_map()` 주요 파라미터

| 파라미터 | 기본값 | 용도 |
| --- | --- | --- |
| `grid_method` | `"corner"` | grid 추출 방식. Gray wafer 검증에는 `"std"`를 사용했다. |
| `notch_align` | `True` | 회전 보정 사용 여부. 이미 정렬된 Gray 이미지면 `False`가 안전하다. |
| `angle_align_method` | `"die_render"` | `die_render`, `notch`, `vertical_line`, `none` 중 선택한다. |
| `clip_partial_edge` | `True` | wafer 외곽에 걸친 die를 map에서 제거한다. |
| `edge_clip_margin_px` | 자동 | partial 판정 safety margin. `-1`이면 작은 pitch의 10%를 사용한다. |
| `edge_mode` | `"circle"` | `circle`은 partial die, `ring`은 grid 최외곽, `both`는 둘 중 하나를 edge로 표시한다. |
| `with_crops` | `False` | `True`면 각 die 항목에 crop 이미지를 함께 넣는다. |
| `offset_x`, `offset_y` | `0` | die crop 중심을 이동한다. |
| `margin_x`, `margin_y` | `0` | die crop을 사방으로 확장한다. |

### `WaferDieMap`에서 자주 쓰는 결과

| 항목 | 의미 |
| --- | --- |
| `wafer_cx`, `wafer_cy`, `wafer_r` | 검출된 wafer 중심과 반지름(px) |
| `pitch_x`, `pitch_y` | 반올림 전의 sub-pixel die pitch(px) |
| `x0`, `y0` | 중심 부근 grid corner 원점(px) |
| `dies` | 포함된 die 목록 |
| `dies_by_index[(ix, iy)]` | index로 die를 빠르게 조회 |
| `aligned_image` | clean 및 회전 보정 뒤, 모든 좌표의 기준이 되는 이미지 |
| `rotation_deg` | 적용한 회전 보정 각도 |
| `notch_center_px` | notch 중심점, 찾지 못하면 `None` |
| `angle_verified` | notch/grid 교차 검증 성공 여부 |
| `quadrant_report` | 4분면 edge coverage 검증 정보 |

각 `die` 항목에는 `index`, `center_px`, `rect_px`, `crop_rect_px`, `real_coord`, `is_edge_partial`, `is_edge_ring`, `is_edge`가 들어간다.

## 2. Wafer 외곽 Particle 검사

```python
import cv2
from use_gray_wafer_die_particle import (
    inspect_edge_particles,
    render_edge_particle_diagnostic_overlay,
)

image = cv2.imread("Gray_Wafer/2222.png", cv2.IMREAD_GRAYSCALE)

inspection = inspect_edge_particles(
    image,
    grid_method="std",
    notch_align=False,
    edge_inner_margin_px=75,
    edge_outer_margin_px=10,
    ring_guard_px=2,
    die_exclusion_margin_px=2,
    white_threshold=220,
    min_area_px=20,
    max_area_px=300,
    max_aspect_ratio=2.5,
    min_fill_ratio=0.45,
    min_local_contrast=45.0,
    include_debug_components=True,
)

for particle in inspection["particles"]:
    print(particle["id"], particle["center_px"], particle["bbox_px"])

debug_image = render_edge_particle_diagnostic_overlay(image, inspection)
cv2.imwrite("edge_particle_debug.png", debug_image)
```

Particle 검사는 흰색 전체를 검출하지 않는다. 먼저 wafer 외곽의 조절 가능한 annulus(ring)를 만들고, 그 안에서도 모든 die 사각형을 제외한다. 남은 영역의 밝은 blob만 면적, 가로세로 비, 채움 비율, 주변 대비 기준을 모두 통과해야 particle이 된다.

| 파라미터 | 의미 |
| --- | --- |
| `edge_inner_margin_px` | wafer edge에서 안쪽으로 검사할 시작 위치 |
| `edge_outer_margin_px` | rim에 너무 가까운 영역을 제외하는 폭 |
| `ring_guard_px` | ring 경계에 걸친 blob을 막는 보호 폭 |
| `die_exclusion_margin_px` | die 내부 제외 영역을 확장하는 폭 |
| `white_threshold` | 밝은 후보의 최소 gray 값 |
| `min_area_px`, `max_area_px` | particle 후보 면적 범위 |
| `max_aspect_ratio`, `min_fill_ratio` | street/긴 선 조각을 제외하는 형상 기준 |
| `min_local_contrast` | 주변 대비가 충분한 blob만 통과시키는 기준 |

반환값 `inspection`에는 최종 `particles`와 함께 `ring_mask`, `die_exclusion_mask`, `inspection_mask`, `mask_summary`, `parameters`가 포함된다. `include_debug_components=True`이면 `debug_components`에 die 내부로 제외된 `D`와 형상/면적/대비에서 탈락한 `R`도 들어간다.

진단 이미지의 표시는 다음과 같다.

| 표시 | 의미 |
| --- | --- |
| 하늘색 원 | 검사 ring의 안쪽/바깥쪽 경계 |
| 주황색 | die 내부여서 검사에서 제외된 영역 |
| 초록색 | 실제 particle 검사 가능 영역 |
| `D1`, `D2` | die 내부의 밝은 회로 blob, particle 제외 |
| `R1`, `R2` | 검사 가능 영역이지만 면적/형상/배경/대비 기준에서 제외 |
| `P1`, `P2` | 모든 기준을 통과한 최종 particle |

## 검증 방법과 현재 결과

```powershell
python evaluate_gray_edge_particles.py
python make_gray_edge_particle_visual.py
python -m py_compile use_gray_wafer_die_particle.py evaluate_gray_edge_particles.py
```

`Gray_Wafer/111.png`, `Gray_Wafer/2222.png`는 1채널 입력으로 정상 처리되었고 각각 190개 die, pitch `76 x 67 px`를 검출했다. 실제 이미지에서 검출된 particle은 0개이며, 이는 보이는 밝은 점이 partial die 내부에 있어 의도적으로 제외되었기 때문이다. `Paticle/22.png`를 허용 영역에 삽입한 synthetic 검증에서는 정확히 1개를 검출해 PASS했다.

상세 결과와 진단 overlay는 [`GRAY_EDGE_PARTICLE_INSPECTION_KO.md`](GRAY_EDGE_PARTICLE_INSPECTION_KO.md)에서 확인할 수 있다.
