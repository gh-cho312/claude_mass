"""Ex 09 — 다중 환경 클로닝 & 벤치마크 (해답)

스캔 워크스테이션 하나를 GridCloner로 N개 복제하고, 배치 API로 한 번에 제어하며
환경 수 / 물리 디바이스 / 렌더 여부에 따른 처리량을 측정한다.

핵심 학습 포인트
  1. GridCloner: define_base_env → 템플릿 구성 → generate_paths → clone
  2. ★ clone()이 반환하는 env 원점 오프셋 — 로컬 목표를 월드로 바꿀 때 필요
  3. 와일드카드 뷰로 N개를 한 번에 (파이썬 루프 금지)
  4. 워밍업을 제외한 정확한 FPS 측정

실행:
    python solution.py --num-envs 16 --steps 300 --device cuda
    for n in 1 4 16 64; do python solution.py --num-envs $n --steps 300; done
"""

from __future__ import annotations

import argparse
import time

import numpy as np

parser = argparse.ArgumentParser(description="Ex09: 다중 환경 클로닝 & 벤치마크")
parser.add_argument("--num-envs", type=int, default=16)
parser.add_argument("--steps", type=int, default=500)
parser.add_argument("--warmup", type=int, default=50)
parser.add_argument("--spacing", type=float, default=2.5)
parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
parser.add_argument("--render", action="store_true", help="렌더링 켜기 (느려집니다)")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--no-robot", action="store_true",
                    help="로봇 없이 팬텀+프로브만 (스케일 한계 탐색용)")
parser.add_argument("--test", action="store_true")
args, _ = parser.parse_known_args()

if args.test:
    args.num_envs = min(args.num_envs, 4)
    args.steps = min(args.steps, 120)
    args.warmup = min(args.warmup, 20)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import carb  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402
from isaacsim.core.cloner import GridCloner  # noqa: E402
from isaacsim.core.prims import Articulation, RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from isaacsim.core.utils.prims import define_prim  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"

HOME = np.array([0.0, -0.6, 0.0, -2.2, 0.0, 1.6, 0.79, 0.04, 0.04])


def build_template(world: World, assets_root: str | None) -> None:
    """env_0 안에 워크스테이션 하나를 구성한다.

    ★ clone() 이전에 이 구성이 끝나 있어야 한다.
      clone 이후에 env_0에 추가한 것은 다른 환경에 복제되지 않는다.
    """
    define_prim("/World/envs/env_0")

    world.scene.add(FixedCuboid(
        prim_path="/World/envs/env_0/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.2, 0.6, TABLE_TOP_Z]), size=1.0,
        color=np.array([65, 75, 90]),
    ))
    world.scene.add(FixedCuboid(
        prim_path="/World/envs/env_0/Phantom", name="phantom",
        position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_H / 2.0]),
        scale=np.array([0.45, 0.28, PHANTOM_H]), size=1.0,
        color=np.array([240, 200, 180]),
    ))
    world.scene.add(DynamicCuboid(
        prim_path="/World/envs/env_0/Probe", name="probe",
        position=np.array([0.0, 0.0, PHANTOM_TOP_Z + 0.25]),
        scale=np.array([0.02, 0.02, 0.10]), size=1.0,
        color=np.array([40, 120, 220]), mass=0.06,
    ))

    if not args.no_robot and assets_root is not None:
        add_reference_to_stage(usd_path=assets_root + FRANKA_USD,
                               prim_path="/World/envs/env_0/Robot")


