# 📑 실습 인덱스 — 한 장으로 모아보기

이 파일은 **10개 과제 + 해답 + 문서**를 한 곳에서 찾아보도록 모은 목차입니다.
전체 소개와 4주 로드맵은 [README.md](README.md)를, 개념/설치는 [docs/](docs/)를 보세요.
여기서는 **"어떤 파일을, 어떻게 실행하고, 뭘 통과 기준으로 보는지"**만 압축했습니다.

> ⚠️ 코드는 Isaac Sim 5.1 공식 소스로 API를 대조해 작성했지만, **GPU 없는 환경에서 만든 것이라 실행 검증은 못 했습니다.** 처음 돌릴 땐 반드시 `--test`로 짧게 확인하세요. (자세한 내용은 [README.md](README.md) 상단 "검증 상태")

---

## 🗂 전체 파일 구조

```
claude_mass/
├── README.md                     # 과제집 소개 + 4주 로드맵
├── INDEX.md                      # ← 지금 이 파일 (한 장 정리)
├── tools/
│   └── check_env.py              # GPU/드라이버/i4h 요구사항 점검 (Isaac Sim 없이 실행 가능)
├── docs/
│   ├── 00-환경설정.md            # 설치 3가지 비교, 하드웨어 요구사항, RTX 3090 판정
│   ├── 01-핵심개념.md            # USD/Stage/Prim, SimulationApp 수명주기, 초보 함정 10가지
│   ├── 02-API-치트시트.md        # 자주 쓰는 import·패턴, 4.x→5.x 변경표
│   └── 03-i4h-연결.md            # Isaac for Healthcare 워크플로우 진입 순서
└── exercises/
    ├── ex01_hello_phantom/       ┐
    ├── ex02_usd_physics/         │
    ├── ...                       │ 각 폴더: README.md(문제·힌트·채점) +
    └── ex10_capstone_autoscan/   ┘ starter.py(빈칸 뼈대) + solution.py(정답+주석)
```

각 과제 폴더는 항상 **3개 파일** 구성입니다.

| 파일 | 용도 |
|---|---|
| `README.md` | 문제 설명, 요구사항 체크리스트, 힌트, **자기 채점 기준**, 확장 과제 |
| `starter.py` | `TODO`가 뚫려 있는 뼈대 코드 — 여기를 채우는 게 실습 |
| `solution.py` | 정답 + 줄줄이 주석 해설 (`--test`로 짧게 실행 가능) |

**권장 흐름**: `README.md` 읽기 → `starter.py` 채우기 → 막히면 힌트 → `solution.py` 비교 → 확장 과제.

---

## 🚀 공통 실행법

Isaac Sim을 **어떻게 설치했는지**에 따라 실행기가 다릅니다.

```bash
# (A) pip 설치(conda/venv) — conda 환경 안에서 그냥 python
conda activate isaacsim
python exercises/ex01_hello_phantom/solution.py --test

# (B) 바이너리 설치 — Isaac Sim 폴더의 python.sh 사용
./python.sh /경로/exercises/ex01_hello_phantom/solution.py --test --headless
```

거의 모든 해답에 공통으로 있는 두 플래그:

| 플래그 | 의미 |
|---|---|
| `--test` | 수백 스텝만 짧게 돌리고 채점 결과 출력 (첫 실행·검증용). **처음엔 항상 이걸로.** |
| `--headless` | GUI 창 없이 실행 (원격 서버/SSH 환경 필수). GUI로 보려면 `--gui` 또는 플래그 생략 |

> 실행 전 `python tools/check_env.py`로 GPU/드라이버부터 점검하세요.

---

## 📋 과제 원스톱 표

| # | 과제 | 의료 시나리오 | 배우는 핵심 | 대응 i4h |
|:--:|---|---|---|---|
| 01 | Hello Phantom | 시술 테이블 + 팬텀 배치 | SimulationApp 수명주기, Visual/Fixed/Dynamic 구분 | 씬 정의(`sim/`) |
| 02 | USD 계층·물리 | 도구가 트레이에서 미끄러짐 | UsdPhysics 스키마, 마찰 계수 실험 | 에셋 물리 속성 |
| 03 | 아티큘레이션 | 프로브 홀더 자세 잡기 | 배치 차원, DOF 매핑, 관절 한계 | Franka/SO-ARM/dVRK 제어 |
| 04 | 카메라 센서 | 복강경 뷰 + 깊이맵 | OpenCV intrinsics → Isaac 렌즈 변환 | room/wrist 듀얼 카메라 |
| 05 | 스캔 궤적 | 복부 초음파 경로 추종 | IK vs RMPFlow 비교 | 스캔 프로토콜 상태기계 |
| 06 | 접촉력 제어 | 프로브 접촉압 8 N 유지 | ContactSensor + 어드미턴스 + 상태기계 | 프로브-피부 접촉 유지 |
| 07 | Replicator SDG | 수술 도구 검출 데이터셋 | 도메인 랜덤화, 시맨틱 라벨 | 합성 학습 데이터 생성 |
| 08 | 커스텀 의료 에셋 | CT 세그먼트 → 장기 USD | mm→m 단위, 충돌 근사 선택 | "bring your own patient" |
| 09 | 다중 환경 클로닝 | RL 학습 준비 | GridCloner, FPS 벤치마크 | Isaac Lab GPU 병렬 RL |
| 10 | 캡스톤 | 자율 스캔 + 데이터셋 생성 | 전체 통합 + HDF5 | HDF5→LeRobot→정책 파인튜닝 |

