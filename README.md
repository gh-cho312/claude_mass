# Isaac Sim for Healthcare — 입문 과제집 (10문제 + 해답)

NVIDIA **Isaac Sim**을 처음 다루는 사람이 **Isaac for Healthcare(i4h)** 워크플로우에
진입하기 전까지 필요한 기본기를 순서대로 익히도록 구성한 과제집입니다.

모든 과제는 **의료 로보틱스 맥락**(초음파 스캔, 복강경 카메라, 수술 도구, 장기 팬텀)으로
포장되어 있어서, 과제를 다 풀고 나면 i4h의 `robotic_ultrasound` / `robotic_surgery`
워크플로우 코드가 "읽히는" 상태가 됩니다.

---

## ⚠️ 먼저 읽어주세요 (검증 상태)

- 이 저장소의 코드는 **Isaac Sim 5.1 공식 소스**(`isaac-sim/IsaacSim` v5.1.0 태그의
  `source/standalone_examples`, `source/extensions`)에서 확인한 API 시그니처를 기준으로
  작성했습니다. import 경로, 클래스명, 메서드명은 실제 릴리스 소스와 대조했습니다.
- 다만 **이 코드를 작성한 환경에는 GPU와 Isaac Sim이 설치되어 있지 않아 실행 검증은 하지 못했습니다.**
  에셋 경로(예: 팬텀 USD)나 미세한 인자 차이는 여러분의 설치 버전에서 조정이 필요할 수 있습니다.
- 각 해답 스크립트는 `--test` 플래그로 짧게(수백 스텝) 돌려볼 수 있게 만들었습니다.
  처음 실행할 때는 `--test`로 먼저 돌려서 API 호환성을 확인하세요.

---

## 학습 로드맵 (4주 / 주당 8~10시간 기준)

| 주차 | 과제 | 얻는 것 |
|:--:|---|---|
| **1주** | Ex 01 ~ 03 | SimulationApp 수명주기, USD Stage/Prim, 물리 속성, 로봇 관절 제어 |
| **2주** | Ex 04 ~ 06 | 카메라 내부 파라미터, IK/모션 생성, 접촉력 기반 제어 |
| **3주** | Ex 07 ~ 09 | Replicator 합성 데이터 생성, 커스텀 의료 에셋 파이프라인, 다중 환경 병렬화 |
| **4주** | Ex 10 + i4h | 자율 스캔 캡스톤 → `i4h-workflows` 실행 및 에셋 교체 |

> 하루 1과제씩 잡으면 2주에도 끝납니다. 다만 **Ex 05(IK)와 Ex 08(에셋 파이프라인)**에서
> 대부분의 시간이 소모되니 여유를 두세요.

---

## 과제 목록

| # | 과제 | 의료 시나리오 | 핵심 API |
|:--:|---|---|---|
| 01 | [Hello Phantom](exercises/ex01_hello_phantom/) | 시술 테이블 + 장기 팬텀 배치 | `SimulationApp`, `World`, `VisualCuboid`/`DynamicCuboid` |
| 02 | [USD 계층과 물리 속성](exercises/ex02_usd_physics/) | 수술 도구가 트레이에 떨어지기 | `UsdGeom`, `RigidPrim`, `GeometryPrim`, `UsdPhysics.MassAPI` |
| 03 | [로봇 아티큘레이션 제어](exercises/ex03_articulation/) | 프로브 홀더 홈 포지션 이동 | `Articulation`, `get_dof_index`, joint position/velocity |
| 04 | [카메라 센서와 내부 파라미터](exercises/ex04_camera_sensor/) | 복강경 카메라 뷰 + 깊이맵 | `isaacsim.sensors.camera.Camera`, `render_product` |
| 05 | [스캔 궤적 추종 (IK/RMPFlow)](exercises/ex05_scan_trajectory/) | 복부 표면 초음파 스캔 경로 | `LulaKinematicsSolver`, `RmpFlow`, `ArticulationMotionPolicy` |
| 06 | [접촉력 기반 스캔 제어](exercises/ex06_contact_force/) | 프로브 접촉압 유지 상태기계 | `ContactSensor`, 상태기계 설계 |
| 07 | [Replicator 합성 데이터 생성](exercises/ex07_replicator_sdg/) | 수술 도구 검출 데이터셋 | `omni.replicator.core`, `AnnotatorRegistry`, `BasicWriter`, `add_labels` |
| 08 | [커스텀 의료 에셋 파이프라인](exercises/ex08_custom_medical_asset/) | CT 세그멘테이션 → 장기 USD | `Usd`/`UsdGeom`, convex decomposition, 단위 변환 |
| 09 | [다중 환경 클로닝 & 벤치마크](exercises/ex09_multi_env_cloning/) | RL 학습용 N개 환경 병렬화 | `GridCloner`, `Articulation` view, headless FPS 측정 |
| 10 | [캡스톤: 자율 초음파 스캔](exercises/ex10_capstone_autoscan/) | 전 과정 통합 + 데이터 로깅 | 위 전부 + HDF5 |

