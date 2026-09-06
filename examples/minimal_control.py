#!/usr/bin/env python3
"""Isaac Sim을 '코드로 통제'하는 최소 예제 (약 40줄).

────────────────────────────────────────────────────────────────────────
핵심 개념: Isaac Sim은 **스텝(step) 시뮬레이션**입니다.
  - 여러분이 world.step() 으로 물리 시간을 '한 칸씩' 전진시키고,
  - 그 사이사이에 상태를 '읽고'(관측)  명령을 '씁니다'(제어).
  이 루프가 곧 "코드로 통제한다"의 실체입니다. GUI로 클릭할 수도 있지만,
  로보틱스/ML에서는 이렇게 파이썬 스크립트가 시뮬레이터를 운전합니다.

이 스크립트가 하는 일:
  공중(z=1.0m)에 큐브 하나를 두고, 매 스텝 물리를 전진시키며 높이 z를 읽어 출력.
  중력에 의해 z가 줄다가 바닥(≈0.05)에서 멈추면 → 물리가 실제로 계산된 것.

실행:
  python examples/minimal_control.py            # (pip 설치) 헤드리스, 200스텝
  ./python.sh examples/minimal_control.py       # (바이너리 설치)
  python examples/minimal_control.py --gui       # 창을 띄워 눈으로 보기
"""
from __future__ import annotations

import argparse

# CLI 파싱은 반드시 SimulationApp 생성 "전"에 (headless 여부를 넘겨야 하므로).
parser = argparse.ArgumentParser()
parser.add_argument("--gui", action="store_true", help="GUI 창 띄우기 (기본: headless)")
parser.add_argument("--steps", type=int, default=200, help="시뮬레이션 스텝 수")
args = parser.parse_args()

# ── 1) 시뮬레이터 부팅 ──────────────────────────────────────────────────
#    ★ 이 줄보다 위에서 isaacsim.* / omni.* 를 import 하면 실패합니다. ★
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": not args.gui})

# ── 2) 부팅 후에야 나머지 모듈 import 가능 ──────────────────────────────
import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid  # noqa: E402

# ── 3) 월드(씬 + 물리 엔진) 생성 후 바닥과 큐브 배치 ────────────────────
world = World(stage_units_in_meters=1.0)
world.scene.add_default_ground_plane()
cube = world.scene.add(
    DynamicCuboid(                       # DynamicCuboid = 강체 물리 + 충돌체 (중력 받음)
        prim_path="/World/cube",
        name="cube",
        position=np.array([0.0, 0.0, 1.0]),   # 높이 1 m 공중에서 시작
        size=0.1,
    )
)

# ── 4) 물리 초기화 ──────────────────────────────────────────────────────
#    reset()이 물리 핸들을 만듭니다. 이걸 부르기 전에는 get_world_pose() 등이
#    올바른 값을 주지 않습니다.
world.reset()

# ── 5) 제어 루프: 시간을 한 스텝씩 전진시키며 상태를 읽는다 ─────────────
print("step |   z (높이, m)")
for i in range(args.steps):
    world.step(render=args.gui)              # ← 물리 한 스텝 전진 ('시간 진행')
    if i % 20 == 0:
        pos, _ = cube.get_world_pose()       # ← 상태 읽기 (관측)
        print(f"{i:4d} | {pos[2]:8.3f}")

# (참고) 상태 '쓰기'(능동 제어)도 같은 자리에서 이렇게 합니다:
#     cube.set_linear_velocity(np.array([0.0, 0.0, 3.0]))  # 위로 튕기기
#     robot.apply_action(...)                              # 로봇 관절에 명령 (Ex03)

# ── 6) 결과 확인 후 종료 ────────────────────────────────────────────────
final_z = float(cube.get_world_pose()[0][2])
print(f"\n최종 높이 z = {final_z:.3f} m")
print("→ 0.05 근처면 큐브가 바닥에 안착 = 중력·충돌이 실제로 계산됐다는 뜻입니다.")

simulation_app.close()
