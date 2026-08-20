# Ex 06 — 접촉력 기반 스캔 제어: 프로브 접촉압 유지

**난이도** ⭐⭐⭐ | **예상 시간** 3~5시간

---

## 시나리오

초음파 프로브는 **피부에 일정한 압력으로 눌려야** 영상이 나옵니다.
너무 약하면 공기층이 생겨 영상이 깨지고, 너무 세면 환자가 아프고 조직이 변형됩니다.
임상에서는 대략 **5~15 N** 범위를 씁니다.

Ex05는 위치만 제어했습니다. 여기서는 **접촉력을 측정해 목표 힘을 유지**하며
표면을 스캔하는 상태기계를 만듭니다.

```
   APPROACH          CONTACT          SWEEP              RETRACT
   ────────►         ──────►          ───────►           ◄──────
   내려간다          힘 감지          힘 유지하며 이동    들어올린다
   (힘 = 0)          (힘 ↑)          (힘 = 8±2 N)       (힘 → 0)
```

---

## 학습 목표

1. `ContactSensor`를 로봇 링크에 붙이고 접촉력을 읽는다
2. **어드미턴스 제어**(힘 오차 → 위치 보정)의 가장 단순한 형태를 구현한다
3. 로보틱스 워크플로우의 뼈대인 **상태기계**를 설계한다
4. 안전 조건(과도한 힘, 접촉 상실)에 대한 중단 로직을 넣는다
5. 힘 이력을 기록하고 목표 대역 유지율을 평가한다

---

## 요구사항

- [ ] Ex05의 씬 + IK 세팅을 재사용 (테이블, 팬텀, Franka, `set_robot_base_pose`)
- [ ] `/World/ProbeHolder/panda_hand/probe_contact`에 `ContactSensor` 부착
- [ ] `add_raw_contact_data_to_frame()`로 상세 접촉 정보 활성화
- [ ] 상태기계 5개 상태 구현: `APPROACH → CONTACT → SWEEP → RETRACT → DONE`
- [ ] **APPROACH**: 표면 위 5 cm에서 시작해 힘이 `CONTACT_THRESHOLD`(1 N)를
      넘을 때까지 매 스텝 1 mm씩 하강
- [ ] **CONTACT**: 어드미턴스 제어로 목표 힘 `8 N`에 수렴할 때까지 z 미세 조정
- [ ] **SWEEP**: 힘을 유지한 채 x 방향으로 20 cm 스캔 (속도 약 2 cm/s)
- [ ] **RETRACT**: 표면에서 10 cm 들어올림
- [ ] **안전**: 힘이 `MAX_FORCE`(25 N)를 넘으면 즉시 `RETRACT`로 전이하고 경고
- [ ] **안전**: SWEEP 중 접촉이 `LOST_CONTACT_STEPS`(60) 스텝 이상 끊기면 중단
- [ ] 리포트: 목표 대역(8±2 N) 유지율, 평균/최대 힘, 스캔 거리

---

## 힌트

<details>
<summary>힌트 1 — ContactSensor 붙이기</summary>

접촉 센서는 **강체 링크의 자식 prim**으로 붙습니다.

```python
from isaacsim.sensors.physics import ContactSensor

sensor = world.scene.add(ContactSensor(
    prim_path="/World/ProbeHolder/panda_hand/probe_contact",
    name="probe_contact",
    min_threshold=0.0,
    max_threshold=1.0e7,
    radius=0.06,                     # 감지 구의 반지름
    translation=np.array([0.0, 0.0, 0.10]),   # 손 기준 프로브 끝 위치
))
sensor.add_raw_contact_data_to_frame()
world.reset()                        # ★ reset() 이후에 읽을 수 있다
```

읽기:
```python
frame = sensor.get_current_frame()
force = float(frame.get("value", 0.0))       # 힘 크기 (N)
in_contact = bool(frame.get("in_contact", False))
```

`radius`가 너무 작으면 접촉을 놓치고, 너무 크면 엉뚱한 접촉까지 잡습니다.
`translation`은 손 프레임 기준이라 프로브 길이에 맞춰 조정하세요.
</details>

<details>
<summary>힌트 2 — 어드미턴스 제어 (가장 단순한 형태)</summary>

"힘이 모자라면 더 내리고, 과하면 올린다."

```python
force_error = desired_force - measured_force     # N
dz = -K_ADMITTANCE * force_error                 # 부호 주의!
dz = np.clip(dz, -MAX_DZ_PER_STEP, MAX_DZ_PER_STEP)
target_z += dz
```

**부호 감각**: 측정 힘이 목표보다 *작으면* `force_error > 0` → 더 눌러야 하므로
`target_z`가 *감소*해야 합니다. 그래서 앞에 마이너스가 붙습니다.

`K_ADMITTANCE`가 크면 진동하고, 작으면 수렴이 느립니다.
`1e-5 ~ 1e-4 m/N` 근처에서 시작해 조정하세요.
</details>

