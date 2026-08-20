# Ex 09 — 다중 환경 클로닝 & 벤치마크: RL 학습 준비

**난이도** ⭐⭐⭐ | **예상 시간** 2~3시간

---

## 시나리오

강화학습이나 대량 데이터 수집을 하려면 **환경 수백 개를 GPU에서 동시에** 돌려야
합니다. 스캔 워크스테이션 하나(로봇 + 팬텀 + 프로브)를 격자로 복제하고,
환경 개수에 따라 처리량(FPS)이 어떻게 변하는지 측정합니다.

```
  env_0    env_1    env_2    env_3
  ┌───┐    ┌───┐    ┌───┐    ┌───┐
  │🤖 │    │🤖 │    │🤖 │    │🤖 │      ← GridCloner가 격자로 복제
  │▬▬ │    │▬▬ │    │▬▬ │    │▬▬ │
  └───┘    └───┘    └───┘    └───┘
  env_4    env_5    env_6    env_7
  ...
```

이 구조가 Isaac Lab의 `/World/envs/env_N/...` 이고, i4h의 RL 워크플로우가
그 위에서 돌아갑니다.

---

## 학습 목표

1. `GridCloner`로 씬 하나를 N개로 복제한다
2. **와일드카드 뷰**(`/World/envs/*/Robot`)로 N개 로봇을 한 번에 제어한다
3. 배치 텐서 shape `(N, num_dof)`를 다룬다
4. headless / CPU vs GPU 물리 / 렌더 on-off가 **처리량에 미치는 영향을 측정**한다
5. 환경별로 다른 초기 상태를 주는(domain randomization의 기초) 방법

---

## 요구사항

- [ ] `/World/envs/env_0`에 **템플릿 환경** 구성 (팬텀 + 프로브 큐브 + Franka)
- [ ] `GridCloner(spacing=2.5)`로 `--num-envs N`개 복제
- [ ] `Articulation(prim_paths_expr="/World/envs/*/Robot")` 뷰 생성 → shape `(N, 9)` 확인
- [ ] `RigidPrim(prim_paths_expr="/World/envs/*/Probe")` 뷰 생성
- [ ] **환경마다 다른 초기 관절 각도**를 한 번의 호출로 설정
- [ ] **환경마다 다른 프로브 초기 위치**를 설정 (env 원점 오프셋 반영)
- [ ] 지정 스텝 수 동안 시뮬레이션하며 **FPS와 환경·스텝 처리량**을 측정
- [ ] `--device cpu|cuda`, `--render` 여부를 인자로 받아 비교
- [ ] 리포트: 환경 수, 스텝 수, 실제 경과 시간, FPS, env-steps/s

---

## ★ 핵심: env 원점 오프셋

`GridCloner.clone()`은 각 환경의 **월드 좌표 오프셋 배열**을 반환합니다.

```python
env_positions = cloner.clone(source_prim_path="/World/envs/env_0", prim_paths=paths)
# env_positions[i] = i번째 환경의 월드 원점, 예: [2.5, 0.0, 0.0]
```

**환경 내부 로컬 좌표로 계산한 목표 위치를 월드 좌표로 바꾸려면 이 오프셋을 더해야
합니다.** 안 더하면 모든 환경이 env_0 위치를 향해 팔을 뻗습니다.

```python
world_target = local_target + env_positions[i]
```

Isaac Lab의 `env_origins`가 정확히 이것입니다.

---

## 힌트

<details>
<summary>힌트 1 — GridCloner 사용 순서</summary>

```python
from isaacsim.core.cloner import GridCloner
from isaacsim.core.utils.prims import define_prim

cloner = GridCloner(spacing=2.5)
cloner.define_base_env("/World/envs")      # 부모 컨테이너 생성
define_prim("/World/envs/env_0")           # 템플릿 prim

# ... 여기서 env_0 안에 씬을 구성 ...

paths = cloner.generate_paths("/World/envs/env", num_envs)   # ['/World/envs/env_0', ...]
env_positions = cloner.clone(source_prim_path="/World/envs/env_0", prim_paths=paths)
```

**순서가 중요합니다.** `clone()`을 부르기 전에 env_0 안의 씬 구성이 끝나 있어야
합니다. clone 이후에 env_0에 뭔가 추가하면 다른 환경에는 반영되지 않습니다.
</details>

<details>
<summary>힌트 2 — 배치 연산</summary>

```python
robots = Articulation(prim_paths_expr="/World/envs/*/Robot", name="robots")
world.scene.add(robots)
world.reset()

print(robots.count)                        # N
print(robots.get_joint_positions().shape)  # (N, 9)

# 환경마다 다른 자세를 한 번에
targets = np.tile(HOME, (num_envs, 1))                       # (N, 9)
targets[:, 0] += np.linspace(-0.4, 0.4, num_envs)            # 관절1만 환경별로 다르게
robots.set_joint_positions(targets)
```

