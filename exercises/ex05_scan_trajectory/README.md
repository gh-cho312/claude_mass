# Ex 05 — 스캔 궤적 추종 (IK / RMPFlow): 복부 초음파 스캔 경로

**난이도** ⭐⭐⭐ | **예상 시간** 4~6시간 (이 과제집에서 가장 오래 걸립니다)

---

## 시나리오

Franka 팔이 초음파 프로브를 들고 **팬텀 복부 표면을 따라 직선으로 스캔**합니다.
프로브 끝(tip)은 항상 표면에 수직으로 눕고, 미리 정한 웨이포인트를 순서대로 지납니다.

```
   프로브 자세 유지 (항상 아래를 향함)
        ↓  ↓  ↓  ↓  ↓
   ●──●──●──●──●──●──●     ← 스캔 웨이포인트 (팬텀 표면 위 일정 높이)
  ╭─────────────────────╮
  │      환자 팬텀        │
  ╰─────────────────────╯
```

관절 각도를 직접 주던 Ex03과 달리, 여기서는 **작업 공간(task space)에서 목표를 주고**
역기구학(IK)이 관절 각도를 풀게 합니다. 실제 스캔 프로토콜을 기술하는 방식입니다.

---

## 학습 목표

1. `LulaKinematicsSolver`로 IK를 풀고 `ArticulationKinematicsSolver`로 관절 액션 생성
2. **★ `set_robot_base_pose()`의 존재 이유** — 로봇 베이스가 원점이 아닐 때의 함정
3. `RmpFlow`로 부드럽고 충돌 회피가 되는 궤적 추종
4. IK 방식과 RMPFlow 방식의 **장단점을 직접 비교**
5. 엔드이펙터 추종 오차를 측정하고 실패 케이스(해가 없는 목표)를 처리

---

## 요구사항

- [ ] 씬: 테이블 + 팬텀 + Franka (베이스는 `(0.0, -0.42, 0.75)`, **원점이 아님**)
- [ ] 팬텀 표면 위 `y=0` 선을 따라 **x = -0.14 → +0.14, 15개 웨이포인트** 생성.
      각 웨이포인트의 z는 팬텀 상단 + 0.02 m
- [ ] 프로브 목표 자세: 엔드이펙터가 **아래(-Z)를 향하도록** 고정 쿼터니언 사용
- [ ] **모드 A (`--mode ik`)**: `LulaKinematicsSolver` + `ArticulationKinematicsSolver`
- [ ] **모드 B (`--mode rmpflow`)**: `RmpFlow` + `ArticulationMotionPolicy`
- [ ] 두 모드 모두 **`set_robot_base_pose()`를 호출**할 것
- [ ] 각 웨이포인트 도달 여부를 판정(허용 오차 5 mm)하고 도달 스텝 수 기록
- [ ] IK가 실패한 웨이포인트는 경고 출력 후 건너뛰기
- [ ] 최종 리포트: 도달한 웨이포인트 수 / 평균 위치 오차 / 최대 오차 / 총 스텝

---

## ★ 가장 중요한 함정: `set_robot_base_pose()`

Lula(및 RMPFlow)는 **로봇 베이스 좌표계 기준**으로 기구학을 계산합니다.
그런데 `compute_inverse_kinematics()`에 주는 `target_position`은
**월드(스테이지) 좌표계**입니다.

솔버는 로봇 베이스가 월드 어디에 있는지 **스스로 알지 못합니다.**
알려주지 않으면 원점에 있다고 가정합니다.

```python
# 로봇 베이스가 (0, -0.42, 0.75)에 있는데 이 줄을 빼먹으면
# IK가 42cm, 75cm씩 어긋난 곳을 풉니다. 그리고 "성공"을 반환합니다.
base_pos, base_quat = arm.get_world_pose()
kinematics_solver.set_robot_base_pose(base_pos, base_quat)
```

