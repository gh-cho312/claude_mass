"""Ex 03 — 로봇 아티큘레이션 제어 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
실행: python starter.py --test --headless
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

# TODO: import
#   carb
#   isaacsim.core.api.World
#   isaacsim.core.prims.Articulation
#   isaacsim.core.utils.stage.add_reference_to_stage
#   isaacsim.core.utils.types.ArticulationActions   ← 배치 뷰용 (복수형!)
#   isaacsim.storage.native.get_assets_root_path

ROBOT_PRIM = "/World/ProbeHolder"
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
TABLE_TOP_Z = 0.75
CONVERGE_TOL = 0.02

HOME_POSE = {
    "panda_joint1": 0.00, "panda_joint2": -0.60, "panda_joint3": 0.00,
    "panda_joint4": -2.20, "panda_joint5": 0.00, "panda_joint6": 1.60,
    "panda_joint7": 0.79, "panda_finger_joint1": 0.04, "panda_finger_joint2": 0.04,
}
SCAN_READY_POSE = {
    "panda_joint1": 0.35, "panda_joint2": 0.25, "panda_joint3": -0.20,
    "panda_joint4": -1.90, "panda_joint5": 0.10, "panda_joint6": 2.10,
    "panda_joint7": 0.85, "panda_finger_joint1": 0.01, "panda_finger_joint2": 0.01,
}


def build_scene():
    # TODO: World 생성 + ground plane
    # TODO: get_assets_root_path() 확인. None이면 에러 메시지 후 종료
    # TODO: add_reference_to_stage 로 Franka를 ROBOT_PRIM에 추가
    # TODO: Articulation 뷰 생성
    # TODO: ★ reset() 전에 set_world_poses(positions=np.array([[0.0, -0.35, TABLE_TOP_Z]]))
    raise NotImplementedError


def pose_dict_to_array(arm, pose: dict[str, float]) -> np.ndarray:
    """{관절이름: 각도} → (1, num_dof) 배열."""
    # TODO: arm.dof_names 로 인덱스를 찾아 채우기. 지정 안 된 관절은 현재값 유지
    raise NotImplementedError


def clamp_to_limits(arm, target: np.ndarray) -> np.ndarray:
    """arm.get_dof_limits() (1, num_dof, 2) 로 클램프 + 경고 출력."""
    # TODO
    raise NotImplementedError


def drive_to_pose(world, arm, target, max_steps):
    """위치 제어로 목표 자세 구동. (수렴스텝, 최대오차) 반환.

    ★ 배치형 Articulation 뷰에는 get_articulation_controller()가 없습니다.
      arm.apply_action(ArticulationActions(joint_positions=target)) 를 쓰세요.
    """
    # TODO: action = ArticulationActions(joint_positions=target)   # (1, num_dof)
    # TODO: 매 스텝 arm.apply_action(action) + world.step
    # TODO: 오차가 CONVERGE_TOL 미만이 된 첫 스텝 기록
    raise NotImplementedError


def main() -> int:
    world, arm = build_scene()
    world.reset()      # ★ 이후에만 dof_names / num_dof 접근 가능

    # TODO: 관절 이름, 개수, 한계 출력
    # TODO: HOME 자세로 이동 후 유지 → 정상상태 오차 출력
    # TODO: SCAN_READY 자세로 이동 → 수렴 스텝과 최대 오차 출력
    # TODO: 최대 오차 < CONVERGE_TOL 이면 PASS

    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
