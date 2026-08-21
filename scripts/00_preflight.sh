#!/usr/bin/env bash
# 00_preflight.sh — 설치 전 하드웨어/OS 사전 점검
#
# i4h robotic_surgery 워크플로 요구사항 대비 현재 시스템을 검사합니다.
# 아무것도 변경하지 않는 읽기 전용 스크립트입니다.
#
# 사용법: ./scripts/00_preflight.sh

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# ── 요구사항 (i4h robotic_surgery README 기준) ────────────────
REQ_VRAM_MB=24000          # ≥24GB VRAM
REQ_COMPUTE_CAP="8.6"      # ≥8.6 (Ampere 이상)
REQ_DRIVER="535.129.03"
REQ_DISK_GB=100            # ≥100GB
REQ_RAM_GB=32              # ≥32GB

PASS=0; WARNS=0; FAILS=0
pass() { ok "$*"; PASS=$((PASS+1)); }
soft() { warn "$*"; WARNS=$((WARNS+1)); }
hard() { err "$*"; FAILS=$((FAILS+1)); }

hdr "1. GPU"
if ! have nvidia-smi; then
  hard "nvidia-smi 를 찾을 수 없습니다. NVIDIA 드라이버가 설치되어 있나요?"
else
  nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version,compute_cap \
    --format=csv 2>/dev/null | sed 's/^/       /'
  echo

  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | xargs)
  VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1 | xargs)
  VRAM_USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1 | xargs)
  DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | xargs)
  CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n1 | xargs)

  info "GPU: $GPU_NAME"

  # VRAM
  if [[ -n "$VRAM_MB" ]] && (( VRAM_MB >= REQ_VRAM_MB )); then
    pass "VRAM ${VRAM_MB}MB (요구 ${REQ_VRAM_MB}MB 이상)"
  else
    hard "VRAM ${VRAM_MB}MB — 요구치 ${REQ_VRAM_MB}MB 미달. num_envs 를 크게 낮춰야 합니다."
  fi

  # 현재 사용 중인 VRAM (디스플레이 점유량 파악)
  if [[ -n "$VRAM_USED" ]]; then
    if (( VRAM_USED > 2000 )); then
      soft "현재 VRAM ${VRAM_USED}MB 사용 중 — 데스크탑/브라우저가 점유 중일 수 있습니다."
      warn "     학습 전에 브라우저를 닫거나, 모니터를 내장 그래픽(iGPU)으로 옮기세요."
    else
      pass "현재 VRAM 사용량 ${VRAM_USED}MB (여유 충분)"
    fi
  fi

  # Compute capability
  if [[ -n "$CC" ]]; then
    if ver_ge "$CC" "$REQ_COMPUTE_CAP"; then
      pass "Compute Capability $CC (요구 $REQ_COMPUTE_CAP 이상)"
    else
      hard "Compute Capability $CC — 요구치 $REQ_COMPUTE_CAP 미달 (Ampere 이상 필요)"
    fi
  else
    soft "Compute Capability 를 조회하지 못했습니다 (드라이버가 오래됐을 수 있음)"
  fi

  # 드라이버
  if [[ -n "$DRIVER" ]]; then
    if ver_ge "$DRIVER" "$REQ_DRIVER"; then
      pass "드라이버 $DRIVER (요구 $REQ_DRIVER 이상)"
    else
      hard "드라이버 $DRIVER — 요구치 $REQ_DRIVER 미달. 업그레이드가 필요합니다."
    fi
  fi

  # GPU 개수
  NGPU=$(nvidia-smi --list-gpus 2>/dev/null | wc -l)
  info "GPU 개수: $NGPU  (여러 개면 CUDA_VISIBLE_DEVICES 로 선택 가능)"
fi

hdr "2. 디스크"
# i4h 저장소가 놓일 위치 기준으로 검사
TARGET_DIR="${I4H_ROOT:-$HOME}"
CHECK_DIR="$TARGET_DIR"
while [[ ! -d "$CHECK_DIR" && "$CHECK_DIR" != "/" ]]; do
  CHECK_DIR=$(dirname "$CHECK_DIR")
done

df -h "$CHECK_DIR" | sed 's/^/       /'
echo
AVAIL_GB=$(df -BG --output=avail "$CHECK_DIR" 2>/dev/null | tail -n1 | tr -dc '0-9')
if [[ -n "$AVAIL_GB" ]]; then
  if (( AVAIL_GB >= REQ_DISK_GB )); then
    pass "여유 공간 ${AVAIL_GB}GB (요구 ${REQ_DISK_GB}GB 이상) @ $CHECK_DIR"
  else
    hard "여유 공간 ${AVAIL_GB}GB — 요구치 ${REQ_DISK_GB}GB 미달 @ $CHECK_DIR"
    warn "     Docker 대신 Conda 설치를 쓰면 컨테이너 이미지 용량을 아낄 수 있습니다."
    warn "     또는 config/env.sh 에서 I4H_ROOT 를 여유 있는 파티션으로 지정하세요."
  fi
