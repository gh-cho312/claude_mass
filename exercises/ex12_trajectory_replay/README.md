# Ex 12 — 공개 궤적을 Isaac Sim dVRK에 재생하기

**난이도** ⭐⭐⭐⭐ | **예상 시간** 4~8시간 | **Isaac Sim 필요**

---

## 시나리오

[Ex11](../ex11_public_dataset/)에서 공개 데이터셋의 액션 스키마를 파악했습니다.
이제 그 궤적을 **i4h `robotic_surgery`의 시뮬레이션 dVRK PSM에 실제로 먹여봅니다.**

```
   공개 데이터셋 궤적          변환기            Isaac Sim dVRK PSM
   ─────────────────         ───────           ──────────────────
   (T, D) 액션 배열     →   좌표계 정합    →   env.step(actions)
   단위·프레임 미상          단위 변환           (N, 8) 텐서
                            리샘플링            [pos3, quat4, grip1]
```

## ⚠️ 이 과제가 가르치는 것은 "된다"가 아니라 "어디까지 되는가"입니다

실기기에서 기록한 궤적을 시뮬레이터에서 재생하면 **팔은 같은 경로로
움직이지만, 접촉과 변형은 전혀 재현되지 않습니다.** 시뮬레이터의 장기
모델은 실제 돼지 간과 형상·물성이 다르기 때문입니다.

즉 이건 **동작 재현(kinematic replay)** 이지 **물리 재현**이 아닙니다.
이 한계를 몸으로 이해하는 것이 과제의 핵심 목표입니다.

배경은 [docs/06](../../docs/06-데이터셋-Isaac-Sim-호환성.md)의 **L2** 절 참고.

---

## 학습 목표

1. Isaac Lab 환경의 **액션 텐서 규약**을 정확히 이해한다
2. 서로 다른 출처의 궤적을 **좌표계·단위·제어주기** 관점에서 정합한다
3. 쿼터니언 규약(wxyz vs xyzw)과 정규화를 다룬다
4. 재생 오차를 **정량 측정**한다 (명령 포즈 vs 실제 EE 포즈)
5. 시뮬레이션 재현의 한계를 실험으로 확인한다

---

## 대상 환경

i4h `robotic_surgery`의 실제 환경 ID와 액션 규약입니다.

| 환경 ID | 설명 |
|---|---|
| `Isaac-Reach-PSM-IK-Abs-v0` | PSM 리칭, **절대 포즈** 명령 |
| `Isaac-Lift-Needle-PSM-IK-Abs-v0` | 봉합침 들어올리기, 절대 포즈 |
| `Isaac-Lift-Needle-PSM-IK-Rel-v0` | 봉합침, **상대 포즈** 명령 |

### 액션 레이아웃 (8차원)

```
actions[:, 0:3]  →  EE 위치 (x, y, z)          단위: m, 베이스 프레임 기준
actions[:, 3:7]  →  쿼터니언 (w, x, y, z)      ← wxyz 순서 주의
actions[:, 7]    →  그리퍼   OPEN=+1.0 / CLOSE=-1.0
```

초기화 시 `actions[:, 3] = 1.0` (단위 쿼터니언 w) 으로 두는 것이 관례입니다.

### 씬 접근

```python
env.unwrapped.scene["robot"]       # PSM 아티큘레이션
env.unwrapped.scene["ee_frame"]    # EE 프레임 센서 → target_pos_w, target_quat_w
env.unwrapped.scene["object"]      # 니들 등 → data.root_pos_w, data.root_quat_w
env.unwrapped.scene.env_origins    # 환경별 원점 (월드 → 베이스 프레임 변환용)
```

---

## 환경 준비

```bash
conda activate robotic_surgery
export PYTHONPATH=$I4H_ROOT/workflows/robotic_surgery/scripts:$PYTHONPATH
```

먼저 데모가 뜨는지 확인하세요:

```bash
./scripts/02_smoke_test.sh reach_psm
```

---

## 요구사항

### Part A — 합성 궤적으로 파이프라인 검증 ★ 여기부터 시작

**실데이터를 붙이기 전에 반드시** 자기가 만든 궤적으로 루프를 검증하세요.
실데이터로 바로 가면 "안 움직이는" 원인이 변환 버그인지 데이터 문제인지
구분할 수 없습니다.

- [ ] 원 궤적(circle)을 코드로 생성한다 — EE 위치가 반지름 2cm 원을 그림
- [ ] 이를 8차원 액션으로 만들어 `Isaac-Reach-PSM-IK-Abs-v0` 에 먹인다
- [ ] EE가 실제로 원을 그리는지 GUI로 확인한다
- [ ] 명령 포즈와 실제 EE 포즈의 오차를 매 스텝 기록한다

### Part B — 궤적 로더

- [ ] `.npy` / `.npz` / `.csv` 궤적 파일을 읽는 로더를 만든다
- [ ] Ex11에서 만든 `compatibility.md` 대응표에 따라 열을 매핑한다
- [ ] 다음을 **명시적 옵션**으로 노출한다
  - 쿼터니언 순서 (`wxyz` / `xyzw`)
  - 위치 단위 (`m` / `mm`)
  - 그리퍼 규약 (`open=+1` / `open=0..1` / `jaw angle(rad)`)
  - 좌표계 오프셋 (평행이동 3벡터)

### Part C — 정합

- [ ] **리샘플링**: 데이터 FPS ≠ 시뮬레이터 제어 주기. 선형보간으로 맞춘다
      (쿼터니언은 선형보간하면 안 됩니다 — slerp를 쓰거나 최소한 정규화할 것)
