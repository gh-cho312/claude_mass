#!/usr/bin/env bash
# =============================================================================
# Isaac Sim이 "멈춘 것"인지 "열심히 일하는 중"인지 판별하는 진단 스크립트.
#
# 첫 실행 때 확장 다운로드 + 셰이더 컴파일로 창이 응답하지 않아 우분투가
# "중단하기 / 기다리기" 대화상자를 띄웁니다. 대부분 정상이며, 이 스크립트로
# 실제 진행 여부를 확인할 수 있습니다.
#
# 사용법 (Isaac Sim이 뜨는 중인 상태에서, 새 터미널을 열어):
#     bash tools/check_isaac_progress.sh
#     bash tools/check_isaac_progress.sh 60     # 60초 간격으로 변화량까지 비교
# =============================================================================
set -uo pipefail
WATCH_SEC="${1:-0}"

hr() { printf '─%.0s' {1..70}; echo; }
cache_size() { du -sb "$@" 2>/dev/null | awk '{s+=$1} END {print s+0}'; }
human() { numfmt --to=iec --suffix=B "${1:-0}" 2>/dev/null || echo "${1:-0}B"; }

CACHES=("$HOME/.cache/ov" "$HOME/.nvidia-omniverse" "$HOME/.local/share/ov")

hr; echo "① Isaac Sim / Kit 프로세스"; hr
if pgrep -af 'isaac|kit' >/dev/null 2>&1; then
  ps -eo pid,etime,time,pcpu,pmem,comm --sort=-pcpu | head -1
  # etime=실행된 시간, time=실제 CPU 사용 시간 (time이 늘면 '일하는 중')
  pgrep -af 'isaac|kit' | awk '{print $1}' | while read -r pid; do
    ps -p "$pid" -o pid,etime,time,pcpu,pmem,comm --no-headers 2>/dev/null
  done
else
  echo "  실행 중인 isaac/kit 프로세스가 없습니다 (아직 시작 전이거나 이미 종료됨)."
fi

hr; echo "② GPU 상태"; hr
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader
  echo "  -- GPU를 쓰는 프로세스 --"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null \
    | grep -Ei 'isaac|kit|python' || echo "  (Isaac 관련 GPU 프로세스 없음)"
else
  echo "  nvidia-smi 없음"
fi

hr; echo "③ 캐시 크기 (커지고 있으면 = 다운로드/컴파일 진행 중)"; hr
for c in "${CACHES[@]}"; do
  [[ -d "$c" ]] && printf "  %-40s %s\n" "$c" "$(human "$(cache_size "$c")")"
done

hr; echo "④ 최신 Kit 로그 (마지막 15줄)"; hr
LOG="$(ls -t "$HOME"/.nvidia-omniverse/logs/Kit/*/*/kit_*.log 2>/dev/null | head -1)"
if [[ -n "${LOG:-}" ]]; then
  echo "  파일: $LOG"
  echo "  수정: $(date -r "$LOG" '+%Y-%m-%d %H:%M:%S')  (지금과 가까우면 살아있는 것)"
  echo "  ----"
  tail -15 "$LOG" | sed 's/^/  /'
else
  echo "  Kit 로그를 찾지 못했습니다 (아직 로그 생성 전일 수 있음)."
fi

if [[ "$WATCH_SEC" -gt 0 ]]; then
  hr; echo "⑤ ${WATCH_SEC}초 동안 변화 관찰"; hr
  before="$(cache_size "${CACHES[@]}")"
  echo "  전: $(human "$before")  — ${WATCH_SEC}초 대기..."
  sleep "$WATCH_SEC"
  after="$(cache_size "${CACHES[@]}")"
  delta=$(( after - before ))
  echo "  후: $(human "$after")   (증가분: $(human "$delta"))"
  if [[ "$delta" -gt 0 ]]; then
    echo "  ✅ 캐시가 커지는 중 → 정상 진행입니다. '기다리기'를 누르고 기다리세요."
  else
    echo "  ⚠️  변화 없음. 로그(④)의 시각도 멈춰 있다면 정말 멈춘 것일 수 있습니다."
    echo "     그 경우 이 출력 전체를 복사해서 문의하세요."
  fi
fi
hr
