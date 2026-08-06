# `use_gray_wafer_die_particle.py` 전체 기능 가이드

## 사용할 최신 파일

실제 검사 프로그램에 넣을 최신 단일 파일은 [`use_gray_wafer_die_particle.py`](use_gray_wafer_die_particle.py)이다.

- 다른 프로젝트 파일을 import하지 않는 독립형 파일이다.
- 필요한 외부 패키지는 `numpy`, `opencv-python`뿐이다.
- 함수에는 파일 경로가 아니라 OpenCV 이미지 배열을 직접 넣을 수 있다. Gray 1채널 `(H, W)` / `(H, W, 1)`, BGR, BGRA를 모두 받을 수 있으며 내부에서 안전하게 BGR로 정규화한다.
- 이전 파일명 `paste_ready_evaluate_bw_noisy_wafer.py` 대신 이 파일을 복사해 사용한다.

## 전체 처리 흐름

![Gray wafer ring ROI particle defect 검사 로직](Visuals/gray_edge_particle_inspection_ko.png)

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
    edge_clip_margin_px=8,
    edge_index_margin_px=20,
    edge_mode="both",
)

print(die_map.num_dies)
print(die_map.pitch_x, die_map.pitch_y)
print(die_map.wafer_cx, die_map.wafer_cy, die_map.wafer_r)

# 점 또는 검출 BBox가 어느 die에 있는지 조회합니다.
found = locate_die(die_map, point=(600, 500))
# found = locate_die(die_map, bbox=(580, 480, 620, 520))
print(found["die_index"], found["die_center_px"], found["is_edge"])

# 현재 is_edge 기준으로 선택된 edge index와 원인별 index를 바로 받습니다.
print(die_map.edge_indices)
print(die_map.edge_index_report["ring"])
print(die_map.edge_index_report["margin"])
```

### `build_die_map()` 주요 파라미터

| 파라미터 | 기본값 | 용도 |
| --- | --- | --- |
| `grid_method` | `"corner"` | grid 추출 방식. Gray wafer 검증에는 `"std"`를 사용했다. |
| `min_pitch`, `max_pitch` | `50`, `None` | 허용할 pitch 범위(px). `max_pitch=70`이면 `pitch_x/y`는 70을 넘지 않는다. |
| `corner_x0_mode` | `"auto"` | `corner` 방식에서 강하고 넓은 세로 흰 노이즈를 감지하면 wafer 중심 방향으로 `pitch_x/2` 이동한다. `nearest`는 보정 끔, `half_pitch`는 강제 보정이다. |
| `notch_align` | `True` | 회전 보정 사용 여부. 이미 정렬된 Gray 이미지면 `False`가 안전하다. |
| `angle_align_method` | `"die_render"` | `die_render`, `notch`, `vertical_line`, `none` 중 선택한다. |
| `clip_partial_edge` | `True` | wafer 외곽에 걸친 die를 map에서 제거한다. |
| `edge_clip_margin_px` | 자동 | partial 판정 safety margin. `-1`이면 작은 pitch의 10%를 사용한다. |
| `edge_index_margin_px` | `0` | 포함된 완전 die 중 안전 원 경계에서 안쪽으로 이 폭만큼을 `is_edge_margin=True`로 표기한다. |
| `edge_mode` | `"both"` | `circle`은 partial die, `ring`은 grid 최외곽, `margin`은 지정 band, `both`는 세 기준 중 하나를 edge로 표시한다. `clip_partial_edge=True`라면 `circle`만 사용할 때 edge가 0개인 것이 정상이다. |
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
| `edge_indices` | 현재 `edge_mode` 기준으로 선택된 `(ix, iy)` 목록 |
| `edge_index_report` | `selected`, `partial`, `ring`, `margin` 원인별 `(ix, iy)` 목록 |

각 `die` 항목에는 `index`, `center_px`, `rect_px`, `crop_rect_px`, `real_coord`, `is_edge_partial`, `is_edge_ring`, `edge_distance_px`, `is_edge_margin`, `is_edge`가 들어간다.

### Edge margin 동작

`edge_clip_margin_px`와 `edge_index_margin_px`는 역할이 다르다. 먼저 유효 원 반지름을 `wafer_r * edge_margin - edge_clip_margin_px`로 만든다. `clip_partial_edge=True`이면 이 유효 원을 조금이라도 넘는 die는 map에서 제거된다. 이후 남은 die마다 가장 먼 모서리와 유효 원 사이의 거리 `edge_distance_px`를 계산한다. 그 값이 `0 <= 거리 <= edge_index_margin_px`이면 `is_edge_margin=True`이다.

예를 들어 `edge_clip_margin_px=8`, `edge_index_margin_px=20`이면 실제 wafer rim에서 8px 안전 여유를 두고 부분 die를 제거한 뒤, 그 안전 원에서 다시 20px 안쪽까지의 완전 die를 margin edge로 분류한다. particle ring ROI와는 별개의 die index 분류다.

## 2. Wafer Ring ROI Particle 검사

```python
import cv2
from use_gray_wafer_die_particle import (
    inspect_particles_in_wafer_ring,
    render_particle_diagnostic_overlay,
)

