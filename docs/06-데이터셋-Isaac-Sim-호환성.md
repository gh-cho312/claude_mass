# 06. Isaac Sim에서 쓸 수 있는 의료 로봇 데이터셋

> [04. i4h 설치](04-i4h-설치-RTX3090.md)로 환경을 갖춘 뒤, 어떤 공개
> 데이터셋을 실제로 붙일 수 있는지 정리한 문서입니다.

---

## ⚠️ 먼저 — "Isaac Sim에서 이용 가능"은 네 가지 다른 뜻입니다

**Isaac Sim은 데이터셋 로더가 아닙니다.** "데이터셋을 Isaac Sim에서 연다"는
개념은 대부분 성립하지 않습니다. 실제로 성립하는 것은 다음 네 층위이고,
데이터셋마다 도달 가능한 층이 다릅니다.

| 층위 | 의미 | 필요 조건 |
|:--:|---|---|
| **L1** | Isaac Sim이 **직접 로드**하는 씬·로봇·장기 모델 | **USD 포맷**이어야 함 |
| **L2** | Isaac Sim 안에서 궤적을 **재생(replay)** | 로봇 모델·액션 공간 일치 + 포맷 변환 |
| **L3** | Isaac Sim으로 만든 정책의 **학습 입력** | LeRobot / RLDS 포맷이면 됨. **시뮬레이터와 무관** |
| **L4** | 비전-언어 백본 사전학습용 | 액션 라벨 없음. 정책 학습 불가 |

앞선 조사에서 나열한 데이터셋 대부분은 **L3**입니다. L1은 사실상 하나뿐이고,
L2는 직접 변환기를 써야 합니다.

---

## 한눈에 보기

| 데이터셋 | L1 | L2 | L3 | L4 | 포맷 | 라이선스 |
|---|:--:|:--:|:--:|:--:|---|---|
| **i4h Asset Catalog** | ✅ | — | — | — | **USD** | Apache-2.0 (일부 제한) |
| **Open-H-Embodiment** | ❌ | ⚠️ | ✅ | ✅ | LeRobot v3.0 | 확인 필요 |
| **SurgVLA-Bench** | ❌ | ❌ | ✅ | — | RLDS + LeRobot | 미확인 |
| **ImitateCholec** | ❌ | ⚠️ | ✅ | ✅ | 비디오 + 키네마틱 | **CC BY 4.0** |
| **CRCD (Expanded)** | ❌ | ⚠️ | ✅ | ✅ | 비디오 + 키네마틱 + 페달 | 논문 확인 |
| **JIGSAWS** | ❌ | ⚠️ | △ | ✅ | 비디오 + 76-D 키네마틱 | 신청 필요 |
| EndoVis / SurgVU / SurgVLM / SurgPub | ❌ | ❌ | ❌ | ✅ | 비디오(+텍스트) | 각기 다름 |

- ✅ 바로 가능 · ⚠️ 변환기 자작 필요 · △ 제한적 · ❌ 불가

---

## L1 — Isaac Sim이 직접 로드하는 유일한 것

### i4h Asset Catalog

공개 "데이터셋" 중 **Isaac Sim이 그대로 여는 것은 이것뿐**입니다. 궤적
데이터가 아니라 **USD 3D 에셋**입니다.

| 항목 | 내용 |
|---|---|
| 내용 | 수술 로봇(dVRK, STAR 등), 해부 모델, 의료 장비, 병원 환경, 물리 설정 |
| 포맷 | **USD** — Isaac Sim 네이티브 |
| 라이선스 | 카탈로그 Apache-2.0. **Lightwheel AI 제공 변형체 에셋은 비상업 R&D 전용** |
| 저장소 | `github.com/isaac-for-healthcare/i4h-asset-catalog` |

**다운로드**

```bash
git clone https://github.com/isaac-for-healthcare/i4h-asset-catalog.git
cd i4h-asset-catalog
pip install -e .

# 로봇 에셋만 받기
i4h-asset-retrieve --sub-path Robots

# 커스텀 경로로
i4h-asset-retrieve --force --download-dir ~/my-assets
```

캐시 위치는 `~/.cache/i4h-assets/<SHA256_HASH>` 입니다. 디스크가 빠듯하면
`I4H_ASSET_DOWNLOAD_DIR` 환경변수로 다른 파티션에 두세요.

**코드에서 쓰기**

```python
from i4h_asset_helper import BaseI4HAssets

class MyAssets(BaseI4HAssets):
    dVRK_ECM = "Robots/dVRK/ECM/ecm.usd"

my_assets = MyAssets()
print(my_assets.dVRK_ECM)   # 로컬 캐시 경로 반환
```

> `robotic_surgery` 워크플로를 설치했다면 이 에셋은 첫 실행 시 자동으로
> 내려받습니다. 별도로 받을 필요는 보통 없습니다.

