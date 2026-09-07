#!/usr/bin/env bash
# =============================================================================
# Isaac Sim for Healthcare 실습 - 로컬 PC 자동 셋업 스크립트
# -----------------------------------------------------------------------------
# 이 스크립트는 "여러분의 로컬 리눅스 PC(RTX GPU 장착)"에서 실행하는 용도입니다.
# 클라우드/원격 세션이 아니라, Isaac Sim을 실제로 돌릴 그 머신에서 실행하세요.
#
# 하는 일 (기본):
#   1) 사전 점검 (OS / GPU / conda). conda 가 없으면 Miniconda 자동 설치(--no-install-conda 로 끔)
#   2) conda 환경 'isaacsim' (Python 3.11) 생성
#   3) Isaac Sim 5.1.0 (pip) + 이 과제집 추가 의존성(h5py) 설치
#   4) tools/check_env.py 로 환경 검증
#
# 선택 (플래그):
#   --with-surrol   SurRoL(수술로봇 RL 시뮬)을 별도 conda 환경 'surrol'(Py3.10)에 설치
#   --with-i4h      Isaac for Healthcare 워크플로우 저장소를 clone (실행은 Docker 기반)
#
# 사용 예:
#   bash setup_local.sh
#   bash setup_local.sh --with-surrol
#   bash setup_local.sh --with-surrol --with-i4h
#   bash setup_local.sh --isaac-version 5.0.0        # i4h가 고정한 5.0으로 맞추고 싶을 때
#
# ⚠️ 이 스크립트는 GPU 없는 환경에서 작성되어 "문법 검사(bash -n)"만 통과한 상태입니다.
#    실제 GPU 머신에서의 전 구간 실행 검증은 하지 못했으니, 단계별 출력 메시지를
#    확인하며 진행하세요. 문제가 생기면 docs/04-로컬셋업.md 의 수동 절차를 따르세요.
# =============================================================================
set -euo pipefail

# ---- 설정 (플래그로 덮어쓰기 가능) -----------------------------------------
ENV_NAME="isaacsim"
PY_VERSION="3.11"
ISAAC_VERSION="5.1.0"
WITH_SURROL=0
WITH_I4H=0
AUTO_INSTALL_CONDA=1                            # conda 없으면 Miniconda 자동 설치 (--no-install-conda 로 끄기)
EXTERNAL_DIR="${HOME}/isaac-healthcare-sims"   # SurRoL / i4h 를 clone 할 상위 폴더
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- 로그 헬퍼 --------------------------------------------------------------
c_reset=$'\033[0m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_red=$'\033[31m'; c_cyn=$'\033[36m'
info()  { printf "%s[정보]%s %s\n"  "$c_cyn" "$c_reset" "$*"; }
ok()    { printf "%s[완료]%s %s\n"  "$c_grn" "$c_reset" "$*"; }
warn()  { printf "%s[경고]%s %s\n"  "$c_ylw" "$c_reset" "$*"; }
die()   { printf "%s[실패]%s %s\n"  "$c_red" "$c_reset" "$*" >&2; exit 1; }
step()  { printf "\n%s==== %s ====%s\n" "$c_cyn" "$*" "$c_reset"; }

# conda 를 확실히 쓸 수 있게 만든다. 성공하면 conda.sh 까지 source 된 상태로 반환.
#   1) PATH 에 있으면 그대로 사용
#   2) 흔한 경로에 설치돼 있으나 PATH 에 없으면 활성화
#   3) 없으면 (AUTO_INSTALL_CONDA=1) Miniconda 를 배치 모드로 자동 설치
ensure_conda() {
  if command -v conda >/dev/null 2>&1; then
    ok "conda 발견: $(conda --version)"
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    return
  fi
  local base
  for base in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" "/opt/conda"; do
    if [[ -f "$base/etc/profile.d/conda.sh" ]]; then
      info "conda 가 설치돼 있지만 PATH 에 없습니다($base). 이번 실행에 활성화합니다."
      # shellcheck disable=SC1091
      source "$base/etc/profile.d/conda.sh"
      # 사용자의 다음 터미널에서도 'conda activate' 가 되도록 init (idempotent)
      "$base/bin/conda" init bash >/dev/null 2>&1 || true
      ok "conda 발견: $(conda --version)  (새 터미널부터 conda 자동 활성화)"
      return
    fi
  done

  if [[ "$AUTO_INSTALL_CONDA" -ne 1 ]]; then
    die "conda 가 없습니다. Miniconda 를 먼저 설치하거나 --no-install-conda 를 빼고 다시 실행하세요."
  fi

  warn "conda 가 없습니다. Miniconda 를 자동 설치합니다 → $HOME/miniconda3"
  local url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
  local installer="/tmp/miniconda_$$.sh"
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$installer" "$url" || die "Miniconda 다운로드 실패(네트워크 확인)."
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$installer" || die "Miniconda 다운로드 실패(네트워크 확인)."
  else
    die "wget/curl 이 없어 Miniconda 를 받을 수 없습니다. 'sudo apt install -y wget' 후 재실행하세요."
  fi
  bash "$installer" -b -p "$HOME/miniconda3" || die "Miniconda 설치 실패."
  rm -f "$installer"
  # shellcheck disable=SC1091
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
  "$HOME/miniconda3/bin/conda" init bash >/dev/null 2>&1 || true
  ok "Miniconda 설치 완료(새 터미널부터 conda 자동 활성화). 이번 실행은 계속 진행합니다."
}

usage() {
  # 파일 상단의 연속된 주석 헤더(2행부터 첫 비주석 행 전까지)만 출력
  awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "${BASH_SOURCE[0]}"
  exit 0
}

# ---- 플래그 파싱 ------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-surrol)      WITH_SURROL=1 ;;
    --with-i4h)         WITH_I4H=1 ;;
    --no-install-conda) AUTO_INSTALL_CONDA=0 ;;
    --env-name)       ENV_NAME="${2:?}"; shift ;;
    --isaac-version)  ISAAC_VERSION="${2:?}"; shift ;;
    --external-dir)   EXTERNAL_DIR="${2:?}"; shift ;;
    -h|--help)        usage ;;
    *) die "알 수 없는 옵션: $1  (도움말: bash setup_local.sh --help)" ;;
  esac
  shift
