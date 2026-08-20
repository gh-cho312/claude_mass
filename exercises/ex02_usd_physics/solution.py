"""Ex 02 — USD 계층과 물리 속성: 수술 도구 트레이 (해답)

같은 모양·같은 질량이지만 마찰 계수만 다른 두 도구를 기울어진 트레이에 떨어뜨려
미끄럼 거리를 비교한다.

핵심 학습 포인트
  1. pxr.UsdGeom으로 Xform 계층과 지오메트리를 직접 생성
  2. UsdPhysics.{CollisionAPI, RigidBodyAPI, MassAPI} 스키마 적용
  3. PhysicsMaterial로 마찰/반발 제어 + GeometryPrim으로 바인딩
  4. stage.Traverse()로 씬 트리 검증

실행:
    python solution.py --test --headless
    python solution.py                    # GUI로 미끄러지는 모습 관찰
"""

from __future__ import annotations

import argparse
import math

import numpy as np

parser = argparse.ArgumentParser(description="Ex02: USD 계층과 물리 속성")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true", help="짧게 실행")
parser.add_argument("--tilt-deg", type=float, default=10.0, help="트레이 경사각(도)")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.materials import PhysicsMaterial  # noqa: E402
from isaacsim.core.prims import GeometryPrim, RigidPrim  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdPhysics  # noqa: E402

# --- 씬 상수 ---------------------------------------------------------------
TRAY_CENTER_Z = 0.80
TRAY_SCALE = Gf.Vec3f(0.50, 0.34, 0.012)      # 얇은 판
TOOL_SCALE = Gf.Vec3f(0.016, 0.016, 0.10)
TOOL_MASS = 0.08
DROP_HEIGHT = 0.10                            # 트레이 위 낙하 높이

# 도구 A/B의 초기 x 위치. 같은 조건에서 출발해야 비교가 유효하다.
TOOL_START = {
    "ToolA": Gf.Vec3d(-0.14, -0.08, TRAY_CENTER_Z + DROP_HEIGHT),
    "ToolB": Gf.Vec3d(-0.14, +0.08, TRAY_CENTER_Z + DROP_HEIGHT),
}

FRICTION_SPECS = {
    # (static_friction, dynamic_friction, restitution)
    "ToolA": (0.90, 0.80, 0.05),    # 실리콘 코팅 손잡이 — 잘 안 미끄러짐
    "ToolB": (0.06, 0.05, 0.02),    # 젖은 스테인리스 — 잘 미끄러짐
}
TRAY_FRICTION = (0.50, 0.45, 0.02)


def _make_box(stage, path: str, translate: Gf.Vec3d, scale: Gf.Vec3f,
              rotate_xyz: Gf.Vec3f | None = None) -> UsdGeom.Cube:
    """UsdGeom.Cube를 만들고 T→R→S 순서로 xformOp를 붙인다.

    UsdGeom.Cube의 size 기본값은 2.0이다. size=1로 두고 scale로 실제 치수를 준다.
    xformOp는 "추가한 순서대로" 적용되므로 Translate → Rotate → Scale 순이 관례.
    """
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)

    xformable = UsdGeom.Xformable(cube.GetPrim())
    xformable.ClearXformOpOrder()              # 기존 op이 있으면 중복 추가로 에러가 난다
    xformable.AddTranslateOp().Set(translate)
    if rotate_xyz is not None:
        xformable.AddRotateXYZOp().Set(rotate_xyz)
    xformable.AddScaleOp().Set(scale)
    return cube


def build_scene() -> tuple[World, dict[str, RigidPrim], dict[str, PhysicsMaterial]]:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    stage = omni.usd.get_context().get_stage()

    light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
    light.CreateIntensityAttr(1800.0)

    # ── Xform 계층 만들기 ─────────────────────────────────────────────────
    # 계층을 잡아두면 나중에 "/World/OR" 하나만 옮겨도 전체가 따라온다.
    # i4h 씬도 이런 식으로 /World/envs/env_N/... 계층을 씁니다.
    UsdGeom.Xform.Define(stage, "/World/OR")
    UsdGeom.Xform.Define(stage, "/World/OR/Instruments")
    UsdGeom.Xform.Define(stage, "/World/PhysicsMaterials")

    # ── 기울어진 트레이 ───────────────────────────────────────────────────
    _make_box(
        stage,
        "/World/OR/Tray",
        translate=Gf.Vec3d(0.0, 0.0, TRAY_CENTER_Z),
        scale=TRAY_SCALE,
        rotate_xyz=Gf.Vec3f(0.0, float(args.tilt_deg), 0.0),   # Y축 회전 → x방향 경사
    )
    tray_prim = stage.GetPrimAtPath("/World/OR/Tray")
    # CollisionAPI만 적용 → 충돌은 하지만 중력을 받지 않는 정적 구조물.
    UsdPhysics.CollisionAPI.Apply(tray_prim)

    # ── 수술 도구 두 개 ───────────────────────────────────────────────────
    for name, start in TOOL_START.items():
        path = f"/World/OR/Instruments/{name}"
        _make_box(stage, path, translate=start, scale=TOOL_SCALE,
                  rotate_xyz=Gf.Vec3f(0.0, float(args.tilt_deg), 0.0))
        prim = stage.GetPrimAtPath(path)
        UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.RigidBodyAPI.Apply(prim)                    # ← 이게 있어야 떨어진다
        UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(TOOL_MASS)

    # ── 물리 재질 생성 및 바인딩 ──────────────────────────────────────────
    materials: dict[str, PhysicsMaterial] = {}

    tray_mat = PhysicsMaterial(
        prim_path="/World/PhysicsMaterials/Tray",
        name="tray_material",
        static_friction=TRAY_FRICTION[0],
        dynamic_friction=TRAY_FRICTION[1],
        restitution=TRAY_FRICTION[2],
    )
    materials["Tray"] = tray_mat
    GeometryPrim(prim_paths_expr="/World/OR/Tray",
                 name="tray_geom").apply_physics_materials(tray_mat)

    for name, (mu_s, mu_d, rest) in FRICTION_SPECS.items():
        mat = PhysicsMaterial(
            prim_path=f"/World/PhysicsMaterials/{name}",
            name=f"{name.lower()}_material",
            static_friction=mu_s,
            dynamic_friction=mu_d,
            restitution=rest,
        )
        materials[name] = mat
        GeometryPrim(prim_paths_expr=f"/World/OR/Instruments/{name}",
                     name=f"{name.lower()}_geom").apply_physics_materials(mat)

    # ── 위치 추적용 RigidPrim 뷰 ──────────────────────────────────────────
    # RigidPrim은 "뷰" 클래스라 반환값에 배치 차원이 붙는다: (N, 3), (N, 4)
    tools = {
        name: RigidPrim(prim_paths_expr=f"/World/OR/Instruments/{name}",
                        name=f"{name.lower()}_view")
        for name in TOOL_START
    }
    for view in tools.values():
        world.scene.add(view)

    set_camera_view(eye=[0.9, -0.9, 1.35], target=[0.0, 0.0, TRAY_CENTER_Z],
                    camera_prim_path="/OmniverseKit_Persp")
    return world, tools, materials