image = cv2.imread("Gray_Wafer/2222.png", cv2.IMREAD_GRAYSCALE)
dm = build_die_map(image, grid_method="std", notch_align=False, edge_mode="both")

inspection = inspect_particles_in_wafer_ring(
    dm,
    ring_inner_margin_px=75,
    ring_outer_margin_px=10,
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

debug_image = render_particle_diagnostic_overlay(dm, inspection)
cv2.imwrite("edge_particle_debug.png", debug_image)
```

**개념 구분:** `is_edge`는 wafer 외곽에 있는 die의 속성이고, `particles`는 defect 후보 목록이다. particle 자체에는 edge 여부를 붙이지 않는다. 기존 흐름처럼 먼저 `dm = build_die_map(image, ...)`을 만들고, 그 `dm`을 모든 particle 함수에 전달한다. `ring_inner_margin_px=75`, `ring_outer_margin_px=10`이면 wafer 원 외곽에서 10px 안쪽부터 75px 안쪽까지의 circle ring을 **검사 ROI**로만 사용한다. 그 안에서도 partial die를 포함한 모든 die 사각형을 제외한다. 남은 영역의 밝은 blob만 면적, 가로세로 비, 채움 비율, 주변 대비 기준을 모두 통과해야 particle이 된다.

이미지만 있고 `dm`을 아직 만들지 않은 경우에는 보조 함수 `inspect_edge_particles_from_image(image, ...)`를 사용할 수 있다. 일반 사용과 overlay 좌표 일관성을 위해서는 `dm` 방식이 권장된다. 이전 `inspect_edge_particles()`와 `render_edge_particle_*()` 이름은 호환용으로 남아 있지만, 새 코드는 `wafer_ring` 이름을 사용한다.

| 파라미터 | 의미 |
| --- | --- |
| `ring_inner_margin_px` | wafer rim에서 안쪽으로 검사 ROI가 끝나는 위치 |
| `ring_outer_margin_px` | rim에 너무 가까운 영역을 ROI에서 제외하는 폭 |
| `ring_guard_px` | ring 경계에 걸친 blob을 막는 보호 폭 |
| `die_exclusion_margin_px` | die 내부 제외 영역을 확장하는 폭 |
| `white_threshold` | 밝은 후보의 최소 gray 값 |
| `min_area_px`, `max_area_px` | particle 후보 면적 범위 |
| `max_aspect_ratio`, `min_fill_ratio` | street/긴 선 조각을 제외하는 형상 기준 |
| `min_local_contrast` | 주변 대비가 충분한 blob만 통과시키는 기준 |

반환값 `inspection`에는 최종 `particles`와 함께 `ring_mask`, `die_exclusion_mask`, `inspection_mask`, `mask_summary`, `parameters`가 포함된다. 모든 mask는 원본과 같은 `(H, W)`의 `uint8`이며 `1=해당`, `0=비해당`이다. `include_debug_components=True`이면 `debug_components`에 die 내부로 제외된 `D`와 형상/면적/대비에서 탈락한 `R`도 들어간다.

| 반환 키 | 의미 |
| --- | --- |
| `particles` | 최종 통과 particle 목록. 각 항목은 `id`, `center_px`, `bbox_px`, `area_px`, `aspect_ratio`, `fill_ratio`, `mean_intensity`, `local_contrast`, `radius_from_wafer_center_px`를 가진다. |
| `ring_mask` | 설정한 wafer 외곽 ring. |
| `die_exclusion_mask` | partial die를 포함해 particle 검사에서 제외한 die 영역. |
| `inspection_mask` | ring 중 die 밖에 남아 실제 검사한 픽셀. |
| `bright_mask` | 검사 영역에서 `white_threshold`를 넘긴 필터 전 후보. |
| `die_bright_mask` | 밝지만 die 내부라 제외된 픽셀. |
| `mask_summary` | 각 영역 pixel 수, 필터 전 후보 수, 최종 particle 수. |
| `parameters` | 이번 결과에 실제 적용한 모든 particle 파라미터. |
| `inspection_radii_px` | wafer 중심 기준 ring의 안쪽/바깥쪽 반지름(px). |
| `debug_components` | `D=die_excluded`, `R=rejected` blob 목록. 디버그 옵션이 꺼지면 `None`. |

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
