# Ex 10 — 캡스톤: 자율 초음파 스캔 + 학습 데이터셋 생성

**난이도** ⭐⭐⭐⭐ | **예상 시간** 6~10시간

---

## 시나리오

Ex01~09에서 배운 것을 전부 합쳐 **엔드투엔드 자율 스캔 워크플로우**를 만듭니다.
그리고 그 실행 궤적을 **정책 학습에 바로 쓸 수 있는 HDF5 데이터셋**으로 저장합니다.

```
   씬 구성        센서          제어              기록
   ────────      ──────        ──────            ──────
   테이블        room 카메라    IK 궤적 추종      관절 상태
   팬텀          wrist 카메라   힘 기반 상태기계   EE 포즈
   Franka        접촉 센서      안전 감시          접촉력
   프로브                                          이미지 2종
                                                   액션
                                                     ↓
                                            demo_0.hdf5  →  i4h 정책 학습
```

이게 완성되면 i4h `robotic_ultrasound`의 데이터 수집 단계를 **직접 구현해본 것**이
됩니다. 이후엔 i4h의 변환 스크립트로 LeRobot 포맷으로 바꿔
PI0 / GR00T N1 정책을 파인튜닝할 수 있습니다.

---

## 학습 목표

1. 여러 서브시스템(IK, 센서, 상태기계, 카메라)을 하나의 루프로 통합한다
2. **제어 주파수 ≠ 물리 주파수**를 다룬다 (물리 60~240 Hz, 기록 15~30 Hz)
3. 로봇 학습 데이터셋의 표준 구조(관측/액션/보상/종료)를 이해한다
4. HDF5로 궤적 + 이미지를 효율적으로 저장한다
5. 데이터셋 품질을 정량 검증한다 (누락, shape 불일치, 이상치)

---

## 요구사항

### 씬 (Ex01~05 통합)
- [ ] 테이블 + 팬텀 + Franka + 프로브 (Ex05 씬 재사용)
- [ ] **room 카메라**: 씬 전체를 비스듬히 내려다봄, 320×240
- [ ] **wrist 카메라**: 엔드이펙터에 자식으로 부착, 320×240
- [ ] 프로브 끝에 `ContactSensor`

### 제어 (Ex05 + Ex06 통합)
- [ ] IK 기반 목표 추종 (`set_robot_base_pose` 필수)
- [ ] 상태기계: `APPROACH → CONTACT → SWEEP → RETRACT → DONE`
- [ ] SWEEP 중 접촉력 8 N 유지 (어드미턴스)
- [ ] 안전 감시: 힘 상한, 접촉 상실, IK 실패 카운트

### 데이터 기록
- [ ] **제어 주파수 분리**: 물리는 매 스텝, 기록은 `--record-every N` 스텝마다
- [ ] 스텝마다 기록할 항목
  - `obs/joint_positions` (T, 9)
  - `obs/joint_velocities` (T, 9)
  - `obs/ee_position` (T, 3)
  - `obs/contact_force` (T, 1)
  - `obs/room_camera` (T, H, W, 3) uint8
  - `obs/wrist_camera` (T, H, W, 3) uint8
  - `actions` (T, 4) — 목표 (x, y, z) + 목표 힘
  - `rewards` (T,) — 힘이 목표 대역 안이면 1, 아니면 0
  - `dones` (T,) — 마지막 스텝만 1
- [ ] `--episodes N`개 에피소드를 수집 (에피소드마다 스캔 시작 y를 조금씩 다르게)
- [ ] `_out_ex10/scan_dataset.hdf5`로 저장 (robomimic 스타일 계층)
- [ ] **h5py가 없으면 `.npz`로 폴백** (에러로 죽지 말 것)

### 검증
- [ ] 저장한 파일을 **다시 읽어** 모든 키가 있고 T가 일치하는지 확인
- [ ] 이미지가 전부 검은색이 아닌지 (평균 밝기 확인)
- [ ] 성공 에피소드 비율, 평균 에피소드 길이, 힘 통계 리포트

