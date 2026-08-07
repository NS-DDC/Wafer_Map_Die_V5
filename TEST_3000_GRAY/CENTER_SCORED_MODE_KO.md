# Center-Scored Cross Mode

약한 Gray 신호에서 중심 근처에 여러 십자가 후보가 생길 때 사용하는 모드다.

```python
dm = build_die_map(
    image,
    grid_method="cross",
    cross_origin_mode="center_scored",
)
```

처리 순서:

1. 반복되는 밝은 세로 noise lane에서 `pitch_x`를 측정한다.
2. 각 lane에서 wafer 중심 방향으로 `pitch_x / 2` 이동해 약한 GV 경계 `x` 후보를 만든다.
3. 가로 방향으로 연속된 thin cross row에서 `y` 후보를 만든다.
4. 모든 `(x, y)` 후보 조합에 대해 wafer 중심까지의 거리를 `pitch_x`, `pitch_y`로 정규화한다.
5. 거리가 가장 작은 조합을 최종 corner로 선택한다.

기본 `gv_boundary` 모드는 중심에 가장 가까운 세로 lane 하나와 중심 바로 위 가로 row를 사용한다. `center_scored`는 여러 후보가 경쟁하는 실제 노이즈 이미지에서 중심 가까운 교차점을 일관되게 선택하기 위한 모드다.

현재 TEST 이미지에서는 두 모드 모두 `(1480, 1482)`를 선택한다. 이는 이 이미지의 중심 후보가 이미 명확하기 때문이다. 회귀 테스트에는 기본 모드가 `(75, 70)`을 고르지만 `center_scored`가 중심에 더 가까운 `(75, 103)`을 고르는 경쟁 후보 사례도 포함했다.
