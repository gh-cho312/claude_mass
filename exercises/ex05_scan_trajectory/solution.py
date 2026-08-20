"""Ex 05 — 스캔 궤적 추종 (IK / RMPFlow) (해답)

Franka가 프로브를 들고 팬텀 표면 위 웨이포인트를 순서대로 지나간다.
두 가지 방식(해석적 IK vs 반응형 RMPFlow)을 같은 경로에 대해 비교한다.

핵심 학습 포인트
  1. ★ set_robot_base_pose() — 로봇 베이스가 원점이 아닐 때 반드시 호출
  2. 모션 생성 모듈은 SingleArticulation을 요구한다 (배치 뷰 아님)
  3. IK: 한 번에 해를 구함 / RMPFlow: 매 스텝 반응적으로 접근
  4. compute_end_effector_pose()는 회전 "행렬"을 반환한다

실행:
    python solution.py --mode ik --test --headless
    python solution.py --mode rmpflow --test --headless
    python solution.py --mode ik --no-base-pose      # ★ 함정 재현 실험
"""

from __future__ import annotations

import argparse

import numpy as np

parser = argparse.ArgumentParser(description="Ex05: 스캔 궤적 추종")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
parser.add_argument("--mode", choices=["ik", "rmpflow"], default="ik")
parser.add_argument("--no-base-pose", action="store_true",
                    help="★ set_robot_base_pose()를 일부러 생략 — 함정 재현용")
parser.add_argument("--position-only", action="store_true",
                    help="자세 제약 없이 위치만 맞춤 (IK 실패가 잦을 때 진단용)")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import isaacsim.core.utils.numpy.rotations as rot_utils  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import FixedCuboid, VisualSphere  # noqa: E402
from isaacsim.core.prims import SingleArticulation  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from isaacsim.robot_motion.motion_generation import (  # noqa: E402
    ArticulationKinematicsSolver,
    ArticulationMotionPolicy,
    LulaKinematicsSolver,
    RmpFlow,
    interface_config_loader,
)
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

# ── 씬 상수 ────────────────────────────────────────────────────────────────
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H            # 0.93
PROBE_CLEARANCE = 0.02                             # 표면에서 띄울 높이

ROBOT_BASE = np.array([0.0, -0.42, TABLE_TOP_Z])   # ★ 원점이 아니다
ROBOT_PRIM = "/World/ProbeHolder"
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
EE_FRAME = "panda_hand"

N_WAYPOINTS = 15
X_START, X_END = -0.14, 0.14
REACH_TOL = 0.005          # 5 mm
MAX_STEPS_PER_WP = 120


def scan_waypoints() -> np.ndarray:
    """팬텀 표면을 따라 x 방향으로 직선 스캔하는 웨이포인트 (N, 3)."""
    xs = np.linspace(X_START, X_END, N_WAYPOINTS)
    return np.stack([
        xs,
        np.zeros_like(xs),
        np.full_like(xs, PHANTOM_TOP_Z + PROBE_CLEARANCE),
    ], axis=1)


def build_scene() -> tuple[World, SingleArticulation, np.ndarray, FixedCuboid]:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    assets_root = get_assets_root_path()
    if assets_root is None:
        raise RuntimeError(
            "Isaac Sim 에셋 폴더를 찾을 수 없습니다. 네트워크/프록시 또는 "
            "ISAAC_NUCLEUS_DIR 환경변수를 확인하세요."
        )

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.4, 0.7, TABLE_TOP_Z]), size=1.0,
        color=np.array([70, 80, 95]),
    ))
    phantom = world.scene.add(FixedCuboid(
        prim_path="/World/Phantom", name="phantom",
        position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_H / 2.0]),
        scale=np.array([0.50, 0.30, PHANTOM_H]), size=1.0,
        color=np.array([240, 200, 180]),
    ))

    add_reference_to_stage(usd_path=assets_root + FRANKA_USD, prim_path=ROBOT_PRIM)

    # ★ 모션 생성 모듈은 SingleArticulation을 요구한다.
    #   Ex03에서 쓴 배치형 Articulation 뷰를 넘기면 ArticulationSubset에서 실패한다.
    arm = SingleArticulation(prim_path=ROBOT_PRIM, name="probe_holder",
                             position=ROBOT_BASE)
    world.scene.add(arm)

    waypoints = scan_waypoints()
    # 웨이포인트를 눈에 보이게 표시 (VisualSphere = 물리 없음)
    for i, wp in enumerate(waypoints):
        world.scene.add(VisualSphere(
            prim_path=f"/World/Waypoints/wp_{i:02d}", name=f"wp_{i:02d}",
            position=wp, radius=0.004, color=np.array([255, 80, 80]),
        ))

    set_camera_view(eye=[1.2, -1.3, 1.6], target=[0.0, -0.1, 0.95],
                    camera_prim_path="/OmniverseKit_Persp")
    return world, arm, waypoints, phantom