---

## 데이터셋 구조 (robomimic / i4h 계열 관례)

```
scan_dataset.hdf5
└── data/                          attrs: total, num_demos, env_args(JSON)
    ├── demo_0/                    attrs: num_samples, success, scan_distance
    │   ├── obs/
    │   │   ├── joint_positions    (T, 9)   float32
    │   │   ├── joint_velocities   (T, 9)   float32
    │   │   ├── ee_position        (T, 3)   float32
    │   │   ├── contact_force      (T, 1)   float32
    │   │   ├── room_camera        (T, 240, 320, 3) uint8   [gzip]
    │   │   └── wrist_camera       (T, 240, 320, 3) uint8   [gzip]
    │   ├── actions                (T, 4)   float32
    │   ├── rewards                (T,)     float32
    │   └── dones                  (T,)     int8
    ├── demo_1/
    └── ...
```

**이 구조를 지키는 이유**: robomimic / LeRobot / i4h 변환 스크립트가
`data/demo_*/obs/*` + `actions` 형태를 전제로 만들어져 있습니다.
자기만의 구조를 만들면 변환기를 새로 짜야 합니다.

---

## 힌트

<details>
<summary>힌트 1 — wrist 카메라를 엔드이펙터에 붙이기</summary>

카메라 prim path를 로봇 링크의 **자식 경로**로 두면 자동으로 따라다닙니다.

```python
wrist_cam = Camera(
    prim_path="/World/ProbeHolder/panda_hand/wrist_cam",   # ← 링크 자식
    translation=np.array([0.0, 0.0, 0.06]),                # 손 기준 오프셋
    orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
    frequency=30,
    resolution=(320, 240),
)
```

`position`(월드 좌표) 대신 `translation`(부모 기준 로컬)을 쓰세요.
`position`을 쓰면 월드에 고정되어 팔을 따라가지 않습니다.
</details>

<details>
<summary>힌트 2 — 제어 주파수 분리</summary>

```python
RECORD_EVERY = 4          # 물리 60 Hz면 기록은 15 Hz

for step in range(max_steps):
    ...제어 계산...
    world.step(render=(step % RECORD_EVERY == 0))    # 기록할 때만 렌더
    if step % RECORD_EVERY == 0:
        record_frame()
```

**렌더링이 병목입니다.** 기록하지 않는 스텝에서는 `render=False`로 두면
데이터 수집 속도가 몇 배 빨라집니다.
</details>

<details>
<summary>힌트 3 — HDF5 저장</summary>

```python
import h5py

with h5py.File(path, "w") as f:
    data_grp = f.create_group("data")
    data_grp.attrs["total"] = total_samples
    data_grp.attrs["env_args"] = json.dumps(env_meta)

    for i, ep in enumerate(episodes):
        demo = data_grp.create_group(f"demo_{i}")
        demo.attrs["num_samples"] = len(ep["actions"])
        obs = demo.create_group("obs")
        for key, arr in ep["obs"].items():
            # 이미지는 반드시 압축. 안 하면 파일이 수 GB가 됩니다.
            kwargs = {"compression": "gzip", "compression_opts": 4} if arr.ndim == 4 else {}
            obs.create_dataset(key, data=arr, **kwargs)
        demo.create_dataset("actions", data=ep["actions"])
```

**이미지 압축을 빼먹으면** 320×240×3 × 300스텝 × 10에피소드 = 약 690 MB가 됩니다.
gzip level 4면 1/5~1/10로 줄어듭니다.
</details>

<details>
<summary>힌트 4 — 메모리 관리</summary>

에피소드 전체를 파이썬 리스트에 담았다가 마지막에 저장하면 RAM이 터집니다.
에피소드가 끝날 때마다 HDF5에 쓰고 리스트를 비우세요.

```python
for ep_idx in range(num_episodes):
    frames = run_episode(...)
    append_episode_to_hdf5(f, ep_idx, frames)
    del frames
```
</details>

