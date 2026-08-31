#!/usr/bin/env bash
# 10_install_openh.sh — Open-H-Embodiment 데이터셋 작업 환경 구축
#
# Open-H-Embodiment 는 시뮬레이터 확장이 아니라 LeRobot 포맷 데이터셋입니다.
# Isaac Sim 과 무관하며, robotic_surgery(Python 3.11)와 요구 버전이 달라
# 반드시 별도 conda 환경을 씁니다.
#
# 사용법:
#   ./scripts/10_install_openh.sh

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_env

OPENH_CONDA_ENV="${OPENH_CONDA_ENV:-openh}"
OPENH_DATA_DIR="${OPENH_DATA_DIR:-$HOME/data/open-h-embodiment}"
PY_VER="3.12"

hdr "Open-H-Embodiment 환경 구축"
info "conda 환경 : $OPENH_CONDA_ENV (Python $PY_VER)"
info "데이터 경로: $OPENH_DATA_DIR"
echo
warn "이 스크립트는 '환경만' 만듭니다. 데이터는 받지 않습니다."
warn "전체 데이터셋은 780시간 규모라 통째로 받으면 디스크가 감당하지 못합니다."
warn "먼저 tools/explore_openh.py 로 스트리밍 탐색한 뒤 필요한 서브셋만 받으세요."
echo

confirm "계속할까요?" || { info "취소했습니다."; exit 0; }

require_cmd conda "Miniconda: https://docs.conda.io/en/latest/miniconda.html"
init_conda || die "conda 초기화 실패"

if conda env list | awk '{print $1}' | grep -qx "$OPENH_CONDA_ENV"; then
  ok "환경 '$OPENH_CONDA_ENV' 이 이미 있습니다. 재사용합니다."
else
  info "환경 생성 중..."
  conda create -n "$OPENH_CONDA_ENV" "python=$PY_VER" -y
  ok "생성 완료"
fi

hdr "패키지 설치"
conda activate "$OPENH_CONDA_ENV"

# lerobot >= 0.6.0 이 LeRobotDataset v3.0 을 지원합니다.
info "lerobot + huggingface_hub 설치 중..."
pip install --upgrade pip
pip install "lerobot>=0.6.0" "huggingface_hub[cli]" pandas pyarrow tqdm

ok "설치 완료"

hdr "설치 확인"
python - <<'PY'
import sys
print(f"  Python  : {sys.version.split()[0]}")
try:
    import lerobot
    print(f"  lerobot : {getattr(lerobot, '__version__', 'unknown')}")
except Exception as e:
    print(f"  lerobot : import 실패 -> {e}")
try:
    import huggingface_hub
    print(f"  hf_hub  : {huggingface_hub.__version__}")
except Exception as e:
    print(f"  hf_hub  : import 실패 -> {e}")
PY

mkdir -p "$OPENH_DATA_DIR"
ok "데이터 디렉터리 준비: $OPENH_DATA_DIR"

hdr "완료"
cat <<MSG

  사용하려면:

    conda activate $OPENH_CONDA_ENV

  다음 단계 — 먼저 '스트리밍으로' 살펴보세요 (디스크를 쓰지 않습니다):

    python tools/explore_openh.py

  살펴본 뒤 필요한 서브셋만 받기:

    python tools/download_openh_subset.py --list
    python tools/download_openh_subset.py --include "<서브셋경로>/*"

MSG