def main() -> int:
    # 물리 디바이스는 World 생성 전에 정하는 게 안전하다.
    SimulationManager.set_physics_sim_device(args.device)
    simulation_app.update()

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    assets_root = get_assets_root_path()
    use_robot = not args.no_robot
    if use_robot and assets_root is None:
        carb.log_warn("에셋 서버 접근 불가 — 로봇 없이 진행합니다.")
        print("[알림] Nucleus 접근 불가. --no-robot 모드로 진행합니다.")
        use_robot = False

    # ── 클로닝 ────────────────────────────────────────────────────────────
    cloner = GridCloner(spacing=args.spacing)
    cloner.define_base_env("/World/envs")
    build_template(world, assets_root if use_robot else None)

    paths = cloner.generate_paths("/World/envs/env", args.num_envs)
    env_positions = np.asarray(
        cloner.clone(source_prim_path="/World/envs/env_0", prim_paths=paths))

    print("--- 클로닝 ---")
    print(f"환경 {args.num_envs}개, spacing {args.spacing} m")
    print(f"env 원점 x 범위: {env_positions[:, 0].min():.1f} ~ {env_positions[:, 0].max():.1f}")

    # ── 와일드카드 뷰 ─────────────────────────────────────────────────────
    # 파이썬 루프로 하나씩 만들지 않는다. 뷰 하나가 N개를 배치로 다룬다.
    probes = RigidPrim(prim_paths_expr="/World/envs/*/Probe", name="probes")
    world.scene.add(probes)

    robots = None
    if use_robot:
        robots = Articulation(prim_paths_expr="/World/envs/*/Robot", name="robots")
        world.scene.add(robots)

    world.reset()

    ok = True

    if robots is not None:
        joint_positions = np.asarray(robots.get_joint_positions())
        print(f"robots.count = {robots.count}   "
              f"joint_positions.shape = {joint_positions.shape}")
        if robots.count != args.num_envs:
            print(f"  [실패] 로봇 개수가 {robots.count}로 기대({args.num_envs})와 다릅니다.")
            ok = False

        # ── 환경마다 다른 초기 자세를 "한 번의 호출"로 ────────────────────
        targets = np.tile(HOME, (args.num_envs, 1))
        if args.num_envs > 1:
            targets[:, 0] += np.linspace(-0.4, 0.4, args.num_envs)
        robots.set_joint_positions(targets)
        world.step(render=False)

        spread = float(np.asarray(robots.get_joint_positions())[:, 0].std())
        print(f"관절1 환경별 표준편차: {spread:.4f}", end="  ")
        if args.num_envs == 1 or spread > 0.05:
            print("(환경별 차이 적용됨)")
        else:
            print("\n  [실패] 환경마다 같은 자세입니다 — 배치 설정을 확인하세요.")
            ok = False

    # ── env 원점 오프셋 반영 ──────────────────────────────────────────────
    # 로컬 좌표 (0, 0, PHANTOM_TOP_Z + 0.25)를 각 환경의 월드 좌표로 변환.
    # 이 오프셋을 빼먹으면 모든 환경이 env_0 자리로 몰린다.
    local_probe = np.array([0.0, 0.0, PHANTOM_TOP_Z + 0.25])
    world_probe = env_positions + local_probe
    probes.set_world_poses(positions=world_probe)
    world.step(render=False)

    probe_x = np.asarray(probes.get_world_poses()[0])[:, 0]
    preview = ", ".join(f"{v:.2f}" for v in probe_x[:6])
    print(f"프로브 월드 x: [{preview}{', ...' if args.num_envs > 6 else ''}]")
    if args.num_envs > 1:
        gaps = np.diff(np.sort(np.unique(np.round(probe_x, 3))))
        if gaps.size and not np.isclose(gaps.min(), args.spacing, atol=1e-2):
            print(f"  [경고] 환경 간 x 간격이 spacing({args.spacing})과 다릅니다: "
                  f"{gaps.min():.3f}")

    # ── 벤치마크 ──────────────────────────────────────────────────────────
    print(f"\n--- 벤치마크 (device={args.device}, render={args.render}) ---")
    # 워밍업: 첫 스텝들은 물리 초기화와 커널 컴파일이 섞여 있어 측정에서 뺀다.
    for _ in range(args.warmup):
        world.step(render=False)
    print(f"워밍업 {args.warmup} 스텝 완료")

    t0 = time.perf_counter()
    for _ in range(args.steps):
        world.step(render=args.render)
    elapsed = time.perf_counter() - t0

    fps = args.steps / elapsed if elapsed > 0 else float("inf")
    env_steps = fps * args.num_envs
    print(f"{args.steps} 스텝 / {elapsed:.2f} s")
    print(f"FPS: {fps:.1f}   env-steps/s: {env_steps:.0f}")

    print("\n--- 요약 (여러 --num-envs로 돌려 비교하세요) ---")
    print(f"{'envs':>5} | {'device':>6} | {'render':>6} | {'FPS':>7} | {'env-steps/s':>11}")
    print(f"{args.num_envs:>5} | {args.device:>6} | {str(args.render):>6} | "
          f"{fps:>7.1f} | {env_steps:>11.0f}")

    print("-" * 60)
    if ok:
        print("PASS: 클로닝과 배치 제어가 정상 동작합니다.")
        return 0
    print("FAIL: 위 [실패] 항목을 확인하세요.")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:
        print(f"[에러] {exc}")
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
