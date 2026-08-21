#!/usr/bin/env bash
# 04_train_rl.sh — RL(PPO) 본 학습 래퍼
#
# 03_find_max_envs.sh 로 찾은 num_envs 를 사용해 학습을 돌립니다.
# 항상 --headless 로 실행합니다 (RTX 3090 에서 VRAM 을 아끼기 위해).
#
# 사용법:
#   ./scripts/04_train_rl.sh
#   ./scripts/04_train_rl.sh --task Isaac-Lift-Needle-PSM-IK-Rel-v0 --envs 512
#   ./scripts/04_train_rl.sh --iters 3000
#   ./scripts/04_train_rl.sh --play          # 학습된 정책 재생 (GUI)

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_env

I4H_ROOT="${I4H_ROOT:-$HOME/i4h-workflows}"
TASK="${DEFAULT_RL_TASK:-Isaac-Reach-PSM-v0}"
NUM_ENVS="${TRAIN_NUM_ENVS:-1024}"
ITERS="${TRAIN_ITERS:-1500}"
LOG_DIR="${LOG_DIR:-$(repo_root)/logs}"
MODE="train"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)  TASK="$2"; shift 2 ;;
    --envs)  NUM_ENVS="$2"; shift 2 ;;
    --iters) ITERS="$2"; shift 2 ;;
    --play)  MODE="play"; shift ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) die "알 수 없는 옵션: $1" ;;
  esac
done

[[ -x "$I4H_ROOT/i4h" ]] || die "i4h 를 찾을 수 없습니다: $I4H_ROOT"
mkdir -p "$LOG_DIR"

# ── 재생 모드 ─────────────────────────────────────────────────
if [[ "$MODE" == "play" ]]; then
  hdr "학습된 정책 재생"
  info "태스크: $TASK"
  warn "재생은 GUI 로 렌더링합니다. num_envs 를 낮게 잡습니다."
  pushd "$I4H_ROOT" >/dev/null
  ./i4h run robotic_surgery play_rl --as-root --run-args="--task $TASK --num_envs 32"
  popd >/dev/null
  exit $?
fi

# ── 학습 모드 ─────────────────────────────────────────────────
hdr "RL 학습 (PPO)"
info "태스크    : $TASK"
info "num_envs  : $NUM_ENVS"
info "iterations: $ITERS"
info "모드      : headless (VRAM 절약)"
echo

# VRAM 사전 확인
if have nvidia-smi; then
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1 | xargs)
  TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1 | xargs)
  info "현재 VRAM : ${USED}MB / ${TOTAL}MB"
  if (( USED > 2000 )); then
    warn "VRAM 을 ${USED}MB 점유 중입니다. 브라우저/IDE 를 닫으면 안정성이 올라갑니다."
    confirm "그대로 진행할까요?" || { info "취소했습니다."; exit 0; }
  fi
fi

if [[ "$NUM_ENVS" == "4096" && -z "${TRAIN_NUM_ENVS:-}" ]]; then
  warn "num_envs=4096 은 문서 예시값입니다. 24GB 카드에서는 OOM 위험이 있습니다."
  warn "먼저 ./scripts/03_find_max_envs.sh 로 실측하길 권합니다."
fi

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOG_DIR/train_${TASK//\//_}_n${NUM_ENVS}_${TS}.log"

info "로그: $LOG"
info "다른 터미널에서 GPU 를 모니터링하세요:  ./scripts/gpu_monitor.sh"
echo
confirm "학습을 시작할까요? (45분 이상 소요)" || { info "취소했습니다."; exit 0; }

hdr "학습 시작"
pushd "$I4H_ROOT" >/dev/null
./i4h run robotic_surgery train_rl --as-root --run-args="\
  --task $TASK \
  --num_envs $NUM_ENVS \
  --max_iterations $ITERS \
  --headless" 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
popd >/dev/null

echo
if (( RC == 0 )); then
  ok "학습 완료. 로그: $LOG"
  info "학습된 정책을 보려면:  ./scripts/04_train_rl.sh --play --task $TASK"
else
  err "학습 실패 (exit $RC). 로그: $LOG"
  if grep -qiE 'out of memory' "$LOG" 2>/dev/null; then
    err "OOM 이 감지되었습니다. num_envs 를 낮추세요:"
    err "  ./scripts/04_train_rl.sh --envs $(( NUM_ENVS / 2 ))"
  fi
  warn "docs/05-문제해결-RTX3090.md 참고"
  exit $RC
fi
