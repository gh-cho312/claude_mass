#!/usr/bin/env bash
# 환경 설정 예시 — 복사해서 사용하세요:
#   cp config/env.example.sh config/env.sh
# config/env.sh 는 .gitignore 되어 있어 로컬 경로를 담아도 안전합니다.

# ─────────────────────────────────────────────────────────────
# i4h-workflows 저장소를 클론할(또는 이미 클론한) 경로
# ─────────────────────────────────────────────────────────────
export I4H_ROOT="${I4H_ROOT:-$HOME/i4h-workflows}"

# robotic_surgery 워크플로용 conda 환경 이름 (Python 3.11 고정)
export I4H_CONDA_ENV="${I4H_CONDA_ENV:-robotic_surgery}"

# ─────────────────────────────────────────────────────────────
# Open-H-Embodiment 데이터셋
# ─────────────────────────────────────────────────────────────
export OPENH_CONDA_ENV="${OPENH_CONDA_ENV:-openh}"

# 데이터 저장 위치. 파티션 용량이 빠듯하면 여유 있는 디스크로 지정하세요.
export OPENH_DATA_DIR="${OPENH_DATA_DIR:-$HOME/data/open-h-embodiment}"

# HuggingFace 데이터셋 repo id
export OPENH_REPO_ID="${OPENH_REPO_ID:-nvidia/PhysicalAI-Robotics-Open-H-Embodiment}"

# HuggingFace 캐시 위치 (기본값은 ~/.cache/huggingface — 홈 파티션을 먹습니다)
# export HF_HOME="/mnt/bigdisk/hf-cache"

# ─────────────────────────────────────────────────────────────
# RTX 3090 튜닝
# ─────────────────────────────────────────────────────────────
# 탐색 스크립트가 시도할 num_envs 사다리
export ENV_LADDER="${ENV_LADDER:-256 512 1024 2048 4096}"

# VRAM 사용률 상한(%). 이 값을 넘으면 탐색을 멈춥니다.
export VRAM_LIMIT_PCT="${VRAM_LIMIT_PCT:-85}"

# 본 학습에 사용할 num_envs (03_find_max_envs.sh 결과를 여기 적으세요)
export TRAIN_NUM_ENVS="${TRAIN_NUM_ENVS:-1024}"

# 기본 태스크
export DEFAULT_RL_TASK="${DEFAULT_RL_TASK:-Isaac-Reach-PSM-v0}"
