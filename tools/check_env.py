#!/usr/bin/env python3
"""Isaac Sim / Isaac for Healthcare 환경 사전 점검 스크립트.

Isaac Sim이 설치되어 있지 않아도 실행됩니다(GPU/드라이버 부분만 검사).
Isaac Sim이 있으면 import 및 에셋 서버 접근까지 확인합니다.

사용법:
    python tools/check_env.py
    python tools/check_env.py --full     # Isaac Sim 부팅까지 시도 (수 분 소요)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys

OK, WARN, FAIL = "  [OK]  ", " [WARN] ", " [FAIL] "


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def check_os() -> list[str]:
    notes = []
    system = platform.system()
    machine = platform.machine()
    print(f"{OK}OS: {system} {platform.release()} ({machine})")
    if system != "Linux":
        notes.append("i4h 워크플로우는 Ubuntu 22.04/24.04 x86_64 전용입니다.")
    if machine != "x86_64":
        notes.append(f"CPU 아키텍처가 {machine} 입니다. i4h는 x86_64만 지원합니다.")
    return notes


def check_python() -> list[str]:
    notes = []
    major, minor = sys.version_info[:2]
    label = f"{major}.{minor}.{sys.version_info[2]}"
    if (major, minor) == (3, 11):
        print(f"{OK}Python {label} (i4h 권장)")
    elif (major, minor) in {(3, 10), (3, 12)}:
        print(f"{WARN}Python {label}")
        notes.append("i4h-workflows는 Python 3.11을 고정합니다. 3.11 환경을 따로 만드세요.")
    else:
        print(f"{FAIL}Python {label}")
        notes.append("Isaac Sim 5.x는 Python 3.11이 필요합니다.")
    return notes


def check_gpu() -> list[str]:
    notes = []
    if shutil.which("nvidia-smi") is None:
        print(f"{FAIL}nvidia-smi 없음 — NVIDIA 드라이버가 설치되지 않았습니다.")
        return ["NVIDIA 드라이버를 설치하세요."]

    info = _run(["nvidia-smi",
                 "--query-gpu=name,compute_cap,memory.total,driver_version",
                 "--format=csv,noheader,nounits"])
    if not info:
        print(f"{FAIL}nvidia-smi 실행 실패")
        return ["드라이버 상태를 확인하세요."]

    for line in info.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        name, cc, vram_mib, driver = parts[0], parts[1], parts[2], parts[3]
        vram_gb = int(float(vram_mib)) / 1024.0
        print(f"{OK}GPU: {name} | compute_cap {cc} | VRAM {vram_gb:.1f} GB | driver {driver}")

        try:
            cc_val = float(cc)
        except ValueError:
            cc_val = 0.0
        if cc_val < 8.6:
            notes.append(f"{name}: compute capability {cc} < 8.6 → i4h 초음파 레이트레이싱 불가.")
        if any(tag in name for tag in ("A100", "H100", "H200")):
            notes.append(f"{name}: 데이터센터 GPU는 RT Core가 없어 i4h robotic_ultrasound가 동작하지 않습니다.")
        if vram_gb < 24:
            notes.append(f"{name}: VRAM {vram_gb:.1f} GB — i4h 권장은 24 GB 이상(파인튜닝 48 GB).")
        elif vram_gb < 48:
            notes.append(f"{name}: VRAM {vram_gb:.1f} GB — 추론/시뮬은 가능, 파인튜닝은 48 GB 권장.")

        try:
            if float(driver.split(".")[0]) < 555:
                notes.append(f"드라이버 {driver} < 555.x — i4h는 555 이상을 요구합니다.")
        except ValueError:
            pass
    return notes


def check_cuda() -> list[str]:
    nvcc = _run(["nvcc", "--version"])
    if nvcc is None:
        print(f"{WARN}nvcc 없음 — CUDA 툴킷 미설치(Isaac Sim 단독 학습에는 무방).")
        return ["i4h 컨테이너 빌드에는 CUDA 12.6 이상(13.0 미만)이 필요합니다."]
    version = next((tok.rstrip(",") for tok in nvcc.split() if tok.startswith("12.") or tok.startswith("13.")), "?")
    print(f"{OK}CUDA 툴킷: {version}")
    if version.startswith("13."):
        return ["CUDA 13.x는 i4h가 요구하는 범위(>=12.6, <13.0)를 벗어납니다."]
    return []


def check_memory_disk() -> list[str]:
    notes = []
    try:
        with open("/proc/meminfo") as fh:
            total_kb = int(next(l for l in fh if l.startswith("MemTotal")).split()[1])
        ram_gb = total_kb / 1024 / 1024
        print(f"{OK}시스템 RAM: {ram_gb:.0f} GB")
        if ram_gb < 64:
            notes.append(f"RAM {ram_gb:.0f} GB — i4h 권장은 64 GB 이상입니다.")
    except (OSError, StopIteration):
        print(f"{WARN}RAM 확인 불가")

    try:
        usage = shutil.disk_usage(".")
        free_gb = usage.free / 1024**3
        print(f"{OK}여유 디스크: {free_gb:.0f} GB")
        if free_gb < 100:
            notes.append(f"여유 디스크 {free_gb:.0f} GB — i4h는 100 GB 이상을 권장합니다.")
    except OSError:
        print(f"{WARN}디스크 확인 불가")
    return notes


def check_docker() -> list[str]:
    if shutil.which("docker") is None:
        print(f"{WARN}docker 없음 — i4h 워크플로우 실행에 필요합니다.")
        return ["Docker + NVIDIA Container Toolkit을 설치하세요."]
    print(f"{OK}docker 설치됨")
    if _run(["docker", "info"]) is None:
        return ["docker 데몬에 접근할 수 없습니다(권한 또는 데몬 미실행)."]
    return []


def check_isaacsim_import() -> list[str]:
    try:
        import isaacsim  # noqa: F401
    except ImportError:
        print(f"{WARN}isaacsim 모듈 없음 — pip 설치가 아니거나 환경 미활성.")
        return ["conda 환경을 활성화했는지, 또는 바이너리 설치의 python.sh를 쓰는지 확인하세요."]
    version = getattr(isaacsim, "__version__", "unknown")
    print(f"{OK}isaacsim 모듈 import 성공 (version={version})")
    return []


def check_isaacsim_boot() -> list[str]:
    """실제로 Kit 앱을 부팅해 에셋 서버 접근까지 확인한다. 수 분 걸릴 수 있음."""
    print("\n--- Isaac Sim 부팅 테스트 (첫 실행은 셰이더 컴파일로 10분 이상 걸릴 수 있습니다) ---")
    try:
        from isaacsim import SimulationApp
    except ImportError:
        print(f"{FAIL}SimulationApp import 실패")
        return ["Isaac Sim이 설치되지 않았습니다."]

    notes = []
    app = SimulationApp({"headless": True})
    try:
        from isaacsim.core.api import World
        from isaacsim.storage.native import get_assets_root_path

        world = World(stage_units_in_meters=1.0)
        world.scene.add_default_ground_plane()
        world.reset()
        for _ in range(10):
            world.step(render=False)
        print(f"{OK}World 생성 및 10 스텝 시뮬레이션 성공")

        root = get_assets_root_path()
        if root:
            print(f"{OK}에셋 루트: {root}")
        else:
            print(f"{FAIL}에셋 루트를 찾을 수 없음")
            notes.append("Nucleus 에셋 서버 접근 불가. 네트워크/프록시를 확인하거나 "
                         "로컬 에셋 팩을 받아 ISAAC_NUCLEUS_DIR를 설정하세요.")
    finally:
        app.close()
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true",
                        help="Isaac Sim을 실제로 부팅해 에셋 접근까지 확인 (수 분 소요)")
    args = parser.parse_args()

    print("=" * 68)
    print("  Isaac Sim / Isaac for Healthcare 환경 점검")
    print("=" * 68)

    notes: list[str] = []
    for check in (check_os, check_python, check_gpu, check_cuda,
                  check_memory_disk, check_docker, check_isaacsim_import):
        notes += check()

    if args.full:
        notes += check_isaacsim_boot()

    print("\n" + "=" * 68)
    if notes:
        print(f"  확인이 필요한 항목 {len(notes)}건")
        print("=" * 68)
        for i, note in enumerate(notes, 1):
            print(f"  {i}. {note}")
        print("\n  Ex01~09(Isaac Sim 단독)는 위 경고가 있어도 대부분 진행 가능합니다.")
        print("  i4h 워크플로우(Ex10 이후)는 모든 항목을 충족해야 합니다.")
    else:
        print("  모든 항목 통과 — i4h 워크플로우까지 진행 가능한 환경입니다.")
        print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
