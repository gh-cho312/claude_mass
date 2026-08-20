# Ex 07 — Replicator 합성 데이터 생성: 수술 도구 검출 데이터셋

**난이도** ⭐⭐⭐ | **예상 시간** 3~4시간

---

## 시나리오

수술 도구(scalpel / forceps / clamp)를 자동 검출하는 비전 모델을 학습시키려는데
라벨링된 실제 수술 영상이 없습니다. **시뮬레이션에서 정답이 딸린 데이터를 찍어냅니다.**

매 프레임마다:
- 도구의 위치·자세를 랜덤화
- 조명 색·강도를 랜덤화
- 카메라 각도를 랜덤화
- **RGB + 시맨틱 세그멘테이션 + 2D 바운딩박스 + 깊이**를 동시에 저장

이게 도메인 랜덤화(domain randomization)이고, i4h 워크플로우의 학습 데이터가
만들어지는 방식입니다.

---

## 학습 목표

1. `omni.replicator.core`의 **선언형 문법**(`with` 블록 = 실행이 아니라 등록)을 이해한다
2. `add_labels()`로 시맨틱 라벨을 붙인다 (**5.x에서 API가 바뀐 부분**)
3. `render_product` + `AnnotatorRegistry`로 여러 정답 채널을 동시에 얻는다
4. `BasicWriter`로 데이터셋을 디스크에 자동 저장한다
5. 도메인 랜덤화의 축(포즈/조명/재질/카메라)을 설계한다
6. SDG 품질 설정(`rt_subframes`, DLSS, async 렌더 끄기)의 의미를 안다

---

## 요구사항

- [ ] 시술 씬: 테이블 + 팬텀 + **도구 3종**(`scalpel`, `forceps`, `clamp`)
- [ ] 각 도구 prim에 `add_labels(prim, labels=["scalpel"], instance_name="class")` 적용
- [ ] `rep.create.camera()` + `rep.create.render_product(camera, (640, 480))`
- [ ] 어노테이터 4종 부착: `rgb`, `semantic_segmentation`, `bounding_box_2d_tight`,
      `distance_to_image_plane`
- [ ] `BasicWriter`로 `_out_ex07/`에 저장
- [ ] **랜덤화 3축**을 `rep.trigger.on_frame()` 블록에 등록
      - 도구 포즈: 팬텀 위 범위에서 `uniform`, 회전은 z축 `-180~180°`
      - 조명: 강도 `uniform(500, 4000)`, 색 `uniform((0.7,0.7,0.7),(1,1,1))`
      - 카메라: 팬텀 주변 반구에서 위치 샘플링, `look_at` 팬텀 중심
- [ ] SDG 품질 설정 적용 (`captureOnPlay=False`, `asyncRendering=False`, DLSS Quality)
- [ ] `--frames N` 만큼 캡처 (기본 20, `--test`면 3)
- [ ] **검증**: 프레임마다 3개 클래스가 모두 바운딩박스로 잡히는지, 파일이 생성됐는지

---

## ★ 핵심 개념: `with` 블록은 실행이 아니라 "등록"이다

```python
with rep.trigger.on_frame():
    with rep.get.prims(path_pattern="/World/Tools/.*"):
        rep.modify.pose(position=rep.distribution.uniform(lo, hi))
```

이 코드는 **한 번만 실행됩니다.** 하는 일은 "매 프레임마다 이렇게 하라"는
**그래프를 등록**하는 것입니다. 실제 랜덤화는 나중에
`rep.orchestrator.step()`을 부를 때마다 일어납니다.

블록 안에 `print()`를 넣어도 매 프레임 찍히지 않습니다.
이걸 모르면 "왜 랜덤화가 안 되지?" 하며 하루를 씁니다.

---

## 힌트

<details>
<summary>힌트 1 — 시맨틱 라벨 (5.x에서 바뀐 부분)</summary>

세그멘테이션/바운딩박스 정답은 **라벨이 붙은 prim만** 나옵니다.

```python
from isaacsim.core.utils.semantics import add_labels
import omni.usd

stage = omni.usd.get_context().get_stage()
prim = stage.GetPrimAtPath("/World/Tools/scalpel")
add_labels(prim, labels=["scalpel"], instance_name="class")
```

**옛 API `add_update_semantics(prim, "scalpel", "class")`는 deprecated입니다.**
인터넷 튜토리얼은 대부분 옛 API를 씁니다. 동작은 하지만 경고가 뜹니다.

**주의**: 라벨은 **메쉬를 가진 prim 또는 그 조상**에 붙여야 합니다.
빈 Xform에만 붙이면 아무것도 안 잡힙니다.
</details>

<details>
<summary>힌트 2 — 어노테이터 부착과 읽기</summary>

```python
import omni.replicator.core as rep

camera = rep.create.camera(position=(0, 0, 1.6), look_at=(0, 0, 0.93))
rp = rep.create.render_product(camera, (640, 480))

rgb  = rep.AnnotatorRegistry.get_annotator("rgb")
seg  = rep.AnnotatorRegistry.get_annotator("semantic_segmentation")
bbox = rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight")
for a in (rgb, seg, bbox):
    a.attach(rp)

rep.orchestrator.step(rt_subframes=8)   # 1프레임 캡처(랜덤화 포함)
data = bbox.get_data()                   # {"data": [...], "info": {"idToLabels": {...}}}
```

