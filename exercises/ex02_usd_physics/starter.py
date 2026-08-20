"""Ex 02 — USD 계층과 물리 속성 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
실행: python starter.py --test --headless
"""

from __future__ import annotations

import argparse

import numpy as np

parser = argparse.ArgumentParser(description="Ex02: USD 계층과 물리 속성")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
parser.add_argument("--tilt-deg", type=float, default=10.0)
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   omni.usd
#   isaacsim.core.api.World
#   isaacsim.core.api.materials.PhysicsMaterial
#   isaacsim.core.prims.{GeometryPrim, RigidPrim}
#   pxr.{Gf, Sdf, UsdGeom, UsdLux, UsdPhysics}

TRAY_CENTER_Z = 0.80
TOOL_MASS = 0.08

FRICTION_SPECS = {
    "ToolA": (0.90, 0.80, 0.05),
    "ToolB": (0.06, 0.05, 0.02),
}


def make_box(stage, path, translate, scale, rotate_xyz=None):
    """UsdGeom.Cube 생성 + xformOp(T→R→S) 부착."""
    # TODO: UsdGeom.Cube.Define, CreateSizeAttr(1.0)
    # TODO: UsdGeom.Xformable(...).ClearXformOpOrder()
    # TODO: AddTranslateOp / AddRotateXYZOp / AddScaleOp
    raise NotImplementedError


def build_scene():
    # TODO: World 생성 + ground plane + 조명

    # TODO: /World/OR, /World/OR/Instruments, /World/PhysicsMaterials Xform 계층 생성

    # TODO: 트레이 생성 (Y축으로 args.tilt_deg 회전) + CollisionAPI만 적용

    # TODO: ToolA, ToolB 생성 + CollisionAPI + RigidBodyAPI + MassAPI(TOOL_MASS)

    # TODO: PhysicsMaterial 3개 생성(트레이/ToolA/ToolB) 후
    #        GeometryPrim(...).apply_physics_materials(mat) 로 바인딩

    # TODO: RigidPrim 뷰를 만들어 위치 추적 준비, world.scene.add()

    raise NotImplementedError


def verify_schemas():
    """각 prim의 CollisionAPI / RigidBodyAPI / mass를 출력."""
    # TODO: stage.GetPrimAtPath(...).HasAPI(UsdPhysics.CollisionAPI) 등으로 검증 출력
    raise NotImplementedError


def main() -> int:
    world, tools, materials = build_scene()
    verify_schemas()
    world.reset()

    # TODO: 초기 위치 기록 (view.get_world_poses()[0][0])

    steps = 400 if args.test else 900
    for i in range(steps):
        world.step(render=not args.headless)

    # TODO: 각 도구의 수평 이동 거리 계산 및 출력
    # TODO: ToolB의 이동이 ToolA의 2배 이상인지 판정 → PASS/FAIL

    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