---

## 문서

- [00. 환경 설정](docs/00-환경설정.md) — 설치 방법 3가지 비교, GPU 요구사항, 첫 실행 검증
- [01. 핵심 개념](docs/01-핵심개념.md) — USD/Stage/Prim, SimulationApp 수명주기, 초보자가 반드시 밟는 함정 10가지
- [02. API 치트시트](docs/02-API-치트시트.md) — 자주 쓰는 import와 패턴 모음
- [03. Isaac for Healthcare로 넘어가기](docs/03-i4h-연결.md) — i4h 워크플로우 구조와 진입 순서
- [04. i4h 설치 (RTX 3090)](docs/04-i4h-설치-RTX3090.md) — `robotic_surgery` 워크플로 설치, num_envs 실측, Open-H-Embodiment 데이터셋
- [05. 문제 해결 (RTX 3090)](docs/05-문제해결-RTX3090.md) — VRAM/OOM, 디스크, 발열, 설치 실패 대응

---

## 시작하기

```bash
# 0) 환경 점검 (Isaac Sim 없이도 GPU/드라이버 확인 가능)
python tools/check_env.py

# 1) Isaac Sim의 python으로 첫 과제 해답 실행 (headless 권장)
./python.sh /path/to/exercises/ex01_hello_phantom/solution.py --test --headless
```

`python.sh`는 Isaac Sim 바이너리 설치 디렉터리에 있습니다.
pip 설치를 썼다면 그냥 conda/venv의 `python`으로 실행하면 됩니다. 자세한 내용은
[docs/00-환경설정.md](docs/00-환경설정.md)를 보세요.

---

## 과제 진행 방식

각 과제 폴더는 이렇게 구성되어 있습니다.

```
exercises/exNN_이름/
├── README.md     # 문제, 요구사항, 힌트, 자기채점 기준
├── starter.py    # 빈칸(TODO)이 있는 뼈대 코드
└── solution.py   # 해답 + 코드 주석 해설
```

**권장 순서**: `README.md` 읽기 → `starter.py`의 TODO 채우기 → 막히면 힌트 →
그래도 막히면 `solution.py` 비교 → README 하단의 **확장 과제** 도전.

---

## 라이선스 및 출처