def probe_down_quat() -> np.ndarray:
    """그리퍼가 월드 -Z(아래)를 향하는 쿼터니언 (w, x, y, z)."""
    return rot_utils.euler_angles_to_quats(np.array([180.0, 0.0, 0.0]), degrees=True)


# ---------------------------------------------------------------------------
# 모드 A — 해석적 IK
# ---------------------------------------------------------------------------
def run_ik(world: World, arm: SingleArticulation, waypoints: np.ndarray) -> dict:
    cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
    ik_solver = LulaKinematicsSolver(**cfg)
    art_ik = ArticulationKinematicsSolver(arm, ik_solver, EE_FRAME)

    print(f"사용 가능 프레임: {ik_solver.get_all_frame_names()}")

    # ★★★ 이 두 줄이 이 과제의 핵심 ★★★
    # Lula는 로봇 베이스 좌표계로 계산하는데, target_position은 월드 좌표계다.
    # 베이스 위치를 알려주지 않으면 원점에 있다고 가정하고 42cm/75cm 어긋난 해를 낸다.
    if not args.no_base_pose:
        base_pos, base_quat = arm.get_world_pose()
        ik_solver.set_robot_base_pose(base_pos, base_quat)
        print(f"로봇 베이스: {np.array2string(base_pos, precision=3)}")
    else:
        print("[실험] set_robot_base_pose()를 생략했습니다 — 대부분 실패할 것입니다.")

    controller = arm.get_articulation_controller()
    target_quat = None if args.position_only else probe_down_quat()

    return _track_waypoints(
        world, arm, waypoints,
        step_fn=lambda wp: _ik_step(art_ik, controller, wp, target_quat),
        ee_pos_fn=lambda: art_ik.compute_end_effector_pose(position_only=True)[0],
    )


def _ik_step(art_ik, controller, wp: np.ndarray, target_quat) -> bool:
    """한 스텝 IK를 풀어 액션을 적용. 해가 없으면 False."""
    action, ok = art_ik.compute_inverse_kinematics(
        target_position=wp,
        target_orientation=target_quat,
    )
    if ok:
        controller.apply_action(action)
    return bool(ok)


# ---------------------------------------------------------------------------
# 모드 B — RMPFlow (반응형 모션 정책)
# ---------------------------------------------------------------------------
def run_rmpflow(world: World, arm: SingleArticulation, waypoints: np.ndarray,
                phantom) -> dict:
    cfg = interface_config_loader.load_supported_motion_policy_config("Franka", "RMPflow")
    rmpflow = RmpFlow(**cfg)

    if not args.no_base_pose:
        base_pos, base_quat = arm.get_world_pose()
        rmpflow.set_robot_base_pose(base_pos, base_quat)
        print(f"로봇 베이스: {np.array2string(base_pos, precision=3)}")
    else:
        print("[실험] set_robot_base_pose()를 생략했습니다 — 대부분 실패할 것입니다.")

    # 팬텀을 장애물로 등록하면 프로브가 뚫고 들어가지 않는다.
    # 초음파는 표면에 "닿아야" 하므로 실제로는 접촉 제어(Ex06)와 함께 써야 한다.
    try:
        rmpflow.add_cuboid(phantom, static=True)
    except Exception as exc:      # 버전에 따라 시그니처가 다를 수 있다
        print(f"[알림] 장애물 등록 생략: {exc}")

    policy = ArticulationMotionPolicy(arm, rmpflow, default_physics_dt=1.0 / 60.0)
    controller = arm.get_articulation_controller()
    target_quat = None if args.position_only else probe_down_quat()

    def step_fn(wp: np.ndarray) -> bool:
        # RMPFlow는 매 스텝 목표를 향해 조금씩 움직이는 반응형 정책이다.
        rmpflow.set_end_effector_target(target_position=wp, target_orientation=target_quat)
        rmpflow.update_world()
        controller.apply_action(policy.get_next_articulation_action())
        return True       # RMPFlow는 "해 없음"을 명시적으로 알려주지 않는다

    def ee_pos_fn() -> np.ndarray:
        pos, _ = rmpflow.get_end_effector_pose(
            policy.get_active_joints_subset().get_joint_positions())
        return np.asarray(pos)

    return _track_waypoints(world, arm, waypoints, step_fn, ee_pos_fn)


