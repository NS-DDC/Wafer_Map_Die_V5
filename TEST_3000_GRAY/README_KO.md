# TEST 3000x3000 Gray 변환 및 Cross Grid 결과

입력은 `E:\mirero\Claude_V5\원본\Claude_V5\TEST\wafer_1.jpg` 한 장만 사용했다. 원본 JPEG는 약 52MB이므로 GitHub에는 올리지 않고, `INTER_AREA` 방식으로 만든 3000x3000 1채널 Gray 결과만 포함한다.

## 포함 파일

| 파일 | 설명 |
| --- | --- |
| `wafer_1_gray_3000.png` | 3000x3000 1채널 Gray 테스트 이미지 |
| `wafer_1_cross_overlay_3000.png` | 검출된 grid/edge/wafer circle/corner overlay |
| `wafer_1_gray_preview.png` | GitHub에서 빠르게 확인할 수 있는 1000px Gray 미리보기 |
| `wafer_1_cross_overlay_preview.png` | 1000px overlay 미리보기 |

## 적용 파라미터

```python
dm = build_die_map(
    gray_3000,
    grid_method="cross",
    min_pitch=30,
    max_pitch=70,
    notch_align=False,
    clip_partial_edge=False,
    edge_clip_margin_px=0,
    edge_mode="circle",
)
```

## 판정 결과

| 항목 | 결과 |
| --- | --- |
| 입력 | 10000x10000 BGR JPEG -> 3000x3000 Gray PNG |
| wafer center | `(1500, 1500)` px |
| wafer radius | `1412` px |
| `pitch_x` | `44.979` px |
| `pitch_y` | `39.000` px |
| corner `(x0, y0)` | `(1502, 1492)` px |
| map Die 수 | `3564` (원에 걸치는 partial Die 포함) |
| EDGE Die 수 | `124` |

![3000px Gray preview](wafer_1_gray_preview.png)

![Cross grid overlay preview](wafer_1_cross_overlay_preview.png)

초록색은 wafer 원 안에 완전히 포함된 일반 Die, 빨간색은 **wafer 원을 한 모서리라도 넘는 모든 box**다. 즉 이 결과에서 EDGE는 최외곽 ring이 아니라 `is_edge_partial=True`인 circle-crossing Die만 의미한다. 하늘색은 wafer circle, 자홍색 십자는 선택한 central grid corner다.

실사용에서도 같은 EDGE 정의가 필요하면 `clip_partial_edge=False`, `edge_clip_margin_px=0`, `edge_mode="circle"`을 함께 사용한다. partial Die를 결과 map에서 제거해야 하는 검사 흐름에서는 `clip_partial_edge=True`로 바꾸되, 그 경우 partial EDGE box 자체는 `dm.dies`에서 제외된다.