<details>
<summary>힌트 5 — 에피소드가 전부 실패한다면</summary>

Ex05, Ex06을 각각 따로 돌려 어느 쪽이 문제인지 먼저 좁히세요.

1. IK가 안 풀리는가 → Ex05의 `--no-base-pose` 실험을 떠올리세요
2. 접촉이 안 잡히는가 → Ex06의 센서 `radius` / `translation` 확인
3. 힘이 진동하는가 → `--kp`를 줄이고 필터 계수를 조정
4. 카메라가 검은가 → Ex04의 조명/워밍업 체크리스트
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 성공률 | 에피소드의 **70% 이상**이 DONE까지 도달 |
| 데이터 완결성 | 모든 demo에서 모든 키의 T가 일치 |
| 이미지 품질 | room / wrist 둘 다 평균 밝기 > 20 |
| 힘 품질 | SWEEP 구간 평균 힘이 목표 ±2 N 안 |
| 파일 크기 | 에피소드당 수십 MB 이하 (압축이 걸렸다는 증거) |
| 재현성 | 저장 → 재로드 후 shape/값이 동일 |

**출력 예시**
```
=== 에피소드 0 (scan_y=+0.000) ===
[  0] APPROACH  force= 0.00 N
[ 48] APPROACH → CONTACT  (1.21 N)
[112] CONTACT → SWEEP     (8.05 N)
[698] SWEEP → RETRACT     (0.201 m)
[772] RETRACT → DONE
기록 프레임 193개, 평균 힘 8.02 N, 스캔 0.201 m  → 성공

=== 데이터셋 검증 ===
파일: _out_ex10/scan_dataset.hdf5 (34.2 MB)
demo 수: 3   총 샘플: 571
demo_0: T=193  키 8개 모두 일치
  room_camera  (193, 240, 320, 3) uint8  밝기 96.4
  wrist_camera (193, 240, 320, 3) uint8  밝기 71.2
성공률: 3/3 (100%)
PASS
```

---

## i4h로 이어가기

이 데이터셋이 만들어졌다면 다음 단계는 i4h의 학습 파이프라인입니다.

```bash
# 1) HDF5 → LeRobot 포맷 변환 (i4h가 제공하는 스크립트)
# 2) PI0 또는 GR00T N1 파인튜닝
# 3) 시뮬레이션에서 정책 평가
```

핵심은 **이 과제에서 상태기계가 만든 "정답 동작"을 신경망이 흉내내게 하는 것**
입니다. 상태기계는 팬텀 위치를 코드로 알고 있지만, 정책은 카메라 이미지만 보고
같은 동작을 만들어내야 합니다. 그래서 room/wrist 카메라 기록이 필수입니다.

**데이터 품질이 정책 품질의 상한입니다.**
- 상태기계가 만든 궤적이 흔들리면 정책도 흔들립니다.
- 에피소드 다양성이 부족하면 정책이 일반화하지 못합니다.
  → 팬텀 위치, 조명, 시작 자세를 에피소드마다 랜덤화하세요 (Ex07의 도메인 랜덤화).

---

## 확장 과제

1. **도메인 랜덤화 통합**: Ex07의 조명/재질 랜덤화를 에피소드마다 적용해
   데이터 다양성을 높이세요.
2. **실패 에피소드도 저장**: 성공만 모으면 정책이 실패에서 회복하는 법을
   못 배웁니다. `success` 플래그를 달아 함께 저장하세요.
3. **텔레오퍼레이션 모드**: 키보드/게임패드로 프로브를 직접 조종해
   사람 시연 데이터를 수집하세요. i4h는 이걸 기본 수집 방식으로 씁니다.
4. **병렬 수집**: Ex09의 클로닝을 적용해 N개 환경에서 동시에 에피소드를 모으세요.
   수집 속도가 N배가 됩니다.
5. **품질 필터**: 힘 대역 유지율, 궤적 매끄러움(저크) 등으로 저품질 에피소드를
   자동 배제하는 필터를 만드세요.
