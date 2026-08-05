# testWafer 가로 Street 검증

이번 검증은 `testWafer/` 안의 이미지로만 수행한다.

- 원본 입력: `testWafer/wafer_1.jpg` (로컬 원본, GitHub 용량 제한 때문에 제외)
- 실제 축소본: `testWafer/wafer_1_3000_gray.png`
- 가로 패턴 강화본: `testWafer/wafer_1_horizontal_street_3000.png`
- 판정 결과: `testWafer/testwafer_validation.json`
- 한글 시각화: `Visuals/testwafer_horizontal_pattern_validation.png`

## 재현 순서

```powershell
python make_testwafer_horizontal_pattern.py
python evaluate_testwafer_images.py
python make_testwafer_validation_visual.py
```

생성기는 축소된 실제 이미지에서 검출한 grid의 `pitch_y`와 `y0`를 사용한다. 따라서 임의의 줄무늬가 아니라 실제 die row 경계에만 2.1px 반폭의 밝은 street band를 추가한다.

GitHub에서 다시 생성할 때는 제외된 원본 JPG 대신 커밋된 `wafer_1_3000_gray.png`를 입력으로 사용한다.

평가기는 두 이미지에서 다음을 확인한다.

- die 검출 수가 500개 이상인지
- 가로 pitch가 2px 이내로 유지되는지
- 가로 street 대비가 강화본에서 증가하는지

`wafer_1.jpg`는 약 52MB이므로 GitHub 50MB 경고를 피하기 위해 `.gitignore`에 넣었다. 커밋되는 PNG와 시각화는 모두 해당 한도보다 작다.
