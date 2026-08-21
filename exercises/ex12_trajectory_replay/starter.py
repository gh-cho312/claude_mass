"""Ex 12 — 공개 궤적을 Isaac Sim dVRK에 재생 (뼈대 코드)

conda env "robotic_surgery" 에서 실행하세요.

실행:
    # Part A — 합성 궤적으로 파이프라인부터 검증
    python starter.py --synthetic circle --gui --steps 600

    # Part B~D — 실제 궤적 파일
    python starter.py --traj _out_ex11/episode.npy --gui

    # 짧은 호환성 확인
    python starter.py --synthetic circle --test
"""

from __future__ import annotations

import argparse

import numpy as np

# ── AppLauncher 부트스트랩 ───────────────────────────────────
# argparse → AppLauncher → 그 다음에 시뮬레이션 모듈 import.
# 순서를 어기면 Isaac Sim 확장이 로드되지 않습니다.
parser = argparse.ArgumentParser(description="Ex12: 외부 궤적 재생")
parser.add_argument("--task", default="Isaac-Reach-PSM-IK-Abs-v0")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--disable_fabric", action="store_true", default=False)
parser.add_argument("--traj", default=None, help=".npy/.npz/.csv 궤적 파일")
parser.add_argument("--synthetic", choices=["circle", "line"], default=None)
parser.add_argument("--steps", type=int, default=600)
parser.add_argument("--test", action="store_true")
parser.add_argument("--gui", dest="headless", action="store_false", default=True)
parser.add_argument("--out", default="_out_ex12")

# 궤적 해석 옵션 (Part B)
parser.add_argument("--quat-order", choices=["wxyz", "xyzw"], default="wxyz")
parser.add_argument("--pos-unit", choices=["m", "mm"], default="m")
parser.add_argument("--gripper-convention",
                    choices=["pm1", "unit", "jaw_rad"], default="pm1")
parser.add_argument("--offset", type=float, nargs=3, default=[0.0, 0.0, 0.0])

from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.test:
    args_cli.steps = min(args_cli.steps, 120)
    args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

from isaaclab_tasks.utils.parse_cfg import parse_env_cfg  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Part A — 합성 궤적
# ─────────────────────────────────────────────────────────────
def make_synthetic(kind: str, n: int) -> np.ndarray:
    """검증용 합성 궤적을 (n, 8) 로 만든다.

    레이아웃: [pos(3), quat_wxyz(4), gripper(1)]

    TODO:
      - "circle": 반지름 0.02m 원을 xy 평면에 그린다. z 는 고정
      - "line"  : 한 점에서 다른 점으로 직선
      - 쿼터니언은 단위 쿼터니언 [1,0,0,0] 고정으로 시작해도 좋다
      - 그리퍼는 중간쯤에서 OPEN(+1) → CLOSE(-1) 로 바꿔 본다

    주의: 여기서 만든 위치는 PSM 워크스페이스 안이어야 합니다.
          첫 실행에서 로봇이 못 따라가면 원 중심을 현재 EE 위치 근처로 옮기세요.
    """
    raise NotImplementedError("TODO: make_synthetic 구현")


# ─────────────────────────────────────────────────────────────
# Part B — 궤적 로더
# ─────────────────────────────────────────────────────────────
def load_trajectory(path: str) -> np.ndarray:
    """.npy / .npz / .csv 를 읽어 (T, D) 배열로 반환한다.

    TODO:
      - 확장자별로 분기해서 읽는다
      - .npz 는 키가 여럿일 수 있다. 어떤 키를 쓸지 정하고 출력하라
      - shape 을 출력해 사용자가 확인할 수 있게 한다
    """
    raise NotImplementedError("TODO: load_trajectory 구현")


