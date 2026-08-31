"""Ex 11 — 공개 의료 로봇 데이터셋 다루기 (뼈대 코드)

Isaac Sim 없이 동작합니다. conda env "openh" 에서 실행하세요.

실행:
    conda activate openh
    python starter.py --test
    python starter.py --episodes 20 --out _out_ex11
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

DEFAULT_REPO = os.environ.get(
    "OPENH_REPO_ID", "nvidia/PhysicalAI-Robotics-Open-H-Embodiment"
)

parser = argparse.ArgumentParser(description="Ex11: 공개 데이터셋 탐색")
parser.add_argument("--repo", default=DEFAULT_REPO, help="HuggingFace repo id")
parser.add_argument("--episodes", type=int, default=20, help="길이 분포에 쓸 에피소드 수")
parser.add_argument("--max-frames", type=int, default=2000, help="에피소드당 최대 프레임")
parser.add_argument("--out", default="_out_ex11")
parser.add_argument("--test", action="store_true", help="짧게 돌려 API 호환성만 확인")
args = parser.parse_args()

if args.test:
    args.episodes = 2
    args.max_frames = 100

os.makedirs(args.out, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Part A — 데이터셋 열기
# ─────────────────────────────────────────────────────────────
def open_streaming(repo_id: str):
    """스트리밍 데이터셋을 연다 (다운로드 없음).

    TODO:
      1. StreamingLeRobotDataset 를 import 한다.
         - lerobot 버전에 따라 모듈 경로가 다르다. 두 경로를 모두 시도할 것:
             lerobot.datasets.streaming_dataset
             lerobot.common.datasets.streaming_dataset
      2. repo_id 로 데이터셋을 열어 반환한다.
      3. 실패하면 원인을 사람이 읽을 수 있게 안내하고 종료한다.
    """
    raise NotImplementedError("TODO: open_streaming 구현")


def report_meta(ds) -> dict:
    """메타 정보를 출력하고 dict 로 반환한다.

    TODO:
      - num_episodes, num_frames, fps 를 찾아 출력한다.
        (ds 에 직접 있을 수도, ds.meta 아래 있을 수도 있다)
      - features 딕셔너리를 키/shape/dtype 로 정리해 출력한다.
    """
    raise NotImplementedError("TODO: report_meta 구현")


def inspect_first_frame(ds) -> dict:
    """첫 프레임의 모든 키에 대해 shape / dtype 을 출력한다.

    TODO:
      - iter(ds) 로 첫 프레임을 꺼낸다
      - 각 값에 대해 shape 이 있으면 shape, 없으면 타입명을 출력
      - 이미지로 보이는 키(3차원 이상)와 벡터 키를 구분해 표시하면 좋다
    """
    raise NotImplementedError("TODO: inspect_first_frame 구현")


# ─────────────────────────────────────────────────────────────
# Part B — 스키마 해석
# ─────────────────────────────────────────────────────────────
def guess_semantics(arr: np.ndarray, name: str) -> list[str]:
    """벡터의 값 분포로부터 각 차원의 의미를 추론한다.

    arr: (T, D) 배열
    반환: 각 차원에 대한 추정 라벨 리스트

    TODO — 다음 휴리스틱을 구현하세요:
      - 값이 대체로 -pi ~ pi 범위      → "joint_angle(rad)?"
      - 절댓값이 1보다 작고 연속적     → "position(m)?"
      - 연속된 4개의 norm 이 1에 가까움 → "quaternion?"
      - 두 값 사이만 오가는 이산적 신호 → "gripper?"
      - 그 외                          → "unknown"

    힌트: arr.min(0), arr.max(0), arr.std(0), np.unique 를 활용하세요.
    """
    raise NotImplementedError("TODO: guess_semantics 구현")


def find_instruction(frame: dict) -> str | None:
    """프레임에서 자연어 지시문으로 보이는 값을 찾는다.

    TODO:
      - 값이 문자열인 키를 찾는다
      - 키 이름에 task / instruction / language / prompt 가 들어가면 우선
    """
    raise NotImplementedError("TODO: find_instruction 구현")


# ─────────────────────────────────────────────────────────────
# Part C — 궤적 수집과 시각화
# ─────────────────────────────────────────────────────────────
def collect_episode(ds, max_frames: int) -> dict[str, np.ndarray]:
    """에피소드 하나 분량의 프레임을 모아 키별 배열로 만든다.

    TODO:
      - iter(ds) 로 프레임을 돌면서 벡터형 키만 리스트에 쌓는다
      - 에피소드 경계를 어떻게 알 수 있는지 생각해 보세요.
        (episode_index 같은 키가 있을 수도, 없을 수도 있습니다.
         없으면 max_frames 로 자르되 그 사실을 출력에 명시하세요.)
      - 각 키를 np.stack 해서 (T, D) 로 만든다
    """
    raise NotImplementedError("TODO: collect_episode 구현")


def plot_trajectory(traj: dict[str, np.ndarray], out_dir: str) -> None:
    """궤적을 PNG 로 저장한다.

    TODO:
      1. 액션으로 보이는 키에 대해 각 차원의 시간축 그래프
      2. 위치 3차원을 찾았다면 3D 궤적 (mpl_toolkits.mplot3d)
      3. 그리퍼로 추정된 차원의 개폐 타이밍

    주의: matplotlib 은 Agg 백엔드로 쓰세요 (headless 환경).
        import matplotlib; matplotlib.use("Agg")
    """
    raise NotImplementedError("TODO: plot_trajectory 구현")


def plot_length_histogram(lengths: list[int], out_dir: str) -> None:
    """에피소드 길이 분포 히스토그램.

    TODO: matplotlib 으로 저장. 평균/중앙값도 함께 출력.
    """
    raise NotImplementedError("TODO: plot_length_histogram 구현")


# ─────────────────────────────────────────────────────────────
# Part D — Isaac Sim dVRK 호환성 판정
# ─────────────────────────────────────────────────────────────
# Ex12 에서 쓸 환경의 액션 레이아웃 (i4h robotic_surgery 실제 값)
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
    """데이터셋 액션 ↔ Isaac PSM 8차원 액션 대응표를 만든다.

    TODO:
      - ISAAC_PSM_ACTION 각 항목에 대해 데이터셋의 어느 차원이 대응되는지 적는다
      - 대응되지 않으면 그 이유를 적는다 (단위 불일치 / 좌표계 불명 / 아예 없음)
      - 결과를 out_dir/compatibility.md 로 저장한다

    이 표가 Ex12 변환기의 설계도가 됩니다. 대충 채우지 마세요.
    """
    raise NotImplementedError("TODO: compatibility_report 구현")


# ─────────────────────────────────────────────────────────────
def main() -> None:
    print(f"[Ex11] repo={args.repo}  out={args.out}")

    ds = open_streaming(args.repo)

    print("\n=== Part A: 메타 ===")
    meta = report_meta(ds)
    inspect_first_frame(ds)

    print("\n=== Part C: 궤적 수집 ===")
    traj = collect_episode(ds, args.max_frames)
    plot_trajectory(traj, args.out)

    print("\n=== Part B: 스키마 추론 ===")
    for key, arr in traj.items():
        if arr.ndim == 2 and arr.shape[1] <= 32:
            print(f"  {key}: {guess_semantics(arr, key)}")

    print("\n=== Part D: 호환성 ===")
    compatibility_report(traj, args.out)

    with open(os.path.join(args.out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n완료. 결과: {args.out}/")


if __name__ == "__main__":
    main()