<details>
<summary>힌트 3 — 상태기계 구조</summary>

```python
from enum import Enum, auto

class ScanState(Enum):
    APPROACH = auto()
    CONTACT = auto()
    SWEEP = auto()
    RETRACT = auto()
    DONE = auto()

state = ScanState.APPROACH
while state is not ScanState.DONE and step < MAX_STEPS:
    force = read_force()

    if force > MAX_FORCE:            # 안전 조건은 상태 분기보다 먼저!
        state = ScanState.RETRACT

    if state is ScanState.APPROACH:
        ...
    elif state is ScanState.CONTACT:
        ...
    world.step(render=...)
```

**안전 조건을 상태 분기보다 먼저 검사**하는 게 중요합니다.
i4h의 `state machine` 데이터 수집 스크립트도 정확히 이 구조입니다.
</details>

<details>
<summary>힌트 4 — 힘이 항상 0이라면</summary>

1. `world.reset()` 이후에 센서를 읽고 있나요?
2. 센서 `radius`가 너무 작지 않나요? (0.05~0.08로 키워보세요)
3. `translation`이 실제 프로브 끝 위치와 맞나요? GUI에서 센서 구를 확인하세요.
4. 팬텀에 `CollisionAPI`가 있나요? (`FixedCuboid`는 기본으로 있습니다)
5. 아예 안 닿았을 수도 있습니다. `target_z`를 로그로 찍어 실제로 내려가는지 보세요.
</details>

<details>
<summary>힌트 5 — 힘이 진동한다면</summary>

- `K_ADMITTANCE`를 절반으로 줄이세요.
- 힘 측정에 **저역통과 필터**를 걸어보세요:
  `filtered = alpha * raw + (1 - alpha) * filtered`  (alpha ≈ 0.1)
- 물리 스텝을 잘게: `World(physics_dt=1/240, rendering_dt=1/60)`
- 팬텀의 `restitution`을 0에 가깝게 (튐 방지)
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 상태 전이 | APPROACH → CONTACT → SWEEP → RETRACT → DONE 순서로 모두 통과 |
| 접촉 감지 | APPROACH에서 힘이 1 N을 넘는 시점이 로그에 찍힘 |
| 힘 유지 | SWEEP 구간 힘의 **80% 이상이 8±2 N 대역** 안 |
| 스캔 거리 | 0.20 m 이상 이동 |
| 안전 | 힘이 25 N을 넘은 적 없음 (넘었다면 즉시 RETRACT 로그) |

**출력 예시**
```
[  0] APPROACH   z=0.980  force= 0.00 N
[ 43] APPROACH → CONTACT   (접촉 감지: 1.34 N, z=0.937)
[ 98] CONTACT → SWEEP      (힘 수렴: 8.12 N)
[300] SWEEP      x=+0.021  force= 7.84 N
[900] SWEEP → RETRACT      (스캔 완료: 0.203 m)
[980] RETRACT → DONE

=== 스캔 리포트 ===
SWEEP 스텝: 612
평균 힘 8.06 N / 최대 12.4 N / 최소 5.1 N
목표 대역(6.0~10.0 N) 유지율: 87.3%
스캔 거리: 0.203 m
PASS
```

---

## 왜 이게 중요한가

- **i4h `robotic_ultrasound`의 정책이 학습하는 것**이 바로 이 힘-위치 협조 동작입니다.
  학습 데이터를 만들려면 먼저 상태기계로 "정답 동작"을 만들어야 합니다.
  (i4h에도 `--state-machine` 모드가 있습니다)
- **안전은 별도 레이어**여야 합니다. 학습된 정책이 무엇을 출력하든,
  힘 상한을 넘으면 즉시 후퇴하는 감시 로직이 위에 있어야 합니다.
- 실물 로봇에서는 **F/T 센서**(force/torque)가 이 역할을 합니다.
  시뮬레이션의 `ContactSensor`가 그 자리를 대신합니다.

---

## 확장 과제

1. **PI 제어로 업그레이드**: 비례항만 있는 현재 구조에 적분항을 추가해
   정상상태 오차를 없애세요.
2. **곡면 추종**: 팬텀 상단을 곡면으로 바꾸고, 힘 제어만으로 곡면을 따라가는지
   확인하세요. (힘 제어의 진짜 가치가 여기서 나옵니다 — 표면 형상을 몰라도 됩니다)
3. **힘 프로파일 기록**: 힘 이력을 CSV로 저장하고 matplotlib으로 그래프를 그리세요.
   진동/오버슈트가 눈에 보입니다.
4. **호흡 모사**: 팬텀을 `sin(2π·0.25·t) × 0.01 m`로 위아래 움직이고
   (분당 15회 호흡), 힘 제어가 이를 따라가는지 보세요.
