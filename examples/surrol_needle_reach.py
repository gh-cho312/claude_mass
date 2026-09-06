#!/usr/bin/env python3
"""SurRoL 가장 간단한 예제 — dVRK 수술로봇(PSM)이 바늘에 도달하는 태스크.

이 파일은 Isaac Sim과 **무관**합니다. SurRoL(PyBullet 기반 수술로봇 RL 시뮬)용이며
반드시 별도 conda 환경('surrol')에서 실행하세요.

────────────────────────────────────────────────────────────────────────
설치 (Python 3.10 + SurRoL-v2 브랜치)
────────────────────────────────────────────────────────────────────────
  conda create -n surrol python=3.10 -y -c conda-forge --override-channels
  conda activate surrol
  mkdir -p ~/isaac-healthcare-sims && cd ~/isaac-healthcare-sims
  git clone -b SurRoL-v2 https://github.com/med-air/SurRoL.git     # ★ v2 브랜치
  cd SurRoL && pip install -e .
  pip install "gym==0.25.2"          # ★ 중요: 0.26+ 는 step API가 바뀌어 깨집니다

  ※ main 브랜치는 연구용 모노레포라 루트에 setup.py 가 없고, 태스크가
    MPM(taichi)까지 끌어옵니다. 간단히 보려면 반드시 SurRoL-v2 를 쓰세요.

실행
────
  python examples/surrol_needle_reach.py              # 창 띄우고 100스텝
  python examples/surrol_needle_reach.py --headless   # 화면 없이(원격/SSH)
  python examples/surrol_needle_reach.py --env NeedlePick-v0 --steps 200

사용 가능한 환경:
  PSM 단일팔 : NeedleReach-v0, NeedlePick-v0, GauzeRetrieve-v0, PegTransfer-v0
  PSM 양팔   : NeedleRegrasp-v0, BiPegTransfer-v0
  ECM 카메라 : ECMReach-v0, MisOrient-v0, StaticTrack-v0, ActiveTrack-v0
"""
from __future__ import annotations

import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--env", default="NeedleReach-v0", help="SurRoL 환경 ID")
parser.add_argument("--steps", type=int, default=100, help="스텝 수")
parser.add_argument("--headless", action="store_true", help="창 없이 실행")
args = parser.parse_args()

try:
    import numpy as np
    import gym
    import surrol.gym  # noqa: F401  ← import 하는 것만으로 환경들이 register 됩니다
except ImportError as exc:
    sys.exit(
        f"import 실패: {exc}\n"
        "→ 'surrol' 환경을 활성화했는지 확인하세요:  conda activate surrol\n"
        "→ 설치가 안 됐다면 이 파일 상단 주석의 설치 절차를 따르세요."
    )


def unpack_reset(result):
    """gym 구/신 API 모두 지원: reset()이 obs 또는 (obs, info)를 반환."""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[0]
    return result


def unpack_step(result):
    """gym 구(4-tuple)/신(5-tuple) API 모두 지원."""
    if len(result) == 5:                       # 신형: obs, reward, terminated, truncated, info
        obs, reward, terminated, truncated, info = result
        return obs, reward, bool(terminated or truncated), info
    return result                              # 구형: obs, reward, done, info


# render_mode='human' 이면 PyBullet GUI 창이 뜹니다 (화면이 있어야 함).
render_mode = None if args.headless else "human"
print(f"환경 생성: {args.env} (render_mode={render_mode})")
env = gym.make(args.env, render_mode=render_mode)

obs = unpack_reset(env.reset())
if isinstance(obs, dict):
    # goal 기반 환경: observation / achieved_goal / desired_goal 로 구성됩니다.
    print("관측 키:", list(obs.keys()))
    print("  observation  :", np.asarray(obs["observation"]).shape)
    print("  achieved_goal:", np.asarray(obs["achieved_goal"]).round(3))
    print("  desired_goal :", np.asarray(obs["desired_goal"]).round(3))
print("행동 공간:", env.action_space)

total_reward, successes = 0.0, 0
for i in range(args.steps):
    action = env.action_space.sample()          # 무작위 동작 (정책 학습 전이라 랜덤)
    obs, reward, done, info = unpack_step(env.step(action))
    total_reward += float(reward)
    if info.get("is_success"):
        successes += 1
    if i % 20 == 0:
        print(f"step {i:4d} | reward {float(reward):7.3f} | is_success={info.get('is_success')}")
    if done:
        obs = unpack_reset(env.reset())

print(f"\n총 {args.steps} 스텝 | 누적 보상 {total_reward:.2f} | 성공 프레임 {successes}")
print("→ 무작위 동작이라 성공률은 낮은 게 정상입니다. 정책을 학습시키면 올라갑니다.")
env.close()
