"""Ex 12 — 공개 궤적을 Isaac Sim dVRK에 재생 (해답)

conda env "robotic_surgery" 에서 실행하세요.

    python solution.py --synthetic circle --gui --steps 600
    python solution.py --traj episode.npy --pos-unit mm --quat-order xyzw --gui
    python solution.py --synthetic circle --test          # 짧게 확인

⚠️ 검증 상태
    i4h robotic_surgery 의 공개된 state machine 스크립트에서 확인한 API
    (환경 ID, 8차원 액션 레이아웃, scene["ee_frame"] 접근 방식)를 기준으로
    작성했습니다. 다만 실제 Isaac Sim 설치 환경에서 실행 검증하지는
    못했습니다. 순수 계산 부분(변환·리샘플링·오차)은 별도로 검증했습니다.

    먼저 --test 로 돌려 API 호환성을 확인한 뒤 --gui 로 넘어가세요.
"""

from __future__ import annotations

import argparse
import os

import numpy as np

parser = argparse.ArgumentParser(description="Ex12: 외부 궤적 재생")
parser.add_argument("--task", default="Isaac-Reach-PSM-IK-Abs-v0")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--disable_fabric", action="store_true", default=False)
parser.add_argument("--traj", default=None)
parser.add_argument("--synthetic", choices=["circle", "line"], default=None)
parser.add_argument("--steps", type=int, default=600)
parser.add_argument("--test", action="store_true")
parser.add_argument("--gui", dest="headless", action="store_false", default=True)
parser.add_argument("--out", default="_out_ex12")
parser.add_argument("--quat-order", choices=["wxyz", "xyzw"], default="wxyz")
parser.add_argument("--pos-unit", choices=["m", "mm"], default="m")
parser.add_argument("--gripper-convention",
                    choices=["pm1", "unit", "jaw_rad"], default="pm1")
parser.add_argument("--offset", type=float, nargs=3, default=[0.0, 0.0, 0.0])
parser.add_argument("--jaw-threshold", type=float, default=0.2,
                    help="jaw_rad 규약에서 이 각(rad)보다 크면 OPEN")
parser.add_argument("--blend-steps", type=int, default=60)

from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.test:
    args_cli.steps = min(args_cli.steps, 120)
    args_cli.headless = True
if args_cli.synthetic is None and args_cli.traj is None:
    args_cli.synthetic = "circle"
    print("[Ex12] --synthetic/--traj 미지정 → circle 로 진행합니다")

os.makedirs(args_cli.out, exist_ok=True)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

from isaaclab_tasks.utils.parse_cfg import parse_env_cfg  # noqa: E402


# ═════════════════════════════════════════════════════════════
# 순수 계산부 — Isaac Sim 없이도 테스트 가능
# ═════════════════════════════════════════════════════════════
IDENTITY_QUAT = np.array([1.0, 0.0, 0.0, 0.0])   # wxyz


def make_synthetic(kind: str, n: int, center=(0.0, 0.0, 0.10),
                   radius: float = 0.02) -> np.ndarray:
    """검증용 합성 궤적 (n, 8). 레이아웃 [pos3, quat_wxyz4, grip1]."""
    t = np.linspace(0.0, 1.0, n)
    cx, cy, cz = center
    out = np.zeros((n, 8))

    if kind == "circle":
        out[:, 0] = cx + radius * np.cos(2 * np.pi * t)
        out[:, 1] = cy + radius * np.sin(2 * np.pi * t)
        out[:, 2] = cz
    else:  # line
        out[:, 0] = cx - radius + 2 * radius * t
        out[:, 1] = cy
        out[:, 2] = cz

    out[:, 3:7] = IDENTITY_QUAT
    out[:, 7] = np.where(t < 0.5, 1.0, -1.0)     # 중간에 닫아본다
    return out


