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

1. 반복되는 밝은 세로 noise lane에서 `pitch_x`만 측정한다.
2. 이 wafer 종류의 사전조건에 따라 `x0 = wafer_center_x`로 둔다. 밝은 세로 lane이나 반 pitch 이동값을 x0으로 쓰지 않는다.
3. 가로 방향으로 연속된 thin cross row에서 `y` 후보를 만든다.
4. `y <= wafer_center_y`인 위쪽 후보가 있으면 아래쪽 후보는 제외한다.
5. 남은 y 후보 중 wafer center에 가장 가까운 값을 최종 `y0`으로 선택한다.

기본 `gv_boundary` 모드는 중심에 가장 가까운 세로 lane 하나와 중심 바로 위 가로 row를 사용한다. `center_scored`는 x가 wafer center와 거의 같고 feature가 항상 wafer center보다 약간 위에 있는 이 wafer 유형 전용 모드다. 아래쪽 후보가 몇 px 더 가까워도 위쪽 후보를 우선한다.

현재 TEST 이미지에서 `center_scored` 결과는 `(1500, 1482)`다. 회귀 테스트에는 중심보다 1px 아래인 노이즈 row보다, center에서 15px 위에 있는 실제 feature row를 `center_scored`가 우선 선택하는 사례도 포함했다.
