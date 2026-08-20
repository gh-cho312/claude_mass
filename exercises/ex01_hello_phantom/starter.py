"""Ex 01 — Hello Phantom (뼈대 코드)

TODO를 채워 시술실 최소 씬을 완성하세요.
자세한 요구사항은 같은 폴더의 README.md 참고.

실행:
    python starter.py --test --headless
"""

from __future__ import annotations

import argparse

import numpy as np

# ---------------------------------------------------------------------------
# 1) CLI 파싱은 SimulationApp 생성 "전"에 (headless 여부를 넘겨야 하므로)
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Ex01: Hello Phantom")
parser.add_argument("--headless", action="store_true", help="GUI 없이 실행")
parser.add_argument("--test", action="store_true", help="짧게 실행 (CI/검증용)")
args, _ = parser.parse_known_args()

# ---------------------------------------------------------------------------
# 2) SimulationApp 부팅 — 이 아래에서만 isaacsim.* / omni.* import 가능
# ---------------------------------------------------------------------------
from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: 필요한 모듈을 import 하세요.
#   - isaacsim.core.api.World
#   - isaacsim.core.api.objects 의 FixedCuboid, DynamicCuboid, VisualSphere
#   - isaacsim.core.utils.viewports.set_camera_view
#   - omni.usd, pxr.Sdf, pxr.UsdLux (조명용)


# --- 씬 치수 상수 (README의 요구사항과 일치) --------------------------------
TABLE_SIZE = np.array([2.00, 0.70, 0.75])   # x, y, z (m)
PHANTOM_SIZE = np.array([0.55, 0.30, 0.18])
TOOL_SIZE = np.array([0.015, 0.015, 0.14])
MARKER_RADIUS = 0.015

TABLE_TOP_Z = TABLE_SIZE[2]                      # 0.75
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_SIZE[2]    # 0.93


def build_scene():
    """씬을 구성하고 (world, tool, marker)를 반환한다."""
    # TODO: World를 stage_units_in_meters=1.0으로 생성

    # TODO: 기본 지면 추가 (world.scene.add_default_ground_plane())

    # TODO: DistantLight 추가
    #   stage = omni.usd.get_context().get_stage()
    #   light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
    #   light.CreateIntensityAttr(1500)

    # TODO: 시술 테이블 (FixedCuboid) — 상판이 z=TABLE_TOP_Z에 오도록
    #   힌트: 중심 z = TABLE_SIZE[2] / 2

    # TODO: 환자 팬텀 (FixedCuboid) — 테이블 위에

    # TODO: 스캔 목표 마커 (VisualSphere) — 팬텀 상단 표면, 물리 없음

    # TODO: 수술 도구 (DynamicCuboid) — 팬텀 위 0.35 m 상공, mass=0.05

    # TODO: 카메라 시점 설정 (set_camera_view)

    raise NotImplementedError("build_scene()을 구현하세요")


def main() -> int:
    world, tool, marker = build_scene()

    world.reset()

    total_steps = 200 if args.test else 600

    for i in range(total_steps):
        world.step(render=not args.headless)

        # TODO: 100 스텝마다 도구와 마커의 z 좌표를 출력
        #   힌트: tool.get_world_pose() -> (position, orientation)

    # TODO: 도구가 팬텀 위(z > 0.90)에 안착했는지 판정하고 PASS/FAIL 출력
    #        판정 결과에 따라 0 또는 1을 반환

    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
