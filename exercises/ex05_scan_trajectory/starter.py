"""Ex 05 — 스캔 궤적 추종 (IK / RMPFlow) (뼈대 코드)

TODO를 채우세요. 요구사항과 함정 설명은 README.md 참고.
특히 ★ set_robot_base_pose() 부분을 놓치지 마세요.

실행: python starter.py --mode ik --test --headless
"""

from __future__ import annotations

import argparse

import numpy as np

parser = argparse.ArgumentParser(description="Ex05: 스캔 궤적 추종")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
parser.add_argument("--mode", choices=["ik", "rmpflow"], default="ik")
parser.add_argument("--no-base-pose", action="store_true")
parser.add_argument("--position-only", action="store_true")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   isaacsim.core.utils.numpy.rotations as rot_utils
#   isaacsim.core.api.World
#   isaacsim.core.api.objects.{FixedCuboid, VisualSphere}
#   isaacsim.core.prims.SingleArticulation     ← ★ 배치 뷰가 아니라 Single!
#   isaacsim.core.utils.stage.add_reference_to_stage
#   isaacsim.robot_motion.motion_generation.{
#       LulaKinematicsSolver, ArticulationKinematicsSolver,
#       RmpFlow, ArticulationMotionPolicy, interface_config_loader}
#   isaacsim.storage.native.get_assets_root_path

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
PROBE_CLEARANCE = 0.02
ROBOT_BASE = np.array([0.0, -0.42, TABLE_TOP_Z])
ROBOT_PRIM = "/World/ProbeHolder"
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
EE_FRAME = "panda_hand"

N_WAYPOINTS = 15
X_START, X_END = -0.14, 0.14
REACH_TOL = 0.005
MAX_STEPS_PER_WP = 120


def scan_waypoints() -> np.ndarray:
    """(N, 3) 웨이포인트: x는 X_START→X_END, y=0, z=PHANTOM_TOP_Z+PROBE_CLEARANCE."""
    # TODO
    raise NotImplementedError


def build_scene():
    # TODO: World + ground plane + 테이블 + 팬텀
    # TODO: Franka 참조 추가
    # TODO: SingleArticulation(prim_path=ROBOT_PRIM, position=ROBOT_BASE)
    # TODO: 웨이포인트를 VisualSphere로 표시
    raise NotImplementedError


def probe_down_quat() -> np.ndarray:
    """그리퍼가 -Z(아래)를 향하는 쿼터니언."""
    # TODO: rot_utils.euler_angles_to_quats(np.array([180., 0., 0.]), degrees=True)
    raise NotImplementedError


def run_ik(world, arm, waypoints):
    # TODO: cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
    # TODO: ik_solver = LulaKinematicsSolver(**cfg)
    # TODO: art_ik = ArticulationKinematicsSolver(arm, ik_solver, EE_FRAME)
    #
    # ★★★ 반드시 필요 ★★★
    # TODO: if not args.no_base_pose:
    #           base_pos, base_quat = arm.get_world_pose()
    #           ik_solver.set_robot_base_pose(base_pos, base_quat)
    #
    # TODO: 웨이포인트마다 compute_inverse_kinematics → apply_action → world.step
    #        오차가 REACH_TOL 미만이면 도달로 기록
    raise NotImplementedError


def run_rmpflow(world, arm, waypoints, phantom):
    # TODO: cfg = interface_config_loader.load_supported_motion_policy_config("Franka", "RMPflow")
    # TODO: rmpflow = RmpFlow(**cfg);  rmpflow.set_robot_base_pose(*arm.get_world_pose())
    # TODO: policy = ArticulationMotionPolicy(arm, rmpflow, default_physics_dt=1/60)
    # TODO: 매 스텝 set_end_effector_target → get_next_articulation_action → apply_action
    raise NotImplementedError


def main() -> int:
    world, arm, waypoints, phantom = build_scene()
    world.reset()

    # TODO: 특이점을 피한 초기 자세로 세팅 후 몇십 스텝 안정화

    if args.mode == "ik":
        report = run_ik(world, arm, waypoints)
    else:
        report = run_rmpflow(world, arm, waypoints, phantom)

    # TODO: 도달 개수 / 평균·최대 오차 / 총 스텝 출력 후 PASS·FAIL
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