done

# ---- 1) 사전 점검 -----------------------------------------------------------
step "1/4  사전 점검"

[[ "$(uname -s)" == "Linux" ]] || warn "이 스크립트는 Ubuntu 22.04/24.04 x86_64 기준입니다. 현재: $(uname -s)"

if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_line="$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -1)"
  ok "GPU 감지: ${gpu_line:-불명}"
else
  warn "nvidia-smi 가 없습니다. NVIDIA GPU/드라이버가 없으면 Isaac Sim은 설치돼도 '실행'이 안 됩니다."
  warn "이 머신이 여러분의 RTX GPU PC가 맞는지 확인하세요. (계속하려면 5초 후 진행)"
  sleep 5
fi

# conda 확보(없으면 자동 설치) + conda.sh source 까지 한 번에 처리
ensure_conda

# ---- 2) isaacsim 환경 생성 --------------------------------------------------
step "2/4  conda 환경 '${ENV_NAME}' (Python ${PY_VERSION})"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  info "환경 '${ENV_NAME}' 이 이미 있습니다. 재사용합니다."
else
  # conda-forge 만 사용(--override-channels)해서 Anaconda 기본 채널의 ToS 게이트를 피한다.
  # (최신 conda는 repo.anaconda.com 기본 채널에 Terms of Service 동의를 요구함)
  conda create -n "$ENV_NAME" "python=${PY_VERSION}" -y -c conda-forge --override-channels
  ok "환경 '${ENV_NAME}' 생성 완료"
fi
conda activate "$ENV_NAME"
ok "활성 환경: $(python -c 'import sys; print(sys.prefix)')"

# ---- 3) Isaac Sim + 의존성 설치 --------------------------------------------
step "3/4  Isaac Sim ${ISAAC_VERSION} + 과제집 의존성 설치"

python -m pip install --upgrade pip
info "Isaac Sim 다운로드는 수 GB이고 수십 분 걸릴 수 있습니다..."
python -m pip install "isaacsim[all,extscache]==${ISAAC_VERSION}" --extra-index-url https://pypi.nvidia.com \
  || die "Isaac Sim 설치 실패. 십중팔구 Python 버전 불일치입니다(5.x는 3.11 필요).
          'pip index versions isaacsim --extra-index-url https://pypi.nvidia.com' 로 받을 수 있는 버전을 확인하세요."

if [[ -f "${REPO_DIR}/requirements.txt" ]]; then
  python -m pip install -r "${REPO_DIR}/requirements.txt"
  ok "과제집 추가 의존성(h5py 등) 설치 완료"
fi

# ---- 4) 환경 검증 -----------------------------------------------------------
step "4/4  환경 검증 (tools/check_env.py)"
python "${REPO_DIR}/tools/check_env.py" || warn "check_env.py 가 경고를 냈습니다. 위 항목을 확인하세요."

cat <<EOF

${c_grn}=== Isaac Sim + 과제집 기본 셋업 완료 ===${c_reset}
다음처럼 첫 과제 해답을 짧게 실행해 API 호환성을 확인하세요:

    conda activate ${ENV_NAME}
    python "${REPO_DIR}/exercises/ex01_hello_phantom/solution.py" --test

전체 목차는 ${REPO_DIR}/INDEX.md 를 보세요.
EOF