def to_isaac_actions(raw: np.ndarray) -> np.ndarray:
    """외부 궤적을 Isaac PSM 8차원 액션으로 변환한다.

    입력 raw: (T, D). Ex11 의 compatibility.md 대응표를 따른다.
    출력:     (T, 8) = [pos3, quat_wxyz4, gripper1]

    TODO — args_cli 의 옵션을 모두 반영하세요:
      1. --pos-unit 이 "mm" 이면 위치를 1000 으로 나눈다
      2. --offset 을 위치에 더한다
      3. --quat-order 가 "xyzw" 면 wxyz 로 재배열한다
      4. 쿼터니언을 정규화한다 (norm==1)
      5. --gripper-convention 에 따라 그리퍼를 ±1 로 변환한다
         - "pm1"    : 그대로
         - "unit"   : 0..1 → -1..+1 로 선형 매핑
         - "jaw_rad": 열림각(rad). 임계값 기준으로 ±1 로 이산화
      6. D 가 8 이 아니면 명확한 에러를 낸다

    구현 후 반드시 assert 로 확인하세요:
        assert np.allclose(np.linalg.norm(out[:, 3:7], axis=1), 1.0)
    """
    raise NotImplementedError("TODO: to_isaac_actions 구현")


# ─────────────────────────────────────────────────────────────
# Part C — 정합
# ─────────────────────────────────────────────────────────────
def slerp(q0: np.ndarray, q1: np.ndarray, u: float) -> np.ndarray:
    """쿼터니언 구면 선형보간. README 힌트 참고."""
    raise NotImplementedError("TODO: slerp 구현")


def resample(actions: np.ndarray, n_out: int) -> np.ndarray:
    """(T, 8) 궤적을 n_out 스텝으로 리샘플링한다.

    TODO:
      - 위치와 그리퍼: 선형보간 (그리퍼는 보간 후 부호로 ±1 재이산화)
      - 쿼터니언: slerp. 선형보간하면 회전이 왜곡됩니다
    """
    raise NotImplementedError("TODO: resample 구현")


def clip_to_workspace(actions: np.ndarray, lo, hi) -> np.ndarray:
    """워크스페이스 밖 좌표를 잘라내고 몇 개가 잘렸는지 출력한다.

    TODO: np.clip 을 쓰되, 잘린 스텝 수를 반드시 경고로 출력할 것.
          조용히 자르면 나중에 원인을 못 찾습니다.
    """
    raise NotImplementedError("TODO: clip_to_workspace 구현")


def blend_from_current(actions: np.ndarray, cur_pos, cur_quat,
                       n_blend: int = 60) -> np.ndarray:
    """현재 EE 포즈에서 궤적 첫 프레임까지 부드럽게 잇는다.

    TODO: 앞쪽에 n_blend 스텝을 덧붙여 순간이동을 막는다.
          이걸 빼면 IK 가 발산합니다.
    """
    raise NotImplementedError("TODO: blend_from_current 구현")


# ─────────────────────────────────────────────────────────────
# Part D — 재생 오차 측정
# ─────────────────────────────────────────────────────────────
def quat_angle_error(q_cmd: np.ndarray, q_act: np.ndarray) -> float:
    """두 쿼터니언 사이 각도 오차(rad).

    TODO: 2 * arccos(|dot(q1, q2)|) — 부호 모호성 때문에 절댓값을 씁니다.
    """
    raise NotImplementedError("TODO: quat_angle_error 구현")


def summarize_errors(log: dict, out_dir: str) -> None:
    """오차 통계를 출력하고 플롯을 저장한다.

    TODO:
      - 위치 오차 평균 / 최대 / 표준편차
      - 각도 오차 평균 / 최대
      - 시간축 플롯 (matplotlib, Agg 백엔드)
    """
    raise NotImplementedError("TODO: summarize_errors 구현")


# ─────────────────────────────────────────────────────────────
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
    actions = torch.zeros(env.unwrapped.action_space.shape, device=device)
    actions[:, 3] = 1.0        # 단위 쿼터니언 w — 빼면 로봇이 안 움직입니다

    # TODO:
    #  1. --synthetic 또는 --traj 로 궤적을 얻는다
    #  2. to_isaac_actions → resample → clip_to_workspace → blend_from_current
    #  3. 매 스텝 actions 에 채워 넣고 env.step(actions)
    #  4. env.unwrapped.scene["ee_frame"] 에서 실제 EE 포즈를 읽어 오차 기록
    #  5. 종료 후 summarize_errors

    raise NotImplementedError("TODO: main 재생 루프 구현")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