---

## L3 — 정책 학습 입력 (가장 현실적인 경로)

여기가 **실제로 대부분의 작업이 일어나는 층**입니다. 데이터셋이 LeRobot
포맷이면 Isaac Sim과 아무 상관없이 GR00T / openpi 파인튜닝에 그대로 들어갑니다.

```
Open-H-Embodiment (LeRobot)  ─┐
SurgVLA-Bench (LeRobot/RLDS) ─┼─→ GR00T / openpi 파인튜닝 → 정책
i4h Arena 자체 수집 데이터    ─┘                              │
                                                              ↓
                                            Isaac Sim(robotic_surgery)에서 평가
```

Isaac Sim은 **평가·추가 학습 무대**이지 데이터 저장소가 아닙니다.

### ① Open-H-Embodiment — 규모 최대, 우선순위 1

| 항목 | 내용 |
|---|---|
| 규모 | **780시간**, 119개 서브 데이터셋 |
| 범위 | 50+ 기관, **20개 로봇 플랫폼**, 33개 태스크 계열, **5종 환경(디지털 시뮬레이션 ~ 실제 임상 시술)** |
| 도메인 | 수술 매니퓰레이션 + 로봇 초음파 + 내시경 |
| 포맷 | LeRobot dataset v3.0 (v2 스펙 기준, LeRobot 0.6.0 / Python 3.12) |
| 특이점 | **실패·복구 스플릿 별도**, per-timestep 지시문, 멀티카메라 캘리브레이션 |
| 부속 | **GR00T-H**(오픈 의료 VLA), Cosmos-H-Surgical-Simulator |

**다운로드**: HuggingFace `nvidia/PhysicalAI-Robotics-Open-H-Embodiment`

```bash
conda activate openh
python tools/explore_openh.py            # 먼저 구조 파악 (다운로드 없음)
python tools/download_openh_subset.py --list
python tools/download_openh_subset.py --include '<서브셋>/*' --dry-run
```

> ⚠️ **780시간을 통째로 받지 마세요.** 반드시 서브셋 단위로 받으세요.
> `docs/04` 7절 참고.

> ⚠️ 라이선스가 출처마다 다르게 표기됩니다 (HF: CC-BY-4.0 / GitHub: OpenMDW-1.1).
> NVIDIA 호스팅이므로 NVIDIA ToS도 함께 적용됩니다. 사용 전 HF 카드에서 직접 확인하세요.

**dVRK 서브셋에 주목하세요.** 20개 플랫폼 중 dVRK 데이터는 i4h
`robotic_surgery`가 시뮬레이션하는 바로 그 로봇입니다. L2(재생)를 노린다면
여기가 가장 가능성이 높습니다.

### ② SurgVLA-Bench — VLA 파이프라인 검증용

| 항목 | 내용 |
|---|---|
| 규모 | 800+ 궤적, 8개 태스크, 약 40,000 액션 프레임 |
| 환경 | **SurRoL (PyBullet 기반)** ← Isaac Sim 아님 |
| 포맷 | **RLDS + LeRobot 둘 다** |
| 평가 대상 | OpenVLA, π₀, π₀.₅, SmolVLA |

**다운로드**: GitHub `VCL-HNU/SurgVLA`, HuggingFace `Kanden1112/surg-vla-dataset`

> ❗ **Isaac Sim에서 이 벤치마크를 돌릴 수 없습니다.** 환경이 SurRoL(PyBullet)
> 전용이라 씬·에셋이 이식되지 않습니다. **데이터(L3)는 쓸 수 있지만
> 평가 루프는 SurRoL을 따로 설치해야 합니다.**
> 자세한 비교는 [docs/04](04-i4h-설치-RTX3090.md) 참고.

---

## L2 — Isaac Sim에서 재생하기 (변환기 자작 필요)

dVRK 키네마틱이 담긴 데이터셋은 **이론상** i4h `robotic_surgery`의
시뮬레이션 dVRK에 먹여 재현할 수 있습니다. 다만 **기성 변환기가 없습니다.**

### i4h가 실제로 제공하는 것

`workflows/agentic` 워크플로의 데이터 툴체인:

| 기능 | 방향 |
|---|---|
| 텔레오퍼레이션 기록 → HDF5 | 생성 |
| **HDF5 재생 (Isaac Sim 내)** | ✅ 재생 |
| 궤적 미믹리 (노이즈 추가 확장) | 증강 |
| **Arena HDF5 → LeRobot 변환** | **내보내기 방향만** |
| GR00T / openpi 파인튜닝 | LeRobot 소비 |
| Qwen3-VL-8B 성공 라벨링 | 주석 |