**증상**: IK가 `success=True`인데 팔이 엉뚱한 데로 가거나, 대부분의 목표가
"도달 불가"로 나옵니다. 로봇을 원점에 두고 테스트할 땐 잘 되다가
씬에 배치하는 순간 망가지는 전형적인 버그입니다.

---

## 힌트

<details>
<summary>힌트 1 — Single vs 뷰 클래스</summary>

**모션 생성 모듈은 `SingleArticulation`을 요구합니다.**
Ex03에서 쓴 배치형 `Articulation` 뷰를 넘기면 안 됩니다.

```python
from isaacsim.core.prims import SingleArticulation

arm = SingleArticulation(prim_path="/World/ProbeHolder", name="probe_holder",
                         position=np.array([0.0, -0.42, 0.75]))
world.scene.add(arm)
world.reset()
arm.get_joint_positions()      # shape (9,) — 배치 차원 없음!
```
</details>

<details>
<summary>힌트 2 — 솔버 설정 로드</summary>

```python
from isaacsim.robot_motion.motion_generation import (
    LulaKinematicsSolver, ArticulationKinematicsSolver, interface_config_loader,
)

cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
ik_solver = LulaKinematicsSolver(**cfg)
print(ik_solver.get_all_frame_names())     # 사용 가능한 프레임 이름 확인
art_ik = ArticulationKinematicsSolver(arm, ik_solver, "panda_hand")
```

지원 로봇 목록은 `interface_config_loader.get_supported_robots_with_lula_kinematics()`.
엔드이펙터 프레임 이름을 틀리면 즉시 에러가 납니다. `get_all_frame_names()`로 확인하세요.
</details>

<details>
<summary>힌트 3 — 프로브가 아래를 향하는 쿼터니언</summary>

Franka의 `panda_hand` 프레임은 기본적으로 +Z가 손 바깥(그리퍼 방향)입니다.
그리퍼가 월드 -Z(아래)를 보게 하려면 X축 기준 180° 회전입니다.

```python
import isaacsim.core.utils.numpy.rotations as rot_utils
down = rot_utils.euler_angles_to_quats(np.array([180.0, 0.0, 0.0]), degrees=True)
# → 대략 (0, 1, 0, 0)  in (w, x, y, z)
```

자세 제약이 너무 빡세면 IK가 실패합니다. 처음에는
`target_orientation=None`(위치만 맞춤)으로 돌려서 경로 자체가 도달 가능한지
확인한 뒤 자세를 추가하세요.
</details>

<details>
<summary>힌트 4 — compute_end_effector_pose는 회전 "행렬"을 반환한다</summary>

```python
ee_pos, ee_rot = art_ik.compute_end_effector_pose()
# ee_pos: (3,) 위치
# ee_rot: (3, 3) 회전 행렬  ← 쿼터니언이 아님!
```
쿼터니언과 비교하려면 변환이 필요합니다. 위치 오차만 볼 거면
`compute_end_effector_pose(position_only=True)`가 더 빠릅니다.
</details>

<details>
<summary>힌트 5 — RMPFlow 루프 구조</summary>

RMPFlow는 매 스텝 조금씩 목표로 다가가는 **반응형** 정책입니다.
IK처럼 한 번에 답을 주는 게 아니라, 매 물리 스텝마다 호출해야 합니다.

```python
from isaacsim.robot_motion.motion_generation import RmpFlow, ArticulationMotionPolicy

cfg = interface_config_loader.load_supported_motion_policy_config("Franka", "RMPflow")
rmpflow = RmpFlow(**cfg)
rmpflow.set_robot_base_pose(*arm.get_world_pose())      # ★ 여기도 필수
policy = ArticulationMotionPolicy(arm, rmpflow, default_physics_dt=1/60.0)

rmpflow.set_end_effector_target(target_position=wp, target_orientation=down)
for _ in range(steps):
    arm.get_articulation_controller().apply_action(policy.get_next_articulation_action())
    world.step(render=True)
```

장애물도 등록할 수 있습니다: `rmpflow.add_cuboid(phantom_cuboid, static=True)`
→ 프로브가 팬텀을 뚫고 지나가지 않게 됩니다.
</details>

