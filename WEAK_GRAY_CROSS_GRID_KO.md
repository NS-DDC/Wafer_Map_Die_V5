# 약신호 Gray 3000x3000 Cross Grid 검출

대상 파일은 [`USE_LATEST/use_gray_wafer_die_particle.py`](USE_LATEST/use_gray_wafer_die_particle.py)다. 이 업데이트는 1채널 Gray wafer에서 wafer 중심, 중심 부근 grid corner, pitch를 자동 검출할 때 사용하는 기본 방식이다.

## 기본 호출

```python
from USE_LATEST.use_gray_wafer_die_particle import build_die_map

# image: (3000, 3000) 1채널 np.ndarray
dm = build_die_map(
    image,
    grid_method="cross",  # 기본값
    min_pitch=30,
    max_pitch=70,
    notch_align=False,     # 약신호 기본값
)

print(dm.wafer_cx, dm.wafer_cy, dm.wafer_r)
print(dm.x0, dm.y0)
print(dm.pitch_x, dm.pitch_y)
```

## 검출 규칙

1. 입력 Gray/BGR/BGRA를 BGR과 uint8 Gray로 안전하게 정규화한다.
2. 여러 약한 threshold 후보에서 큰 원형 silhouette를 비교해 wafer 중심과 반지름을 고른다. 전체 프레임 노이즈는 wafer 후보에서 제외한다.
3. wafer 중심 주변 ROI에 CLAHE와 local high-pass를 적용해 약한 선을 강조한다.
4. 세로 ridge와 가로 ridge를 각각 검출한다. 물리적으로 1~2px인 street는 보정 후 4px 정도 응답까지 허용한다.
5. 폭이 큰 세로 noise band는 세로 후보에서 제외한다. 남은 얇은 세로 ridge 중 wafer 중심에 가장 가까운 X와, 얇은 가로 ridge 중 wafer 중심 바로 위 Y를 조합해 corner `(x0,y0)`로 사용한다.
6. 좌우 세로 cross 위치 간격으로 `pitch_x`, 상하 가로 cross 위치 간격으로 `pitch_y`를 구한다. 두 값 모두 30~70px을 넘지 않도록 hard bound를 적용한다.

## 조정 기준

| 상황 | 조정 |
| --- | --- |
| 실제 street가 4px보다 넓음 | `detect_thin_cross_grid(..., thin_width_max=5)`처럼 1px씩만 증가 |
| 실제 pitch가 범위 밖 | `min_pitch`, `max_pitch`를 실제 범위로 함께 조정 |
| 실제 wafer가 기울어짐 | 먼저 `notch_align=True` 또는 별도 정렬을 검토. 정렬 후 `cross` 사용 권장 |
| corner가 아닌 다른 grid 방식 비교 필요 | `grid_method="corner"` 또는 `"std"`를 명시적으로 지정 |

## 검증 범위

`원본/Claude_V5` 폴더에는 3000x3000 검사 원본이 아니라 기존 V5 소스와 문서만 존재했다. 따라서 이번 검증은 외부 이미지 없이 메모리에서 생성한 3000x3000 1채널 약신호 wafer로 수행했다. 1~2px grid, 30~70px pitch, 그리고 14px 폭의 강한 세로 noise를 넣은 두 경우에서 wafer center, X/Y pitch, 중심 corner를 복원했다. 실제 검사 이미지가 추가되면 그 폴더의 파일만 사용해 추가 검증한다.
