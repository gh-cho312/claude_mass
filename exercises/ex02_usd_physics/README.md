# Ex 02 — USD 계층과 물리 속성: 수술 도구 트레이

**난이도** ⭐⭐ | **예상 시간** 2~3시간

---

## 시나리오

수술 도구 세트를 기울어진 트레이 위에 떨어뜨립니다.
**같은 모양, 같은 질량인데 마찰 계수만 다른 두 도구**가 얼마나 다르게 미끄러지는지
측정합니다. 실제 수술 시뮬레이션에서 "도구가 손에서 미끄러지느냐"를 결정하는 값입니다.

```
                 ↓ 도구 A (마찰 0.8, 실리콘 코팅)
                 ↓ 도구 B (마찰 0.05, 젖은 스테인리스)
        ╱────────────────╲
      ╱   기울어진 트레이   ╲   ← 10° 경사
    ╱────────────────────────╲
```

Ex01에서는 `DynamicCuboid` 같은 편의 클래스를 썼습니다. 이번에는 **USD API를 직접 써서**
prim을 만들고 스키마를 적용합니다. i4h의 씬 정의 코드를 읽으려면 이 레벨이 필요합니다.

---

## 학습 목표

1. `pxr.UsdGeom`으로 Xform 계층과 지오메트리를 직접 만든다
2. `UsdPhysics.RigidBodyAPI` / `CollisionAPI` / `MassAPI` 스키마를 적용한다
3. `PhysicsMaterial`로 정지마찰·운동마찰·반발계수를 제어한다
4. `GeometryPrim.set_collision_approximations()`로 충돌 근사 방식을 고른다
5. `stage.Traverse()`로 씬 트리를 점검한다

---

## 요구사항

- [ ] `/World/OR` 아래에 **Xform 계층**을 만든다
      (`/World/OR/Tray`, `/World/OR/Instruments/ToolA`, `/World/OR/Instruments/ToolB`)
- [ ] 트레이는 `UsdGeom.Cube`로 만들고 **Y축 기준 10° 회전**시킨다.
      `CollisionAPI`만 적용(강체 아님 → 고정 구조물)
- [ ] 도구 A/B는 `UsdGeom.Cube`로 만들고 `RigidBodyAPI` + `CollisionAPI` + `MassAPI`(0.08 kg) 적용
- [ ] 도구 A에는 **고마찰 재질**(static 0.9 / dynamic 0.8 / restitution 0.05),
      도구 B에는 **저마찰 재질**(static 0.06 / dynamic 0.05 / restitution 0.02)을 바인딩
- [ ] 트레이에는 중간 마찰(0.5/0.45)을 준다
- [ ] 시뮬레이션 후 **각 도구의 수평 이동 거리**를 측정해 출력
- [ ] `stage.Traverse()`로 각 prim이 어떤 스키마를 갖고 있는지 검증 출력
- [ ] **도구 B가 도구 A보다 확실히 더 멀리 미끄러졌는지** 판정

---

## 힌트

<details>
<summary>힌트 1 — USD로 큐브 만들고 크기 주기</summary>

`UsdGeom.Cube`의 기본 크기는 한 변이 2인 정육면체입니다(`size` 어트리뷰트 기본값 2.0).
원하는 치수를 만들려면 `size`를 1로 두고 `Scale` 연산을 씁니다.

```python
from pxr import UsdGeom, Gf

cube = UsdGeom.Cube.Define(stage, "/World/OR/Tray")
cube.CreateSizeAttr(1.0)
xform = UsdGeom.Xformable(cube.GetPrim())
xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.80))
xform.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 10.0, 0.0))
xform.AddScaleOp().Set(Gf.Vec3f(0.40, 0.30, 0.01))
```

**주의**: xformOp의 **추가 순서가 곧 적용 순서**입니다.
Translate → Rotate → Scale 순으로 넣는 게 관례입니다.
이미 op이 있는 prim에 또 `AddTranslateOp()`을 하면 에러가 납니다.
`xform.ClearXformOpOrder()`로 먼저 비우세요.
</details>

<details>
<summary>힌트 2 — 물리 스키마 적용</summary>

```python
from pxr import UsdPhysics, PhysxSchema

prim = stage.GetPrimAtPath("/World/OR/Instruments/ToolA")
UsdPhysics.CollisionAPI.Apply(prim)          # 충돌체
UsdPhysics.RigidBodyAPI.Apply(prim)          # 강체(중력 받음)
mass_api = UsdPhysics.MassAPI.Apply(prim)
mass_api.CreateMassAttr(0.08)
```

