"""Ex 06 — 접촉력 기반 스캔 제어 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
실행: python starter.py --test --headless
"""

from __future__ import annotations

import argparse
from enum import Enum, auto

import numpy as np

parser = argparse.ArgumentParser(description="Ex06: 접촉력 기반 스캔 제어")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
parser.add_argument("--desired-force", type=float, default=8.0)
parser.add_argument("--kp", type=float, default=4.0e-5)
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import — Ex05의 IK 세트 + isaacsim.sensors.physics.ContactSensor

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
PROBE_LENGTH = 0.11

CONTACT_THRESHOLD = 1.0
MAX_FORCE = 25.0
FORCE_BAND = 2.0
APPROACH_DZ = 0.001
MAX_DZ_PER_STEP = 0.0005
SWEEP_DX = 0.00035
SWEEP_DISTANCE = 0.20
LOST_CONTACT_STEPS = 60
FORCE_FILTER_ALPHA = 0.15


class ScanState(Enum):
    APPROACH = auto()
    CONTACT = auto()
    SWEEP = auto()
    RETRACT = auto()
    DONE = auto()


def build_scene():
    # TODO: Ex05 씬 + ContactSensor 부착
    #   ContactSensor(prim_path="/World/ProbeHolder/panda_hand/probe_contact",
    #                 radius=0.06, translation=np.array([0, 0, PROBE_LENGTH]), ...)
    #   sensor.add_raw_contact_data_to_frame()
    raise NotImplementedError


def read_force(sensor) -> tuple[float, bool]:
    """(힘 크기 N, 접촉 여부)."""
    # TODO: frame = sensor.get_current_frame(); frame["value"], frame["in_contact"]
    raise NotImplementedError


def main() -> int:
    world, arm, sensor = build_scene()
    world.reset()

    # TODO: IK 세팅 (★ ik_solver.set_robot_base_pose(*arm.get_world_pose()))
    # TODO: 초기 자세 세팅 + 안정화

    state = ScanState.APPROACH
    # TODO: target_x, target_z, filtered_force 등 초기화

    for step in range(900 if args.test else 2500):
        # TODO: raw_force, in_contact = read_force(sensor)
        # TODO: 저역통과 필터 적용
        # TODO: ★ 안전 조건(raw_force > MAX_FORCE)을 상태 분기보다 먼저 검사
        #
        # TODO: APPROACH  — target_z를 APPROACH_DZ씩 낮추고 접촉 감지 시 CONTACT로
        # TODO: CONTACT   — 어드미턴스: dz = -kp * (desired - filtered); 수렴하면 SWEEP
        # TODO: SWEEP     — 힘 유지 + target_x 전진; 거리 도달 또는 접촉 상실 시 RETRACT
        # TODO: RETRACT   — target_z 상승; 충분히 올라가면 DONE
        #
        # TODO: IK로 (target_x, 0, target_z) 추종 후 world.step()
        # TODO: 힘 이력 기록
        pass

    # TODO: SWEEP 구간 힘 통계와 대역 유지율 출력 → PASS/FAIL
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
