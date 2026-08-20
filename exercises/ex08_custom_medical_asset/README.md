# Ex 08 — 커스텀 의료 에셋 파이프라인: CT 세그멘테이션 → 시뮬 가능한 장기 USD

**난이도** ⭐⭐⭐ | **예상 시간** 4~5시간

---

## 시나리오

CT/MRI를 세그멘테이션해서 얻은 장기 메쉬(STL)를 Isaac Sim에서 **물리적으로 상호작용
가능한 USD 에셋**으로 만듭니다. i4h의 "bring your own patient"가 하는 일입니다.

```
  CT DICOM ──▶ 세그멘테이션 ──▶ 메쉬(STL, mm 단위) ──▶ [이 과제] ──▶ 시뮬 가능한 USD
              (TotalSegmentator 등)                        │
                                                            ├─ 단위 변환 (mm → m)
                                                            ├─ 충돌 근사 선택
                                                            ├─ 시맨틱 라벨
                                                            └─ 물리 재질
```

**실제 데이터 없이 진행할 수 있습니다.** 스크립트가 간(liver)과 비슷한 형태의
울퉁불퉁한 타원체 메쉬를 **밀리미터 단위로** 생성해 STL로 저장하고,
그것을 입력으로 씁니다.

---

## 학습 목표

1. 외부 메쉬 → `UsdGeom.Mesh` prim 생성 (points, faceVertexIndices, faceVertexCounts)
2. **★ 단위 함정**: mm 단위 메쉬를 그대로 넣으면 간이 200 m가 된다
3. **충돌 근사 선택**이 시뮬레이션 정확도와 속도를 어떻게 바꾸는지
4. `add_labels()`로 장기 라벨 부착
5. USD 파일로 저장 → 다시 로드 → 물리 검증하는 왕복 파이프라인
6. 해부학적 타당성 검증 (크기, 부피)

---

## 요구사항

### 1단계: 입력 메쉬 준비
- [ ] 간과 유사한 울퉁불퉁한 타원체를 생성 (반경 대략 `140 × 90 × 60` **mm**)
- [ ] 바이너리 STL로 `_out_ex08/liver_raw.stl` 저장
- [ ] 정점 수와 바운딩박스를 출력 (mm 단위임을 확인)

### 2단계: USD 변환
- [ ] STL을 읽어 `UsdGeom.Mesh`로 `/World/Organs/Liver`에 생성
- [ ] **단위 변환**: `metersPerUnit`을 확인하고 mm → m 스케일(0.001) 적용
- [ ] 법선(normals)과 `subdivisionScheme="none"` 설정
- [ ] `displayColor`로 간 색상(어두운 적갈색) 지정

### 3단계: 물리 속성
- [ ] `CollisionAPI` 적용
- [ ] `--approx` 인자로 충돌 근사 선택:
      `convexHull` / `convexDecomposition` / `boundingCube` / `none`(삼각메쉬)
- [ ] `MassAPI`로 질량 1.5 kg (성인 간 평균)
- [ ] `PhysicsMaterial`로 마찰 0.4 / 반발 0.02 (조직 특성)

### 4단계: 라벨과 저장
- [ ] `add_labels(prim, labels=["liver"], instance_name="class")`
- [ ] `_out_ex08/liver.usd`로 저장

### 5단계: 검증
- [ ] 저장한 USD를 **새 stage에 다시 로드**
- [ ] 월드 바운딩박스가 **미터 단위로 해부학적으로 타당한지** 검증
      (간: 대략 0.20~0.30 m × 0.12~0.20 m × 0.08~0.14 m)
- [ ] 프로브(작은 구)를 간 위에 떨어뜨려 **충돌이 실제로 일어나는지** 확인
- [ ] 근사 방식별 시뮬레이션 스텝 시간을 측정해 비교

---

## ★ 함정 1: 단위

STL/OBJ에는 단위 정보가 **없습니다.** 그냥 숫자입니다.
의료 영상 파이프라인은 거의 항상 **밀리미터**를 씁니다.
Isaac Sim stage는 보통 **미터**입니다.

```python
# stage 단위 확인
from pxr import UsdGeom
meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)   # 보통 1.0

# mm 데이터를 m stage에 넣으려면
MM_TO_M = 0.001
points_m = points_mm * MM_TO_M
```

