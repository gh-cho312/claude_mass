"""Ex 11 — 공개 의료 로봇 데이터셋 다루기 (해답)

Isaac Sim 없이 동작합니다.

실행:
    conda activate openh
    python solution.py --test              # API 호환성만 짧게 확인
    python solution.py --episodes 20

주의: 이 코드는 lerobot 의 공개 API 를 기준으로 작성했으나, 실제
Open-H-Embodiment 데이터를 내려받아 실행 검증하지는 못했습니다.
키 이름이 다르면 --test 로 먼저 돌려 실제 스키마를 확인한 뒤 조정하세요.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

DEFAULT_REPO = os.environ.get(
    "OPENH_REPO_ID", "nvidia/PhysicalAI-Robotics-Open-H-Embodiment"
)

parser = argparse.ArgumentParser(description="Ex11: 공개 데이터셋 탐색")
parser.add_argument("--repo", default=DEFAULT_REPO)
parser.add_argument("--episodes", type=int, default=20)
parser.add_argument("--max-frames", type=int, default=2000)
parser.add_argument("--out", default="_out_ex11")
parser.add_argument("--test", action="store_true")
args = parser.parse_args()

if args.test:
    args.episodes = 2
    args.max_frames = 100

os.makedirs(args.out, exist_ok=True)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Part A
# ─────────────────────────────────────────────────────────────
def open_streaming(repo_id: str):
    """스트리밍 데이터셋을 연다. 모듈 경로는 lerobot 버전마다 다르다."""
    cls = None
    errors = []
    for mod in (
        "lerobot.datasets.streaming_dataset",
        "lerobot.common.datasets.streaming_dataset",
    ):
        try:
            cls = __import__(mod, fromlist=["StreamingLeRobotDataset"])
            cls = cls.StreamingLeRobotDataset
            print(f"  StreamingLeRobotDataset <- {mod}")
            break
        except Exception as e:  # ImportError 외에도 하위 의존성 문제가 날 수 있음
            errors.append(f"{mod}: {e}")

    if cls is None:
        sys.exit(
            "StreamingLeRobotDataset 를 import 하지 못했습니다.\n  "
            + "\n  ".join(errors)
            + "\n\n  pip install -U 'lerobot>=0.6.0'"
        )

    try:
        return cls(repo_id)
    except Exception as e:
        sys.exit(
            f"데이터셋을 열지 못했습니다: {repo_id}\n"
            f"  {e}\n"
            "  - HF 로그인이 필요할 수 있습니다: hf auth login\n"
            "  - 이 저장소가 LeRobot v3.0 포맷이 아닐 수 있습니다.\n"
            "    python tools/explore_openh.py --tree 로 실제 구조를 확인하세요."
        )


def _get(ds, name):
    """ds 또는 ds.meta 에서 속성을 찾는다."""
    v = getattr(ds, name, None)
    if v is None and hasattr(ds, "meta"):
        v = getattr(ds.meta, name, None)
    return v


def report_meta(ds) -> dict:
    meta = {}
    for name in ("num_episodes", "num_frames", "fps"):
        v = _get(ds, name)
        meta[name] = v
        print(f"  {name}: {v}")

    features = _get(ds, "features")
    if isinstance(features, dict):
        print("  features:")
        feat_out = {}
        for k, v in features.items():
            print(f"    {k}: {v}")
            feat_out[k] = str(v)
        meta["features"] = feat_out
    else:
        print("  features: (조회 실패 — 프레임에서 직접 확인합니다)")
    return meta


def _describe(v) -> str:
    shape = getattr(v, "shape", None)
    if shape is not None:
        return f"shape={tuple(shape)} dtype={getattr(v, 'dtype', '?')}"
    if isinstance(v, str):
        return f"str({len(v)}자): {v[:60]!r}"
    return type(v).__name__


def inspect_first_frame(ds) -> dict:
    frame = next(iter(ds))
    images, vectors, others = [], [], []
    for k, v in frame.items():
        shape = getattr(v, "shape", None)
        if shape is not None and len(shape) >= 3:
            images.append(k)
        elif shape is not None:
            vectors.append(k)
        else:
            others.append(k)
        print(f"    {k:<44} {_describe(v)}")

    print(f"\n  이미지 키 {len(images)}개: {images}")
    print(f"  벡터   키 {len(vectors)}개: {vectors}")
    print(f"  기타   키 {len(others)}개: {others}")
    return frame


# ─────────────────────────────────────────────────────────────
# Part B
# ─────────────────────────────────────────────────────────────
def guess_semantics(arr: np.ndarray, name: str) -> list[str]:
    """값 분포로 각 차원의 의미를 추론한다.

    쿼터니언 탐지가 까다롭습니다. 위치 성분이 작으면 `[pos_x, pos_y, pos_z,
    quat_w]` 같은 엉뚱한 창의 norm 도 1에 가까워집니다. 그래서 앞에서부터
    greedy 하게 잡으면 진짜 쿼터니언 블록을 가로챕니다.

    해결: 모든 4연속 창의 "norm 이 1에서 벗어난 정도"를 점수로 매기고,
    점수가 좋은 순서로 겹치지 않게 배정합니다. 진짜 쿼터니언은 편차가
    사실상 0이라 항상 이깁니다.

    또한 쿼터니언 성분은 상수일 수 있으므로(quat_y=quat_z=0 인 경우가 흔함)
    상수·이산 판정을 쿼터니언 배정 **뒤에** 해야 합니다.
    """
    if arr.ndim != 2:
        return ["(2차원 배열 아님)"]

    D = arr.shape[1]
    lo, hi, sd = arr.min(0), arr.max(0), arr.std(0)
    labels: list[str | None] = [None] * D

    # 1) 단위 쿼터니언 후보 창을 점수순으로 배정
    # 이산적으로 토글하는 열(그리퍼 등)은 쿼터니언 성분일 수 없다.
    # 단, 상수 0 인 열은 quat_y/quat_z 로 흔하므로 배제하지 않는다.
    def _is_toggling(col: np.ndarray) -> bool:
        return col.std() > 1e-8 and len(np.unique(np.round(col, 3))) <= 3

    toggling = {d for d in range(D) if _is_toggling(arr[:, d])}

    cands = []
    for i in range(D - 3):
        window = range(i, i + 4)
        if any(d in toggling for d in window):
            continue                        # 그리퍼가 낀 창은 쿼터니언이 아니다
        block = arr[:, i : i + 4]
        if block.std(0).max() <= 1e-9:      # 전부 상수인 창은 제외
            continue
        dev = float(np.abs(np.linalg.norm(block, axis=1) - 1.0).max())
        if dev < 5e-3:
            # 타이브레이크: 0 으로 패딩된 이웃이 있으면 여러 창이 동시에
            # norm 1 을 만족한다. 예) [0, qw, qx, qy] 와 [qw, qx, qy, qz].
            # 값만으로는 구분되지 않으므로, 첫 성분의 크기가 큰 쪽을 고른다.
            # 회전이 작을수록 quat_w 가 1에 가깝다는 성질을 이용한 휴리스틱이다.
            w_mag = float(np.abs(block[:, 0]).mean())
            cands.append((round(dev, 9), -w_mag, i))

    taken: set[int] = set()
    for _dev, _w, i in sorted(cands):
        window = set(range(i, i + 4))
        if window & taken:
            continue
        for j in window:
            labels[j] = "quaternion?"
        taken |= window

    # 2) 남은 차원 분류
    for d in range(D):
        if labels[d] is not None:
            continue
        if sd[d] < 1e-8:
            labels[d] = "constant"
        elif len(np.unique(np.round(arr[:, d], 3))) <= 3:
            labels[d] = "gripper?/discrete"
        elif lo[d] >= -np.pi - 0.1 and hi[d] <= np.pi + 0.1 and hi[d] - lo[d] > 1.0:
            labels[d] = "joint_angle(rad)?"
        elif abs(lo[d]) < 1.0 and abs(hi[d]) < 1.0:
            labels[d] = "position(m)?/normalized"
        else:
            labels[d] = "unknown"

    return [x or "unknown" for x in labels]


def find_instruction(frame: dict) -> str | None:
    preferred = ("task", "instruction", "language", "prompt")
    fallback = None
    for k, v in frame.items():
        if isinstance(v, str):
            if any(p in k.lower() for p in preferred):
                return f"{k}: {v}"
            fallback = fallback or f"{k}: {v}"
    return fallback


# ─────────────────────────────────────────────────────────────
# Part C
# ─────────────────────────────────────────────────────────────
def collect_episode(ds, max_frames: int) -> dict[str, np.ndarray]:
    """벡터형 키만 모아 (T, D) 배열로 만든다."""
    buf: dict[str, list] = {}
    ep_key = None
    ep_first = None
    n = 0

    for frame in ds:
        # 에피소드 경계 감지
        for cand in ("episode_index", "episode_id", "episode"):
            if cand in frame:
                ep_key = cand
                break
        if ep_key is not None:
            val = frame[ep_key]
            val = int(val) if np.ndim(val) == 0 else int(np.asarray(val).flat[0])
            if ep_first is None:
                ep_first = val
            elif val != ep_first:
                print(f"  에피소드 경계 감지 ({ep_key}={ep_first} 종료), {n} 프레임")
                break

        for k, v in frame.items():
            shape = getattr(v, "shape", None)
            if shape is None or len(shape) >= 3:
                continue  # 이미지·문자열 제외
            arr = np.asarray(v, dtype=np.float64).reshape(-1)
            buf.setdefault(k, []).append(arr)

        n += 1
        if n >= max_frames:
            print(f"  max_frames({max_frames}) 도달 — 에피소드 끝이 아닐 수 있습니다")
            break

    if ep_key is None:
        print("  에피소드 인덱스 키를 찾지 못했습니다. max_frames 로 잘랐습니다.")

    out = {}
    for k, lst in buf.items():
        try:
            out[k] = np.stack(lst)
        except ValueError:
            print(f"  {k}: 프레임마다 길이가 달라 건너뜁니다")
    print(f"  수집: {n} 프레임, 키 {len(out)}개")
    return out


def _pick(traj: dict, *needles) -> str | None:
    for k in traj:
        if any(nd in k.lower() for nd in needles):
            return k
    return None


def plot_trajectory(traj: dict[str, np.ndarray], out_dir: str) -> None:
    act_key = _pick(traj, "action") or _pick(traj, "state", "observation")
    if act_key is None or traj[act_key].ndim != 2:
        print("  플롯할 액션 키를 찾지 못했습니다.")
        return

    a = traj[act_key]
    T, D = a.shape

    # 1) 차원별 시간축
    ncol = min(4, D)
    nrow = (D + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 2.2 * nrow), squeeze=False)
    labels = guess_semantics(a, act_key)
    for d in range(D):
        ax = axes[d // ncol][d % ncol]
        ax.plot(a[:, d], lw=0.9)
        ax.set_title(f"dim {d} — {labels[d]}", fontsize=8)
        ax.tick_params(labelsize=6)
    for d in range(D, nrow * ncol):
        axes[d // ncol][d % ncol].axis("off")
    fig.suptitle(f"{act_key}  (T={T}, D={D})", fontsize=10)
    fig.tight_layout()
    p = os.path.join(out_dir, "action_dims.png")
    fig.savefig(p, dpi=110)
    plt.close(fig)
    print(f"  저장: {p}")

    # 2) 앞 3차원을 위치로 보고 3D 궤적
    if D >= 3:
        fig = plt.figure(figsize=(5, 4.5))
        ax = fig.add_subplot(111, projection="3d")
        ax.plot(a[:, 0], a[:, 1], a[:, 2], lw=1.0)
        ax.scatter(*a[0, :3], c="g", s=40, label="start")
        ax.scatter(*a[-1, :3], c="r", s=40, label="end")
        ax.set_xlabel("dim0"); ax.set_ylabel("dim1"); ax.set_zlabel("dim2")
        ax.legend(fontsize=8)
        ax.set_title("First 3 dims as XYZ trajectory", fontsize=10)
        p = os.path.join(out_dir, "trajectory_3d.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        print(f"  저장: {p}")

    # 3) 그리퍼 후보
    grip = [d for d, lb in enumerate(labels) if "gripper" in lb]
    if grip:
        fig, ax = plt.subplots(figsize=(8, 2.4))
        for d in grip:
            ax.step(range(T), a[:, d], where="post", label=f"dim {d}")
        ax.set_title("Gripper open/close timing", fontsize=10)
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = os.path.join(out_dir, "gripper.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        print(f"  저장: {p}")


def plot_length_histogram(lengths: list[int], out_dir: str) -> None:
    if not lengths:
        return
    arr = np.array(lengths)
    print(f"  에피소드 길이 — 평균 {arr.mean():.0f}, 중앙값 {np.median(arr):.0f}, "
          f"최소 {arr.min()}, 최대 {arr.max()}")
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.hist(arr, bins=min(20, max(3, len(arr) // 2)))
    ax.set_xlabel("frames"); ax.set_ylabel("episodes")
    ax.set_title(f"Episode length distribution (n={len(arr)})", fontsize=10)
    fig.tight_layout()
    p = os.path.join(out_dir, "episode_lengths.png")
    fig.savefig(p, dpi=110)
    plt.close(fig)
    print(f"  저장: {p}")


# ─────────────────────────────────────────────────────────────
# Part D
# ─────────────────────────────────────────────────────────────
ISAAC_PSM_ACTION = [
    ("pos_x", "m", "베이스 프레임 기준 EE 위치"),
    ("pos_y", "m", ""),
    ("pos_z", "m", ""),
    ("quat_w", "-", "쿼터니언 wxyz 순서"),
    ("quat_x", "-", ""),
    ("quat_y", "-", ""),
    ("quat_z", "-", ""),
    ("gripper", "-", "OPEN=+1.0 / CLOSE=-1.0"),
]


def compatibility_report(traj: dict[str, np.ndarray], out_dir: str) -> None:
    act_key = _pick(traj, "action")
    lines = [
        "# Ex11 — Isaac PSM 액션 호환성 판정",
        "",
        "대상 환경: `Isaac-Lift-Needle-PSM-IK-Abs-v0` (액션 8차원)",
        "",
        "| Isaac 액션 | 단위 | 설명 | 데이터셋 대응 | 판정 |",
        "|---|---|---|---|---|",
    ]

    if act_key is None:
        for name, unit, desc in ISAAC_PSM_ACTION:
            lines.append(f"| `{name}` | {unit} | {desc} | — | ❌ 액션 키 없음 |")
        note = "데이터셋에서 action 키를 찾지 못했습니다."
    else:
        a = traj[act_key]
        labels = guess_semantics(a, act_key)
        D = a.shape[1]
        for i, (name, unit, desc) in enumerate(ISAAC_PSM_ACTION):
            if i < D:
                mapped = f"`{act_key}[{i}]` ({labels[i]})"
                verdict = "⚠️ 추정" if "?" in labels[i] else "✅"
            else:
                mapped = "—"
                verdict = f"❌ 데이터 차원 {D} < 8"
            lines.append(f"| `{name}` | {unit} | {desc} | {mapped} | {verdict} |")
        note = (
            f"데이터셋 액션 차원 = {D}. "
            + ("차원 수는 맞습니다. " if D == 8 else "차원 수가 다릅니다. ")
            + "차원이 맞아도 **좌표계 원점·축 방향·단위**가 같다는 보장은 없습니다."
        )

    lines += [
        "",
        "## 주의",
        "",
        f"- {note}",
        "- 위 대응은 **값 분포에 근거한 추정**입니다. 데이터셋 문서로 반드시 교차 확인하세요.",
        "- 차원과 단위가 모두 맞아도, 실기기에서 기록한 궤적을 시뮬레이터에서",
        "  재생하면 **동작은 재현되지만 접촉·변형은 재현되지 않습니다.**",
        "  자세한 내용은 `docs/06-데이터셋-Isaac-Sim-호환성.md` L2 절 참고.",
        "",
        "## 다음 단계",
        "",
        "이 표를 설계도 삼아 `exercises/ex12_trajectory_replay/` 로 진행하세요.",
    ]

    p = os.path.join(out_dir, "compatibility.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  저장: {p}")
    print("\n" + "\n".join(lines[4 : 4 + 10]))


# ─────────────────────────────────────────────────────────────
def main() -> None:
    print(f"[Ex11] repo={args.repo}  out={args.out}")

    ds = open_streaming(args.repo)

    print("\n=== Part A: 메타 ===")
    meta = report_meta(ds)

    print("\n  첫 프레임 구조:")
    frame = inspect_first_frame(ds)

    instr = find_instruction(frame)
    print(f"\n  자연어 지시문: {instr if instr else '(없음)'}")

    print("\n=== Part C: 궤적 수집 ===")
    traj = collect_episode(ds, args.max_frames)

    if traj:
        plot_trajectory(traj, args.out)

        print("\n=== Part B: 스키마 추론 ===")
        for key, arr in traj.items():
            if arr.ndim == 2 and arr.shape[1] <= 32:
                print(f"  {key} (D={arr.shape[1]}): {guess_semantics(arr, key)}")

        print("\n=== Part D: 호환성 ===")
        compatibility_report(traj, args.out)
    else:
        print("  수집된 벡터 키가 없어 이후 단계를 건너뜁니다.")

    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n완료. 결과: {args.out}/")
    if args.test:
        print("(--test 모드였습니다. 실제 분석은 --test 없이 돌리세요.)")


if __name__ == "__main__":
    main()
