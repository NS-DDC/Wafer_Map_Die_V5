# Gray_Wafer Angle Correction 검증

`Gray_Wafer/Gray.png`을 기준으로 OpenCV의 양(반시계) 방향으로 `+0.1°`부터 `+1.0°`까지 0.1도 단위 회전 이미지를 생성한다.

## 폴더 구성

- `Gray_Wafer/Gray.png`: 제공된 실제 흑백 wafer 원본
- `Gray_Wafer/angle_cases/`: 10개의 회전 입력 이미지
- `Gray_Wafer/angle_overlays/`: 대표 3개(0.1°, 0.5°, 1.0°) 보정 후 overlay
- `Gray_Wafer/gray_angle_validation.json`: 전 케이스의 정량 결과
- `Visuals/gray_wafer_angle_validation.png`: 한글 시각화 자료

## 실행

```powershell
python make_gray_wafer_angle_cases.py
python evaluate_gray_wafer_angles.py
python make_gray_wafer_angle_visual.py
```

평가에는 `wafer_die_map_v5_refined.build_die_map(..., angle_align_method="die_render")`를 사용한다. 양의 입력 회전에는 음의 보정값이 적용되어야 하며, 보정 뒤 격자 잔여 각도는 `0.12°` 이하여야 통과다.

`0.1°`는 기본 보정 임계값보다 작은 조건이다. 이 경우 보정값이 0일 수 있지만, 잔여 격자 각도가 허용 범위에 있으면 안정 상태로 판정한다.
