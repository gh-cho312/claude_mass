# Ex 04 — 카메라 센서와 내부 파라미터: 복강경 뷰

**난이도** ⭐⭐ | **예상 시간** 2~3시간

---

## 시나리오

수술 부위 위에 **복강경 카메라**를 배치하고 RGB 영상과 깊이맵을 캡처합니다.
실제 카메라의 **OpenCV 내부 파라미터(fx, fy, cx, cy)**를 Isaac Sim의
렌즈 파라미터(초점거리, 조리개)로 변환해, 시뮬레이션 영상이 실제 카메라와
같은 시야각을 갖도록 맞춥니다.

이게 안 맞으면 시뮬레이션에서 학습한 비전 모델이 실물에서 안 돕니다.
**sim-to-real 갭의 절반은 카메라 캘리브레이션 불일치**입니다.

---

## 학습 목표

1. `isaacsim.sensors.camera.Camera`로 카메라 prim을 만들고 초기화한다
2. **OpenCV intrinsics → Isaac Sim 렌즈 파라미터 변환**을 손으로 계산한다
3. RGB와 깊이(distance_to_image_plane)를 동시에 얻는다
4. `render=True`가 왜 필요한지 이해한다
5. 이미지를 파일로 저장하고 수치로 검증한다

---

## 요구사항

- [ ] 시술 씬 구성: 테이블 + 팬텀 + 서로 다른 높이의 도구 3개
- [ ] `/World/Endoscope`에 카메라 생성 — 해상도 `640×480`, 팬텀을 수직으로 내려다봄
- [ ] 아래 **RealSense D435i 계열 intrinsics**를 렌즈 파라미터로 변환해 적용
  ```
  width=640, height=480
  fx=612.418, fy=612.362, cx=309.723, cy=245.359
  pixel_size = 1.4 µm
  ```
- [ ] `add_distance_to_image_plane_to_frame()`으로 깊이 채널 활성화
- [ ] 시뮬레이션을 안정화시킨 뒤 RGB/깊이를 캡처
- [ ] RGB를 `_out_ex04/endoscope_rgb.png`, 깊이를 컬러맵 PNG로 저장
- [ ] **검증**: 이미지 shape, 깊이 최소/최대값이 카메라~팬텀 거리와 일치하는지
- [ ] **수평 시야각(HFOV)**을 계산해 이론값과 비교

---

## 힌트

<details>
<summary>힌트 1 — OpenCV intrinsics → Isaac 렌즈 변환식</summary>

Isaac Sim(정확히는 Omniverse Kit)의 카메라는 **물리 렌즈 모델**을 씁니다.
초점거리(mm)와 센서 크기(aperture, mm)로 시야각이 정해집니다.

```
horizontal_aperture [mm] = pixel_size[µm] × 1e-3 × width[px]
vertical_aperture   [mm] = pixel_size[µm] × 1e-3 × height[px]
focal_length        [mm] = ((fx + fy) / 2) × pixel_size[µm] × 1e-3
```

그리고 **Kit의 내부 단위는 cm 기반**이라 세터에 넣을 때 10으로 나눕니다.

```python
camera.set_focal_length(focal_length / 10.0)
camera.set_horizontal_aperture(horizontal_aperture / 10.0)
camera.set_vertical_aperture(vertical_aperture / 10.0)
```

이 `/10.0`은 NVIDIA 공식 예제(`camera_ros.py`)에도 그대로 나오는 관례입니다.
빠뜨리면 시야각이 10배 틀어집니다.
</details>

<details>
<summary>힌트 2 — 이미지가 새까맣게 나온다면</summary>

1. **조명이 없다** → `UsdLux.DistantLight` 또는 `SphereLight`를 추가하세요.
2. **`render=False`로 스텝했다** → 카메라를 읽으려면 `world.step(render=True)`.
3. **첫 프레임이라 아직 렌더가 안 끝났다** → 캡처 전에 몇십 스텝 워밍업하세요.
   RTX 렌더러는 누적 방식이라 첫 프레임은 노이즈투성이입니다.
4. **피사계심도(DoF) 때문에 흐리다** → `camera.set_lens_aperture(0.0)`으로 끄세요.
</details>

<details>
<summary>힌트 3 — 깊이 읽기</summary>

```python
camera.add_distance_to_image_plane_to_frame()   # initialize() 이후, 캡처 전에
...
frame = camera.get_current_frame()
depth = frame["distance_to_image_plane"]        # (H, W) float32, 단위 m
```

배경(하늘/무한대)은 `inf` 또는 매우 큰 값이 들어옵니다.
통계를 낼 때는 `np.isfinite()`로 걸러야 합니다.
</details>

<details>
<summary>힌트 4 — 카메라 방향 잡기</summary>

카메라는 기본적으로 자기 로컬 **-Z 방향**을 봅니다.
수직으로 아래를 보게 하려면 Y축으로 -90°(또는 +90°) 회전시킵니다.

```python
import isaacsim.core.utils.numpy.rotations as rot_utils
orientation = rot_utils.euler_angles_to_quats(np.array([0, 90, 0]), degrees=True)
```

부호가 헷갈리면 두 방향 다 렌더해보고 팬텀이 보이는 쪽을 고르세요.
GUI에서 카메라 prim을 선택하면 절두체(frustum)가 표시되어 직관적입니다.
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| RGB shape | `(480, 640, 4)` uint8 |
| 깊이 shape | `(480, 640)` float32 |
| 이미지 내용 | 새까맣지 않음 (평균 밝기 > 20) |
| 깊이 값 | 팬텀 상단까지의 거리 ≈ 카메라 z − 0.93 (±5%) |
| HFOV | 계산값 ≈ 55~58° (D435i 컬러 스트림 스펙과 유사) |
| 파일 | `_out_ex04/endoscope_rgb.png`, `endoscope_depth.png` 생성 |

**출력 예시**
```
--- 렌즈 파라미터 변환 ---
horizontal_aperture = 0.8960 mm   → set 0.08960
vertical_aperture   = 0.6720 mm   → set 0.06720
focal_length        = 0.8573 mm   → set 0.08573
계산된 HFOV = 55.2°

--- 캡처 결과 ---
RGB   shape=(480, 640, 4) dtype=uint8  mean=118.4
Depth shape=(480, 640) dtype=float32
  유효 픽셀 비율: 96.3%
  최소 거리 0.2712 m / 최대 거리 0.5501 m
  카메라 z=1.20, 팬텀 상단 z=0.93 → 기대 최소 거리 0.27 m
PASS
```

---

## 확장 과제

1. **손목 카메라 추가**: 로봇 엔드이펙터(`/World/ProbeHolder/panda_hand`) 아래에
   카메라를 자식으로 붙여 wrist view를 만드세요. i4h는 room view + wrist view
   **두 개**를 정책 입력으로 씁니다.
2. **어안 렌즈**: 실제 복강경은 시야각이 70~120°입니다.
   `focal_length`를 줄여 광각으로 만들고 왜곡을 관찰하세요.
3. **깊이 → 포인트클라우드**: intrinsics를 역으로 써서 깊이맵을 3D 점으로 변환하고,
   팬텀 상단 평면의 z가 실제로 0.93인지 검증하세요.
4. **모션 블러 / 노이즈**: 카메라를 움직이며 캡처해 실제 내시경 영상처럼
   흔들림이 생기는지 확인하세요. (도메인 랜덤화의 기초 — Ex07로 이어집니다)
