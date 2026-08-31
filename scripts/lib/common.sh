#!/usr/bin/env bash
# 공통 유틸리티 — 다른 스크립트에서 source 해서 사용합니다.
# 사용법: source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# 색상 (터미널이 아니면 비활성화)
if [[ -t 1 ]]; then
  C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YEL=$'\033[0;33m'
  C_BLU=$'\033[0;34m'; C_BLD=$'\033[1m';    C_OFF=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_BLD=""; C_OFF=""
fi

info()  { printf '%s[INFO]%s %s\n'  "$C_BLU" "$C_OFF" "$*"; }
ok()    { printf '%s[ OK ]%s %s\n'  "$C_GRN" "$C_OFF" "$*"; }
warn()  { printf '%s[WARN]%s %s\n'  "$C_YEL" "$C_OFF" "$*" >&2; }
err()   { printf '%s[FAIL]%s %s\n'  "$C_RED" "$C_OFF" "$*" >&2; }
hdr()   { printf '\n%s=== %s ===%s\n' "$C_BLD" "$*" "$C_OFF"; }

die() { err "$*"; exit 1; }

# 명령 존재 확인
have() { command -v "$1" >/dev/null 2>&1; }

require_cmd() {
  have "$1" || die "'$1' 명령을 찾을 수 없습니다. ${2:-먼저 설치해 주세요.}"
}

# 사용자 확인 (기본 No). CONFIRM_YES=1 이면 자동 승인.
confirm() {
  local prompt="${1:-계속할까요?}"
  if [[ "${CONFIRM_YES:-0}" == "1" ]]; then
    info "$prompt -> CONFIRM_YES=1 이므로 자동 진행"
    return 0
  fi
  local reply
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# 숫자 비교 (소수점 포함 버전 문자열용)
# ver_ge "535.230.02" "535.129.03"  -> 0(참) / 1(거짓)
ver_ge() {
  [[ "$1" == "$2" ]] && return 0
  local lower
  lower=$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)
  [[ "$lower" == "$2" ]]
}

# 프로젝트 루트 (이 파일 기준 두 단계 위)
repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

# config/env.sh 가 있으면 읽어들임
load_env() {
  local root cfg
  root="$(repo_root)"
  cfg="$root/config/env.sh"
  if [[ -f "$cfg" ]]; then
    # shellcheck disable=SC1090
    source "$cfg"
    info "설정 로드: $cfg"
  else
    warn "config/env.sh 가 없습니다. config/env.example.sh 를 복사해 만드세요."
    warn "  cp config/env.example.sh config/env.sh"
  fi
}

# conda 초기화 (비대화식 셸에서 conda activate 를 쓰기 위함)
init_conda() {
  if have conda; then
    local base
    base="$(conda info --base 2>/dev/null)" || return 1
    # shellcheck disable=SC1091
    source "$base/etc/profile.d/conda.sh"
    return 0
  fi
  return 1
}
