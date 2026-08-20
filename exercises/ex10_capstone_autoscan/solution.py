"""Ex 10 — 캡스톤: 자율 초음파 스캔 + 학습 데이터셋 생성 (해답)

Ex01~09를 통합한 엔드투엔드 워크플로우.
상태기계로 자율 스캔을 수행하고, 그 궤적을 정책 학습용 HDF5 데이터셋으로 저장한다.

핵심 학습 포인트
  1. 서브시스템 통합 — IK + 접촉 센서 + 상태기계 + 듀얼 카메라
  2. 제어 주파수(기록) ≠ 물리 주파수 — 렌더는 기록할 때만
  3. robomimic 스타일 HDF5 계층 (data/demo_N/obs/*, actions, rewards, dones)
  4. 이미지 압축을 빼먹으면 파일이 GB 단위가 된다

실행:
    python solution.py --test --episodes 1
    python solution.py --episodes 5 --out _out_ex10
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
parser.add_argument("--record-every", type=int, default=4, help="N 물리 스텝마다 기록")
parser.add_argument("--desired-force", type=float, default=8.0)
parser.add_argument("--kp", type=float, default=4.0e-5)
parser.add_argument("--img-width", type=int, default=320)
parser.add_argument("--img-height", type=int, default=240)
args, _ = parser.parse_known_args()

if args.test:
    args.episodes = min(args.episodes, 1)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import isaacsim.core.utils.numpy.rotations as rot_utils  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
from isaacsim.core.prims import SingleArticulation  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.robot_motion.motion_generation import (  # noqa: E402
    ArticulationKinematicsSolver,
    LulaKinematicsSolver,
    interface_config_loader,
)
from isaacsim.sensors.camera import Camera  # noqa: E402
from isaacsim.sensors.physics import ContactSensor  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402
from pxr import Sdf, UsdLux  # noqa: E402

# ── 씬 상수 ────────────────────────────────────────────────────────────────
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H
ROBOT_BASE = np.array([0.0, -0.42, TABLE_TOP_Z])
ROBOT_PRIM = "/World/ProbeHolder"
FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
EE_FRAME = "panda_hand"
PROBE_LENGTH = 0.11

# ── 제어 파라미터 (Ex06과 동일) ────────────────────────────────────────────
CONTACT_THRESHOLD = 1.0
MAX_FORCE = 25.0
FORCE_BAND = 2.0
APPROACH_DZ = 0.001
MAX_DZ_PER_STEP = 0.0005
SWEEP_DX = 0.00035
SWEEP_DISTANCE = 0.20
LOST_CONTACT_STEPS = 60
FORCE_FILTER_ALPHA = 0.15
IK_FAIL_LIMIT = 120
START_X = -0.10
START_HEIGHT = 0.05


class ScanState(Enum):
    APPROACH = auto()
    CONTACT = auto()
    SWEEP = auto()
    RETRACT = auto()
    DONE = auto()


def build_scene():
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    assets_root = get_assets_root_path()
    if assets_root is None:
        raise RuntimeError("Isaac Sim 에셋 폴더를 찾을 수 없습니다.")

    stage = omni.usd.get_context().get_stage()
    key = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
    key.CreateIntensityAttr(2500.0)
    scope = UsdLux.SphereLight.Define(stage, Sdf.Path("/World/ScopeLight"))
    scope.CreateIntensityAttr(25000.0)
    scope.CreateRadiusAttr(0.03)
    scope.AddTranslateOp().Set((0.0, -0.15, 1.35))

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.4, 0.7, TABLE_TOP_Z]), size=1.0,
        color=np.array([65, 75, 90]),
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

    contact = world.scene.add(ContactSensor(
        prim_path=f"{ROBOT_PRIM}/panda_hand/probe_contact",
        name="probe_contact",
        min_threshold=0.0, max_threshold=1.0e7,
        radius=0.06, translation=np.array([0.0, 0.0, PROBE_LENGTH]),
    ))
    contact.add_raw_contact_data_to_frame()

    resolution = (args.img_width, args.img_height)

    # room 카메라: 씬 전체를 비스듬히 내려다본다. 월드에 고정.
    room_cam = Camera(
        prim_path="/World/RoomCamera",
        position=np.array([0.75, -0.85, 1.55]),
        orientation=rot_utils.euler_angles_to_quats(np.array([0.0, 35.0, 132.0]),
                                                    degrees=True),
        frequency=30, resolution=resolution,
    )

    # wrist 카메라: 로봇 링크의 "자식"으로 두면 팔을 따라다닌다.
    # ★ position(월드) 대신 translation(부모 기준 로컬)을 써야 한다.
    wrist_cam = Camera(
        prim_path=f"{ROBOT_PRIM}/panda_hand/WristCamera",
        translation=np.array([0.0, 0.0, 0.055]),
        orientation=rot_utils.euler_angles_to_quats(np.array([0.0, 0.0, 0.0]),
                                                    degrees=True),
        frequency=30, resolution=resolution,
    )

    return world, arm, contact, room_cam, wrist_cam


def read_force(sensor: ContactSensor) -> tuple[float, bool]:
    frame = sensor.get_current_frame()
    if not frame:
        return 0.0, False
    force = float(frame.get("value", 0.0) or 0.0)
    return abs(force), bool(frame.get("in_contact", force > 0.0))


def grab_rgb(camera: Camera, height: int, width: int) -> np.ndarray:
    """카메라에서 (H, W, 3) uint8을 얻는다. 실패하면 검은 프레임."""
    rgba = camera.get_rgba()
    if rgba is None or np.size(rgba) == 0:
        return np.zeros((height, width, 3), dtype=np.uint8)
    return np.ascontiguousarray(np.asarray(rgba)[:, :, :3]).astype(np.uint8)


def run_episode(world, arm, contact, room_cam, wrist_cam, art_ik,
                controller, probe_down, scan_y: float, ep_idx: int) -> dict:
    """에피소드 하나를 실행하고 기록된 프레임 묶음을 반환한다."""
    print(f"\n=== 에피소드 {ep_idx} (scan_y={scan_y:+.3f}) ===")

    # 매 에피소드 시작 시 초기 자세로 복귀
    arm.set_joint_positions(np.array([0.0, -0.4, 0.0, -2.0, 0.0, 1.6, 0.79, 0.02, 0.02]))
    for _ in range(30):
        world.step(render=False)

    state = ScanState.APPROACH
    target_x = START_X
    target_z = PHANTOM_TOP_Z + START_HEIGHT + PROBE_LENGTH
    filtered_force = 0.0
    lost_contact = 0
    ik_fail = 0
    sweep_start_x: float | None = None
    swept = 0.0

    rec = {k: [] for k in ("joint_positions", "joint_velocities", "ee_position",
                           "contact_force", "room_camera", "wrist_camera")}
    actions, rewards, dones = [], [], []
    sweep_forces: list[float] = []

    max_steps = 700 if args.test else 2200
    lo, hi = args.desired_force - FORCE_BAND, args.desired_force + FORCE_BAND

    for step in range(max_steps):
        raw_force, in_contact = read_force(contact)
        filtered_force = (FORCE_FILTER_ALPHA * raw_force
                          + (1.0 - FORCE_FILTER_ALPHA) * filtered_force)

        # 안전 감시는 상태 분기보다 먼저
        if raw_force > MAX_FORCE and state in (ScanState.APPROACH, ScanState.CONTACT,
                                               ScanState.SWEEP):
            print(f"[{step:4d}] ⚠ 안전 정지: {raw_force:.1f} N")
            state = ScanState.RETRACT

        if state is ScanState.APPROACH:
            target_z -= APPROACH_DZ
            if filtered_force > CONTACT_THRESHOLD:
                print(f"[{step:4d}] APPROACH → CONTACT  ({filtered_force:.2f} N)")
                state = ScanState.CONTACT
            elif target_z < PHANTOM_TOP_Z - 0.05 + PROBE_LENGTH:
                print(f"[{step:4d}] ✗ 접촉 미감지 — 중단")
                state = ScanState.RETRACT

        elif state is ScanState.CONTACT:
            error = args.desired_force - filtered_force
            target_z += float(np.clip(-args.kp * error, -MAX_DZ_PER_STEP, MAX_DZ_PER_STEP))
            if abs(error) < FORCE_BAND * 0.5:
                print(f"[{step:4d}] CONTACT → SWEEP     ({filtered_force:.2f} N)")
                state = ScanState.SWEEP
                sweep_start_x = target_x

        elif state is ScanState.SWEEP:
            error = args.desired_force - filtered_force
            target_z += float(np.clip(-args.kp * error, -MAX_DZ_PER_STEP, MAX_DZ_PER_STEP))
            target_x += SWEEP_DX
            swept = target_x - (sweep_start_x if sweep_start_x is not None else START_X)
            sweep_forces.append(filtered_force)

            lost_contact = 0 if in_contact else lost_contact + 1
            if lost_contact > LOST_CONTACT_STEPS:
                print(f"[{step:4d}] ✗ 접촉 상실 — 중단")
                state = ScanState.RETRACT
            elif swept >= SWEEP_DISTANCE:
                print(f"[{step:4d}] SWEEP → RETRACT     ({swept:.3f} m)")
                state = ScanState.RETRACT

        elif state is ScanState.RETRACT:
            target_z += APPROACH_DZ * 2.0
            if target_z > PHANTOM_TOP_Z + 0.10 + PROBE_LENGTH:
                print(f"[{step:4d}] RETRACT → DONE")
                state = ScanState.DONE

        if state is ScanState.DONE:
            break

        target = np.array([target_x, scan_y, target_z])
        action, ok = art_ik.compute_inverse_kinematics(
            target_position=target, target_orientation=probe_down)
        if ok:
            controller.apply_action(action)
            ik_fail = 0
        else:
            ik_fail += 1
            if ik_fail > IK_FAIL_LIMIT:
                print(f"[{step:4d}] ✗ IK 연속 실패 {ik_fail}회 — 중단")
                break

        # ★ 기록하는 스텝에서만 렌더링한다. 렌더가 병목이다.
        record_now = (step % args.record_every == 0)
        world.step(render=record_now)

        if record_now:
            ee_pos, _ = art_ik.compute_end_effector_pose(position_only=True)
            rec["joint_positions"].append(np.asarray(arm.get_joint_positions(), dtype=np.float32))
            rec["joint_velocities"].append(np.asarray(arm.get_joint_velocities(), dtype=np.float32))
            rec["ee_position"].append(np.asarray(ee_pos, dtype=np.float32))
            rec["contact_force"].append(np.array([filtered_force], dtype=np.float32))
            rec["room_camera"].append(grab_rgb(room_cam, args.img_height, args.img_width))
            rec["wrist_camera"].append(grab_rgb(wrist_cam, args.img_height, args.img_width))

            actions.append(np.array([target_x, scan_y, target_z, args.desired_force],
                                    dtype=np.float32))
            # 보상: 힘이 목표 대역 안이면 1. 정책 학습 시 성공 신호로 쓴다.
            rewards.append(np.float32(1.0 if lo <= filtered_force <= hi else 0.0))
            dones.append(np.int8(0))

        if step % 250 == 0:
            print(f"[{step:4d}] {state.name:9s} force={filtered_force:5.2f} N  x={target_x:+.3f}")

    if dones:
        dones[-1] = np.int8(1)

    success = (state is ScanState.DONE) and (swept >= SWEEP_DISTANCE * 0.9)
    mean_force = float(np.mean(sweep_forces)) if sweep_forces else 0.0
    print(f"기록 프레임 {len(actions)}개, 평균 힘 {mean_force:.2f} N, "
          f"스캔 {swept:.3f} m  → {'성공' if success else '실패'}")

    return {
        "obs": {k: np.asarray(v) for k, v in rec.items()},
        "actions": np.asarray(actions, dtype=np.float32),
        "rewards": np.asarray(rewards, dtype=np.float32),
        "dones": np.asarray(dones, dtype=np.int8),
        "success": bool(success),
        "scan_distance": float(swept),
        "mean_force": mean_force,
    }


# ---------------------------------------------------------------------------
# 저장
# ---------------------------------------------------------------------------
def save_dataset(episodes: list[dict], out_dir: str) -> str:
    """robomimic 스타일 HDF5로 저장. h5py가 없으면 .npz로 폴백."""
    os.makedirs(out_dir, exist_ok=True)
    env_meta = {
        "env_name": "IsaacSimAutoScan-v0",
        "control_hz": round(60.0 / max(args.record_every, 1), 2),
        "desired_force_N": args.desired_force,
        "image_size": [args.img_height, args.img_width],
        "phantom_top_z": PHANTOM_TOP_Z,
        "robot_base": ROBOT_BASE.tolist(),
    }

    try:
        import h5py
    except ImportError:
        path = os.path.join(out_dir, "scan_dataset.npz")
        flat: dict[str, np.ndarray] = {}
        for i, ep in enumerate(episodes):
            for key, arr in ep["obs"].items():
                flat[f"demo_{i}/obs/{key}"] = arr
            flat[f"demo_{i}/actions"] = ep["actions"]
            flat[f"demo_{i}/rewards"] = ep["rewards"]
            flat[f"demo_{i}/dones"] = ep["dones"]
        np.savez_compressed(path, env_args=json.dumps(env_meta), **flat)
        print(f"\n[알림] h5py가 없어 .npz로 저장했습니다: {path}")
        print("       설치: pip install h5py  (바이너리 설치면 ./python.sh -m pip install h5py)")
        return path

    path = os.path.join(out_dir, "scan_dataset.hdf5")
    with h5py.File(path, "w") as fh:
        data = fh.create_group("data")
        data.attrs["total"] = int(sum(len(ep["actions"]) for ep in episodes))
        data.attrs["num_demos"] = len(episodes)
        data.attrs["env_args"] = json.dumps(env_meta)

        for i, ep in enumerate(episodes):
            demo = data.create_group(f"demo_{i}")
            demo.attrs["num_samples"] = int(len(ep["actions"]))
            demo.attrs["success"] = bool(ep["success"])
            demo.attrs["scan_distance"] = float(ep["scan_distance"])

            obs = demo.create_group("obs")
            for key, arr in ep["obs"].items():
                # ★ 이미지는 반드시 압축. 안 하면 파일이 GB 단위가 된다.
                kwargs = ({"compression": "gzip", "compression_opts": 4}
                          if arr.ndim == 4 else {})
                obs.create_dataset(key, data=arr, **kwargs)

            demo.create_dataset("actions", data=ep["actions"])
            demo.create_dataset("rewards", data=ep["rewards"])
            demo.create_dataset("dones", data=ep["dones"])
    return path


def verify_dataset(path: str, episodes: list[dict]) -> bool:
    """저장한 파일을 다시 읽어 완결성을 검증한다."""
    print("\n=== 데이터셋 검증 ===")
    size_mb = os.path.getsize(path) / 1024 ** 2
    print(f"파일: {path} ({size_mb:.1f} MB)")

    ok = True
    expected_keys = {"joint_positions", "joint_velocities", "ee_position",
                     "contact_force", "room_camera", "wrist_camera"}

    if path.endswith(".npz"):
        print("[알림] npz 폴백 — 구조 검증은 생략하고 통계만 확인합니다.")
    else:
        import h5py
        with h5py.File(path, "r") as fh:
            data = fh["data"]
            print(f"demo 수: {data.attrs['num_demos']}   총 샘플: {data.attrs['total']}")
            for name in sorted(data.keys()):
                demo = data[name]
                lengths = {k: demo["obs"][k].shape[0] for k in demo["obs"]}
                lengths["actions"] = demo["actions"].shape[0]
                lengths["rewards"] = demo["rewards"].shape[0]
                lengths["dones"] = demo["dones"].shape[0]

                missing = expected_keys - set(demo["obs"].keys())
                if missing:
                    print(f"{name}: [실패] 누락된 키 {missing}")
                    ok = False
                    continue

                unique_t = set(lengths.values())
                if len(unique_t) != 1:
                    print(f"{name}: [실패] T 불일치 {lengths}")
                    ok = False
                    continue

                t = unique_t.pop()
                print(f"{name}: T={t}  키 {len(lengths)}개 모두 일치")
                for cam in ("room_camera", "wrist_camera"):
                    arr = demo["obs"][cam]
                    brightness = float(np.asarray(arr[: min(8, t)]).mean())
                    print(f"  {cam:13s} {arr.shape} {arr.dtype}  밝기 {brightness:.1f}")
                    if brightness < 20:
                        print(f"    [실패] {cam}가 거의 검은색입니다 — 조명/렌더를 확인하세요")
                        ok = False

    successes = sum(1 for ep in episodes if ep["success"])
    rate = successes / max(len(episodes), 1)
    print(f"성공률: {successes}/{len(episodes)} ({rate * 100:.0f}%)")
    forces = [ep["mean_force"] for ep in episodes if ep["mean_force"] > 0]
    if forces:
        print(f"에피소드 평균 힘: {np.mean(forces):.2f} N (목표 {args.desired_force} N)")
        if abs(np.mean(forces) - args.desired_force) > FORCE_BAND:
            print("  [경고] 평균 힘이 목표 대역을 벗어났습니다 — --kp 를 조정하세요.")

    if rate < 0.7:
        print(f"  [실패] 성공률 {rate * 100:.0f}% < 70%")
        ok = False
    return ok


def main() -> int:
    world, arm, contact, room_cam, wrist_cam = build_scene()
    world.reset()

    room_cam.initialize()
    wrist_cam.initialize()

    cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
    ik_solver = LulaKinematicsSolver(**cfg)
    ik_solver.set_robot_base_pose(*arm.get_world_pose())      # ★ 필수 (Ex05 참고)
    art_ik = ArticulationKinematicsSolver(arm, ik_solver, EE_FRAME)
    controller = arm.get_articulation_controller()
    probe_down = rot_utils.euler_angles_to_quats(np.array([180.0, 0.0, 0.0]), degrees=True)

    # 카메라 렌더 워밍업 (Ex04에서 배운 것)
    for _ in range(40):
        world.step(render=True)

    # 에피소드마다 스캔 라인의 y를 조금씩 다르게 — 데이터 다양성 확보
    scan_ys = np.linspace(-0.05, 0.05, args.episodes) if args.episodes > 1 else np.array([0.0])

    episodes = []
    for idx, scan_y in enumerate(scan_ys):
        episodes.append(run_episode(world, arm, contact, room_cam, wrist_cam,
                                    art_ik, controller, probe_down,
                                    float(scan_y), idx))

    path = save_dataset(episodes, args.out)
    ok = verify_dataset(path, episodes)

    print("-" * 60)
    if ok:
        print("PASS: 학습에 쓸 수 있는 데이터셋이 생성되었습니다.")
        print("      다음 단계 → docs/03-i4h-연결.md 의 학습 파이프라인")
        return 0
    print("FAIL: 위 [실패] 항목을 확인하세요.")
    print("      Ex05(IK) / Ex06(접촉) / Ex04(카메라)를 따로 돌려 원인을 좁히세요.")
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
