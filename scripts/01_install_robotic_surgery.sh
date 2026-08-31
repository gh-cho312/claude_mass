#!/usr/bin/env bash
# 01_install_robotic_surgery.sh — i4h robotic_surgery 워크플로 설치
#
# ORBIT-Surgical 의 공식 후계자인 Isaac for Healthcare 의 robotic_surgery
# 워크플로를 설치합니다. (Isaac Sim 5.0 / Isaac Lab 2.3.0 / Python 3.11)
#
# 원본 ORBIT-Surgical(Isaac Sim 4.1.0 / Isaac Lab 1.0.0 / Python 3.10)은
# 현재 스택과 충돌하므로 설치하지 않습니다. docs/04-i4h-설치-RTX3090.md 참고.
#
# 사용법:
#   ./scripts/01_install_robotic_surgery.sh
#   CONFIRM_YES=1 ./scripts/01_install_robotic_surgery.sh   # 확인 없이 진행

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_env

I4H_ROOT="${I4H_ROOT:-$HOME/i4h-workflows}"
I4H_CONDA_ENV="${I4H_CONDA_ENV:-robotic_surgery}"
PY_VER="3.11"
REPO_URL="https://github.com/isaac-for-healthcare/i4h-workflows.git"

hdr "i4h robotic_surgery 설치"
info "설치 경로   : $I4H_ROOT"
info "conda 환경  : $I4H_CONDA_ENV (Python $PY_VER)"
info "예상 소요   : 40~60분 (env_setup 스크립트가 대부분 차지)"
echo
warn "설치 중 디스크를 100GB 가까이 사용합니다. 사전에 00_preflight.sh 를 돌리세요."
echo

confirm "계속 진행할까요?" || { info "취소했습니다."; exit 0; }

# ── 1. 저장소 클론 ────────────────────────────────────────────
hdr "1/4 저장소 준비"
require_cmd git

if [[ -d "$I4H_ROOT/.git" ]]; then
  ok "이미 존재합니다: $I4H_ROOT"
  info "최신 상태로 맞추려면 직접 실행하세요:  git -C '$I4H_ROOT' pull"
else
  if [[ -e "$I4H_ROOT" ]]; then
    die "$I4H_ROOT 가 이미 있지만 git 저장소가 아닙니다. 경로를 정리하거나 I4H_ROOT 를 바꾸세요."
  fi
  info "클론 중: $REPO_URL"
  git clone "$REPO_URL" "$I4H_ROOT"
  ok "클론 완료"
fi

# ── 2. conda 환경 ─────────────────────────────────────────────
hdr "2/4 conda 환경"
require_cmd conda "Miniconda: https://docs.conda.io/en/latest/miniconda.html"
init_conda || die "conda 초기화에 실패했습니다."

if conda env list | awk '{print $1}' | grep -qx "$I4H_CONDA_ENV"; then
  ok "환경 '$I4H_CONDA_ENV' 이 이미 있습니다. 재사용합니다."
  ACTUAL_PY=$(conda run -n "$I4H_CONDA_ENV" python --version 2>&1 | awk '{print $2}')
  info "기존 Python 버전: $ACTUAL_PY"
  if [[ "$ACTUAL_PY" != $PY_VER* ]]; then
    warn "Python 버전이 $PY_VER 계열이 아닙니다. 문제가 생기면 환경을 지우고 다시 만드세요:"
    warn "  conda env remove -n $I4H_CONDA_ENV"
  fi
else
  info "환경 생성: $I4H_CONDA_ENV (Python $PY_VER)"
  conda create -n "$I4H_CONDA_ENV" "python=$PY_VER" -y
  ok "생성 완료"
fi

# ── 3. 의존성 설치 ────────────────────────────────────────────
hdr "3/4 의존성 설치 (40~60분)"
SETUP_SCRIPT="$I4H_ROOT/tools/env_setup_robot_surgery.sh"

if [[ ! -f "$SETUP_SCRIPT" ]]; then
  err "설치 스크립트를 찾을 수 없습니다: $SETUP_SCRIPT"
  err "저장소 구조가 바뀌었을 수 있습니다. 아래에서 확인하세요:"
  err "  https://github.com/isaac-for-healthcare/i4h-workflows/tree/main/workflows/robotic_surgery"
  exit 1
fi

info "실행: bash tools/env_setup_robot_surgery.sh"
info "(Isaac Sim 5.0 + Isaac Lab 2.3.0 + RSL-RL 을 설치합니다. 오래 걸립니다.)"
echo

conda activate "$I4H_CONDA_ENV"
pushd "$I4H_ROOT" >/dev/null
bash "$SETUP_SCRIPT"
popd >/dev/null
ok "의존성 설치 완료"

# ── 4. PYTHONPATH ─────────────────────────────────────────────
hdr "4/4 PYTHONPATH 설정"
PYPATH_LINE="export PYTHONPATH=$I4H_ROOT/workflows/robotic_surgery/scripts:\$PYTHONPATH"

if grep -qF "$I4H_ROOT/workflows/robotic_surgery/scripts" "$HOME/.bashrc" 2>/dev/null; then
  ok "~/.bashrc 에 이미 등록되어 있습니다."
else
  if confirm "~/.bashrc 에 PYTHONPATH 를 영구 등록할까요?"; then
    {
      echo ""
      echo "# i4h robotic_surgery (added by claude_mass setup)"
      echo "$PYPATH_LINE"
    } >> "$HOME/.bashrc"
    ok "~/.bashrc 에 추가했습니다. 새 터미널부터 적용됩니다."
  else
    info "건너뜁니다. 매번 아래를 직접 실행하세요:"
    echo "    $PYPATH_LINE"
  fi
fi

# ── 완료 ──────────────────────────────────────────────────────
hdr "설치 완료"
cat <<MSG

  사용하려면 매 세션마다:

    conda activate $I4H_CONDA_ENV
    export PYTHONPATH=$I4H_ROOT/workflows/robotic_surgery/scripts:\$PYTHONPATH
    cd $I4H_ROOT

  다음 단계:

    ./scripts/02_smoke_test.sh        # 데모가 뜨는지 확인
    ./scripts/03_find_max_envs.sh     # RTX 3090 의 num_envs 상한 탐색
    ./scripts/04_train_rl.sh          # 본 학습

MSG
ok "다음 단계: ./scripts/02_smoke_test.sh"
