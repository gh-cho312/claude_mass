"""Ex 06 — 접촉력 기반 스캔 제어: 프로브 접촉압 유지 (해답)

프로브를 팬텀에 접근시켜 접촉을 감지하고, 목표 힘(8 N)을 유지하며 표면을 스캔한 뒤
안전하게 후퇴한다. 로보틱스 워크플로우의 뼈대인 상태기계 + 어드미턴스 제어 예제.

핵심 학습 포인트
  1. ContactSensor를 로봇 링크에 붙이고 힘을 읽는다
  2. 어드미턴스 제어: 힘 오차 → 위치 보정 (부호 감각이 핵심)
  3. 상태기계 구조 — 안전 조건은 상태 분기보다 "먼저" 검사한다
  4. 힘 이력 통계로 제어 품질을 정량 평가

실행:
    python solution.py --test --headless
    python solution.py --desired-force 12.0     # 더 세게 누르기
"""

from __future__ import annotations

import argparse
from enum import Enum, auto

import numpy as np

parser = argparse.ArgumentParser(description="Ex06: 접촉력 기반 스캔 제어")
parser.add_argument("--headless", action="store_true")
parser.add_argument("--test", action="store_true")
parser.add_argument("--desired-force", type=float, default=8.0, help="목표 접촉력 (N)")
parser.add_argument("--kp", type=float, default=4.0e-5, help="어드미턴스 이득 (m/N)")
parser.add_argument("--csv", default="", help="힘 이력을 저장할 CSV 경로")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import isaacsim.core.utils.numpy.rotations as rot_utils  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
from isaacsim.core.prims import SingleArticulation  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from isaacsim.robot_motion.motion_generation import (  # noqa: E402
    ArticulationKinematicsSolver,
    LulaKinematicsSolver,
    interface_config_loader,
)
from isaacsim.sensors.physics import ContactSensor  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

# ── 씬 상수 ────────────────────────────────────────────────────────────────
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H            # 0.93
ROBOT_BASE = np.array([0.0, -0.42, TABLE_TOP_Z])
ROBOT_PRIM = "/World/ProbeHolder"
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
EE_FRAME = "panda_hand"

# 손(panda_hand) 프레임 원점에서 프로브 끝까지의 오프셋.
# 엔드이펙터 목표 z는 "프로브 끝이 표면에 닿는 z" + 이 값이 된다.
PROBE_LENGTH = 0.11

# ── 제어 파라미터 ──────────────────────────────────────────────────────────
CONTACT_THRESHOLD = 1.0       # N — 이 이상이면 "닿았다"
MAX_FORCE = 25.0              # N — 안전 상한
FORCE_BAND = 2.0              # N — 목표 ±이 값이 허용 대역
APPROACH_DZ = 0.001           # m/step — 하강 속도
MAX_DZ_PER_STEP = 0.0005      # m/step — 어드미턴스 보정 상한
SWEEP_DX = 0.00035            # m/step — 약 2 cm/s @ 60 Hz
SWEEP_DISTANCE = 0.20         # m
LOST_CONTACT_STEPS = 60
FORCE_FILTER_ALPHA = 0.15     # 저역통과 필터 계수

START_X = -0.10
START_HEIGHT = 0.05           # 표면 위에서 시작하는 높이


class ScanState(Enum):
    APPROACH = auto()
    CONTACT = auto()
    SWEEP = auto()
    RETRACT = auto()
    DONE = auto()


def build_scene() -> tuple[World, SingleArticulation, ContactSensor]:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    assets_root = get_assets_root_path()
    if assets_root is None:
        raise RuntimeError("Isaac Sim 에셋 폴더를 찾을 수 없습니다.")

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.4, 0.7, TABLE_TOP_Z]), size=1.0,
        color=np.array([70, 80, 95]),
    ))
    world.scene.add(FixedCuboid(
        prim_path="/World/Phantom", name="phantom",
        position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_H / 2.0]),
        scale=np.array([0.50, 0.30, PHANTOM_H]), size=1.0,
        color=np.array([240, 200, 180]),
    ))

    add_reference_to_stage(usd_path=assets_root + FRANKA_USD, prim_path=ROBOT_PRIM)
    arm = SingleArticulation(prim_path=ROBOT_PRIM, name="probe_holder", position=ROBOT_BASE)
    world.scene.add(arm)

    # 접촉 센서는 강체 링크의 자식으로 붙인다.
    # translation은 손 프레임 기준 — 프로브 끝 근처에 감지 구를 둔다.
    sensor = world.scene.add(ContactSensor(
        prim_path=f"{ROBOT_PRIM}/panda_hand/probe_contact",
        name="probe_contact",
        min_threshold=0.0,
        max_threshold=1.0e7,
        radius=0.06,
        translation=np.array([0.0, 0.0, PROBE_LENGTH]),
    ))
    sensor.add_raw_contact_data_to_frame()

    set_camera_view(eye=[1.0, -1.2, 1.4], target=[0.0, -0.05, 0.95],
                    camera_prim_path="/OmniverseKit_Persp")
    return world, arm, sensor