# ---------------------------------------------------------------------------
# 공통 추종 루프
# ---------------------------------------------------------------------------
def _track_waypoints(world: World, arm, waypoints: np.ndarray,
                     step_fn, ee_pos_fn) -> dict:
    render = not args.headless
    max_steps = 60 if args.test else MAX_STEPS_PER_WP

    reached, errors, total_steps = 0, [], 0

    for idx, wp in enumerate(waypoints):
        hit_step: int | None = None
        last_error = float("inf")
        solver_failed = False

        for step in range(max_steps):
            if not step_fn(wp):
                solver_failed = True
                break
            world.step(render=render)
            total_steps += 1

            last_error = float(np.linalg.norm(ee_pos_fn() - wp))
            if last_error < REACH_TOL:
                hit_step = step
                break

        if solver_failed:
            print(f" wp {idx:2d} x={wp[0]:+.3f}  ✗ IK 해 없음 — 건너뜀")
            continue
        if hit_step is None:
            print(f" wp {idx:2d} x={wp[0]:+.3f}  ✗ 미도달 "
                  f"({max_steps} 스텝, 오차 {last_error * 1000:.1f} mm)")
            continue

        reached += 1
        errors.append(last_error)
        print(f" wp {idx:2d} x={wp[0]:+.3f}  ✓ 도달  "
              f"(스텝 {hit_step:3d}, 오차 {last_error * 1000:.1f} mm)")

    return {
        "reached": reached,
        "total": len(waypoints),
        "mean_error_mm": float(np.mean(errors) * 1000) if errors else float("nan"),
        "max_error_mm": float(np.max(errors) * 1000) if errors else float("nan"),
        "total_steps": total_steps,
    }


def main() -> int:
    world, arm, waypoints, phantom = build_scene()
    world.reset()

    # 스캔을 시작하기 좋은 초기 자세로 보내둔다.
    # 특이점(팔이 쭉 펴진 상태) 근처에서 시작하면 IK가 잘 안 풀린다.
    arm.set_joint_positions(np.array([0.0, -0.4, 0.0, -2.0, 0.0, 1.6, 0.79, 0.02, 0.02]))
    for _ in range(30):
        world.step(render=not args.headless)

    print(f"\n--- 모드: {args.mode} ---")
    if args.mode == "ik":
        report = run_ik(world, arm, waypoints)
    else:
        report = run_rmpflow(world, arm, waypoints, phantom)

    print(f"\n=== 리포트 ({args.mode}) ===")
    print(f"도달: {report['reached']}/{report['total']}   "
          f"평균 오차 {report['mean_error_mm']:.1f} mm   "
          f"최대 오차 {report['max_error_mm']:.1f} mm   "
          f"총 {report['total_steps']} 스텝")

    threshold = 12 if args.mode == "ik" else 13
    if args.test:
        threshold = max(6, threshold - 5)       # 짧은 실행은 기준 완화

    if report["reached"] >= threshold:
        print("PASS")
        return 0

    print("FAIL")
    print("  점검 순서:")
    print("   1. set_robot_base_pose()를 호출했나요? (--no-base-pose 로 차이를 확인해보세요)")
    print("   2. --position-only 로 자세 제약을 빼면 도달하나요? → 자세 제약이 원인")
    print("   3. 웨이포인트가 로봇 작업 반경(약 0.85 m) 안에 있나요?")
    print("   4. GUI로 실행해 팔이 테이블/팬텀과 충돌하는지 보세요")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:
        print(f"[에러] {exc}")
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
