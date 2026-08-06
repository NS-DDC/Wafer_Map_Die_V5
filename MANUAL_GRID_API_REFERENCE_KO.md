# Manual Grid API 반환값 레퍼런스

대상 파일: [`use_manual_grid_wafer_map.py`](use_manual_grid_wafer_map.py)

이 문서는 자동 grid 검출을 쓰지 않고, 호출부가 float `corner_point`와 float `pitch`를 전달하는 경우의 API만 정리한다.

## 전체 호출 순서

```python
import cv2
from use_manual_grid_wafer_map import detect_wafer_center, build_die_map, locate_die

image = cv2.imread("wafer.png", cv2.IMREAD_GRAYSCALE)
if image is None:
    raise FileNotFoundError("wafer.png")

# A. wafer center 확인용. build_die_map 내부에서도 동일하게 실행된다.
wafer = detect_wafer_center(image)

# B. 호출부가 ROI에서 직접 구한 float grid 값
corner_point = (625.25, 593.75)
pitch = (76.125, 67.50)

# C. wafer 중심 검출 + 수동 grid 기반 Die map 생성
dm = build_die_map(image, corner_point, pitch)

# D. defect point/BBox -> Die index 및 좌표
result = locate_die(dm, point=(580.2, 480.4))
# result = locate_die(dm, bbox=(560.0, 460.0, 600.0, 500.0))
```

## A. `detect_wafer_center(image)` 반환값

원본 Gray/BGR/BGRA 이미지에서 가장 큰 non-background 영역을 wafer로 보고 중심/반지름을 계산한다.

```python
wafer = detect_wafer_center(image)
```

| 키 | 타입 | 의미 |
| --- | --- | --- |
| `wafer["wafer_cx"]` | `int` | wafer 중심 X 좌표(px) |
| `wafer["wafer_cy"]` | `int` | wafer 중심 Y 좌표(px) |
| `wafer["wafer_r"]` | `int` | wafer 반지름(px) |

## B. `build_die_map(...)` 입력값

```python
dm = build_die_map(
    image,
    corner_point=(x0, y0),
    pitch=(pitch_x, pitch_y),
    pixel_per_unit=32.0,
    edge_clip_margin_px=8.0,
    edge_index_margin_px=20.0,
    edge_mode="both",
)
```

| 인자 | 타입 | 의미 |
| --- | --- | --- |
| `image` | `np.ndarray` | Gray `(H,W)`, BGR `(H,W,3)`, BGRA `(H,W,4)` 원본 이미지 |
| `corner_point` | `(float, float)` | ROI에서 구한 공유 grid corner `(x0,y0)` |
| `pitch` | `(float, float)` | ROI에서 구한 `(pitch_x,pitch_y)` |
| `pixel_per_unit` | `float` | 실측 좌표 환산값. 기본 `32.0 px = 1 unit` |
| `edge_clip_margin_px` | `float` | wafer rim에서 안쪽으로 줄일 안전 여유. 음수 기본값은 작은 pitch의 10% 자동 사용 |
| `edge_index_margin_px` | `float` | 안전 원에서 안쪽으로 edge index로 표시할 폭 |
| `edge_mode` | `str` | `circle`, `ring`, `margin`, `both` 중 선택 |
| `clip_partial_edge` | `bool` | 안전 원에 걸치는 Die를 map에서 제거할지 여부. 기본 `True` |
| `with_crops` | `bool` | 각 Die entry에 crop 이미지를 넣을지 여부 |
| `offset_x`, `offset_y` | `float` | crop 중심 보정값(px) |
| `margin_x`, `margin_y` | `float` | crop 영역 확장값(px) |

## C. `dm` 반환값: `WaferDieMap`

| 속성 | 타입 | 의미 |
| --- | --- | --- |
| `dm.wafer_cx`, `dm.wafer_cy`, `dm.wafer_r` | `int` | 이미지에서 검출한 wafer 중심/반지름(px) |
| `dm.x0`, `dm.y0` | `float` | 전달한 `corner_point`. 모듈이 수정하지 않음 |
| `dm.pitch_x`, `dm.pitch_y` | `float` | 전달한 `pitch`. 모듈이 수정하지 않음 |
| `dm.die_w`, `dm.die_h` | `float` | Die 폭/높이. 수동 pitch와 동일 |
| `dm.pixel_per_unit` | `float` | 실측 좌표 환산값 |
| `dm.num_dies` | `int` | map에 남은 Die 수 |
| `dm.dies` | `list[dict]` | 모든 Die entry 리스트 |
| `dm.dies_by_index` | `dict` | `{(ix,iy): die_entry}` 형태의 빠른 조회용 map |
| `dm.get_die(ix, iy)` | `dict or None` | 해당 index Die entry. 없으면 `None` |
| `dm.edge_indices` | `list[(int,int)]` | 현재 `edge_mode` 기준 edge Die index 목록 |
| `dm.edge_index_report` | `dict` | `selected`, `partial`, `ring`, `margin` 원인별 index 목록 |
| `dm.edge_mode` | `str` | 실제 적용된 edge mode |
| `dm.edge_clip_margin_px` | `float` | 실제 적용된 clip margin |
| `dm.edge_index_margin_px` | `float` | 실제 적용된 index band 폭 |
| `dm.edge_limit_r` | `float` | margin을 적용한 실제 안전 원 반지름 |
| `dm.aligned_image` | `np.ndarray` | BGR로 정규화한 원본 이미지. 이 버전은 회전 보정을 하지 않음 |
| `dm.image_shape` | `(int,int)` | `(height,width)` |
| `dm.quadrant_report` | `dict` | 4분면 Die coverage 확인값 |

