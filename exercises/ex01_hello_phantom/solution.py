"""Ex 01 — Hello Phantom (해답)

시술 테이블 + 환자 팬텀 + 스캔 마커 + 낙하하는 수술 도구로 이루어진 최소 씬.

핵심 학습 포인트
  1. SimulationApp 부팅 전후의 import 경계
  2. Visual* / Fixed* / Dynamic* 세 계열의 차이
  3. world.reset() → world.step() 루프
  4. 오브젝트 position은 "중심점"이라는 것 (상판 z 계산)

실행:
    python solution.py --test --headless     # 짧게, 화면 없이
    python solution.py                       # GUI로 관찰
"""

from __future__ import annotations

import argparse

import numpy as np

# ---------------------------------------------------------------------------
# 1) CLI 파싱은 SimulationApp 생성 "전"에.
#    headless 여부를 SimulationApp 설정으로 넘겨야 하기 때문.
#    argparse / numpy 같은 순수 파이썬 모듈은 여기 있어도 안전하다.
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Ex01: Hello Phantom")
parser.add_argument("--headless", action="store_true", help="GUI 없이 실행")
parser.add_argument("--test", action="store_true", help="짧게 실행 (CI/검증용)")
args, _ = parser.parse_known_args()

# ---------------------------------------------------------------------------
# 2) SimulationApp 부팅.
#    이 줄이 Kit 앱을 띄우고 확장(extension)을 로드한다.
#    ★ 이 줄보다 위에서 isaacsim.* / omni.* 를 import하면 실패한다. ★
# ---------------------------------------------------------------------------
from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# ---------------------------------------------------------------------------
# 3) 여기서부터 Isaac / Omniverse 모듈 import 가능
# ---------------------------------------------------------------------------
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid, VisualSphere  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from pxr import Sdf, UsdLux  # noqa: E402

# --- 씬 치수 상수 (단위: m) -------------------------------------------------
TABLE_SIZE = np.array([2.00, 0.70, 0.75])   # 시술 테이블 x, y, z
PHANTOM_SIZE = np.array([0.55, 0.30, 0.18])  # 환자 몸통 팬텀
TOOL_SIZE = np.array([0.015, 0.015, 0.14])   # 메스 형태의 도구
MARKER_RADIUS = 0.015

TABLE_TOP_Z = float(TABLE_SIZE[2])                      # 0.75 — 테이블 상판 높이
PHANTOM_TOP_Z = TABLE_TOP_Z + float(PHANTOM_SIZE[2])    # 0.93 — 팬텀 상단(= 피부면)
TOOL_DROP_Z = PHANTOM_TOP_Z + 0.35                      # 1.28 — 도구 낙하 시작 높이

# 안착 판정 기준: 팬텀 상단 위에 도구가 눕든 서든 z는 0.90을 넘어야 한다.
SETTLE_Z_MIN = 0.90