`CollisionAPI`만 적용하면 **움직이지 않는 충돌체**(정적 구조물)가 됩니다.
`RigidBodyAPI`까지 붙여야 중력을 받습니다. Ex01의 `Fixed*` vs `Dynamic*` 차이가
사실 이 스키마 조합의 차이입니다.
</details>

<details>
<summary>힌트 3 — 물리 재질 바인딩</summary>

`isaacsim.core.api.materials.PhysicsMaterial`을 만들고
`GeometryPrim.apply_physics_materials()`로 바인딩하는 게 가장 간단합니다.

```python
from isaacsim.core.api.materials import PhysicsMaterial
from isaacsim.core.prims import GeometryPrim

mat = PhysicsMaterial(
    prim_path="/World/PhysicsMaterials/HighFriction",
    name="high_friction",
    static_friction=0.9,
    dynamic_friction=0.8,
    restitution=0.05,
)
geo = GeometryPrim(prim_paths_expr="/World/OR/Instruments/ToolA")
geo.apply_physics_materials(mat)
```
</details>

<details>
<summary>힌트 4 — 두 도구가 똑같이 움직인다면</summary>

- 재질 바인딩이 실제로 걸렸는지 `geo.get_applied_physics_materials()`로 확인하세요.
- PhysX의 **마찰 결합 방식**은 기본이 "평균"입니다. 트레이 마찰이 아주 높으면
  도구 B의 낮은 마찰이 상쇄될 수 있습니다. 트레이 마찰을 중간(0.45)으로 두세요.
- 경사가 너무 완만하면 둘 다 안 미끄러집니다. 10~15° 사이로 조절하세요.
- 시뮬레이션 스텝이 너무 짧으면 차이가 안 납니다. 600 스텝 이상 돌리세요.
</details>

---

## 자기 채점 기준

| 항목 | 기대 결과 |
|---|---|
| 씬 트리 | `/World/OR/Instruments/ToolA`, `ToolB`가 존재 |
| 스키마 검증 | 트레이는 `CollisionAPI` O, `RigidBodyAPI` X / 도구는 둘 다 O |
| 물리 동작 | 두 도구 모두 트레이에 닿은 뒤 경사 아래로 이동 |
| 마찰 차이 | **도구 B의 수평 이동 거리 > 도구 A의 2배 이상** |
| 재질 확인 | `get_applied_physics_materials()`가 각각 다른 재질 반환 |

**출력 예시**
```
--- 씬 스키마 검증 ---
/World/OR/Tray                     Cube   collision=True  rigidbody=False
/World/OR/Instruments/ToolA        Cube   collision=True  rigidbody=True   mass=0.080
/World/OR/Instruments/ToolB        Cube   collision=True  rigidbody=True   mass=0.080

--- 미끄럼 거리 ---
ToolA (고마찰): 수평 이동 0.021 m
ToolB (저마찰): 수평 이동 0.187 m
비율 B/A = 8.9x
PASS: 마찰 계수가 미끄럼 거리에 명확히 반영되었습니다.
```

---

## 왜 이게 의료 시뮬레이션에서 중요한가

- **수술 도구 파지(grasping)**: 그리퍼가 도구를 놓치느냐 마느냐는 마찰이 결정합니다.
  혈액/생리식염수로 젖은 상황을 모사하려면 마찰을 낮춥니다.
- **초음파 프로브 접촉**: 젤을 바른 프로브-피부 접촉은 저마찰 + 저반발입니다.
- **충돌 근사**: 장기 메쉬에 `convexHull`을 쓰면 오목한 부분이 메워져
  기구가 장기 안으로 못 들어갑니다. Ex08에서 다시 다룹니다.

---

## 확장 과제

1. **경사각 스윕**: 5°, 10°, 15°, 20°로 바꿔가며 미끄럼 시작 각도를 찾으세요.
   이론값 `θ = arctan(μ_s)`와 비교해보세요. (μ_s=0.8 → 38.7°, μ_s=0.06 → 3.4°)
2. **반발계수 실험**: `restitution`을 0.0과 0.9로 바꿔 도구가 튀는 정도를 비교하세요.
3. **접촉력 읽기**: `GeometryPrim(..., track_contact_forces=True)`로 만들고
   `get_net_contact_forces()`로 도구가 트레이에 가하는 힘을 출력하세요. (Ex06 예고편)
4. **충돌 근사 비교**: 도구를 `UsdGeom.Mesh`로 바꾸고
   `set_collision_approximations(["convexHull"])` vs `["convexDecomposition"]`의
   시뮬레이션 속도와 정확도를 비교하세요.
