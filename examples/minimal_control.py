#!/usr/bin/env python3
"""Isaac Sim을 '코드로 통제'하는 최소 예제.

────────────────────────────────────────────────────────────────────────
핵심 개념: Isaac Sim은 **스텝(step) 시뮬레이션**입니다.
  - 여러분이 world.step() 으로 물리 시간을 '한 칸씩' 전진시키고,
  - 그 사이사이에 상태를 '읽고'(관측)  명령을 '씁니다'(제어).
  이 루프가 곧 "코드로 통제한다"의 실체입니다.

이 스크립트가 하는 일:
  공중(z=1.0m)에 큐브를 두고, 매 스텝 물리를 전진시키며 높이 z를 읽어 출력.
  중력에 의해 z가 줄다가 바닥(≈0.05)에서 멈추면 → 물리가 실제로 계산된 것.

실행:
  python examples/minimal_control.py            # 헤드리스: 200스텝 후 종료(빠른 검증)
  python examples/minimal_control.py --gui      # 창을 띄워 눈으로 보기(반복 낙하)
  python examples/minimal_control.py --gui --repeat 90   # 더 자주 떨어뜨리기

--gui 로 보는 법 (Omniverse 뷰포트 조작):
  Alt + 마우스 왼쪽 드래그 = 회전 / 마우스 휠 = 확대·축소 / 마우스 가운데 드래그 = 이동
  창을 닫거나 터미널에서 Ctrl+C 를 누르면 종료됩니다.
"""
from __future__ import annotations

import argparse

# CLI 파싱은 반드시 SimulationApp 생성 "전"에 (headless 여부를 넘겨야 하므로).
parser = argparse.ArgumentParser()
parser.add_argument("--gui", action="store_true", help="GUI 창 띄우기 (기본: headless)")
parser.add_argument("--steps", type=int, default=None,
                    help="시뮬레이션 스텝 수 (기본: headless 200, GUI 6000)")
parser.add_argument("--repeat", type=int, default=None,
                    help="N 스텝마다 큐브를 다시 떨어뜨림 (기본: GUI일 때 150, headless는 끔)")
args = parser.parse_args()

# GUI로 볼 때는 오래 돌면서 반복 낙하해야 '볼 만'합니다.
# headless는 기존대로 짧게 끝나서 빠른 검증용으로 남깁니다.
if args.steps is None:
    args.steps = 6000 if args.gui else 200
if args.repeat is None:
    args.repeat = 150 if args.gui else 0

# ── 1) 시뮬레이터 부팅 ──────────────────────────────────────────────────
#    ★ 이 줄보다 위에서 isaacsim.* / omni.* 를 import 하면 실패합니다. ★
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": not args.gui})

# ── 2) 부팅 후에야 나머지 모듈 import 가능 ──────────────────────────────
import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402

START_POS = np.array([0.0, 0.0, 1.0])   # 큐브가 출발하는 높이 1 m

# ── 3) 월드(씬 + 물리 엔진) 생성 후 바닥과 큐브 배치 ────────────────────
world = World(stage_units_in_meters=1.0)
world.scene.add_default_ground_plane()
cube = world.scene.add(
    DynamicCuboid(                       # DynamicCuboid = 강체 물리 + 충돌체 (중력 받음)
        prim_path="/World/cube",
        name="cube",
        position=START_POS,
        size=0.1,
    )
)

# GUI일 때 큐브가 화면 가운데 오도록 카메라를 잡아줍니다.
if args.gui:
    set_camera_view(eye=[2.2, 2.2, 1.4], target=[0.0, 0.0, 0.3])

# ── 4) 물리 초기화 ──────────────────────────────────────────────────────
#    reset()이 물리 핸들을 만듭니다. 이걸 부르기 전에는 get_world_pose() 등이
#    올바른 값을 주지 않습니다.
world.reset()

# ── 5) 제어 루프: 시간을 한 스텝씩 전진시키며 읽고(관측) / 쓴다(제어) ────
if args.gui:
    print(f"GUI 모드: {args.repeat} 스텝마다 큐브를 다시 떨어뜨립니다. "
          "창을 닫거나 Ctrl+C 로 종료하세요.")
print("step |   z (높이, m)")
try:
    for i in range(args.steps):
        world.step(render=args.gui)          # ← 물리 한 스텝 전진 ('시간 진행')

        if i % 20 == 0:
            pos, _ = cube.get_world_pose()   # ← 상태 '읽기' (관측)
            print(f"{i:4d} | {pos[2]:8.3f}")

        # ← 상태 '쓰기' (능동 제어): 큐브를 다시 공중으로 올리고 속도를 0으로.
        #    로봇 제어도 위치가 다를 뿐 '루프 안에서 명령을 쓴다'는 구조는 같습니다.
        if args.repeat and i > 0 and i % args.repeat == 0:
            cube.set_world_pose(position=START_POS)
            cube.set_linear_velocity(np.array([0.0, 0.0, 0.0]))
            cube.set_angular_velocity(np.array([0.0, 0.0, 0.0]))
            print(f"     ↻ 다시 떨어뜨림 (step {i})")
except KeyboardInterrupt:
    print("\n사용자가 Ctrl+C 로 중단했습니다.")

# ── 6) 결과 확인 후 종료 ────────────────────────────────────────────────
final_z = float(cube.get_world_pose()[0][2])
print(f"\n최종 높이 z = {final_z:.3f} m")
print("→ 0.05 근처면 큐브가 바닥에 안착 = 중력·충돌이 실제로 계산됐다는 뜻입니다.")

simulation_app.close()