**증상**: 장기가 화면에 안 보이거나(너무 커서 카메라 안쪽에 있음),
물리가 폭발하거나(거대 물체 + 중력), FPS가 1 이하로 떨어집니다.

**진단법**: 항상 바운딩박스를 출력하세요. 간의 폭이 `0.25`면 정상,
`250`이면 mm를 그대로 넣은 것입니다.

---

## ★ 함정 2: 충돌 근사

`UsdGeom.Mesh`는 그냥 삼각형 덩어리입니다. PhysX가 충돌 계산을 하려면
**충돌 형상(collider)**이 필요하고, 여기에는 선택지가 있습니다.

| 근사 방식 | 정확도 | 속도 | 오목한 형상 | 의료 용도 |
|---|:--:|:--:|:--:|---|
| `boundingCube` | ✗ | ★★★ | ✗ | 대략적인 배치 확인용 |
| `convexHull` | △ | ★★★ | ✗ **오목부가 메워짐** | 단순 볼록 장기 |
| `convexDecomposition` | ○ | ★★ | ✅ | **대부분의 장기에 권장** |
| `none` (삼각메쉬) | ★★★ | ✗ **정적만 가능** | ✅ | 움직이지 않는 해부 구조 |
| `sdf` | ★★★ | ★ | ✅ | 정밀 접촉(도구-조직) |

**의료에서 왜 중요한가**: 위, 대장, 혈관, 심장의 심실은 **오목**합니다.
`convexHull`을 쓰면 내부 공간이 통째로 메워져서 **카테터나 내시경이 안으로
들어갈 수 없습니다.** 시각적으로는 멀쩡한데 물리적으로는 통짜 덩어리가 됩니다.

> **강체(RigidBody) 제약**: 삼각메쉬(`none`) 충돌체는 **동적 강체에 쓸 수 없습니다.**
> 정적 충돌체로만 가능합니다. 움직이는 장기라면 `convexDecomposition`이나 `sdf`를 쓰세요.

---

## 힌트

<details>
<summary>힌트 1 — numpy 배열 → UsdGeom.Mesh</summary>

```python
from pxr import UsdGeom, Vt, Gf

mesh = UsdGeom.Mesh.Define(stage, "/World/Organs/Liver")
mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype("float32")))
mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(faces.ravel().astype("int32")))
mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(faces)))
mesh.CreateSubdivisionSchemeAttr("none")      # 세분화 끄기 (성능)
mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(0.45, 0.16, 0.13)]))
```

`faceVertexIndices`는 **평탄화된 1차원 배열**이고,
`faceVertexCounts`는 각 면의 정점 개수(삼각형이면 전부 3)입니다.
</details>

<details>
<summary>힌트 2 — 충돌 근사 적용</summary>

```python
from isaacsim.core.prims import GeometryPrim

geo = GeometryPrim(prim_paths_expr="/World/Organs/Liver", name="liver_geom")
geo.apply_collision_apis()
geo.set_collision_approximations(["convexDecomposition"])
print(geo.get_collision_approximations())
```

`convexDecomposition`은 첫 적용 시 **수 초~수십 초**가 걸립니다(볼록 분해 계산).
결과는 USD에 캐시되므로 다음 로드부터는 빠릅니다.
</details>

<details>
<summary>힌트 3 — 바운딩박스 계산</summary>

```python
from pxr import UsdGeom, Usd

cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
bound = cache.ComputeWorldBound(prim)
rng = bound.ComputeAlignedRange()
size = rng.GetSize()            # Gf.Vec3d, stage 단위
```
</details>

<details>
<summary>힌트 4 — USD 저장 / 로드</summary>

```python
stage.GetRootLayer().Export("_out_ex08/liver.usd")

# 다시 로드
from isaacsim.core.utils.stage import add_reference_to_stage
add_reference_to_stage(usd_path="_out_ex08/liver.usd", prim_path="/World/LoadedLiver")
```
</details>

<details>
<summary>힌트 5 — 프로브가 간을 뚫고 지나간다면</summary>

