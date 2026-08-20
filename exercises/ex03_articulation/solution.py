"""Ex 03 — 로봇 아티큘레이션 제어: 프로브 홀더 자세 잡기 (해답)

Franka Panda를 시술 테이블 옆에 세우고 HOME → SCAN_READY 자세로 움직이며
관절 수렴 특성을 측정한다.

핵심 학습 포인트
  1. Nucleus 에셋 → add_reference_to_stage 로 로봇 붙이기
  2. Articulation "뷰" 클래스의 배치 차원 (N, num_dof)
  3. world.reset() 전후에 가능한 연산의 경계
  4. dof_names로 이름↔인덱스 매핑, 관절 한계 검증
  5. set_joint_positions(텔레포트) vs ArticulationAction(위치 제어)의 차이

실행:
    python solution.py --test --headless
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

parser = argparse.ArgumentParser(description="Ex03: 아티큘레이션 제어")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import carb  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
from isaacsim.core.prims import Articulation  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.core.utils.types import ArticulationActions  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

ROBOT_PRIM = "/World/ProbeHolder"
# 릴리스에 따라 경로가 바뀔 수 있다. 404면 GUI Content 브라우저에서 확인할 것.
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"

TABLE_TOP_Z = 0.75
ROBOT_BASE = np.array([[0.0, -0.35, TABLE_TOP_Z]])   # (1, 3) — 배치 차원 주의

# 관절 이름 → 목표 각도(rad). 이름으로 지정하면 DOF 순서가 바뀌어도 안전하다.
HOME_POSE = {
    "panda_joint1": 0.00,
    "panda_joint2": -0.60,
    "panda_joint3": 0.00,
    "panda_joint4": -2.20,
    "panda_joint5": 0.00,
    "panda_joint6": 1.60,
    "panda_joint7": 0.79,
    "panda_finger_joint1": 0.04,
    "panda_finger_joint2": 0.04,
}

# 프로브를 팬텀 위로 내려 스캔을 시작할 수 있는 자세.
SCAN_READY_POSE = {
    "panda_joint1": 0.35,
    "panda_joint2": 0.25,
    "panda_joint3": -0.20,
    "panda_joint4": -1.90,
    "panda_joint5": 0.10,
    "panda_joint6": 2.10,
    "panda_joint7": 0.85,
    "panda_finger_joint1": 0.01,   # 프로브를 쥔 상태
    "panda_finger_joint2": 0.01,
}

CONVERGE_TOL = 0.02      # rad
HOLD_STEPS = 300


def build_scene() -> tuple[World, Articulation]:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    assets_root = get_assets_root_path()
    if assets_root is None:
        carb.log_error("Isaac Sim 에셋 폴더를 찾을 수 없습니다.")
        print("\n[에러] Nucleus 에셋 서버에 접근할 수 없습니다.")
        print("       - 네트워크/프록시 설정을 확인하세요.")
        print("       - 로컬 에셋 팩이 있다면 ISAAC_NUCLEUS_DIR 환경변수를 설정하세요.")
        simulation_app.close()
        sys.exit(1)

    # 시술 테이블 (시각적 맥락용)
    world.scene.add(
        FixedCuboid(
            prim_path="/World/Table",
            name="table",
            position=np.array([0.0, 0.30, TABLE_TOP_Z / 2.0]),
            scale=np.array([1.8, 0.7, TABLE_TOP_Z]),
            size=1.0,
            color=np.array([90, 100, 115]),
        )
    )

    # 로봇을 참조로 붙인다. 원본 USD는 복사되지 않고 링크만 걸린다.
    add_reference_to_stage(usd_path=assets_root + FRANKA_USD, prim_path=ROBOT_PRIM)

    arm = Articulation(prim_paths_expr=ROBOT_PRIM, name="probe_holder")

    # ★ reset() "전"에 베이스 위치를 잡는다.
    #   reset() 후에 옮기면 물리가 이미 초기화된 상태라 튀거나 무시될 수 있다.
    arm.set_world_poses(positions=ROBOT_BASE)

    world.scene.add(arm)
    set_camera_view(eye=[1.6, -1.6, 1.8], target=[0.0, 0.1, 1.0],
                    camera_prim_path="/OmniverseKit_Persp")
    return world, arm


def pose_dict_to_array(arm: Articulation, pose: dict[str, float]) -> np.ndarray:
    """{관절이름: 각도} → (1, num_dof) 배열. 지정 안 된 관절은 현재값 유지."""
    current = np.array(arm.get_joint_positions())      # (1, num_dof)
    target = current.copy()
    names = list(arm.dof_names)
    for name, value in pose.items():
        if name not in names:
            print(f"  [경고] 관절 '{name}'이 로봇에 없습니다. 무시합니다.")
            continue
        target[0, names.index(name)] = value
    return target


def clamp_to_limits(arm: Articulation, target: np.ndarray) -> np.ndarray:
    """관절 한계를 벗어난 목표를 경고와 함께 클램프한다."""
    limits = np.array(arm.get_dof_limits())            # (1, num_dof, 2)
    lower, upper = limits[0, :, 0], limits[0, :, 1]
    clamped = np.clip(target[0], lower, upper)
    for i, name in enumerate(arm.dof_names):
        if abs(clamped[i] - target[0, i]) > 1e-9:
            print(f"  [경고] {name}: 목표 {target[0, i]:+.3f} 이 한계 "
                  f"[{lower[i]:+.3f}, {upper[i]:+.3f}] 를 벗어나 클램프됨 → {clamped[i]:+.3f}")
    return clamped.reshape(1, -1)


def print_robot_info(arm: Articulation, target: np.ndarray) -> None:
    limits = np.array(arm.get_dof_limits())[0]
    print(f"\n로봇: {arm.num_dof} DOF")
    for i, name in enumerate(arm.dof_names):
        print(f"  [{i}] {name:22s} limit [{limits[i, 0]:+.3f}, {limits[i, 1]:+.3f}]  "
              f"target {target[0, i]:+.3f}")


def drive_to_pose(world: World, arm: Articulation, target: np.ndarray,
                  max_steps: int, label: str) -> tuple[int | None, float, str]:
    """위치 제어로 목표 자세까지 구동. (수렴 스텝, 최대오차, 최악관절명) 반환.

    set_joint_positions()는 상태를 순간이동시키는 함수라 중력을 이기지 못한다.
    자세를 "유지"하려면 아래처럼 위치 제어 목표를 줘야 한다.

    ★ 배치형 Articulation "뷰"에는 get_articulation_controller()가 없다.
      뷰는 apply_action(ArticulationActions(...))를 직접 받고, 인자는 (N, num_dof).
      단일 로봇용 SingleArticulation만 get_articulation_controller()를 갖는다.
      (그쪽은 ArticulationActions가 아니라 단수형 ArticulationAction을 쓴다)
    """
    action = ArticulationActions(joint_positions=target)   # target shape: (1, num_dof)

    converged_at: int | None = None
    render = not args.headless

    for step in range(max_steps):
        arm.apply_action(action)
        world.step(render=render)

        error = np.abs(np.array(arm.get_joint_positions())[0] - target[0])
        if converged_at is None and float(error.max()) < CONVERGE_TOL:
            converged_at = step

    error = np.abs(np.array(arm.get_joint_positions())[0] - target[0])
    worst_idx = int(error.argmax())
    return converged_at, float(error.max()), arm.dof_names[worst_idx]


def main() -> int:
    world, arm = build_scene()

    # ★ reset() 이후에만 dof_names / num_dof / 관절 상태에 접근할 수 있다.
    world.reset()

    home = clamp_to_limits(arm, pose_dict_to_array(arm, HOME_POSE))
    print_robot_info(arm, home)

    # ── 1) HOME 자세: 텔레포트 후 위치 제어로 유지 ────────────────────────
    print("\n--- HOME 자세 유지 ---")
    # set_joint_positions는 순간이동. 초기 자세를 세팅할 때 유용하다.
    arm.set_joint_positions(home)
    hold_steps = 120 if args.test else HOLD_STEPS
    _, home_err, home_worst = drive_to_pose(world, arm, home, hold_steps, "HOME")
    print(f"정상상태 최대 오차: {home_err:.4f} rad ({home_worst})")

    # ── 2) SCAN_READY 자세로 이동 ─────────────────────────────────────────
    print("\n--- SCAN_READY 자세 이동 ---")
    scan_ready = clamp_to_limits(arm, pose_dict_to_array(arm, SCAN_READY_POSE))
    move_steps = 250 if args.test else 600
    converged_at, scan_err, scan_worst = drive_to_pose(
        world, arm, scan_ready, move_steps, "SCAN_READY")

    if converged_at is None:
        print(f"수렴 실패: {move_steps} 스텝 안에 {CONVERGE_TOL} rad 이내로 못 들어옴")
    else:
        print(f"수렴: {converged_at} 스텝 (기준 {CONVERGE_TOL} rad)")
    print(f"최대 오차: {scan_err:.4f} rad ({scan_worst})")

    # 참고: 각 관절이 중력 보상에 쓰는 토크. 팔을 뻗을수록 관절 2, 4가 커진다.
    efforts = np.array(arm.get_measured_joint_efforts())[0]
    print("\n--- 측정 관절 토크 (N·m) ---")
    for name, tau in zip(arm.dof_names, efforts):
        print(f"  {name:22s} {tau:+8.3f}")

    print("-" * 60)
    if scan_err < CONVERGE_TOL and home_err < CONVERGE_TOL:
        print("PASS: 두 자세 모두 허용 오차 안에서 수렴했습니다.")
        return 0
    print("FAIL: 수렴 오차가 기준을 넘었습니다.")
    print("      → 스텝 수를 늘리거나, arm.set_gains()로 stiffness를 올려보세요.")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
