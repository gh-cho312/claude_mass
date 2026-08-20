"""Ex 09 — 다중 환경 클로닝 & 벤치마크 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
★ clone()이 반환하는 env 원점 오프셋을 반드시 활용하세요.

실행: python starter.py --num-envs 4 --test
"""

from __future__ import annotations

import argparse
import time

import numpy as np

parser = argparse.ArgumentParser(description="Ex09: 다중 환경 클로닝")
parser.add_argument("--num-envs", type=int, default=16)
parser.add_argument("--steps", type=int, default=500)
parser.add_argument("--warmup", type=int, default=50)
parser.add_argument("--spacing", type=float, default=2.5)
parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
parser.add_argument("--render", action="store_true")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--no-robot", action="store_true")
parser.add_argument("--test", action="store_true")
args, _ = parser.parse_known_args()

if args.test:
    args.num_envs = min(args.num_envs, 4)
    args.steps = min(args.steps, 120)
    args.warmup = min(args.warmup, 20)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   isaacsim.core.api.World
#   isaacsim.core.api.objects.{DynamicCuboid, FixedCuboid}
#   isaacsim.core.cloner.GridCloner
#   isaacsim.core.prims.{Articulation, RigidPrim}
#   isaacsim.core.simulation_manager.SimulationManager
#   isaacsim.core.utils.prims.define_prim
#   isaacsim.core.utils.stage.add_reference_to_stage
#   isaacsim.storage.native.get_assets_root_path

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
HOME = np.array([0.0, -0.6, 0.0, -2.2, 0.0, 1.6, 0.79, 0.04, 0.04])


def build_template(world, assets_root):
    """★ clone() 이전에 env_0 구성을 끝내야 한다."""
    # TODO: define_prim("/World/envs/env_0")
    # TODO: 테이블 / 팬텀 / 프로브(DynamicCuboid) 를 env_0 아래에 생성
    # TODO: (선택) Franka를 /World/envs/env_0/Robot 에 참조 추가
    raise NotImplementedError


def main() -> int:
    # TODO: SimulationManager.set_physics_sim_device(args.device)
    # TODO: World 생성 + ground plane

    # TODO: cloner = GridCloner(spacing=args.spacing); cloner.define_base_env("/World/envs")
    # TODO: build_template(...)
    # TODO: paths = cloner.generate_paths("/World/envs/env", args.num_envs)
    # TODO: env_positions = cloner.clone(source_prim_path="/World/envs/env_0", prim_paths=paths)

    # TODO: 와일드카드 뷰 생성
    #   probes = RigidPrim(prim_paths_expr="/World/envs/*/Probe", name="probes")
    #   robots = Articulation(prim_paths_expr="/World/envs/*/Robot", name="robots")
    # TODO: world.reset()

    # TODO: shape 확인 (N, 9) / 환경마다 다른 관절1 값을 한 번의 호출로 설정
    # TODO: ★ env_positions를 더해 프로브 월드 위치 설정 (오프셋을 빼먹지 말 것)

    # TODO: 워밍업 후 time.perf_counter()로 FPS / env-steps/s 측정 및 출력
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
