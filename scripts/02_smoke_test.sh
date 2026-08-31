#!/usr/bin/env bash
# 02_smoke_test.sh — robotic_surgery 데모 태스크 실행
#
# 설치가 제대로 됐는지 확인합니다. GUI 창이 뜨고 로봇이 움직이면 성공입니다.
#
# 사용법:
#   ./scripts/02_smoke_test.sh                 # 목록 출력
#   ./scripts/02_smoke_test.sh reach_psm       # 특정 태스크 실행
#   ./scripts/02_smoke_test.sh --all           # 가벼운 데모 순차 실행

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_env

I4H_ROOT="${I4H_ROOT:-$HOME/i4h-workflows}"

# 태스크 이름 → 설명 (실행 시간은 README 기준 2~7분)
declare -A TASKS=(
  [reach_psm]="단일 PSM 리칭 — 가장 가벼움. 여기부터 시작하세요."
  [reach_dual_psm]="양팔 PSM 협응 리칭"
  [reach_star]="STAR 로봇 리칭"
  [lift_needle]="봉합침 들어올리기"
  [lift_needle_organs]="장기가 포함된 수술실 씬에서 봉합침 들어올리기 (가장 무거움)"
  [lift_block]="블록/페그 트랜스퍼"
)

# 가벼운 것부터 무거운 것 순
ORDER=(reach_psm reach_dual_psm reach_star lift_block lift_needle lift_needle_organs)

usage() {
  hdr "사용 가능한 데모 태스크"
  for t in "${ORDER[@]}"; do
    printf '  %s%-20s%s %s\n' "$C_BLD" "$t" "$C_OFF" "${TASKS[$t]}"
  done
  echo
  info "실행:      ./scripts/02_smoke_test.sh <태스크명>"
  info "전체 실행: ./scripts/02_smoke_test.sh --all"
  echo
  warn "GUI 데모는 창이 뜹니다. SSH 로 접속 중이라면 X11 포워딩이 필요합니다."
}

run_task() {
  local task="$1"
  hdr "실행: $task"
  info "${TASKS[$task]}"
  info "예상 소요: 2~7분. 창을 닫거나 Ctrl+C 로 종료합니다."
  echo

  pushd "$I4H_ROOT" >/dev/null
  # i4h CLI 래퍼 사용 (Docker 기본). Conda 설치라면 --no-docker-build 로 재사용.
  if ./i4h run robotic_surgery "$task" --as-root; then
    ok "$task 완료"
    popd >/dev/null
    return 0
  else
    local rc=$?
    err "$task 실패 (exit $rc)"
    popd >/dev/null
    return $rc
  fi
}

# ── 사전 확인 ─────────────────────────────────────────────────
[[ -d "$I4H_ROOT" ]] || die "i4h 저장소가 없습니다: $I4H_ROOT — 먼저 01_install_robotic_surgery.sh 를 실행하세요."
[[ -x "$I4H_ROOT/i4h" ]] || die "$I4H_ROOT/i4h 실행 파일이 없습니다. 설치가 끝났는지 확인하세요."

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

if [[ "$1" == "--all" ]]; then
  info "가벼운 데모부터 순차 실행합니다. 각 태스크 사이에 확인을 받습니다."
  FAILED=()
  for t in "${ORDER[@]}"; do
    confirm "다음 태스크를 실행할까요: $t ?" || { info "건너뜀: $t"; continue; }
    run_task "$t" || FAILED+=("$t")
  done
  hdr "결과"
  if (( ${#FAILED[@]} == 0 )); then
    ok "실행한 태스크가 모두 정상 종료했습니다."
  else
    err "실패: ${FAILED[*]}"
    warn "docs/05-문제해결-RTX3090.md 를 확인하세요."
    exit 1
  fi
  exit 0
fi

TASK="$1"
if [[ -z "${TASKS[$TASK]:-}" ]]; then
  err "알 수 없는 태스크: $TASK"
  usage
  exit 1
fi

run_task "$TASK"
echo
ok "다음 단계: ./scripts/03_find_max_envs.sh"
