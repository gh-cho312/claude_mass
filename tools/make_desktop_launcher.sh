#!/usr/bin/env bash
# =============================================================================
# Isaac Sim (pip 설치) 클릭 실행 아이콘 만들기
# -----------------------------------------------------------------------------
# pip 설치는 바탕화면/앱메뉴 아이콘을 만들지 않습니다. 이 스크립트가 conda 환경의
# 'isaacsim' 실행기를 가리키는 .desktop 런처를 만들어, 앱 메뉴/바탕화면에서
# 클릭으로 Isaac Sim GUI를 열 수 있게 합니다.
#
# 사용법 (여러분 로컬 PC에서):
#     bash tools/make_desktop_launcher.sh            # 환경 이름 기본값 'isaacsim'
#     bash tools/make_desktop_launcher.sh myenv      # 다른 conda 환경 이름
#
# 만든 뒤: 앱 메뉴에서 "Isaac Sim" 검색 → 클릭. (첫 실행은 EULA 동의 +
# 확장 다운로드로 10분 이상 걸리며, 터미널 창이 함께 떠서 진행이 보입니다.)
# =============================================================================
set -euo pipefail

ENV_NAME="${1:-isaacsim}"

# conda base 경로 찾기 (활성/비활성 모두 대응)
CONDA_BASE=""
if command -v conda >/dev/null 2>&1; then
  CONDA_BASE="$(conda info --base)"
else
  for b in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" "/opt/conda"; do
    [[ -f "$b/etc/profile.d/conda.sh" ]] && CONDA_BASE="$b" && break
  done
fi
[[ -n "$CONDA_BASE" ]] || { echo "conda 를 찾을 수 없습니다. 먼저 setup_local.sh 로 설치하세요." >&2; exit 1; }

# 실제로 그 환경에 isaacsim 실행기가 있는지 확인
if [[ ! -x "${CONDA_BASE}/envs/${ENV_NAME}/bin/isaacsim" ]]; then
  echo "경고: ${CONDA_BASE}/envs/${ENV_NAME}/bin/isaacsim 가 없습니다." >&2
  echo "      Isaac Sim 설치가 끝난 환경 이름을 인자로 주세요. 예: bash tools/make_desktop_launcher.sh isaacsim" >&2
fi

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
DESKTOP_FILE="$APPS/isaac-sim.desktop"

# Terminal=true : 첫 실행의 EULA 동의/확장 다운로드 진행을 볼 수 있도록 터미널을 함께 띄움
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Isaac Sim
Comment=NVIDIA Isaac Sim (conda 환경: ${ENV_NAME})
Exec=bash -lc 'source "${CONDA_BASE}/etc/profile.d/conda.sh" && conda activate ${ENV_NAME} && isaacsim isaacsim.exp.full.kit'
Icon=applications-science
Terminal=true
Categories=Development;Science;Education;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"
echo "만듦: $DESKTOP_FILE"

# 바탕화면에도 하나 복사 (있을 때)
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [[ -d "$DESKTOP_DIR" ]]; then
  cp "$DESKTOP_FILE" "$DESKTOP_DIR/isaac-sim.desktop"
  chmod +x "$DESKTOP_DIR/isaac-sim.desktop"
  # GNOME 계열에서 바탕화면 아이콘 '신뢰' 표시(더블클릭 허용)
  gio set "$DESKTOP_DIR/isaac-sim.desktop" metadata::trusted true 2>/dev/null || true
  echo "만듦: $DESKTOP_DIR/isaac-sim.desktop"
fi

update-desktop-database "$APPS" >/dev/null 2>&1 || true

cat <<'MSG'

완료.
- 앱 메뉴(Show Applications)에서 "Isaac Sim" 검색 → 클릭하면 실행됩니다.
- 바탕화면 아이콘이 회색/실행 거부면: 우클릭 → "실행 허용(Allow Launching)" 한 번 눌러주세요.
- 첫 실행은 EULA 동의 + 확장 다운로드로 10분 이상 걸립니다(정상). 함께 뜬 터미널로 진행 상황이 보입니다.
MSG