fi

# NVMe 여부 (권장사항)
ROOT_SRC=$(df --output=source "$CHECK_DIR" 2>/dev/null | tail -n1)
if [[ "$ROOT_SRC" == *nvme* ]]; then
  pass "NVMe SSD 로 보입니다 ($ROOT_SRC)"
else
  soft "NVMe 가 아닐 수 있습니다 ($ROOT_SRC) — 에셋 로딩이 느려질 수 있습니다."
fi

hdr "3. 시스템 메모리"
free -h | head -2 | sed 's/^/       /'
echo
RAM_GB=$(free -g | awk '/^Mem:/ {print $2}')
if [[ -n "$RAM_GB" ]]; then
  if (( RAM_GB >= REQ_RAM_GB - 2 )); then   # 표기 오차 감안
    pass "RAM ${RAM_GB}GB (요구 ${REQ_RAM_GB}GB 이상)"
  else
    hard "RAM ${RAM_GB}GB — 요구치 ${REQ_RAM_GB}GB 미달"
  fi
fi

SWAP_GB=$(free -g | awk '/^Swap:/ {print $2}')
if [[ -n "$SWAP_GB" ]] && (( SWAP_GB == 0 )); then
  soft "스왑이 없습니다. 에셋 로딩 중 OOM 위험이 있으니 16GB 정도 잡아두길 권합니다."
fi

hdr "4. 운영체제"
if have lsb_release; then
  lsb_release -a 2>/dev/null | sed 's/^/       /'
  DISTRO=$(lsb_release -is 2>/dev/null)
  REL=$(lsb_release -rs 2>/dev/null)
  if [[ "$DISTRO" == "Ubuntu" && ( "$REL" == "22.04" || "$REL" == "24.04" ) ]]; then
    pass "Ubuntu $REL (지원 대상)"
  else
    soft "$DISTRO $REL — 공식 지원은 Ubuntu 22.04 / 24.04 LTS 입니다."
  fi
else
  cat /etc/os-release 2>/dev/null | head -3 | sed 's/^/       /'
  soft "lsb_release 없음 — OS 판정을 건너뜁니다."
fi

echo
info "커널: $(uname -r)"

hdr "5. 필수 도구"
for c in git curl conda; do
  if have "$c"; then
    pass "$c 있음 ($(command -v "$c"))"
  else
    case "$c" in
      conda) hard "conda 없음 — Miniconda 설치가 필요합니다: https://docs.conda.io/en/latest/miniconda.html" ;;
      *)     hard "$c 없음 — sudo apt install $c" ;;
    esac
  fi
done

if have docker; then
  pass "docker 있음 (컨테이너 설치 경로 사용 가능)"
  if docker info >/dev/null 2>&1; then
    pass "docker 데몬 접근 가능"
  else
    soft "docker 데몬에 접근할 수 없습니다 (sudo 필요하거나 미실행). Conda 경로를 쓰세요."
  fi
else
  info "docker 없음 — Conda 설치 경로를 사용하면 됩니다 (디스크도 절약)."
fi

hdr "6. 디스플레이 점유 확인 (RTX 3090 중요)"
if have nvidia-smi; then
  PROCS=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory \
            --format=csv,noheader 2>/dev/null)
  if [[ -n "$PROCS" ]]; then
    warn "GPU 를 사용 중인 프로세스:"
    echo "$PROCS" | sed 's/^/       /'
    warn "학습 전에 정리하면 num_envs 를 더 올릴 수 있습니다."
  else
    pass "GPU 연산을 점유한 프로세스 없음"
  fi

  if [[ -n "${DISPLAY:-}" ]]; then
    soft "DISPLAY=$DISPLAY — 그래픽 세션이 붙어 있습니다."
    warn "     학습은 --headless 로 돌리고, 가능하면 모니터를 iGPU 로 옮기세요."
  else
    pass "그래픽 세션 없음 (headless 환경 — VRAM 을 온전히 씁니다)"
  fi
fi

# ── 요약 ──────────────────────────────────────────────────────
hdr "판정 요약"
printf '       통과 %s%d%s / 경고 %s%d%s / 실패 %s%d%s\n' \
  "$C_GRN" "$PASS" "$C_OFF" "$C_YEL" "$WARNS" "$C_OFF" "$C_RED" "$FAILS" "$C_OFF"
echo

if (( FAILS > 0 )); then
  err "필수 요구사항 미달 항목이 ${FAILS}건 있습니다. 위 [FAIL] 항목을 먼저 해결하세요."
  exit 1
elif (( WARNS > 0 )); then
  warn "경고 ${WARNS}건 — 진행은 가능하지만 성능/안정성에 영향이 있을 수 있습니다."
  ok "다음 단계: ./scripts/01_install_robotic_surgery.sh"
  exit 0
else
  ok "모든 점검을 통과했습니다."
  ok "다음 단계: ./scripts/01_install_robotic_surgery.sh"
  exit 0
fi