---

## 🔎 과제별 상세 (실행 + 통과 기준)

### Ex01 — Hello Phantom
- **파일**: [README](exercises/ex01_hello_phantom/README.md) · [starter](exercises/ex01_hello_phantom/starter.py) · [solution](exercises/ex01_hello_phantom/solution.py)
- **실행**: `python exercises/ex01_hello_phantom/solution.py --test`
- **통과 기준**: 낙하한 수술 도구가 팬텀 위에 안착 (`z > 0.90`, 예: `z≈0.94`).
- **포인트**: `SimulationApp`은 **다른 isaacsim import보다 먼저** 생성해야 함. Visual(충돌X)·Fixed(고정)·Dynamic(물리 낙하) 구분.

### Ex02 — USD 계층과 물리 속성
- **파일**: [README](exercises/ex02_usd_physics/README.md) · [starter](exercises/ex02_usd_physics/starter.py) · [solution](exercises/ex02_usd_physics/solution.py)
- **실행**: `python exercises/ex02_usd_physics/solution.py --test --tilt-deg 10`
- **통과 기준**: 마찰 계수 차이가 도구의 **미끄럼 거리**에 뚜렷이 반영됨.
- **포인트**: `UsdGeom.Cube` 직접 생성 + `RigidBodyAPI`/`CollisionAPI`/`MassAPI` + `PhysicsMaterial`. XformOp 순서(T→R→S).

### Ex03 — 로봇 아티큘레이션 제어
- **파일**: [README](exercises/ex03_articulation/README.md) · [starter](exercises/ex03_articulation/starter.py) · [solution](exercises/ex03_articulation/solution.py)
- **실행**: `python exercises/ex03_articulation/solution.py --test`
- **통과 기준**: 최대 관절 오차 `< 0.02 rad` (예: ~168스텝 수렴).
- **포인트**: 배치 `Articulation` 뷰는 `apply_action(ArticulationActions(...))` (복수형). DOF 이름→인덱스 매핑, 관절 한계 클램핑.

### Ex04 — 카메라 센서와 내부 파라미터
- **파일**: [README](exercises/ex04_camera_sensor/README.md) · [starter](exercises/ex04_camera_sensor/starter.py) · [solution](exercises/ex04_camera_sensor/solution.py)
- **실행**: `python exercises/ex04_camera_sensor/solution.py --test` (GUI로 보려면 `--gui`, 이미지 저장 `--out _out_ex04`)
- **통과 기준**: RGB `(480,640,4)` uint8 / 깊이 `(480,640)` float32, HFOV ≈ 55~58°, 깊이 ≈ 카메라 z − 0.93 (±5%).
- **포인트**: OpenCV `fx,fy,cx,cy` → Isaac `focal_length`/`aperture` 변환 (cm 단위 `/10.0` 규칙).

### Ex05 — 스캔 궤적 추종 (IK / RMPFlow)
- **파일**: [README](exercises/ex05_scan_trajectory/README.md) · [starter](exercises/ex05_scan_trajectory/starter.py) · [solution](exercises/ex05_scan_trajectory/solution.py)
- **실행**: `python exercises/ex05_scan_trajectory/solution.py --test --mode ik` (비교: `--mode rmpflow`, 실험: `--no-base-pose`, `--position-only`)
- **통과 기준**: 15개 웨이포인트를 오차 내에 추종. IK vs RMPFlow(충돌 회피·부드러움) 차이 확인.
- **포인트**: Lula/RMPFlow는 **로봇 베이스 좌표계** 기준 → `set_robot_base_pose()`를 빠뜨리면 엉뚱한 곳을 품(그래서 `--no-base-pose`로 일부러 깨보기).