def verify_schemas() -> None:
    """stage를 순회하며 각 prim이 어떤 물리 스키마를 갖는지 출력한다.

    "왜 안 떨어지지?" / "왜 통과하지?" 를 디버깅할 때 가장 먼저 하는 확인이다.
    """
    stage = omni.usd.get_context().get_stage()
    print("\n--- 씬 스키마 검증 ---")
    for path in ("/World/OR/Tray",
                 "/World/OR/Instruments/ToolA",
                 "/World/OR/Instruments/ToolB"):
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            print(f"{path:35s} <존재하지 않음>")
            continue
        has_col = prim.HasAPI(UsdPhysics.CollisionAPI)
        has_rb = prim.HasAPI(UsdPhysics.RigidBodyAPI)
        mass_txt = ""
        if prim.HasAPI(UsdPhysics.MassAPI):
            mass = UsdPhysics.MassAPI(prim).GetMassAttr().Get()
            mass_txt = f"  mass={mass:.3f}"
        print(f"{path:35s} {str(prim.GetTypeName()):6s} "
              f"collision={has_col!s:5s} rigidbody={has_rb!s:5s}{mass_txt}")


def main() -> int:
    world, tools, materials = build_scene()
    verify_schemas()

    world.reset()

    # 초기 위치 기록. reset() 이후에 읽어야 물리 뷰가 유효하다.
    start_pos = {name: view.get_world_poses()[0][0].copy() for name, view in tools.items()}

    steps = 400 if args.test else 900
    render = not args.headless
    for i in range(steps):
        world.step(render=render)
        if i % 200 == 0:
            xs = {n: float(v.get_world_poses()[0][0][0]) for n, v in tools.items()}
            print(f"[{i:4d}] " + "  ".join(f"{n} x={x:+.4f}" for n, x in xs.items()))

    # ── 미끄럼 거리 측정 ──────────────────────────────────────────────────
    print("\n--- 미끄럼 거리 ---")
    travel: dict[str, float] = {}
    for name, view in tools.items():
        end = view.get_world_poses()[0][0]
        delta = end[:2] - start_pos[name][:2]        # 수평(x, y) 성분만
        travel[name] = float(np.linalg.norm(delta))
        label = "고마찰" if name == "ToolA" else "저마찰"
        mu_s = FRICTION_SPECS[name][0]
        print(f"{name} ({label}, μs={mu_s:.2f}): 수평 이동 {travel[name]:.4f} m")

    # 이론적 미끄럼 시작 각도와 비교 — 물리가 상식과 맞는지 확인하는 감각 훈련
    print("\n--- 이론값 대조 (μs = tan θ_critical) ---")
    for name, (mu_s, _, _) in FRICTION_SPECS.items():
        theta_c = math.degrees(math.atan(mu_s))
        verdict = "미끄러져야 함" if args.tilt_deg > theta_c else "정지해야 함"
        print(f"{name}: θ_critical = {theta_c:5.1f}°  (현재 경사 {args.tilt_deg:.1f}° → {verdict})")

    # ── 재질이 실제로 바인딩됐는지 확인 ───────────────────────────────────
    print("\n--- 바인딩된 물리 재질 ---")
    for name in tools:
        geo = GeometryPrim(prim_paths_expr=f"/World/OR/Instruments/{name}",
                           name=f"{name.lower()}_check")
        applied = geo.get_applied_physics_materials()
        bound = applied[0].name if applied and applied[0] is not None else "<없음>"
        print(f"{name}: {bound}")

    # ── 판정 ──────────────────────────────────────────────────────────────
    print("-" * 60)
    a, b = travel["ToolA"], travel["ToolB"]
    ratio = b / a if a > 1e-6 else float("inf")
    print(f"비율 B/A = {ratio:.1f}x")
    if b > 2.0 * a and b > 0.02:
        print("PASS: 마찰 계수가 미끄럼 거리에 명확히 반영되었습니다.")
        return 0
    print("FAIL: 두 도구의 거동 차이가 충분하지 않습니다.")
    print("      → --tilt-deg 를 15~20으로 올리거나, 스텝 수를 늘려보세요.")
    print("      → 트레이 마찰이 너무 높으면 도구 마찰 차이가 상쇄됩니다.")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