**핵심 제약**: LeRobot 변환은 `Arena HDF5 → LeRobot` **한 방향뿐**입니다.
외부 LeRobot 데이터셋을 Isaac Sim 안에서 재생하는 경로는 기본 제공되지
않습니다. 하려면 `외부 데이터 → Arena HDF5 스키마` 변환기를 직접 써야 합니다.

지원 로봇: SO-ARM 101, Unitree G1, Franka(초음파 간 스캔),
**dVRK PSM(수술 리칭, 블록/니들 리프팅)**, STAR

```bash
workflows/agentic/setup.sh [--with-cosmos]
workflows/agentic/scripts/e2e/run.sh --env scissor_pick_and_place
```

> ⚠️ **드라이버 요구가 다릅니다.** `agentic` 워크플로는 **580.65.06 이상**을
> 요구합니다 (`robotic_surgery`는 535.129.03 이상). RTX 3090에서 `agentic`을
> 쓰려면 드라이버를 먼저 확인하세요. 디스크는 약 30GB 추가.

### L2 후보 데이터셋

#### ImitateCholec — 실기기 데이터 중 최우선

| 항목 | 내용 |
|---|---|
| 규모 | **18,000+ 데모**, 약 20시간, 34건 ex vivo 돼지 담낭절제술 |
| 로봇 | **dVRK** ← i4h가 시뮬레이션하는 로봇과 동일 |
| 구성 | 클리핑·커팅 구간을 17개 세부 태스크로 분절 |
| 특이점 | **정상 실행 + 복구 조작 모두 수록** |
| 라이선스 | **CC BY 4.0** — 가장 깨끗함 |