`bounding_box_2d_tight`의 반환은 구조화 배열입니다.
`data["data"]`의 각 원소가 `(semanticId, x_min, y_min, x_max, y_max, occlusionRatio)`,
`data["info"]["idToLabels"]`가 id → 라벨 매핑입니다.
</details>

<details>
<summary>힌트 3 — BasicWriter</summary>

어노테이터를 직접 읽는 대신 파일로 바로 떨구려면:

```python
writer = rep.WriterRegistry.get("BasicWriter")
writer.initialize(
    output_dir="_out_ex07",
    rgb=True,
    semantic_segmentation=True,
    bounding_box_2d_tight=True,
    distance_to_image_plane=True,
    colorize_semantic_segmentation=True,
)
writer.attach([rp])
for _ in range(num_frames):
    rep.orchestrator.step(rt_subframes=8)
writer.detach()     # ★ 잊으면 파일이 안 flush될 수 있다
```
</details>

<details>
<summary>힌트 4 — SDG 품질 설정</summary>

NVIDIA 공식 SDG 예제가 항상 켜는 설정입니다.

```python
import carb
s = carb.settings.get_settings()
s.set("/omni/replicator/captureOnPlay", False)   # 재생 중 자동 캡처 끄기
s.set("/omni/replicator/asyncRendering", False)  # 비동기 렌더 끄기 (프레임 동기화)
s.set("/app/asyncRendering", False)
s.set("rtx/post/dlss/execMode", 2)               # DLSS Quality
```

**`asyncRendering`을 끄지 않으면** 랜덤화가 반영되기 전 프레임이 캡처되어
"이미지와 라벨이 한 프레임씩 어긋나는" 최악의 버그가 생깁니다.

`rt_subframes`는 캡처 전에 렌더러를 몇 번 더 돌릴지입니다.
RTX는 누적 방식이라 값이 작으면 잔상(ghosting)이 남습니다. 4~16 사이를 쓰세요.
</details>

<details>
<summary>힌트 5 — 세그멘테이션이 전부 배경으로 나온다면</summary>

1. 라벨을 안 붙였거나, 빈 Xform에 붙였습니다 → 메쉬 prim에 붙이세요
2. `instance_name`이 `"class"`가 아닙니다 → 어노테이터가 찾는 기본 키입니다
3. 도구가 카메라 시야 밖입니다 → RGB를 먼저 눈으로 확인하세요
4. 랜덤화로 도구가 팬텀 안에 파묻혔습니다 → 위치 범위를 좁히세요
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 라벨 | `get_labels(prim)`가 `{"class": ["scalpel"]}` 형태 반환 |
| RGB | 프레임마다 밝기가 다름 (조명 랜덤화 작동) |
| 바운딩박스 | 프레임마다 **3개 클래스가 모두** 검출 (가려짐 제외) |
| 포즈 랜덤화 | 프레임 간 바운딩박스 좌표가 명확히 다름 |
| 파일 | `_out_ex07/` 아래 rgb / semantic_segmentation / bounding_box_2d_tight 폴더 생성 |

**출력 예시**
```
--- 시맨틱 라벨 ---
/World/Tools/scalpel   → {'class': ['scalpel']}
/World/Tools/forceps   → {'class': ['forceps']}
/World/Tools/clamp     → {'class': ['clamp']}

--- 캡처 ---
frame  0: rgb mean=104.2  bbox 3개  labels={'scalpel', 'forceps', 'clamp'}
frame  1: rgb mean=157.8  bbox 3개  labels={'scalpel', 'forceps', 'clamp'}
frame  2: rgb mean= 88.3  bbox 2개  labels={'forceps', 'clamp'}      ← 가려짐
...
--- 검증 ---
클래스별 검출 프레임 수: scalpel 19/20, forceps 20/20, clamp 18/20
RGB 밝기 표준편차: 26.4 (조명 랜덤화 작동 중)
bbox 위치 표준편차: 71.3 px (포즈 랜덤화 작동 중)
PASS
```

---

## 확장 과제

1. **재질 랜덤화**: `rep.randomizer.materials()` 또는
   `rep.modify.attribute("diffuseColor", ...)`로 팬텀 피부색을 다양화하세요.
   실제 환자의 피부톤 편차를 모사하는 것입니다.
2. **가림(occlusion) 제어**: 바운딩박스의 `occlusionRatio`를 읽어
   80% 이상 가려진 객체는 라벨에서 제외하세요. 학습 데이터 품질이 크게 좋아집니다.
3. **COCO 포맷 변환**: `bounding_box_2d_tight` 출력을 COCO JSON으로 변환하는
   스크립트를 쓰세요. 대부분의 검출 모델이 이 포맷을 먹습니다.
4. **YCB 실물 에셋**: `/Isaac/Props/YCB/Axis_Aligned/` 아래 실제 3D 스캔 물체를
   방해물(distractor)로 뿌려 배경 복잡도를 올리세요.
5. **PathTracing 비교**: `rep.orchestrator.step()` 전에 렌더러를 PathTracing으로 바꿔
   이미지 품질과 생성 속도를 비교하세요.
