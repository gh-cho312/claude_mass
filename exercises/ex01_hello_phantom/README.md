# Ex 01 — Hello Phantom: 첫 시술실 씬 만들기

**난이도** ⭐ | **예상 시간** 1~2시간

---

## 시나리오

초음파 시술실의 최소 구성을 시뮬레이션에 올립니다.

```
        ● 스캔 목표 마커 (시각 전용, 물리 없음)
        │
   ┌────────────────┐  ← 환자 팬텀 몸통 (고정)
   │                │
 ┌─┴────────────────┴─┐  ← 시술 테이블 (고정)
 │                    │
─┴────────────────────┴─  ← 바닥
```

여기에 **수술 도구(메스)를 공중에서 떨어뜨려** 팬텀 위에 안착하는지 확인합니다.
물리가 실제로 돌고 있다는 걸 눈으로/숫자로 확인하는 게 목적입니다.

---

## 학습 목표

1. `SimulationApp` 수명주기와 **import 순서 규칙**을 몸으로 익힌다
2. `World`와 `world.scene`으로 오브젝트를 등록하는 패턴을 익힌다
3. `Visual*` / `Fixed*` / `Dynamic*` 세 계열의 차이를 이해한다
4. `world.reset()` → `world.step()` 루프를 이해한다
5. headless와 GUI 모드를 오가며 실행할 수 있다

---

## 요구사항

`starter.py`의 TODO를 채워 아래를 만족시키세요.

- [ ] `--headless`, `--test` 두 개의 CLI 인자를 받는다
- [ ] Stage 단위는 미터(`stage_units_in_meters=1.0`)
- [ ] 기본 지면(ground plane)과 `DistantLight`를 추가한다
- [ ] **시술 테이블**: `FixedCuboid`, 크기 `2.0 × 0.7 × 0.75 m`, 상판이 z=0.75에 오도록 배치
- [ ] **환자 팬텀 몸통**: `FixedCuboid`, 크기 `0.55 × 0.30 × 0.18 m`, 테이블 위에 배치
- [ ] **스캔 목표 마커**: `VisualSphere`, 반지름 0.015 m, 팬텀 상단 표면에 배치 (물리 없음)
- [ ] **수술 도구**: `DynamicCuboid`, 크기 `0.015 × 0.015 × 0.14 m`, 질량 0.05 kg,
      팬텀 위 0.35 m 높이에서 낙하
- [ ] 시뮬레이션을 진행하며 도구의 z 좌표를 주기적으로 출력
- [ ] 마지막에 **도구가 팬텀 위(z > 0.9 m)에 정지**했는지 판정하고 결과를 출력

---

## 힌트

<details>
<summary>힌트 1 — import 순서</summary>

`isaacsim.*`나 `omni.*` 모듈은 **`SimulationApp(...)`을 생성한 뒤에만** import할 수 있습니다.
하지만 `argparse`로 `--headless`를 먼저 파싱해야 `SimulationApp`에 넘길 수 있으니,
`argparse`와 `numpy`는 최상단에 둡니다.

```python
import argparse
args = ...              # 먼저 파싱

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": args.headless})

from isaacsim.core.api import World      # ← 이제부터 가능
```
</details>

<details>
<summary>힌트 2 — 위치 계산이 헷갈릴 때</summary>

`FixedCuboid`의 `position`은 **중심점**입니다. 상판을 z=0.75에 두려면
높이가 0.75인 박스의 중심은 z=0.375에 와야 합니다.

```python
TABLE_H = 0.75
table_position = np.array([0.0, 0.0, TABLE_H / 2.0])
```

팬텀(높이 0.18)을 테이블 위에 올리려면 중심은 `0.75 + 0.18/2 = 0.84`.
</details>

<details>
<summary>힌트 3 — scale vs size</summary>

`DynamicCuboid(size=1.0, scale=np.array([0.015, 0.015, 0.14]))`처럼
`size`를 1로 두고 `scale`로 실제 치수를 주는 게 관례입니다.
`size`만 쓰면 정육면체가 됩니다.
</details>

<details>
<summary>힌트 4 — 물체가 바닥을 뚫고 지나간다면</summary>

낙하 속도가 너무 빠르면 물리 스텝 사이에 충돌을 건너뛰는 **터널링**이 발생합니다.
낙하 높이를 줄이거나, 물리 스텝을 잘게 하거나(`World(physics_dt=1/120)`),
CCD(continuous collision detection)를 켜세요. 이 과제 정도의 높이라면 문제없습니다.
</details>

---

## 실행

```bash
# headless로 짧게 (권장: 첫 실행)
python solution.py --test --headless

# GUI로 눈으로 보기
python solution.py
```

바이너리 설치라면 `./python.sh solution.py --test --headless`.

---

## 자기 채점 기준

| 항목 | 확인 방법 |
|---|---|
| 씬이 정상 생성됨 | 에러 없이 시뮬레이션 루프 진입 |
| 물리가 동작함 | 도구의 z가 시간에 따라 **감소**하다가 멈춤 |
| 도구가 팬텀 위에 안착 | 최종 z ≈ 0.93 ~ 0.95 (팬텀 상단 0.93 + 도구 반높이) |
| 마커는 물리 무시 | 마커의 z가 시종일관 0.93 그대로 |
| 정상 종료 | `simulation_app.close()`까지 도달, 프로세스가 매달리지 않음 |

**최종 출력 예시**
```
[  0] tool z = 1.2800   marker z = 0.9300
[100] tool z = 0.9420   marker z = 0.9300
[200] tool z = 0.9400   marker z = 0.9300
...
PASS: 도구가 팬텀 위에 안착했습니다 (z=0.9400)
```

---

## 확장 과제

1. **GUI에서 확인**: `--headless` 없이 실행하고, Stage 창에서 `/World/Phantom`을
   클릭해 Property 패널의 `xformOp:translate` 값을 눈으로 확인하세요.
2. **마커를 물리 객체로 바꾸기**: `VisualSphere`를 `DynamicSphere`로 바꾸면
   마커도 떨어집니다. 왜 그런지 `docs/01-핵심개념.md`의 표로 설명해보세요.
3. **재질 바꾸기**: 도구의 `color`를 바꾸고, 팬텀의 색을 살구색(`[240, 200, 180]`)으로
   바꿔 실제 팬텀처럼 보이게 하세요.
4. **여러 번 리셋**: 바깥 루프를 만들어 `world.reset()`을 3번 반복하면
   도구가 매번 초기 위치로 돌아가는 것을 확인하세요.
   → `reset()`이 "초기 상태 복원"이라는 걸 체감할 수 있습니다.