def build_scene() -> tuple[World, DynamicCuboid, VisualSphere]:
    """시술실 씬을 구성하고 (world, tool, marker)를 반환한다."""

    # World가 stage와 물리 씬을 만든다. stage_units_in_meters=1.0 → 1 unit = 1 m.
    # 의료 에셋은 mm 단위가 많으므로, 단위를 명시적으로 고정해두는 습관이 중요하다.
    world = World(stage_units_in_meters=1.0)

    # 바닥. 충돌체가 있는 무한 평면 + 기본 조명이 함께 들어온다.
    world.scene.add_default_ground_plane()

    # 조명 하나 추가. headless여도 카메라 캡처를 하려면 조명이 필요하다.
    stage = omni.usd.get_context().get_stage()
    key_light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
    key_light.CreateIntensityAttr(1500.0)

    # ── 시술 테이블 ────────────────────────────────────────────────────────
    # FixedCuboid = 충돌체는 있지만 강체 물리는 없음 → 밀어도 안 움직인다.
    # position은 박스의 "중심"이므로 상판을 z=0.75에 두려면 중심은 0.375.
    world.scene.add(
        FixedCuboid(
            prim_path="/World/Table",
            name="table",
            position=np.array([0.0, 0.0, TABLE_SIZE[2] / 2.0]),
            scale=TABLE_SIZE,
            size=1.0,
            color=np.array([90, 100, 115]),
        )
    )

    # ── 환자 팬텀(몸통) ────────────────────────────────────────────────────
    # 실제 워크플로우에서는 CT에서 만든 메시 USD가 들어갈 자리다(→ Ex08).
    # 지금은 직육면체로 대체해 씬 구조부터 익힌다.
    world.scene.add(
        FixedCuboid(
            prim_path="/World/Phantom",
            name="phantom",
            position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_SIZE[2] / 2.0]),
            scale=PHANTOM_SIZE,
            size=1.0,
            color=np.array([240, 200, 180]),   # 살구색
        )
    )

    # ── 스캔 목표 마커 ─────────────────────────────────────────────────────
    # VisualSphere = 렌더링만 되고 물리는 전혀 없음.
    # 목표 지점, 웨이포인트 표시 등에 쓰는 "유령" 오브젝트.
    marker = world.scene.add(
        VisualSphere(
            prim_path="/World/ScanTarget",
            name="scan_target",
            position=np.array([0.12, 0.0, PHANTOM_TOP_Z]),
            radius=MARKER_RADIUS,
            color=np.array([255, 60, 60]),
        )
    )

    # ── 수술 도구 ──────────────────────────────────────────────────────────
    # DynamicCuboid = 강체 물리 + 충돌체. 중력을 받아 떨어진다.
    tool = world.scene.add(
        DynamicCuboid(
            prim_path="/World/Tool",
            name="tool",
            position=np.array([-0.10, 0.05, TOOL_DROP_Z]),
            scale=TOOL_SIZE,
            size=1.0,
            color=np.array([200, 205, 210]),
            mass=0.05,
        )
    )

    # 뷰포트 카메라를 테이블이 잘 보이는 각도로. GUI 모드에서만 의미가 있다.
    set_camera_view(
        eye=[1.6, -1.4, 1.7],
        target=[0.0, 0.0, PHANTOM_TOP_Z],
        camera_prim_path="/OmniverseKit_Persp",
    )

    return world, tool, marker


def main() -> int:
    world, tool, marker = build_scene()

    # reset()이 물리 핸들을 만든다. 이걸 부르기 전에는 get_world_pose() 같은
    # 물리 관련 조회가 불안정하다. 씬 구성이 끝난 뒤 정확히 한 번 부른다.
    world.reset()

    total_steps = 200 if args.test else 600
    render = not args.headless

    tool_z = float("nan")
    for i in range(total_steps):
        # render=False면 렌더링을 건너뛰어 훨씬 빠르다.
        # 카메라 이미지를 읽을 게 아니라면 headless 학습에서는 항상 False.
        world.step(render=render)

        if i % 100 == 0:
            tool_pos, _ = tool.get_world_pose()
            marker_pos, _ = marker.get_world_pose()
            print(f"[{i:4d}] tool z = {tool_pos[2]:.4f}   marker z = {marker_pos[2]:.4f}")

    tool_pos, _ = tool.get_world_pose()
    tool_z = float(tool_pos[2])
    marker_pos, _ = marker.get_world_pose()

    print("-" * 60)
    if tool_z > SETTLE_Z_MIN:
        print(f"PASS: 도구가 팬텀 위에 안착했습니다 (z={tool_z:.4f})")
        result = 0
    else:
        print(f"FAIL: 도구가 팬텀 위에 없습니다 (z={tool_z:.4f}, 기대 > {SETTLE_Z_MIN})")
        print("      → 팬텀 위치/크기 또는 도구의 낙하 지점(x, y)을 확인하세요.")
        result = 1

    # 마커는 VisualSphere라 물리를 받지 않는다. 시종일관 제자리여야 한다.
    if abs(float(marker_pos[2]) - PHANTOM_TOP_Z) < 1e-6:
        print(f"PASS: 마커는 물리 영향을 받지 않았습니다 (z={marker_pos[2]:.4f})")
    else:
        print(f"FAIL: 마커가 움직였습니다 (z={marker_pos[2]:.4f}) — Visual* 대신 Dynamic*을 쓰지 않았나요?")
        result = 1

    return result


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        # try/finally로 감싸야 중간에 예외가 나도 Kit 앱이 정상 종료된다.
        # 이걸 빠뜨리면 프로세스가 좀비로 남아 GPU 메모리를 물고 있는다.
        simulation_app.close()
    raise SystemExit(exit_code)