# ---- (선택) SurRoL ----------------------------------------------------------
if [[ "$WITH_SURROL" -eq 1 ]]; then
  step "선택  SurRoL 설치 (별도 환경 'surrol', Python 3.10)"
  warn "SurRoL은 Isaac Sim과 파이썬/의존성이 완전히 다릅니다. 반드시 별도 환경에 설치합니다."
  mkdir -p "$EXTERNAL_DIR"
  surrol_ok=1
  if conda env list | awk '{print $1}' | grep -qx "surrol"; then
    info "환경 'surrol' 이 이미 있습니다. 재사용합니다."
  elif ! conda create -n surrol python=3.10 -y -c conda-forge --override-channels; then
    warn "surrol 환경(python 3.10) 생성 실패 — SurRoL 설치를 건너뜁니다. (핵심 Isaac Sim 셋업은 정상)"
    surrol_ok=0
  fi
  if [[ "$surrol_ok" -eq 1 ]]; then
    conda activate surrol
    # ★ main 브랜치는 연구용 모노레포(루트에 setup.py 없음 + 태스크가 MPM/taichi 요구)라
    #   간단히 쓰기 어렵습니다. 깔끔한 SurRoL-v2 브랜치를 씁니다.
    if [[ -d "${EXTERNAL_DIR}/SurRoL/.git" ]]; then
      # 예전에 main 브랜치로 받아둔 클론이 남아있으면 clone 이 거부되고, main 에는
      # 루트 setup.py 가 없어 pip install 도 실패한다. 그래서 브랜치를 강제로 맞춘다.
      info "SurRoL 저장소가 이미 있습니다 → SurRoL-v2 브랜치로 전환합니다."
      ( cd "${EXTERNAL_DIR}/SurRoL" \
          && git fetch origin SurRoL-v2 \
          && git checkout -B SurRoL-v2 origin/SurRoL-v2 ) \
        || warn "SurRoL-v2 로 전환하지 못했습니다.
                 흔한 원인: 이전 'pip install -e .' 가 만든 surrol.egg-info 등 빌드 부산물이
                 로컬 변경으로 잡혀 체크아웃을 막습니다. 둘 중 하나로 푸세요.
                 (A) 지우고 다시 받기 — 가장 확실하고 v2 는 훨씬 작습니다:
                     rm -rf ${EXTERNAL_DIR}/SurRoL && bash setup_local.sh --with-surrol
                 (B) 로컬 변경을 버리고 전환 — 그 폴더에 직접 수정한 게 없을 때만:
                     cd ${EXTERNAL_DIR}/SurRoL && git reset --hard && git clean -fd \\
                       && git checkout -B SurRoL-v2 origin/SurRoL-v2"
    else
      git clone -b SurRoL-v2 https://github.com/med-air/SurRoL.git "${EXTERNAL_DIR}/SurRoL" \
        || warn "SurRoL clone 실패(네트워크 확인)."
    fi
    if [[ -f "${EXTERNAL_DIR}/SurRoL/setup.py" ]]; then
      ( cd "${EXTERNAL_DIR}/SurRoL" \
          && python -m pip install --upgrade pip \
          && python -m pip install -e . \
          && python -m pip install "gym==0.25.2" ) \
        || warn "SurRoL 설치가 끝까지 가지 못했습니다. 알려진 마찰 요인:
                 · panda3d==1.10.11 은 Python 3.11+ 휠이 없음(그래서 이 환경은 3.10)
                 · gym 은 반드시 <0.26 (0.26+ 는 step API가 5-tuple로 바뀌어 깨짐)
                 자세한 내용은 docs/04-로컬셋업.md 의 B절을 보세요."
      ok "SurRoL 설치 시도 완료. 예제: python examples/surrol_needle_reach.py"
    else
      warn "SurRoL 루트에 setup.py 가 없습니다(${EXTERNAL_DIR}/SurRoL).
            업스트림 구조가 또 바뀌었을 수 있습니다. docs/04-로컬셋업.md 의 B절을 참고하세요."
    fi
    conda activate "$ENV_NAME"
  fi
fi

# ---- (선택) i4h -------------------------------------------------------------
if [[ "$WITH_I4H" -eq 1 ]]; then
  step "선택  Isaac for Healthcare 워크플로우 clone"
  mkdir -p "$EXTERNAL_DIR"
  if [[ -d "${EXTERNAL_DIR}/i4h-workflows/.git" ]]; then
    info "i4h-workflows 가 이미 있습니다: ${EXTERNAL_DIR}/i4h-workflows"
  else
    git clone https://github.com/isaac-for-healthcare/i4h-workflows.git "${EXTERNAL_DIR}/i4h-workflows"
  fi
  ok "i4h clone 완료. 실행은 Docker 기반입니다 — docs/03-i4h-연결.md 를 따라
      'cd ${EXTERNAL_DIR}/i4h-workflows && ./i4h run robotic_ultrasound full_pipeline --as-root' 등을 실행하세요."
fi

step "모든 요청 단계 완료"
ok "요약: Isaac Sim='${ENV_NAME}' 환경 / SurRoL=$([[ $WITH_SURROL -eq 1 ]] && echo '설치됨(surrol 환경)' || echo '건너뜀') / i4h=$([[ $WITH_I4H -eq 1 ]] && echo 'clone됨' || echo '건너뜀')"