1. `apply_collision_apis()`를 호출했나요?
2. 근사가 `none`(삼각메쉬)인데 간을 **동적** 강체로 만들었나요? → 지원 안 됩니다
3. 프로브가 너무 빨리 떨어져 터널링? → 낙하 높이를 줄이거나 CCD를 켜세요
4. 스케일이 안 맞아 간이 아주 작은 건 아닌가요? → 바운딩박스 출력으로 확인
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| STL 생성 | 정점 수 > 500, 바운딩박스가 mm 스케일(수백 단위) |
| 정점 중복 | STL은 정점을 공유하지 않으므로 읽은 정점 수 = 삼각형 × 3 (정상) |
| 단위 변환 | USD 바운딩박스가 m 스케일(0.2~0.3) |
| 해부학적 타당성 | 폭 0.20~0.30 m, 두께 0.08~0.14 m |
| 충돌 | 프로브가 간 표면에서 멈춤 (관통 X) |
| 라벨 | `get_labels()`가 `{"class": ["liver"]}` 반환 |
| 왕복 | 저장한 USD를 재로드해도 크기/충돌이 유지 |

**출력 예시**
```
--- 1단계: 입력 메쉬 (mm 단위) ---
정점 15360개, 삼각형 5120개
바운딩박스(mm): [302.5, 202.5, 131.7]      ← 수백 단위 = mm
저장: _out_ex08/liver_raw.stl

--- 2단계: USD 변환 ---
stage metersPerUnit = 1.0  →  mm 메쉬에 0.001 스케일 적용
바운딩박스(m): [0.303, 0.203, 0.132]        ← 해부학적으로 타당
  ✓ x: 0.303 m (타당 범위 0.20~0.32)
  ✓ y: 0.203 m (타당 범위 0.12~0.22)
  ✓ z: 0.132 m (타당 범위 0.08~0.16)

--- 3단계: 충돌 근사 ---
approximation = convexDecomposition
적용 소요: 3.42 s

--- 5단계: 물리 검증 ---
프로브 낙하: z 1.400 → 0.998 (간 상단 0.991)
✓ 관통 없음
평균 스텝 시간: 2.81 ms
PASS
```

---

## 근사 방식 비교 실험

```bash
for approx in boundingCube convexHull convexDecomposition none; do
  python solution.py --approx $approx --test --headless
done
```

`convexHull`에서는 간의 오목한 부분(담낭와)이 메워집니다.
프로브 정지 높이를 비교해보면 차이가 수치로 보입니다.

---

## 실제 CT 데이터로 확장하기

이 과제는 합성 메쉬를 쓰지만, 실제 파이프라인은 이렇습니다.

```
DICOM/NIfTI
  └─ TotalSegmentator / MONAI  →  라벨 볼륨 (.nii.gz)
       └─ marching cubes (skimage/vtk)  →  삼각 메쉬
            └─ 메쉬 정리 (trimesh: 구멍 메우기, 데시메이션, 법선 정렬)
                 └─ [이 과제] USD 변환 + 물리 속성
```

**실무 팁**
- 세그멘테이션 메쉬는 정점이 수십만 개입니다. **데시메이션 필수**
  (충돌용은 5천~2만 정점이면 충분).
- 구멍(non-watertight)이 있으면 `convexDecomposition`이 실패합니다.
  `trimesh.repair.fill_holes()`로 먼저 메우세요.
- 렌더용 고해상도 메쉬와 충돌용 저해상도 메쉬를 **분리**하는 게 정석입니다.
- DICOM의 `PixelSpacing`, `SliceThickness`로 실제 물리 크기를 계산해야
  단위가 맞습니다. 환자마다 다릅니다.

---

## 확장 과제

1. **렌더/충돌 메쉬 분리**: 고해상도 메쉬를 렌더용으로 두고,
   데시메이션한 저해상도 메쉬를 `purpose="guide"`로 충돌 전용으로 붙이세요.
2. **변형체(deformable)**: `isaacsim.core.prims.DeformablePrim`으로 장기를
   연조직처럼 변형되게 만드세요. 강체보다 훨씬 사실적입니다.
3. **다중 장기**: 간 + 신장 + 비장을 각각 다른 라벨로 만들고, 부모 Xform
   `/World/Organs` 하나로 전체를 환자 좌표계에 정렬하세요.
4. **실제 NIfTI**: `nibabel` + `skimage.measure.marching_cubes`로
   공개 데이터셋(예: Medical Segmentation Decathlon)에서 메쉬를 뽑아 이 파이프라인에 넣으세요.