- 코드 패턴은 [isaac-sim/IsaacSim](https://github.com/isaac-sim/IsaacSim) (Apache-2.0)의
  `source/standalone_examples`를 참고했습니다.
- 의료 워크플로우 맥락은 [isaac-for-healthcare/i4h-workflows](https://github.com/isaac-for-healthcare/i4h-workflows) (Apache-2.0)를 참고했습니다.

---

## 과제집을 끝낸 뒤 — 실제 워크플로 구축 (RTX 3090)

과제집(Ex 01~10)이 Isaac Sim 자체를 다루는 기본기라면, 이 절부터는
**실제 수술 로봇 학습 워크플로를 데스크탑에 올리는 단계**입니다.

`scripts/` 의 스크립트들이 그 과정을 자동화합니다. RTX 3090(24GB)은
`robotic_surgery` 워크플로 요구사항을 정확히 **최소선으로** 충족하므로,
문서의 예시값을 그대로 쓰면 OOM이 납니다. 스크립트는 그 여유 없는 상황을
전제로 VRAM을 실측해 튜닝합니다.

### 빠른 시작

```bash
cp config/env.example.sh config/env.sh
$EDITOR config/env.sh                    # 경로 설정

./scripts/00_preflight.sh                # 하드웨어 점검
./scripts/01_install_robotic_surgery.sh  # 설치 (40~60분)
./scripts/02_smoke_test.sh reach_psm     # 동작 확인
./scripts/03_find_max_envs.sh            # num_envs 실측 ★
./scripts/04_train_rl.sh                 # 학습
```

### 스크립트 목록

| 스크립트 | 역할 |
|---|---|
| `scripts/00_preflight.sh` | VRAM·연산능력·드라이버·디스크·RAM·OS 점검 (읽기 전용) |
| `scripts/01_install_robotic_surgery.sh` | i4h `robotic_surgery` 설치 (conda, Python 3.11) |
| `scripts/02_smoke_test.sh` | 데모 태스크 실행 — 가벼운 것부터 순서대로 |
| `scripts/03_find_max_envs.sh` | **num_envs 상한 실측** — 짧은 학습을 돌리며 VRAM 피크 측정 |
| `scripts/04_train_rl.sh` | PPO 학습 래퍼 — 항상 headless, OOM 시 대안 제시 |
| `scripts/gpu_monitor.sh` | VRAM·온도·전력 실시간 모니터 (스로틀 경고) |
| `scripts/10_install_openh.sh` | Open-H-Embodiment 환경 (별도 conda, Python 3.12) |
| `tools/explore_openh.py` | 데이터셋 탐색 — 다운로드 없이 구조·용량 파악 |
| `tools/download_openh_subset.py` | 서브셋 선택 다운로드 — 용량 계산 후 확인 |

### 무엇을 설치하는가

| | 내용 |
|---|---|
| **i4h robotic_surgery** | ORBIT-Surgical의 공식 후계자. dVRK / STAR 수술 로봇 시뮬레이션 + RL 학습 |
| **Open-H-Embodiment** | 780시간 규모 의료 로봇 데이터셋 (LeRobot 포맷). **Isaac Sim과 무관** |

> **ORBIT-Surgical 원본은 설치하지 않습니다.**
> i4h `robotic_surgery` 워크플로 README가 "This workflow originated from the
> ORBIT-Surgical framework" 라고 명시하고 있으며, 원본은
> Isaac Sim 4.1 / Isaac Lab 1.0 / Python 3.10 으로
> 현재 스택(5.0 / 2.3.0 / 3.11)과 세 항목 모두 충돌합니다.

### RTX 3090 요점 세 가지

1. **`--num_envs 4096` 을 그대로 쓰지 마세요.** 문서 예시값은 더 큰 GPU
   기준입니다. `03_find_max_envs.sh` 로 실측하세요.
2. **학습은 항상 `--headless`.** `04_train_rl.sh` 가 자동으로 붙입니다.
3. **모니터를 내장 그래픽(iGPU)으로 옮기면** 24GB를 온전히 씁니다.
   데스크탑 환경이 1~2GB를 먹으면 그만큼 `num_envs` 를 못 올립니다.

자세한 절차는 [docs/04-i4h-설치-RTX3090.md](docs/04-i4h-설치-RTX3090.md),
문제가 생기면 [docs/05-문제해결-RTX3090.md](docs/05-문제해결-RTX3090.md) 를 보세요.

> 과제집 코드와 마찬가지로, 이 스크립트들도 **실제 Isaac Sim 설치 환경에서
> 실행 검증되지 않았습니다.** 문법 검사와 전제조건 부재 시의 안전한 중단만
> 확인했습니다. 파괴적 동작은 없으며, 대용량 다운로드 전에는 용량을 계산해
> 확인을 받습니다.