### Ex06 — 접촉력 기반 스캔 제어
- **파일**: [README](exercises/ex06_contact_force/README.md) · [starter](exercises/ex06_contact_force/starter.py) · [solution](exercises/ex06_contact_force/solution.py)
- **실행**: `python exercises/ex06_contact_force/solution.py --test --desired-force 8.0 --kp 4e-5` (힘 이력 저장 `--csv force.csv`)
- **통과 기준**: 상태가 `APPROACH → CONTACT → SWEEP → RETRACT → DONE` 순서로 모두 전이하고 SWEEP 구간에서 목표 힘 유지.
- **포인트**: `ContactSensor` + 어드미턴스(`dz = -kp*(desired-force)`) + 상태기계. 분기 전 안전 체크.

### Ex07 — Replicator 합성 데이터 생성
- **파일**: [README](exercises/ex07_replicator_sdg/README.md) · [starter](exercises/ex07_replicator_sdg/starter.py) · [solution](exercises/ex07_replicator_sdg/solution.py)
- **실행**: `python exercises/ex07_replicator_sdg/solution.py --test --frames 20 --out _out_ex07`
- **통과 기준**: 라벨 `{'class': ['scalpel']}` 형태 반환, 프레임마다 3클래스 검출(가려짐 제외), 조명/포즈 랜덤화 작동(밝기·bbox 위치 표준편차).
- **포인트**: `with` 블록은 **등록**이지 실행이 아님. `add_labels`(5.x, 구 `add_update_semantics` 대체), `BasicWriter`, `asyncRendering=False`.

### Ex08 — 커스텀 의료 에셋 파이프라인
- **파일**: [README](exercises/ex08_custom_medical_asset/README.md) · [starter](exercises/ex08_custom_medical_asset/starter.py) · [solution](exercises/ex08_custom_medical_asset/solution.py)
- **실행**: `python exercises/ex08_custom_medical_asset/solution.py --test --approx convexDecomposition --subdiv 4 --out _out_ex08`
- **통과 기준**: 메쉬→USD 변환 성공, mm→m 단위 변환 확인, 충돌 근사 방식별 특성 이해(`convexDecomposition` 권장 등).
- **포인트**: 충돌 근사 선택 = 정확도 vs 성능 vs 동적 지원 트레이드오프. `none`(삼각메쉬)은 정적 전용.

### Ex09 — 다중 환경 클로닝 & 벤치마크
- **파일**: [README](exercises/ex09_multi_env_cloning/README.md) · [starter](exercises/ex09_multi_env_cloning/starter.py) · [solution](exercises/ex09_multi_env_cloning/solution.py)
- **실행**: `python exercises/ex09_multi_env_cloning/solution.py --num-envs 4 --steps 100 --device cuda` (스케일링: `--num-envs 1 4 16 64`)
- **통과 기준**: `robots.count == num_envs`, 배치 shape `(N, 9)`, 환경 수↑ 시 env-steps/s 증가.
- **포인트**: `GridCloner` + 와일드카드 뷰 `/World/envs/*/Robot` + env 원점 오프셋. FPS 벤치마크. (이 과제는 벤치마크라 `--test` 대신 위 옵션 사용)

### Ex10 — 캡스톤: 자율 초음파 스캔
- **파일**: [README](exercises/ex10_capstone_autoscan/README.md) · [starter](exercises/ex10_capstone_autoscan/starter.py) · [solution](exercises/ex10_capstone_autoscan/solution.py)
- **실행**: `python exercises/ex10_capstone_autoscan/solution.py --test --episodes 3 --out _out_ex10`
- **통과 기준**: 에피소드 70%+ DONE 도달, HDF5 모든 키 T 일치, room/wrist 이미지 밝기 > 20, SWEEP 힘 목표 ±2 N, 저장→재로드 재현.
- **포인트**: Ex03·04·06을 통합. 듀얼 카메라(room 고정 + wrist는 `panda_hand` 자식), robomimic 스타일 HDF5(gzip 압축) 출력 → i4h 학습 입력 형식과 동일 역할.

---

## 🩺 다 끝낸 다음 (i4h로)

Ex10의 출력(HDF5 궤적 + 이미지)이 곧 i4h 학습 파이프라인의 입력입니다. 진입 순서와
데이터 수집→변환→파인튜닝→평가 분업(24GB는 로컬, 파인튜닝만 클라우드)은
[docs/03-i4h-연결.md](docs/03-i4h-연결.md)를 보세요.

## 💻 하드웨어 한 줄

**RTX 3090(24GB)이면 이 과제집 전부 + i4h 시뮬·추론까지 OK.** 파인튜닝(48GB)만 클라우드.
GPU별 판정은 [docs/00-환경설정.md](docs/00-환경설정.md) + `python tools/check_env.py`.