### `dm.edge_index_report` 형식

```python
{
    "selected": [(ix, iy), ...],  # 현재 edge_mode에서 is_edge=True인 Die
    "partial":  [(ix, iy), ...],  # 안전 원 밖으로 일부라도 걸친 Die
    "ring":     [(ix, iy), ...],  # 8방향 이웃이 모두 존재하지 않는 최외곽 Die
    "margin":   [(ix, iy), ...],  # 안전 원에서 안쪽 edge band에 있는 완전 Die
}
```

## D. `dm.dies` 항목 하나의 반환값

```python
die = dm.dies[0]
```

| 키 | 타입 | 의미 |
| --- | --- | --- |
| `die["index"]` | `(int,int)` | `(ix,iy)`. 오른쪽은 `ix+`, 위쪽은 `iy+` |
| `die["center_px"]` | `(float,float)` | float grid 기준 Die 중심 `(cx,cy)` |
| `die["rect_px"]` | `(int,int,int,int)` | 화면 표시/crop용 반올림된 `(x1,y1,x2,y2)` |
| `die["crop_rect_px"]` | `(int,int,int,int)` | offset/margin을 적용한 crop 영역 |
| `die["real_coord"]` | `(float,float)` | Die 중심의 wafer 중심 기준 실측 좌표 |
| `die["edge_distance_px"]` | `float` | 안전 원에서 Die의 가장 먼 모서리까지 남은 거리. 음수면 원 밖으로 걸침 |
| `die["is_edge_partial"]` | `bool` | 안전 원에 걸치는 부분 Die 여부 |
| `die["is_edge_ring"]` | `bool` | 최외곽 grid ring 여부 |
| `die["is_edge_margin"]` | `bool` | 지정한 edge index band 여부 |
| `die["is_edge"]` | `bool` | `edge_mode`로 선택된 최종 edge 여부 |
| `die["image"]` | `np.ndarray` | `with_crops=True`일 때만 존재하는 crop 이미지 |

## E. `locate_die(dm, point=... | bbox=...)` 반환값

입력 point 또는 BBox 중심이 어느 수동 grid Die에 속하는지 계산한다. map에서 clip되어 제거된 위치라도 grid index와 이론상 Die 좌표는 반환한다.

| 키 | 타입 | 의미 |
| --- | --- | --- |
| `input_type` | `str` | `point` 또는 `bbox` |
| `query_px` | `(float,float)` | 실제 사용한 입력 좌표. BBox면 중심 좌표 |
| `die_index` | `(int,int)` | 입력 좌표가 속한 `(ix,iy)` |
| `die_center_px` | `(float,float)` | 해당 Die의 float 중심 좌표 |
| `die_rect_px` | `(int,int,int,int)` | 해당 Die 사각형 `(x1,y1,x2,y2)` |
| `crop_rect_px` | `(int,int,int,int)` | offset/margin 적용 crop 영역 |
| `real_coord` | `(float,float)` | 입력 point/BBox 중심의 실측 좌표 |
| `real_distance` | `float` | wafer 중심에서 입력 좌표까지 실측 거리 |
| `die_real_coord` | `(float,float)` | Die 중심의 실측 좌표 |
| `wafer_center_px` | `(int,int)` | 검출한 wafer 중심 |
| `corner_px` | `(float,float)` | 전달한 grid corner `(x0,y0)` |
| `is_edge` | `bool` | 현재 `edge_mode` 기준 최종 edge 여부 |
| `is_edge_partial` | `bool` | 부분 Die 여부 |
| `is_edge_ring` | `bool` | 최외곽 grid ring 여부 |
| `is_edge_margin` | `bool` | edge index band 여부 |
| `edge_distance_px` | `float` | 안전 원까지 남은 거리 |
| `edge_mode` | `str` | 적용된 edge mode |
| `in_wafer` | `bool` | 입력 좌표 자체가 원본 wafer 원 안에 있는지 |

## F. 좌표 공식

공유 grid corner를 `(x0,y0)`라고 할 때, Die `(ix,iy)`는 다음 float 공식을 사용한다.

```python
left   = x0 + ix * pitch_x
right  = x0 + (ix + 1) * pitch_x
top    = y0 - (iy + 1) * pitch_y
bottom = y0 - iy * pitch_y
center = ((left + right) / 2.0, (top + bottom) / 2.0)
```

각 Die 경계는 이 식으로 독립 계산한다. 즉 `round(pitch)`를 계속 더하는 방식이 아니므로 wafer 중심에서 멀어져도 반올림 오차가 누적되지 않는다.
