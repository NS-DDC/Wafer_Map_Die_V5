# Weak Guide-Line Fallback

`cross_origin_mode="center_scored"`에서 가로 guide line이 약하거나 일부가 끊겨 morphology band가 충분히 생기지 않을 때 쓰는 보완 로직이다.

1. `pitch_y`는 남아 있는 band가 있으면 그 값으로, 없으면 30~70px 범위의 autocorrelation 주기로 추정한다.
2. wafer center보다 위쪽 약 `0.12 ~ 1.20 * pitch_y` 범위만 검사한다.
3. 가로 방향으로 연속된 신호의 row score를 우선하고, 약한 raw ridge row score를 보조로 더한다.
4. 가장 점수가 높은 row를 `y0` guide line으로 사용한다.
5. 두 신호 모두 없으면 `wafer_center_y - 0.46 * pitch_y`를 안전 fallback으로 사용한다.

이 fallback은 `center_scored`에서만 사용한다. `x0`은 계속 wafer center x를 사용하며, 약한 세로 noise lane을 x0으로 오인하지 않는다.
