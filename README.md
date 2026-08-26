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

## 💻 하드웨어 한 줄 요약

**RTX 3090(24GB)이면 이 과제집 전부 + i4h 시뮬레이션·추론까지 됩니다.**
파인튜닝(정책 학습)만 48GB를 권장하므로 그 단계만 클라우드로 넘기세요.
A100/H100은 RT Core가 없어 초음파 레이트레이싱이 안 되니 **오히려 부적합**합니다.
자세한 내용과 GPU별 판정은 [docs/00-환경설정.md](docs/00-환경설정.md)와
`python tools/check_env.py`를 보세요.

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