- [ ] **정규화**: 모든 쿼터니언의 norm을 1로 맞춘다
- [ ] **워크스페이스 클리핑**: PSM이 도달할 수 없는 좌표는 잘라내고 경고
- [ ] **부드러운 시작**: 첫 프레임으로 순간이동하지 말고 현재 포즈에서 보간

### Part D — 재생 오차 측정

- [ ] 매 스텝 기록: 명령 위치, 실제 EE 위치, 위치 오차(norm), 각도 오차
- [ ] 결과를 요약 출력 — 평균/최대 오차
- [ ] 오차가 큰 구간이 궤적의 어디인지 플롯

### Part E — 한계 확인 (이 과제의 결론)

- [ ] 니들이 있는 환경(`Isaac-Lift-Needle-PSM-IK-Abs-v0`)에서 같은 궤적을 재생
- [ ] **그리퍼가 닫히는 타이밍에 니들이 실제로 잡히는가?** 관찰하고 기록
- [ ] 잡히지 않는다면 그 이유를 적는다 (씬 배치? 물성? 좌표계?)
- [ ] 결론: 동작 재현과 물리 재현의 차이를 한 문단으로 정리

---

## 힌트

<details>
<summary>AppLauncher 부트스트랩 (Isaac Lab 규약)</summary>

argparse → AppLauncher → **그 다음에** 시뮬레이션 모듈 import 순서를 지켜야 합니다.

```python
import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--disable_fabric", action="store_true", default=False)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# 여기서부터 isaaclab / gymnasium import
import gymnasium as gym
import torch
```
</details>

<details>
<summary>환경 생성과 스텝</summary>

```python
env_cfg = parse_env_cfg(
    "Isaac-Reach-PSM-IK-Abs-v0",
    device=args_cli.device,
    num_envs=args_cli.num_envs,
    use_fabric=not args_cli.disable_fabric,
)
env = gym.make("Isaac-Reach-PSM-IK-Abs-v0", cfg=env_cfg)
env.reset()

actions = torch.zeros(env.unwrapped.action_space.shape, device=env.unwrapped.device)
actions[:, 3] = 1.0          # 단위 쿼터니언 w

while simulation_app.is_running():
    with torch.inference_mode():
        obs, rew, terminated, truncated, info = env.step(actions)
```
</details>

<details>
<summary>실제 EE 포즈 읽기</summary>

```python
ee = env.unwrapped.scene["ee_frame"]
ee_pos_w  = ee.data.target_pos_w[..., 0, :]     # 월드 좌표
ee_quat_w = ee.data.target_quat_w[..., 0, :]

# 베이스(환경) 프레임으로
ee_pos_b = ee_pos_w - env.unwrapped.scene.env_origins
```
</details>

<details>
<summary>쿼터니언 slerp</summary>

선형보간 후 정규화는 각속도가 일정하지 않지만, 프레임 간격이 촘촘하면
실용적으로 충분합니다. 정확히 하려면:

```python
def slerp(q0, q1, u):
    q0 = q0 / np.linalg.norm(q0); q1 = q1 / np.linalg.norm(q1)
    d = float(np.dot(q0, q1))
    if d < 0.0:                 # 최단 경로
        q1, d = -q1, -d
    if d > 0.9995:              # 거의 같으면 선형
        q = q0 + u * (q1 - q0)
        return q / np.linalg.norm(q)
    th0 = np.arccos(d); th = th0 * u
    q2 = q1 - q0 * d
    q2 /= np.linalg.norm(q2)
    return q0 * np.cos(th) + q2 * np.sin(th)
```
</details>

---

## 검증 체크리스트

- [ ] Part A 합성 원 궤적이 GUI에서 실제로 원으로 보인다
- [ ] 재생 중 EE가 튀거나 발산하지 않는다
- [ ] 위치 오차 평균이 궤적 스케일 대비 합리적이다
- [ ] 쿼터니언 norm이 항상 1이다 (assert로 확인)
- [ ] Part E에서 **재현되지 않는 것**을 구체적으로 적었다

---

## 자주 막히는 지점

| 증상 | 원인 / 해결 |
|---|---|
| 로봇이 전혀 안 움직임 | 액션이 전부 0. `actions[:, 3] = 1.0` 을 안 넣으면 쿼터니언이 무효 |
| EE가 순간이동 후 발산 | 첫 프레임으로 점프. Part C의 "부드러운 시작" 구현 필요 |
| 회전이 이상함 | 쿼터니언 순서. Isaac은 **wxyz**, 많은 데이터셋은 xyzw |
| 위치가 1000배 어긋남 | 단위. 데이터가 mm 인데 Isaac은 m |
| 도달 못 하고 떨림 | 워크스페이스 밖. IK가 수렴 못 함 → 클리핑 필요 |
| 니들이 안 잡힘 | **정상입니다.** 이게 Part E의 관찰 대상입니다 |
| OOM | `--num_envs 1` 로 두세요. 재생은 병렬이 필요 없습니다 |

---

## 이 과제 이후

동작 재현의 한계를 확인했다면, 실기기 데이터의 올바른 쓰임새는
**시뮬레이터 재생이 아니라 정책 학습 입력(L3)** 이라는 결론에 도달하게 됩니다.
그 경로는 [docs/06](../../docs/06-데이터셋-Isaac-Sim-호환성.md)의 권장 파이프라인 절을 보세요.
