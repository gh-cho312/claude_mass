"""Ex 10 — 캡스톤: 자율 초음파 스캔 + 학습 데이터셋 생성 (뼈대 코드)

Ex01~09를 통합합니다. 각 서브시스템은 이전 과제의 해답을 가져다 쓰되,
"통합"과 "기록"이 이 과제의 학습 대상입니다.

실행: python starter.py --test --episodes 1
"""

from __future__ import annotations

import argparse
import json
import os
from enum import Enum, auto

import numpy as np

parser = argparse.ArgumentParser(description="Ex10: 자율 스캔 캡스톤")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--test", action="store_true")
parser.add_argument("--episodes", type=int, default=3)
parser.add_argument("--out", default="_out_ex10")
parser.add_argument("--record-every", type=int, default=4)
parser.add_argument("--desired-force", type=float, default=8.0)
parser.add_argument("--kp", type=float, default=4.0e-5)
parser.add_argument("--img-width", type=int, default=320)
parser.add_argument("--img-height", type=int, default=240)
args, _ = parser.parse_known_args()

if args.test:
    args.episodes = min(args.episodes, 1)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import — Ex04(Camera) + Ex05(IK) + Ex06(ContactSensor) 세트

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
ROBOT_BASE = np.array([0.0, -0.42, TABLE_TOP_Z])
ROBOT_PRIM = "/World/ProbeHolder"
EE_FRAME = "panda_hand"
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
START_X = -0.10
START_HEIGHT = 0.05


class ScanState(Enum):
    APPROACH = auto()
    CONTACT = auto()
    SWEEP = auto()
    RETRACT = auto()
    DONE = auto()


def build_scene():
    # TODO: Ex05 씬 + Ex06 ContactSensor
    # TODO: room 카메라 — 월드 고정, position/orientation 사용
    # TODO: wrist 카메라 — ★ prim_path를 panda_hand의 자식으로,
    #        position 대신 translation(부모 기준 로컬)을 쓸 것
    raise NotImplementedError


def read_force(sensor):
    # TODO: Ex06과 동일
    raise NotImplementedError


def grab_rgb(camera, height, width) -> np.ndarray:
    """(H, W, 3) uint8. 실패 시 검은 프레임 반환."""
    # TODO
    raise NotImplementedError


def run_episode(world, arm, contact, room_cam, wrist_cam, art_ik,
                controller, probe_down, scan_y, ep_idx) -> dict:
    # TODO: 초기 자세 복귀 후 Ex06 상태기계 실행
    #
    # ★ 기록 주파수 분리:
    #   record_now = (step % args.record_every == 0)
    #   world.step(render=record_now)          # 기록할 때만 렌더
    #   if record_now: ...관측/액션/보상/종료 기록...
    #
    # 기록 항목:
    #   obs/joint_positions, joint_velocities, ee_position, contact_force,
    #   room_camera, wrist_camera
    #   actions (target_x, scan_y, target_z, desired_force)
    #   rewards (힘이 대역 안이면 1)
    #   dones (마지막만 1)
    raise NotImplementedError


def save_dataset(episodes, out_dir) -> str:
    """robomimic 스타일 HDF5. h5py가 없으면 .npz 폴백."""
    # TODO: data/ 그룹 attrs: total, num_demos, env_args(JSON)
    # TODO: data/demo_i/obs/*, actions, rewards, dones
    # TODO: ★ 이미지 데이터셋에는 compression="gzip" 을 반드시 걸 것
    raise NotImplementedError


def verify_dataset(path, episodes) -> bool:
    # TODO: 파일 재로드 → 키 존재/ T 일치 / 이미지 밝기 / 성공률 검증
    raise NotImplementedError


def main() -> int:
    world, arm, contact, room_cam, wrist_cam = build_scene()
    world.reset()

    # TODO: 카메라 initialize()
    # TODO: IK 세팅 (★ ik_solver.set_robot_base_pose(*arm.get_world_pose()))
    # TODO: 렌더 워밍업

    # TODO: 에피소드마다 scan_y를 조금씩 바꿔 run_episode 실행
    # TODO: save_dataset → verify_dataset → PASS/FAIL
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
