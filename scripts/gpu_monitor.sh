#!/usr/bin/env bash
# gpu_monitor.sh — 학습 중 GPU 상태 모니터링
#
# 별도 터미널에서 띄워두고 VRAM / 온도 / 전력을 관찰하세요.
# RTX 3090 은 TDP 350W 라 장시간 학습 시 발열이 큽니다.
#
# 사용법:
#   ./scripts/gpu_monitor.sh              # 2초 간격
#   ./scripts/gpu_monitor.sh 5            # 5초 간격
#   ./scripts/gpu_monitor.sh 2 gpu.csv    # CSV 로 기록도 남김

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_cmd nvidia-smi
INTERVAL="${1:-2}"
CSV="${2:-}"

TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1 | xargs)
NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | xargs)

hdr "GPU 모니터"
info "$NAME  /  VRAM ${TOTAL}MB  /  ${INTERVAL}초 간격"
[[ -n "$CSV" ]] && { echo "timestamp,vram_mb,vram_pct,temp_c,power_w,util_pct" > "$CSV"; info "CSV 기록: $CSV"; }
info "Ctrl+C 로 종료"
echo
printf '%-10s %10s %7s %7s %9s %7s  %s\n' "TIME" "VRAM" "VRAM%" "TEMP" "POWER" "UTIL" "STATUS"
printf '%s\n' "------------------------------------------------------------------------"

PEAK=0
MAXTEMP=0

while true; do
  read -r used temp power util < <(
    nvidia-smi --query-gpu=memory.used,temperature.gpu,power.draw,utilization.gpu \
      --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d ' ' | tr ',' ' '
  )
  [[ -z "${used:-}" ]] && { warn "nvidia-smi 조회 실패"; sleep "$INTERVAL"; continue; }

  pct=$(( used * 100 / TOTAL ))
  (( used > PEAK )) && PEAK=$used
  temp_i=${temp%.*}
  (( temp_i > MAXTEMP )) && MAXTEMP=$temp_i

  # 상태 판정
  status=""
  color="$C_GRN"
  if (( pct >= 95 )); then
    status="VRAM 위험"; color="$C_RED"
  elif (( pct >= 85 )); then
    status="VRAM 높음"; color="$C_YEL"
  fi
  if (( temp_i >= 83 )); then
    status="${status:+$status / }스로틀 위험"; color="$C_RED"
  elif (( temp_i >= 78 )); then
    status="${status:+$status / }온도 높음"
    [[ "$color" == "$C_GRN" ]] && color="$C_YEL"
  fi

  printf '%s%-10s %8sMB %6s%% %6s°C %8sW %6s%%  %s%s\n' \
    "$color" "$(date +%H:%M:%S)" "$used" "$pct" "$temp" "$power" "$util" "$status" "$C_OFF"

  [[ -n "$CSV" ]] && echo "$(date -Iseconds),$used,$pct,$temp,$power,$util" >> "$CSV"

  sleep "$INTERVAL"
done
