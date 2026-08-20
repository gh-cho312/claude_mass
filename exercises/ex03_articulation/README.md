# Ex 03 — 로봇 아티큘레이션 제어: 프로브 홀더 자세 잡기

**난이도** ⭐⭐ | **예상 시간** 2~3시간

---

## 시나리오

초음파 프로브를 들 로봇 팔(Franka Panda)을 씬에 올리고,
**대기 자세 → 스캔 준비 자세**로 관절을 움직입니다.
그리고 각 관절이 목표에 얼마나 정확히, 얼마나 빨리 수렴하는지 측정합니다.

이건 i4h `robotic_ultrasound`의 첫 줄에서 하는 일과 정확히 같습니다.
로봇을 씬에 붙이고, 관절 상태를 읽고, 목표 자세를 명령하는 것.

---

## 학습 목표

1. Nucleus 에셋 서버에서 로봇 USD를 가져와 씬에 **참조**로 붙인다
2. `Articulation` **뷰 클래스**의 배치 차원을 다룬다
3. `dof_names`로 관절 이름 ↔ 인덱스 매핑을 만든다
4. `world.reset()` 전후에 할 수 있는 일의 경계를 체득한다
5. 관절 한계(joint limit)를 조회하고 목표값이 범위 안인지 검증한다
6. 위치 제어 명령 후 **수렴 시간과 정상상태 오차**를 측정한다

---

## 요구사항

- [ ] `get_assets_root_path()`로 에셋 루트를 얻고, **None이면 명확한 에러 메시지와 함께 종료**
- [ ] Franka Panda를 `/World/ProbeHolder`에 참조로 추가
- [ ] `world.reset()` **전에** 로봇의 베이스를 `(0, -0.35, 0.75)`에 배치 (시술 테이블 옆)
- [ ] `reset()` 후 `dof_names`, `num_dof`, 관절 한계를 출력
- [ ] 관절 이름으로 인덱스를 찾는 헬퍼 `dof_index(name)` 작성
- [ ] **HOME 자세**로 이동 후 300 스텝 유지 → 정상상태 오차 출력
- [ ] **SCAN_READY 자세**로 이동 후 수렴까지 걸린 스텝 수 측정
- [ ] 목표 자세가 관절 한계를 벗어나면 **경고 후 클램프**
- [ ] 최대 관절 오차가 0.02 rad 미만이면 PASS

---

## 힌트

<details>
<summary>힌트 1 — 에셋 경로</summary>

```python
from isaacsim.storage.native import get_assets_root_path
from isaacsim.core.utils.stage import add_reference_to_stage

root = get_assets_root_path()
if root is None:
    carb.log_error("Isaac Sim 에셋 폴더를 찾을 수 없습니다")
    simulation_app.close(); sys.exit(1)

add_reference_to_stage(
    usd_path=root + "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
    prim_path="/World/ProbeHolder",
)
```

**경로는 릴리스마다 바뀝니다.** 404가 나면 GUI의 Content 브라우저에서
`Isaac/Robots/` 아래를 열어 실제 경로를 확인하세요.
</details>

<details>
<summary>힌트 2 — 배치 차원 (가장 많이 틀리는 부분)</summary>

`Articulation`은 여러 로봇을 한 번에 다루는 **뷰**입니다.

```python
arm = Articulation(prim_paths_expr="/World/ProbeHolder", name="probe_holder")

arm.get_joint_positions()             # shape (1, 9)  ← 앞에 배치 차원!
arm.set_joint_positions([[0.0] * 9])  # 2중 리스트!
arm.set_world_poses(positions=np.array([[0.0, -0.35, 0.75]]))   # (1, 3)
```

`set_joint_positions([0.0] * 9)`처럼 1차원을 주면 shape 에러가 납니다.
</details>

<details>
<summary>힌트 3 — reset() 전후 경계</summary>

| 시점 | 가능 | 불가능 |
|---|---|---|
| `reset()` 전 | `add_reference_to_stage`, `set_world_poses` | `get_joint_positions`, `num_dof`, `dof_names` |
| `reset()` 후 | 전부 | — |

