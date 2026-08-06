# Manual Grid Wafer Map 가이드

사용 파일은 [`use_manual_grid_wafer_map.py`](use_manual_grid_wafer_map.py)다. 이 파일은 `numpy`, `opencv-python`만 사용하는 독립형 파일이며, 기존 자동 grid 검출을 실행하지 않는다.

## 역할 분리

| 단계 | 담당 | 입력/출력 |
| --- | --- | --- |
| 1 | 이 모듈 | 원본 image에서 wafer 중심 `(wafer_cx, wafer_cy)`와 반지름 `wafer_r` 검출 |
| 2 | 호출부 | 원하는 ROI에서 grid corner와 pitch를 직접 측정 |
| 3 | 이 모듈 | 전달받은 float corner/pitch로 Die map, edge index, crop 좌표, 실측 좌표 생성 |
| 4 | 호출부 | `locate_die()`로 defect/BBox의 Die index와 좌표 조회 |

이 버전은 angle 보정, grid 검출, corner 보정, pitch 추정을 하지 않는다. 따라서 호출부가 얻은 값이 최종 기준이며, 이 모듈이 이를 다시 바꾸지 않는다.

## 좌표 규칙

`corner_point=(x0, y0)`는 네 Die가 만나는 공유 grid corner다. 오른쪽 위 Die가 `(ix, iy)=(0, 0)`이다.

```text
                 iy +1
                   ^
      (-1, 0)     |      (0, 0)
                 (x0, y0) --------> ix +1
      (-1,-1)             (0,-1)
```

Die `(ix, iy)`의 float 경계와 중심은 다음과 같다.

```python
left   = x0 + ix * pitch_x
right  = x0 + (ix + 1) * pitch_x
top    = y0 - (iy + 1) * pitch_y
bottom = y0 - iy * pitch_y
center = ((left + right) / 2, (top + bottom) / 2)
```

`corner_point`와 `pitch`는 모두 float으로 전달할 수 있다. 매 Die마다 float 식으로 독립 계산하고, 화면에 쓸 `rect_px`만 마지막에 반올림한다. 따라서 멀리 있는 Die가 누적 반올림 때문에 밀리지 않는다.

## 기본 호출

```python
import cv2
from use_manual_grid_wafer_map import build_die_map, locate_die

# 원본 이미지. Gray 1채널, BGR, BGRA 모두 가능하다.
image = cv2.imread("wafer.png", cv2.IMREAD_GRAYSCALE)
if image is None:
    raise FileNotFoundError("wafer.png")

# 이 값은 호출부가 ROI에서 직접 구한 값이다. 반드시 float으로 전달 가능하다.
corner_point = (625.25, 593.75)
pitch = (76.125, 67.50)

dm = build_die_map(
    image,
    corner_point=corner_point,
    pitch=pitch,
    pixel_per_unit=32.0,
    edge_clip_margin_px=8.0,
    edge_index_margin_px=20.0,
    edge_mode="both",
)

# 이 모듈이 이미지에서 찾은 wafer 중심/반지름
print(dm.wafer_cx, dm.wafer_cy, dm.wafer_r)

# 전달한 float 값이 그대로 저장된다.
print(dm.x0, dm.y0, dm.pitch_x, dm.pitch_y)

# edge Die index
print(dm.edge_indices)
print(dm.edge_index_report["ring"])
print(dm.edge_index_report["margin"])

# defect 점 또는 BBox가 속한 Die 조회
result = locate_die(dm, bbox=(580.2, 480.4, 620.8, 520.6))
print(result["die_index"], result["die_rect_px"], result["real_coord"])
```

## 반환 데이터

`build_die_map()`은 `WaferDieMap`을 반환한다.

| 항목 | 의미 |
| --- | --- |
| `wafer_cx`, `wafer_cy`, `wafer_r` | 이미지에서 검출한 wafer 중심/반지름(px) |
| `x0`, `y0` | 호출부가 전달한 float grid corner, 수정하지 않음 |
| `pitch_x`, `pitch_y` | 호출부가 전달한 float pitch, 수정하지 않음 |
| `dies` | map에 포함된 Die 목록 |
| `dies_by_index[(ix, iy)]` | index로 Die 항목을 즉시 조회 |
| `edge_indices` | 현재 `edge_mode` 기준 edge `(ix, iy)` 목록 |
| `edge_index_report` | `selected`, `partial`, `ring`, `margin` 기준별 index 목록 |
| `aligned_image` | 좌표 변경 없이 BGR로 정규화한 원본 이미지 |

각 `dies` 항목은 `index`, `center_px`, `rect_px`, `crop_rect_px`, `real_coord`, `is_edge_partial`, `is_edge_ring`, `edge_distance_px`, `is_edge_margin`, `is_edge`를 가진다.

## Edge margin

`edge_clip_margin_px`는 wafer 원을 안쪽으로 줄이는 안전 여유다. `clip_partial_edge=True`이면 이 안전 원에 한 모서리라도 걸치는 Die를 제거한다.

`edge_index_margin_px`는 제거 후 남은 완전 Die 중 안전 원에서 안쪽으로 지정 폭까지를 `is_edge_margin=True`로 분류하는 값이다. 예를 들어 `clip=8.0`, `index=20.0`이면 wafer rim에서 8px 안전 여유를 둔 뒤 그 안쪽 20px 폭의 완전 Die를 margin edge index로 얻는다.

`edge_mode="both"`은 partial/ring/margin 중 하나라도 만족하면 `is_edge=True`다. margin band만 쓰려면 `edge_mode="margin"`을 사용한다.