<details>
<summary>힌트 6 — 모든 웨이포인트가 도달 불가라면</summary>

1. `set_robot_base_pose()`를 호출했는지 (99%의 원인)
2. 웨이포인트가 로봇 작업 반경(Franka는 약 0.85 m) 안에 있는지
3. 자세 제약을 풀어보기(`target_orientation=None`)
4. `ik_solver.get_all_frame_names()`로 엔드이펙터 이름이 맞는지
5. 테이블/팬텀과 팔이 충돌해서 못 가는 건 아닌지 (GUI로 보면 즉시 보입니다)
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| IK 모드 | 15개 중 **12개 이상** 도달, 평균 오차 < 5 mm |
| RMPFlow 모드 | 15개 중 **13개 이상** 도달, 궤적이 부드러움(관절 급변 없음) |
| base pose | `set_robot_base_pose()` 없이 돌리면 대부분 실패 → 있으면 성공 (직접 비교해볼 것) |
| 실패 처리 | 도달 불가 웨이포인트에서 크래시 없이 경고 후 진행 |

**출력 예시**
```
로봇 베이스: [ 0.000 -0.420  0.750]
사용 가능 프레임: ['panda_link0', ..., 'panda_hand', 'right_gripper', ...]

--- 모드: ik ---
 wp  0 x=-0.140  ✓ 도달  (스텝  62, 오차 1.8 mm)
 wp  1 x=-0.120  ✓ 도달  (스텝  41, 오차 2.1 mm)
 ...
 wp 14 x=+0.140  ✗ IK 해 없음 — 건너뜀

=== 리포트 (ik) ===
도달: 13/15   평균 오차 2.4 mm   최대 오차 4.7 mm   총 731 스텝
PASS
```

---

## IK vs RMPFlow — 언제 무엇을 쓰나

| | LulaKinematicsSolver (IK) | RmpFlow |
|---|---|---|
| 방식 | 목표 자세에 대한 관절해를 **한 번에** 계산 | 매 스텝 **반응적으로** 목표에 접근 |
| 충돌 회피 | ❌ 없음 | ✅ 등록한 장애물 회피 |
| 궤적 부드러움 | ✗ 웨이포인트 간 점프 가능 | ✅ 부드러움 |
| 속도 | 빠름 | 매 스텝 계산 필요 |
| 실패 시 | `success=False` 명확 | 조용히 목표 근처에서 멈춤 |
| 적합 | 사전 계획된 정적 경로 | 움직이는 목표, 장애물 있는 환경 |

**의료 시나리오 적용**
- **사전 계획된 스캔 프로토콜** → IK (경로를 미리 검증할 수 있음)
- **호흡으로 움직이는 장기 추종, 술자 텔레오퍼레이션** → RMPFlow
- i4h `robotic_ultrasound`는 학습된 정책(PI0/GR00T)이 이 자리를 대신합니다.
  이 과제는 그 정책이 **무엇을 대체하는지** 이해하기 위한 것입니다.

---

## 확장 과제

1. **`set_robot_base_pose()`를 주석 처리**하고 돌려보세요. 몇 개나 실패하나요?
   이 경험이 이 과제의 핵심입니다.
2. **장애물 등록**: `rmpflow.add_cuboid(phantom, static=True)`로 팬텀을 장애물로
   넣고, 웨이포인트 z를 팬텀 안쪽으로 낮춰보세요. 프로브가 멈추나요?
3. **곡면 스캔**: 팬텀 상단을 평면이 아니라 원기둥면으로 가정하고
   `z = z0 + r - sqrt(r² - x²)` 형태의 곡선 경로를 만드세요.
   그리고 각 지점에서 **표면 법선 방향으로 프로브를 기울이세요.**
   (실제 초음파 스캔은 이걸 해야 영상이 나옵니다)
4. **속도 제한**: 웨이포인트 간 이동 속도를 제한해 실제 스캔 속도(~2 cm/s)를 모사하세요.