`num_dof`가 `None`이면 십중팔구 `reset()`을 안 부른 것입니다.
</details>

<details>
<summary>힌트 4 — Franka의 DOF 순서</summary>

Franka Panda는 **9 DOF**입니다: 팔 7개 + 그리퍼 손가락 2개.

```
panda_joint1 ... panda_joint7, panda_finger_joint1, panda_finger_joint2
```

**DOF 순서는 USD의 관절 정의 순서지 이름 정렬 순이 아닙니다.**
반드시 `arm.dof_names`를 출력해 확인하고, 이름으로 인덱스를 찾으세요.
</details>

<details>
<summary>힌트 5 — 관절 한계 조회</summary>

```python
lower, upper = arm.get_dof_limits()[0, :, 0], arm.get_dof_limits()[0, :, 1]
```
`get_dof_limits()`는 `(num_envs, num_dof, 2)` 형태를 반환합니다.
</details>

<details>
<summary>힌트 6 — 로봇이 축 늘어진다면</summary>

`set_joint_positions()`는 **상태를 순간이동시키는** 함수입니다(텔레포트).
중력에 대항해 자세를 **유지**하려면 위치 제어 목표를 줘야 합니다.

**★ 여기서 배치형과 단일형의 API가 갈립니다.**

```python
# 배치형 Articulation "뷰" — get_articulation_controller()가 없다!
from isaacsim.core.utils.types import ArticulationActions        # 복수형
arm.apply_action(ArticulationActions(joint_positions=target))    # target: (N, num_dof)

# 단일형 SingleArticulation — 컨트롤러를 거친다
from isaacsim.core.utils.types import ArticulationAction         # 단수형
ctrl = single_arm.get_articulation_controller()
ctrl.apply_action(ArticulationAction(joint_positions=target))    # target: (num_dof,)
```

`Articulation` 뷰에 `get_articulation_controller()`를 부르면 `AttributeError`가 납니다.
Ex05 이후 모션 생성 모듈은 `SingleArticulation`을 쓰므로 그쪽 API를 쓰게 됩니다.

이 과제에서는 텔레포트와 위치 제어를 둘 다 써보고 차이를 관찰하는 게 목적입니다.
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 에셋 로딩 | `dof_names` 9개 출력, 이름이 `panda_joint*`로 시작 |
| 배치 차원 | shape 에러 없이 `set_joint_positions([[...]])` 동작 |
| 한계 검증 | 각 관절의 (lower, upper)가 출력되고 목표가 범위 내 |
| 수렴 | SCAN_READY 자세에서 최대 오차 < 0.02 rad |
| 수렴 속도 | 300 스텝(약 5초) 이내 수렴 |

**출력 예시**
```
로봇: 9 DOF
  [0] panda_joint1          limit [-2.897,  2.897]  target  0.000
  [1] panda_joint2          limit [-1.763,  1.763]  target -0.600
  ...
--- HOME 자세 유지 ---
정상상태 최대 오차: 0.0031 rad (panda_joint4)
--- SCAN_READY 자세 이동 ---
수렴: 168 스텝 (기준 0.02 rad)
최대 오차: 0.0094 rad
PASS
```

---

## 확장 과제

1. **속도 제어**: `set_joint_velocities()`로 관절 1을 일정 속도로 돌려보세요.
   위치 제어와 어떻게 다른가요?
2. **게인 튜닝**: `arm.set_gains(kps=..., kds=...)`로 stiffness/damping을 바꿔
   수렴 속도와 오버슈트가 어떻게 변하는지 관찰하세요.
3. **토크 측정**: `get_measured_joint_efforts()`로 각 자세에서 중력 보상에
   얼마나 큰 토크가 필요한지 출력하세요. 팔을 뻗을수록 관절 2, 4의 토크가 커집니다.
4. **그리퍼 열기/닫기**: `panda_finger_joint1/2`를 0.0(닫힘) ↔ 0.04(열림)으로
   움직여 프로브를 쥐는 동작을 만드세요.