**다운로드**: Johns Hopkins Research Data Repository
DOI [`10.7281/T1PF3FYK`](https://doi.org/10.7281/T1PF3FYK)
논문: [Nature *Scientific Data* (2025)](https://www.nature.com/articles/s41597-025-06526-z)

라이선스·접근성·규모·로봇 일치도를 종합하면 **실기기 데이터로는 이게
현재 최선**입니다.

#### CRCD (Expanded) — 콘솔 조작까지

dVRK, ex vivo 돼지 간, 외과의 7명. **키네마틱 + 페달 입력 + 내시경 움직임
타임스탬프**를 모두 기록한 거의 유일한 데이터셋입니다. 확장판에는
세그멘테이션·키포인트 어노테이션 추가.

**다운로드**: [arXiv 2312.01183](https://arxiv.org/abs/2312.01183) /
[Expanded: arXiv 2412.12238](https://arxiv.org/abs/2412.12238) 논문의 링크 참조

#### JIGSAWS — 고전 베이스라인

da Vinci, 외과의 8명 × 3난이도, suturing / knot-tying / needle-passing.
**76차원 키네마틱 @ 30Hz** (PSM/MTM 양팔 위치·회전행렬·선속도·각속도·그리퍼 각도)
+ 비디오 + 제스처 트랜스크립트.

**자연어 지시문이 없어** VLA 학습에는 그대로 쓰기 어렵습니다. 제스처
트랜스크립트를 언어 라벨로 변환하는 접근이 흔합니다. 벤치마크 비교용으로 유효.

**다운로드**: JHU-ISI 배포 페이지에서 신청
([논문 PMC5559351](https://pmc.ncbi.nlm.nih.gov/articles/PMC5559351/))

### L2 변환 시 실제로 부딪히는 문제

1. **액션 공간 정의 불일치** — 같은 dVRK라도 데이터셋의 좌표계·단위·기준
   프레임이 시뮬레이터 설정과 다릅니다. 캘리브레이션이 필요합니다
2. **비디오-키네마틱 동기화** — 타임스탬프 정렬 품질이 데이터셋마다 다릅니다
   (CRCD가 이 지점을 특별히 신경 쓴 케이스)
3. **씬이 재현되지 않음** — 실제 돼지 간의 형상·물성은 시뮬레이터 장기 모델과
   다릅니다. 궤적을 그대로 재생해도 **접촉·변형이 어긋납니다.**
   순수 키네마틱 재현은 되지만 물리적으로 같은 결과는 나오지 않습니다
4. **제어 주기 차이** — JIGSAWS 30Hz vs 시뮬레이터 물리 스텝

> 3번이 가장 근본적입니다. **실기기 궤적을 시뮬레이터에서 재생하는 것은
> "동작 확인"까지이지 "물리적 재현"이 아닙니다.** 실기기 데이터는 L3(정책
> 학습 입력)로 쓰고, 시뮬레이터는 별도로 자체 데이터를 생성하는 편이
> 실무적으로 훨씬 낫습니다.

---

## L4 — 액션 없음, 비전-언어 백본용

정책 학습에 **직접 쓸 수 없습니다.** 다만 VLA의 비전-언어 백본을 의료
도메인에 적응시키는 데는 유용합니다.

| 데이터셋 | 내용 |
|---|---|
| EndoVis 2018 | 로봇 수술 비디오 14편 (MICCAI 챌린지) |
| SurgVU / SurgToolLoc | Intuitive 주최 챌린지 (2022–2025), 도구 위치 |
| SurgVLM | 대형 수술 VLM + 평가 벤치마크 |
| SurgPub-Video | 대규모 수술 비디오-언어 |
| GP-VLS / SurgXBench / CAT-ViL | 수술 VQA·설명 |

---

## 권장 파이프라인

```
[1] 백본 도메인 적응        SurgVLM / SurgPub-Video          (L4)
         ↓
[2] VLA 정책 학습           Open-H-Embodiment + ImitateCholec (L3)
         ↓                  → GR00T-H / GR00T / openpi
[3] 시뮬레이터 평가·RL      i4h robotic_surgery              (L1 에셋)
         ↓
[4] 데이터 부족분 자체 생성  i4h agentic (텔레오퍼레이션 → HDF5 → LeRobot)
```

**RTX 3090 기준 현실적 시작점:**

| 목표 | 데이터셋 | 이유 |
|---|---|---|
| 일단 돌려보기 | i4h Asset Catalog | 이미 설치됨, 추가 작업 0 |
| 실기기 데이터로 학습 | **ImitateCholec** | CC BY 4.0, dVRK 일치, 18k 데모 |
| 스케일 | Open-H-Embodiment 서브셋 | 반드시 부분 다운로드 |
| VLA 벤치마킹 | SurgVLA-Bench | 단, **SurRoL 별도 설치 필요** |
| 데이터 직접 생성 | i4h agentic | 드라이버 580.65.06+ 확인 |

---

## 정리 — 오해하기 쉬운 세 가지

1. **"Isaac Sim에서 데이터셋을 연다"는 개념은 거의 없습니다.** USD 에셋만
   직접 로드되고, 나머지는 전부 학습 파이프라인 쪽 이야기입니다.
2. **SurgVLA-Bench는 Isaac Sim에서 못 돌립니다.** 데이터는 쓸 수 있지만
   환경이 SurRoL 전용입니다.
3. **실기기 궤적을 시뮬레이터에서 재생해도 물리적으로 같지 않습니다.**
   L2는 생각보다 쓸모가 제한적이고, 대부분의 실무는 L3에서 이뤄집니다.

---

## 검증 상태

이 문서의 정보는 공개 저장소 README와 문서를 교차 확인해 작성했습니다.
다만 다음은 **실제로 받아서 확인하지 못했습니다**:

- Open-H-Embodiment v1의 정확한 디렉터리 구조와 포맷 (HF 직접 접속 불가 환경)
- 각 데이터셋의 실제 액션 공간 스키마
- L2 변환의 실현 가능성 (변환기를 작성·실행해보지 않음)

실제 다운로드 후 구조가 다르면 `tools/explore_openh.py --tree` 로 확인하고
이 문서를 갱신하세요.

---

## 참고 링크

**에셋 / 워크플로**
- [i4h-asset-catalog](https://github.com/isaac-for-healthcare/i4h-asset-catalog)
- [i4h-workflows](https://github.com/isaac-for-healthcare/i4h-workflows) ·
  [robotic_surgery](https://github.com/isaac-for-healthcare/i4h-workflows/tree/main/workflows/robotic_surgery) ·
  [agentic](https://github.com/isaac-for-healthcare/i4h-workflows/tree/main/workflows/agentic)
- [Isaac for Healthcare 문서](https://isaac-for-healthcare.github.io/i4h-docs/)

**데이터셋**
- [Open-H-Embodiment](https://github.com/open-h/open-h-embodiment) ·
  [HuggingFace](https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-Open-H-Embodiment) ·
  [arXiv 2604.21017](https://arxiv.org/abs/2604.21017)
- [ImitateCholec (Nature Sci Data)](https://www.nature.com/articles/s41597-025-06526-z) ·
  [JHU Repository](https://doi.org/10.7281/T1PF3FYK)
- [SurgVLA-Bench](https://github.com/VCL-HNU/SurgVLA) ·
  [arXiv 2606.29247](https://arxiv.org/abs/2606.29247)
- [CRCD](https://arxiv.org/abs/2312.01183) ·
  [Expanded CRCD](https://arxiv.org/abs/2412.12238)
- [JIGSAWS](https://pmc.ncbi.nlm.nih.gov/articles/PMC5559351/)

**시뮬레이터**
- [ORBIT-Surgical](https://arxiv.org/abs/2404.16027) (robotic_surgery의 전신)
- [SurRoL](https://github.com/med-air/SurRoL) (SurgVLA-Bench 실행에 필요)

**포맷**
- [LeRobotDataset v3.0](https://huggingface.co/docs/lerobot/lerobot-dataset-v3)
