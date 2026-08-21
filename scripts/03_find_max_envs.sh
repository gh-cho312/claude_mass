#!/usr/bin/env bash
# 03_find_max_envs.sh — RTX 3090 에서 안전한 num_envs 상한 탐색
#
# num_envs 를 단계적으로 올려가며 짧은 학습을 돌리고, VRAM 최대 사용량을
# 관측합니다. OOM 이 나거나 VRAM 사용률이 상한을 넘으면 멈춥니다.
#
# README 예시값(4096)은 여유 있는 GPU 기준이라 24GB 카드에서는 그대로
# 쓰면 학습 중반에 터질 수 있습니다. 이 스크립트로 실측하세요.
#
# 사용법:
#   ./scripts/03_find_max_envs.sh
#   ./scripts/03_find_max_envs.sh --task Isaac-Lift-Needle-PSM-IK-Rel-v0
#   ENV_LADDER="128 256 512" ./scripts/03_find_max_envs.sh

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_env

TASK="${DEFAULT_RL_TASK:-Isaac-Reach-PSM-v0}"
LADDER="${ENV_LADDER:-256 512 1024 2048 4096}"
LIMIT_PCT="${VRAM_LIMIT_PCT:-85}"
I4H_ROOT="${I4H_ROOT:-$HOME/i4h-workflows}"
PROBE_ITERS="${PROBE_ITERS:-10}"      # 각 단계에서 돌릴 iteration 수
PROBE_TIMEOUT="${PROBE_TIMEOUT:-900}" # 단계별 최대 대기(초)
LOG_DIR="${LOG_DIR:-$(repo_root)/logs}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)    TASK="$2"; shift 2 ;;
    --ladder)  LADDER="$2"; shift 2 ;;
    --limit)   LIMIT_PCT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) die "알 수 없는 옵션: $1" ;;
  esac
done

require_cmd nvidia-smi
[[ -x "$I4H_ROOT/i4h" ]] || die "i4h 를 찾을 수 없습니다: $I4H_ROOT — 먼저 01_install_robotic_surgery.sh 실행"
mkdir -p "$LOG_DIR"

VRAM_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1 | xargs)
VRAM_BASE=$(nvidia-smi --query-gpu=memory.used  --format=csv,noheader,nounits | head -n1 | xargs)

hdr "num_envs 상한 탐색"
info "태스크        : $TASK"
info "사다리        : $LADDER"
info "VRAM 총량     : ${VRAM_TOTAL}MB"
info "현재 점유     : ${VRAM_BASE}MB (데스크탑/브라우저)"
info "허용 상한     : ${LIMIT_PCT}%  (= $(( VRAM_TOTAL * LIMIT_PCT / 100 ))MB)"
info "단계별 반복   : ${PROBE_ITERS} iterations"
echo

if (( VRAM_BASE > 2000 )); then
  warn "이미 ${VRAM_BASE}MB 를 쓰고 있습니다. 브라우저/IDE 를 닫으면 상한이 올라갑니다."
  echo
fi

confirm "탐색을 시작할까요? (단계당 수 분 소요)" || { info "취소했습니다."; exit 0; }

VRAM_CAP=$(( VRAM_TOTAL * LIMIT_PCT / 100 ))
BEST=""
declare -A RESULTS

# GPU 가 유휴 상태로 돌아올 때까지 대기
wait_gpu_idle() {
  local tries=0
  while (( tries < 30 )); do
    local used
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1 | xargs)
    (( used <= VRAM_BASE + 500 )) && return 0
    sleep 2
    tries=$((tries+1))
  done
  warn "GPU 메모리가 완전히 회수되지 않았습니다. 다음 측정이 부정확할 수 있습니다."
  return 0
}

probe() {
  local n="$1"
  local log="$LOG_DIR/probe_${TASK//\//_}_n${n}.log"
  local peak=0 rc=0

  info "── num_envs=$n 측정 중 (로그: $log)"

  pushd "$I4H_ROOT" >/dev/null
  ./i4h run robotic_surgery train_rl --as-root --run-args="\
    --task $TASK \
    --num_envs $n \
    --max_iterations $PROBE_ITERS \
    --headless" > "$log" 2>&1 &
  local pid=$!
  popd >/dev/null

  local elapsed=0
  while kill -0 "$pid" 2>/dev/null; do
    local used
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -n1 | xargs)
    [[ -n "$used" ]] && (( used > peak )) && peak=$used

    if (( elapsed >= PROBE_TIMEOUT )); then
      warn "타임아웃(${PROBE_TIMEOUT}s) — 프로세스를 종료합니다."
      kill -TERM "$pid" 2>/dev/null
      sleep 5
      kill -KILL "$pid" 2>/dev/null
      rc=124
      break
    fi
    sleep 2
    elapsed=$((elapsed+2))
  done

  if (( rc == 0 )); then
    wait "$pid"; rc=$?
  fi

  local pct=0
  (( VRAM_TOTAL > 0 )) && pct=$(( peak * 100 / VRAM_TOTAL ))

  # OOM 흔적 확인
  local oom=0
  if grep -qiE 'out of memory|CUDA error: out of memory|cudaErrorMemoryAllocation' "$log" 2>/dev/null; then
    oom=1
  fi

  RESULTS[$n]="peak=${peak}MB pct=${pct}% rc=${rc} oom=${oom}"

  if (( oom == 1 )); then
    err "num_envs=$n : OOM 발생 (peak ${peak}MB / ${pct}%)"
    return 1
  elif (( rc != 0 )); then
    err "num_envs=$n : 실패 (exit $rc, peak ${peak}MB / ${pct}%) — 로그: $log"
    return 1
  elif (( pct > LIMIT_PCT )); then
    warn "num_envs=$n : 성공했지만 VRAM ${pct}% 로 상한(${LIMIT_PCT}%) 초과 — 여기서 멈춥니다."
    return 1
  else
    ok "num_envs=$n : 성공 (peak ${peak}MB / ${pct}%)"
    BEST="$n"
    return 0
  fi
}

for n in $LADDER; do
  wait_gpu_idle
  if ! probe "$n"; then
    break
  fi
done

# ── 결과 ──────────────────────────────────────────────────────
hdr "측정 결과"
for n in $LADDER; do
  if [[ -n "${RESULTS[$n]:-}" ]]; then
    printf '  %-8s %s\n' "$n" "${RESULTS[$n]}"
  else
    printf '  %-8s (미측정)\n' "$n"
  fi
done
echo

if [[ -z "$BEST" ]]; then
  err "가장 낮은 단계조차 통과하지 못했습니다."
  warn "더 작은 값으로 다시 시도해 보세요:"
  warn "  ENV_LADDER=\"32 64 128\" ./scripts/03_find_max_envs.sh"
  warn "그래도 실패하면 docs/05-문제해결-RTX3090.md 를 확인하세요."
  exit 1
fi

# 안전 마진을 둔 권장값 (측정 성공한 최대값을 그대로 쓰되, 상한 근접이면 한 단계 아래)
RECOMMEND="$BEST"
hdr "권장 설정"
ok "이 태스크($TASK)에서 안전한 num_envs = ${C_BLD}${RECOMMEND}${C_OFF}"
echo
info "config/env.sh 에 반영하세요:"
echo "    export TRAIN_NUM_ENVS=$RECOMMEND"
echo
warn "주의: 태스크마다 상한이 다릅니다."
warn "  변형체가 포함된 lift_needle_organs 는 훨씬 낮게 잡아야 합니다."
warn "  태스크를 바꾸면 --task 옵션으로 다시 측정하세요."
echo
ok "다음 단계: ./scripts/04_train_rl.sh"