def load_trajectory(path: str) -> np.ndarray:
    """.npy / .npz / .csv 를 (T, D) 로 읽는다."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        arr = np.load(path)
    elif ext == ".npz":
        z = np.load(path)
        keys = list(z.keys())
        prefer = [k for k in keys if "action" in k.lower()] or keys
        key = prefer[0]
        print(f"  .npz 키 {keys} 중 '{key}' 사용")
        arr = z[key]
    elif ext in (".csv", ".txt"):
        arr = np.loadtxt(path, delimiter=",")
    else:
        raise ValueError(f"지원하지 않는 확장자: {ext} (npy/npz/csv)")

    arr = np.atleast_2d(np.asarray(arr, dtype=np.float64))
    print(f"  로드: {path}  shape={arr.shape}")
    return arr


def to_isaac_actions(raw: np.ndarray) -> np.ndarray:
    """외부 궤적 → Isaac PSM 8차원 액션."""
    if raw.ndim != 2 or raw.shape[1] != 8:
        raise ValueError(
            f"8열이 필요합니다. 받은 shape={raw.shape}\n"
            "  Ex11 의 compatibility.md 대응표를 보고 열을 골라 8열로 만드세요.\n"
            "  예: raw[:, [0,1,2, 6,3,4,5, 7]]"
        )

    out = raw.astype(np.float64).copy()

    # 1) 단위
    if args_cli.pos_unit == "mm":
        out[:, 0:3] /= 1000.0

    # 2) 좌표계 오프셋
    out[:, 0:3] += np.asarray(args_cli.offset, dtype=np.float64)

    # 3) 쿼터니언 순서 xyzw → wxyz
    if args_cli.quat_order == "xyzw":
        out[:, 3:7] = out[:, [6, 3, 4, 5]]

    # 4) 정규화 — 0 벡터는 단위 쿼터니언으로 대체
    norms = np.linalg.norm(out[:, 3:7], axis=1, keepdims=True)
    degenerate = (norms < 1e-8).ravel()
    if degenerate.any():
        print(f"  경고: 쿼터니언 norm≈0 인 프레임 {degenerate.sum()}개 → 단위로 대체")
        out[degenerate, 3:7] = IDENTITY_QUAT
        norms[degenerate] = 1.0
    out[:, 3:7] /= norms

    # 5) 그리퍼 규약
    g = out[:, 7]
    if args_cli.gripper_convention == "unit":
        g = g * 2.0 - 1.0                      # 0..1 → -1..+1
    elif args_cli.gripper_convention == "jaw_rad":
        g = np.where(g > args_cli.jaw_threshold, 1.0, -1.0)
    out[:, 7] = np.clip(g, -1.0, 1.0)

    assert np.allclose(np.linalg.norm(out[:, 3:7], axis=1), 1.0, atol=1e-6)
    return out


def slerp(q0: np.ndarray, q1: np.ndarray, u: float) -> np.ndarray:
    """쿼터니언 구면 선형보간 (wxyz)."""
    q0 = q0 / np.linalg.norm(q0)
    q1 = q1 / np.linalg.norm(q1)
    d = float(np.dot(q0, q1))
    if d < 0.0:                    # 최단 경로
        q1, d = -q1, -d
    if d > 0.9995:                 # 거의 같으면 선형 + 정규화
        q = q0 + u * (q1 - q0)
        return q / np.linalg.norm(q)
    th0 = np.arccos(np.clip(d, -1.0, 1.0))
    th = th0 * u
    q2 = q1 - q0 * d
    q2 /= np.linalg.norm(q2)
    return q0 * np.cos(th) + q2 * np.sin(th)


def resample(actions: np.ndarray, n_out: int) -> np.ndarray:
    """(T,8) → (n_out,8). 위치·그리퍼는 선형, 쿼터니언은 slerp."""
    T = actions.shape[0]
    if T == n_out:
        return actions.copy()
    if T == 1:
        return np.repeat(actions, n_out, axis=0)

    src = np.linspace(0.0, T - 1.0, n_out)
    out = np.zeros((n_out, 8))

    for d in list(range(0, 3)) + [7]:
        out[:, d] = np.interp(src, np.arange(T), actions[:, d])

    for k, s in enumerate(src):
        i = int(np.floor(s))
        if i >= T - 1:
            out[k, 3:7] = actions[-1, 3:7]
        else:
            out[k, 3:7] = slerp(actions[i, 3:7], actions[i + 1, 3:7], s - i)

    # 그리퍼는 보간 후 다시 이산화 (중간값은 물리적으로 의미 없음)
    out[:, 7] = np.where(out[:, 7] >= 0.0, 1.0, -1.0)
    return out


def clip_to_workspace(actions: np.ndarray, lo, hi) -> np.ndarray:
    """워크스페이스 밖 좌표를 자르되, 몇 개가 잘렸는지 반드시 알린다."""
    lo = np.asarray(lo, dtype=np.float64)
    hi = np.asarray(hi, dtype=np.float64)
    pos = actions[:, 0:3]
    outside = ((pos < lo) | (pos > hi)).any(axis=1)
    n = int(outside.sum())
    if n:
        print(f"  경고: 워크스페이스 밖 {n}/{len(actions)} 스텝을 클리핑했습니다")
        print(f"        데이터 범위 min={pos.min(0)} max={pos.max(0)}")
        print(f"        허용 범위   lo={lo} hi={hi}")
        print("        좌표계나 --offset 이 틀렸을 가능성이 큽니다.")
    out = actions.copy()
    out[:, 0:3] = np.clip(pos, lo, hi)
    return out


def blend_from_current(actions: np.ndarray, cur_pos: np.ndarray,
                       cur_quat: np.ndarray, n_blend: int = 60) -> np.ndarray:
    """현재 포즈 → 궤적 첫 프레임을 잇는 구간을 앞에 붙인다."""
    if n_blend <= 0:
        return actions
    first = actions[0]
    bridge = np.zeros((n_blend, 8))
    for k in range(n_blend):
        u = (k + 1) / n_blend
        bridge[k, 0:3] = cur_pos * (1 - u) + first[0:3] * u
        bridge[k, 3:7] = slerp(cur_quat, first[3:7], u)
        bridge[k, 7] = first[7]
    return np.vstack([bridge, actions])


def quat_angle_error(q_cmd: np.ndarray, q_act: np.ndarray) -> float:
    """두 쿼터니언 사이 각도 오차(rad). q 와 -q 는 같은 회전이므로 절댓값 사용.

    분모에 epsilon 을 더해 정규화하면 안 됩니다. norm 이 정확히 1인
    입력에서도 미세하게 어긋나, 동일한 쿼터니언끼리 비교했을 때
    0 이 아닌 값(~1e-6 rad)이 나옵니다.
    """
    na = float(np.linalg.norm(q_cmd))
    nb = float(np.linalg.norm(q_act))
    if na < 1e-12 or nb < 1e-12:
        return float("nan")
    d = float(np.clip(abs(np.dot(q_cmd / na, q_act / nb)), 0.0, 1.0))
    return 2.0 * float(np.arccos(d))


def summarize_errors(log: dict, out_dir: str) -> None:
    """오차 통계 출력 + 플롯 저장."""
    pe = np.asarray(log["pos_err"])
    ae = np.asarray(log["ang_err"])
    if pe.size == 0:
        print("  기록된 오차가 없습니다.")
        return

    print("\n=== 재생 오차 ===")
    print(f"  위치 오차  평균 {pe.mean()*1000:7.2f} mm   "
          f"최대 {pe.max()*1000:7.2f} mm   표준편차 {pe.std()*1000:6.2f} mm")
    print(f"  각도 오차  평균 {np.degrees(ae.mean()):7.2f}°    "
          f"최대 {np.degrees(ae.max()):7.2f}°")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  (matplotlib 없음 — 플롯 생략: {e})")
        return

    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    ax[0].plot(pe * 1000, lw=0.9)
    ax[0].set_ylabel("position error [mm]")
    ax[1].plot(np.degrees(ae), lw=0.9, color="tab:orange")
    ax[1].set_ylabel("angle error [deg]")
    ax[1].set_xlabel("step")
    fig.suptitle("Replay tracking error", fontsize=11)
    fig.tight_layout()
    p = os.path.join(out_dir, "replay_error.png")
    fig.savefig(p, dpi=110)
    plt.close(fig)
    print(f"  저장: {p}")

    cmd = np.asarray(log["cmd_pos"])
    act = np.asarray(log["act_pos"])
    fig = plt.figure(figsize=(5.5, 5))
    ax3 = fig.add_subplot(111, projection="3d")
    ax3.plot(cmd[:, 0], cmd[:, 1], cmd[:, 2], lw=1.2, label="commanded")
    ax3.plot(act[:, 0], act[:, 1], act[:, 2], lw=1.2, ls="--", label="actual EE")
    ax3.legend(fontsize=8)
    ax3.set_title("Commanded vs actual", fontsize=10)
    p = os.path.join(out_dir, "replay_3d.png")
    fig.savefig(p, dpi=110)
    plt.close(fig)
    print(f"  저장: {p}")


# ═════════════════════════════════════════════════════════════
# 시뮬레이션 루프
# ═════════════════════════════════════════════════════════════
def read_ee_pose(env) -> tuple[np.ndarray, np.ndarray]:
    """EE 프레임의 위치·자세를 베이스(환경) 프레임 기준으로 읽는다."""
    ee = env.unwrapped.scene["ee_frame"]
    pos_w = ee.data.target_pos_w[..., 0, :]
    quat_w = ee.data.target_quat_w[..., 0, :]
    pos_b = pos_w - env.unwrapped.scene.env_origins
    return (pos_b[0].detach().cpu().numpy(),
            quat_w[0].detach().cpu().numpy())


def main() -> None:
    env_cfg = parse_env_cfg(
        args_cli.task,
        device=args_cli.device,
        num_envs=args_cli.num_envs,
        use_fabric=not args_cli.disable_fabric,
    )
    env = gym.make(args_cli.task, cfg=env_cfg)
    env.reset()

    device = env.unwrapped.device
    actions_t = torch.zeros(env.unwrapped.action_space.shape, device=device)
    actions_t[:, 3] = 1.0        # 단위 쿼터니언 w — 빼면 로봇이 안 움직입니다

    # 액션 차원이 예상과 다르면 즉시 알린다
    adim = actions_t.shape[-1]
    if adim != 8:
        print(f"  경고: 액션 차원이 {adim} 입니다 (8을 기대). "
              "이 태스크는 레이아웃이 다를 수 있습니다.")

    # ── 궤적 준비 ────────────────────────────────────────────
    if args_cli.synthetic:
        cur_pos, cur_quat = read_ee_pose(env)
        print(f"  현재 EE 위치: {cur_pos}")
        traj = make_synthetic(args_cli.synthetic, args_cli.steps,
                              center=tuple(cur_pos))
        print(f"  합성 궤적 '{args_cli.synthetic}' 생성: {traj.shape}")
    else:
        raw = load_trajectory(args_cli.traj)
        traj = to_isaac_actions(raw)
        cur_pos, cur_quat = read_ee_pose(env)

    traj = resample(traj, args_cli.steps)

    # 워크스페이스: 현재 EE 위치 ± 15cm 를 보수적 경계로 사용
    lo = cur_pos - 0.15
    hi = cur_pos + 0.15
    traj = clip_to_workspace(traj, lo, hi)
    traj = blend_from_current(traj, cur_pos, cur_quat, args_cli.blend_steps)

    print(f"  재생 시작: {len(traj)} 스텝 "
          f"(블렌드 {args_cli.blend_steps} 포함)")

    # ── 재생 루프 ────────────────────────────────────────────
    log = {"cmd_pos": [], "act_pos": [], "pos_err": [], "ang_err": []}
    k = 0

    while simulation_app.is_running() and k < len(traj):
        with torch.inference_mode():
            cmd = traj[k]
            n = min(adim, 8)
            actions_t[:, :n] = torch.as_tensor(
                cmd[:n], dtype=actions_t.dtype, device=device
            )

            env.step(actions_t)

            act_pos, act_quat = read_ee_pose(env)
            log["cmd_pos"].append(cmd[0:3].copy())
            log["act_pos"].append(act_pos.copy())
            log["pos_err"].append(float(np.linalg.norm(cmd[0:3] - act_pos)))
            log["ang_err"].append(quat_angle_error(cmd[3:7], act_quat))

        k += 1
        if k % 100 == 0:
            print(f"    step {k}/{len(traj)}  "
                  f"pos_err={log['pos_err'][-1]*1000:.1f}mm")

    summarize_errors(log, args_cli.out)

    print("\n=== Part E 관찰 과제 ===")
    print("  니들이 있는 환경에서 같은 궤적을 돌려보세요:")
    print("    --task Isaac-Lift-Needle-PSM-IK-Abs-v0")
    print("  그리퍼가 닫힐 때 니들이 실제로 잡히는지 관찰하고,")
    print("  잡히지 않는다면 그 이유를 적으세요. 그것이 이 과제의 결론입니다.")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
