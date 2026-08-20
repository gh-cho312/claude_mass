"""Ex 04 — 카메라 센서와 내부 파라미터 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
실행: python starter.py --test
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np

parser = argparse.ArgumentParser(description="Ex04: 카메라 센서")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--test", action="store_true")
parser.add_argument("--out", default="_out_ex04")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   isaacsim.core.utils.numpy.rotations as rot_utils
#   omni.usd, pxr.{Sdf, UsdLux}
#   isaacsim.core.api.World
#   isaacsim.core.api.objects.{DynamicCuboid, FixedCuboid}
#   isaacsim.sensors.camera.Camera

IMG_W, IMG_H = 640, 480
FX, FY = 612.418, 612.362
CX, CY = 309.723, 245.359
PIXEL_SIZE_UM = 1.4

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
CAMERA_Z = 1.20


def build_scene():
    # TODO: World + ground plane
    # TODO: 조명 (DistantLight + SphereLight)
    # TODO: 테이블, 팬텀, 높이가 다른 도구 3개
    # TODO: Camera 생성 (해상도 IMG_W x IMG_H, 수직 하향)
    #   힌트: rot_utils.euler_angles_to_quats(np.array([0, 90, 0]), degrees=True)
    raise NotImplementedError


def apply_opencv_intrinsics(camera):
    """OpenCV intrinsics → Isaac 렌즈 파라미터 변환 후 적용, HFOV 반환."""
    # TODO: horizontal_aperture = PIXEL_SIZE_UM * 1e-3 * IMG_W
    # TODO: focal_length = ((FX + FY) / 2) * PIXEL_SIZE_UM * 1e-3
    # TODO: camera.set_focal_length(focal_length / 10.0) 등 — ★ /10.0 잊지 말 것
    # TODO: camera.set_lens_aperture(0.0), set_clipping_range(...)
    # TODO: HFOV 계산 후 출력
    raise NotImplementedError


def save_images(rgba, depth, out_dir):
    # TODO: PIL로 RGB PNG 저장, 깊이는 정규화해서 8비트 PNG로 저장
    raise NotImplementedError


def main() -> int:
    world, camera = build_scene()
    world.reset()

    # TODO: camera.initialize()
    # TODO: camera.add_distance_to_image_plane_to_frame()
    # TODO: apply_opencv_intrinsics(camera)

    # TODO: render=True로 40~90 스텝 워밍업 (첫 프레임은 노이즈)

    # TODO: rgba = camera.get_rgba()
    # TODO: depth = camera.get_current_frame()["distance_to_image_plane"]
    # TODO: shape / 평균 밝기 / 깊이 min·max 검증 후 PASS·FAIL 출력
    # TODO: save_images(...)

    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