def read_force(sensor: ContactSensor) -> tuple[float, bool]:
    """접촉 센서에서 (힘 크기 N, 접촉 여부)를 읽는다."""
    frame = sensor.get_current_frame()
    if not frame:
        return 0.0, False
    force = float(frame.get("value", 0.0) or 0.0)
    in_contact = bool(frame.get("in_contact", force > 0.0))
    return abs(force), in_contact


def main() -> int:
    world, arm, sensor = build_scene()
    world.reset()

    # ── IK 세팅 (Ex05와 동일. set_robot_base_pose를 잊지 말 것) ────────────
    cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
    ik_solver = LulaKinematicsSolver(**cfg)
    base_pos, base_quat = arm.get_world_pose()
    ik_solver.set_robot_base_pose(base_pos, base_quat)          # ★ 필수
    art_ik = ArticulationKinematicsSolver(arm, ik_solver, EE_FRAME)
    controller = arm.get_articulation_controller()

    probe_down = rot_utils.euler_angles_to_quats(np.array([180.0, 0.0, 0.0]), degrees=True)

    # 초기 자세 (특이점 회피)
    arm.set_joint_positions(np.array([0.0, -0.4, 0.0, -2.0, 0.0, 1.6, 0.79, 0.02, 0.02]))
    for _ in range(30):
        world.step(render=not args.headless)

    # ── 상태기계 초기화 ───────────────────────────────────────────────────
    state = ScanState.APPROACH
    target_x = START_X
    target_z = PHANTOM_TOP_Z + START_HEIGHT + PROBE_LENGTH
    filtered_force = 0.0
    lost_contact = 0
    sweep_start_x: float | None = None
    swept = 0.0
    force_log: list[tuple[int, str, float, float, float]] = []
    peak_force = 0.0
    safety_tripped = False

    max_steps = 900 if args.test else 2500
    render = not args.headless
    desired = args.desired_force

    def log_transition(step: int, old: ScanState, new: ScanState, note: str) -> None:
        print(f"[{step:4d}] {old.name} → {new.name}   ({note})")

    for step in range(max_steps):
        raw_force, in_contact = read_force(sensor)
        # 접촉력은 스텝마다 크게 튄다. 필터를 걸지 않으면 제어가 진동한다.
        filtered_force = (FORCE_FILTER_ALPHA * raw_force
                          + (1.0 - FORCE_FILTER_ALPHA) * filtered_force)
        peak_force = max(peak_force, raw_force)

        # ── 안전 조건은 상태 분기보다 "먼저" ──────────────────────────────
        if raw_force > MAX_FORCE and state in (ScanState.APPROACH, ScanState.CONTACT,
                                               ScanState.SWEEP):
            print(f"[{step:4d}] ⚠ 안전 정지: 접촉력 {raw_force:.1f} N > {MAX_FORCE} N")
            log_transition(step, state, ScanState.RETRACT, "과도한 힘")
            state = ScanState.RETRACT
            safety_tripped = True

        # ── 상태별 동작 ───────────────────────────────────────────────────
        if state is ScanState.APPROACH:
            target_z -= APPROACH_DZ
            if filtered_force > CONTACT_THRESHOLD:
                log_transition(step, state, ScanState.CONTACT,
                               f"접촉 감지: {filtered_force:.2f} N, z={target_z:.3f}")
                state = ScanState.CONTACT
            elif target_z < PHANTOM_TOP_Z - 0.05 + PROBE_LENGTH:
                print(f"[{step:4d}] ✗ 표면을 지나쳤는데 접촉이 감지되지 않음 "
                      f"(센서 radius/translation을 확인하세요)")
                state = ScanState.RETRACT

        elif state is ScanState.CONTACT:
            # 어드미턴스: 힘이 부족하면(오차>0) 더 내려간다 → dz는 음수
            force_error = desired - filtered_force
            dz = float(np.clip(-args.kp * force_error, -MAX_DZ_PER_STEP, MAX_DZ_PER_STEP))
            target_z += dz
            if abs(force_error) < FORCE_BAND * 0.5:
                log_transition(step, state, ScanState.SWEEP,
                               f"힘 수렴: {filtered_force:.2f} N")
                state = ScanState.SWEEP
                sweep_start_x = target_x

        elif state is ScanState.SWEEP:
            # 스캔하며 계속 힘을 유지한다 (같은 어드미턴스 법칙)
            force_error = desired - filtered_force
            dz = float(np.clip(-args.kp * force_error, -MAX_DZ_PER_STEP, MAX_DZ_PER_STEP))
            target_z += dz
            target_x += SWEEP_DX
            swept = target_x - (sweep_start_x if sweep_start_x is not None else START_X)

            lost_contact = 0 if in_contact else lost_contact + 1
            if lost_contact > LOST_CONTACT_STEPS:
                print(f"[{step:4d}] ✗ 접촉 상실이 {LOST_CONTACT_STEPS} 스텝 지속 — 중단")
                log_transition(step, state, ScanState.RETRACT, "접촉 상실")
                state = ScanState.RETRACT
            elif swept >= SWEEP_DISTANCE:
                log_transition(step, state, ScanState.RETRACT,
                               f"스캔 완료: {swept:.3f} m")
                state = ScanState.RETRACT

        elif state is ScanState.RETRACT:
            target_z += APPROACH_DZ * 2.0
            if target_z > PHANTOM_TOP_Z + 0.10 + PROBE_LENGTH:
                log_transition(step, state, ScanState.DONE, "후퇴 완료")
                state = ScanState.DONE

        if state is ScanState.DONE:
            break

        # ── IK로 목표 자세 추종 ───────────────────────────────────────────
        action, ok = art_ik.compute_inverse_kinematics(
            target_position=np.array([target_x, 0.0, target_z]),
            target_orientation=probe_down,
        )
        if ok:
            controller.apply_action(action)
        elif step % 100 == 0:
            print(f"[{step:4d}] [경고] IK 해 없음 target=({target_x:+.3f}, 0, {target_z:.3f})")

        world.step(render=render)
        force_log.append((step, state.name, raw_force, filtered_force, target_x))

        if step % 200 == 0:
            print(f"[{step:4d}] {state.name:9s} x={target_x:+.3f} z={target_z:.3f} "
                  f"force={filtered_force:5.2f} N")

    # ── 리포트 ────────────────────────────────────────────────────────────
    sweep_forces = np.array([f for (_, s, _, f, _) in force_log if s == "SWEEP"])
    lo, hi = desired - FORCE_BAND, desired + FORCE_BAND

    print("\n=== 스캔 리포트 ===")
    print(f"SWEEP 스텝: {len(sweep_forces)}")
    if sweep_forces.size:
        in_band = float(((sweep_forces >= lo) & (sweep_forces <= hi)).mean())
        print(f"평균 힘 {sweep_forces.mean():.2f} N / "
              f"최대 {sweep_forces.max():.1f} N / 최소 {sweep_forces.min():.1f} N")
        print(f"목표 대역({lo:.1f}~{hi:.1f} N) 유지율: {in_band * 100:.1f}%")
    else:
        in_band = 0.0
        print("SWEEP 구간이 없습니다 — 접촉 감지 단계에서 실패했습니다.")
    print(f"스캔 거리: {swept:.3f} m")
    print(f"최대 순간 힘: {peak_force:.1f} N (안전 상한 {MAX_FORCE} N)")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as fh:
            fh.write("step,state,raw_force_N,filtered_force_N,target_x_m\n")
            for row in force_log:
                fh.write(f"{row[0]},{row[1]},{row[2]:.4f},{row[3]:.4f},{row[4]:.5f}\n")
        print(f"힘 이력 저장: {args.csv}")

    # ── 판정 ──────────────────────────────────────────────────────────────
    print("-" * 60)
    band_target = 0.60 if args.test else 0.80
    dist_target = 0.05 if args.test else SWEEP_DISTANCE * 0.9
    ok = (in_band >= band_target and swept >= dist_target and not safety_tripped)
    if ok:
        print("PASS: 목표 힘을 유지하며 스캔을 완료했습니다.")
        return 0
    print("FAIL")
    if safety_tripped:
        print("  → 안전 상한을 넘었습니다. --kp 를 줄이거나 APPROACH_DZ를 줄이세요.")
    if in_band < band_target:
        print(f"  → 힘 유지율 {in_band * 100:.1f}% < {band_target * 100:.0f}%. "
              "--kp 조정, 필터 계수(FORCE_FILTER_ALPHA) 조정을 시도하세요.")
    if swept < dist_target:
        print(f"  → 스캔 거리 {swept:.3f} m 부족. 스텝 수를 늘리거나 "
              "접촉 감지가 제대로 되는지 확인하세요.")
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