**루프를 돌지 마세요.** 배치 API 한 번의 호출이 GPU에서 병렬 처리됩니다.
파이썬 루프로 하나씩 부르면 병렬화의 의미가 사라집니다.
</details>

<details>
<summary>힌트 3 — 물리 디바이스 전환</summary>

```python
from isaacsim.core.simulation_manager import SimulationManager
SimulationManager.set_physics_sim_device("cuda")   # 또는 "cpu"
```
`World(...)` 생성 **전에** 호출하는 게 안전합니다.

또는 `World(device="cuda", backend="torch")`로도 지정할 수 있습니다.
환경이 적을 때(<16)는 CPU가 더 빠를 수 있습니다. GPU는 커널 실행 오버헤드가
있어서 환경이 많아야 이득이 납니다. **직접 측정해서 손익분기점을 찾으세요.**
</details>

<details>
<summary>힌트 4 — FPS 측정 요령</summary>

```python
import time

# 워밍업 — 첫 스텝들은 초기화/캐시 컴파일이 섞여 있어 제외해야 한다
for _ in range(50):
    world.step(render=False)

t0 = time.perf_counter()
for _ in range(steps):
    world.step(render=render)
elapsed = time.perf_counter() - t0

fps = steps / elapsed
env_steps_per_sec = fps * num_envs
```

**워밍업을 빼먹으면** 측정값이 실제보다 훨씬 나쁘게 나옵니다.
</details>

<details>
<summary>힌트 5 — 환경이 많아지면 크래시/OOM</summary>

- `--render` 없이(헤드리스, `step(render=False)`) 돌리세요. 렌더링이 VRAM을 가장 많이 씁니다.
- 로봇 없이 팬텀+프로브만으로 먼저 스케일을 확인하세요.
- `spacing`이 너무 작으면 환경끼리 충돌합니다. 로봇 작업 반경의 2배 이상 두세요.
- 물리 solver iteration을 줄이면 빨라지지만 정확도가 떨어집니다.
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 클로닝 | `robots.count == num_envs` |
| 배치 shape | `get_joint_positions().shape == (N, 9)` |
| 환경별 차이 | 환경마다 관절1 값이 다름 (표준편차 > 0.05) |
| env 오프셋 | 프로브의 월드 x 좌표가 환경마다 `spacing`만큼 떨어져 있음 |
| 처리량 | 환경 수가 늘 때 **env-steps/s가 증가** (선형은 아니어도) |

**출력 예시**
```
--- 클로닝 ---
환경 16개, spacing 2.5 m
env 원점 x 범위: 0.0 ~ 7.5
robots.count = 16   joint_positions.shape = (16, 9)
프로브 월드 x: [0.00, 2.50, 5.00, 7.50, 0.00, ...]

--- 벤치마크 (device=cuda, render=False) ---
워밍업 50 스텝 완료
500 스텝 / 3.21 s
FPS: 155.8   env-steps/s: 2493

--- 스케일링 비교 ---
 envs |    FPS | env-steps/s
    1 |  312.4 |         312
    4 |  268.1 |        1072
   16 |  155.8 |        2493
   64 |   52.3 |        3347
```

---

## 스케일링 실험

```bash
for n in 1 4 16 64; do
  python solution.py --num-envs $n --steps 300 --device cuda
done
```

**관찰 포인트**
- FPS는 떨어지지만 **env-steps/s는 올라갑니다.** 이게 병렬화의 이득입니다.
- 어느 시점부터 env-steps/s가 포화됩니다. 그게 이 GPU의 한계입니다.
- `--device cpu`와 비교하면 손익분기점이 보입니다.
- `--render`를 켜면 처리량이 급감합니다. **학습 중에는 렌더를 끄세요.**

---

## 확장 과제

1. **환경별 도메인 랜덤화**: 환경마다 팬텀의 마찰/질량/색을 다르게 주세요.
   `isaacsim.replicator.domain_randomization`의 `physics_view` API를 쓰면
   물리 파라미터를 배치로 랜덤화할 수 있습니다.
2. **선택적 리셋**: 일부 환경만 리셋하는 함수를 만드세요.
   RL에서는 에피소드가 끝난 환경만 리셋합니다. (`reset_inds` 개념)
3. **관측 벡터 구성**: 각 환경의 (관절 각도, 프로브 위치, 목표까지 거리)를
   `(N, obs_dim)` 텐서로 모으세요. 이게 RL 환경의 `get_observations()`입니다.
4. **Isaac Lab으로 이행**: 이 과제를 Isaac Lab의 `DirectRLEnv`로 옮겨보세요.
   여기서 손으로 한 것들을 Isaac Lab이 프레임워크로 제공합니다.
