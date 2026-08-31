# Ex 11 — 공개 의료 로봇 데이터셋 다루기

**난이도** ⭐⭐ | **예상 시간** 2~3시간 | **Isaac Sim 불필요**

---

## 시나리오

Ex10에서 **직접 만든** 궤적을 HDF5로 저장했습니다. 이번엔 반대로,
**남이 만들어 공개한** 데이터를 열어서 구조를 파악합니다.

실제 연구는 대부분 여기서 시작합니다. 데이터를 새로 모으는 게 아니라,
공개 데이터셋을 받아서 "이게 뭘 담고 있고 내 문제에 쓸 수 있나"를 판단하는 일입니다.

```
    Ex10 (내가 만든 것)              Ex11 (남이 만든 것)
    ────────────────                ──────────────────
    demo_0.hdf5                      Open-H-Embodiment
      스키마를 내가 정함      →        스키마를 알아내야 함
      단위를 내가 앎                   단위가 문서에만 있음
      좌표계를 내가 정함               좌표계가 로봇마다 다름
```

이 과제가 끝나면 [Ex12](../ex12_trajectory_replay/)에서 이 궤적을
Isaac Sim의 dVRK에 실제로 먹여봅니다.

---

## 학습 목표

1. **LeRobot 데이터셋 포맷**의 구조를 이해한다 (메타 / 에피소드 / 프레임)
2. **스트리밍**으로 대용량 데이터셋을 디스크 없이 탐색한다
3. 관측·액션 텐서의 **shape과 의미**를 스스로 알아낸다
4. 궤적을 시각화해 데이터 품질을 눈으로 검증한다
5. "이 데이터가 내 시뮬레이터와 호환되는가"를 판정하는 기준을 세운다

---

## 왜 스트리밍인가

Open-H-Embodiment는 **780시간**입니다. 통째로 받으면 디스크가 감당하지
못합니다. LeRobot v3.0은 다운로드 없이 읽는 `StreamingLeRobotDataset`을
제공합니다. **먼저 스트리밍으로 훑고, 필요한 서브셋만 받는 것**이 표준 절차입니다.

---

## 환경 준비

Isaac Sim과 **무관한** 별도 환경을 씁니다. 데이터셋은 시뮬레이터 확장이
아니라 그냥 파일이기 때문입니다.

```bash
./scripts/10_install_openh.sh     # conda env "openh" (Python 3.12) + lerobot
conda activate openh
```

자세한 배경은 [docs/06](../../docs/06-데이터셋-Isaac-Sim-호환성.md) 참고.

---

## 요구사항

### Part A — 데이터셋 열기

- [ ] `StreamingLeRobotDataset`으로 Open-H-Embodiment를 연다 (다운로드 없이)
- [ ] 다음 메타 정보를 출력한다
  - 에피소드 수, 총 프레임 수, FPS
  - `features` 딕셔너리 전체 (키 이름 / shape / dtype)
- [ ] 첫 프레임을 하나 꺼내 **모든 키의 shape과 dtype**을 출력한다

### Part B — 스키마 해석

프레임에서 다음을 찾아내 보고서 형태로 정리합니다.

- [ ] **액션 벡터의 차원과 의미** — 관절각인가 EE 포즈인가? 그리퍼는 몇 번째인가?
- [ ] **상태(state) 벡터의 차원과 의미**
- [ ] **이미지 키가 몇 개인가** (카메라 대수), 해상도는?
- [ ] **자연어 지시문**이 있는가? 있다면 어떤 키에?
- [ ] 로봇 플랫폼을 식별할 수 있는가? (dVRK인지 아닌지)

> 💡 정답이 문서에 없을 수 있습니다. shape과 값의 범위로 **추론**하는 게
> 이 과제의 핵심입니다. 예: 7차원이고 값이 −π~π면 관절각일 가능성이 높고,
> 마지막 원소가 0/1 근처를 오가면 그리퍼입니다.

### Part C — 궤적 시각화

- [ ] 에피소드 하나를 끝까지 읽어 궤적을 모은다
- [ ] 다음을 플롯한다 (matplotlib, 저장은 PNG)
  - 액션 각 차원의 시간축 그래프
  - EE 위치를 찾았다면 3D 궤적
  - 그리퍼 개폐 타이밍
- [ ] 에피소드 길이 분포를 히스토그램으로 (최소 20 에피소드 샘플)

### Part D — 호환성 판정

- [ ] 이 데이터의 액션 공간이 [Ex12](../ex12_trajectory_replay/)에서 쓸
      `Isaac-Lift-Needle-PSM-IK-Abs-v0`의 **8차원 액션**
      `[위치3, 쿼터니언4, 그리퍼1]`과 어떻게 대응되는지 표로 정리
- [ ] 대응되지 않는 항목과 그 이유를 적는다 (단위? 좌표계? 차원 수?)

---

## 힌트

<details>
<summary>스트리밍 데이터셋 열기</summary>

```python
from lerobot.datasets.streaming_dataset import StreamingLeRobotDataset

ds = StreamingLeRobotDataset("nvidia/PhysicalAI-Robotics-Open-H-Embodiment")
frame = next(iter(ds))
for k, v in frame.items():
    print(k, getattr(v, "shape", type(v).__name__))
```

lerobot 버전에 따라 모듈 경로가 다를 수 있습니다.
`lerobot.common.datasets.streaming_dataset` 도 시도해 보세요.
</details>

<details>
<summary>액션 차원 추론하기</summary>

값의 통계를 보면 대부분 알 수 있습니다.

```python
import numpy as np
a = np.stack(actions)                    # (T, D)
print("범위:", a.min(0), a.max(0))
print("표준편차:", a.std(0))
```

- 값이 −1~1에 갇혀 있고 마지막 차원만 이산적 → 정규화된 액션 + 그리퍼
- 값이 −π~π → 관절각(라디안)
- 4개가 연속으로 norm 1 → 쿼터니언
- 값이 0.0x 단위의 작은 수 → 미터 단위 위치
</details>

<details>
<summary>서브셋만 받기</summary>

스트리밍으로 파악한 뒤 필요한 것만:

```bash
python tools/download_openh_subset.py --list
python tools/download_openh_subset.py --include '<서브셋>/*' --dry-run
```
</details>

---

## 검증 체크리스트

- [ ] 다운로드 없이 메타 정보를 출력했다
- [ ] 액션·상태 벡터의 각 차원이 무엇인지 근거와 함께 설명할 수 있다
- [ ] 궤적 플롯이 물리적으로 말이 된다 (튀는 값 없음, 연속적)
- [ ] Ex12의 8차원 액션과의 대응 표를 만들었다
- [ ] **호환되지 않는 부분**을 명확히 적었다 ← 이게 가장 중요

---

## 자주 막히는 지점

| 증상 | 원인 / 해결 |
|---|---|
| `StreamingLeRobotDataset` import 실패 | `pip install -U 'lerobot>=0.6.0'`. 모듈 경로가 버전마다 다름 |
| 저장소를 열지 못함 | HF 로그인 필요할 수 있음: `hf auth login` |
| 포맷이 v3.0이 아닌 듯함 | 공개된 v1과 문서상 v2 스펙이 다를 수 있음. `python tools/explore_openh.py --tree` 로 실제 구조 확인 |
| 프레임 반복이 너무 느림 | 스트리밍은 네트워크 바운드. 서브셋을 받아 로컬로 여는 편이 빠름 |

---

## 다음 단계

[Ex 12 — 공개 궤적을 Isaac Sim dVRK에 재생](../ex12_trajectory_replay/)
