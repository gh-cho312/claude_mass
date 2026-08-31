#!/usr/bin/env python3
"""
download_openh_subset.py — Open-H-Embodiment 서브셋 선택 다운로드

전체 780시간을 받으면 디스크가 감당하지 못합니다. 필요한 부분만 받습니다.
받기 전에 반드시 용량을 계산해 보여주고 확인을 받습니다.

사용법:
    # 어떤 서브셋이 있는지 보기
    python tools/download_openh_subset.py --list

    # 용량만 계산 (받지 않음)
    python tools/download_openh_subset.py --include 'surgical/*' --dry-run

    # 실제 다운로드
    python tools/download_openh_subset.py --include 'surgical/*'

    # 여러 패턴
    python tools/download_openh_subset.py --include 'meta/*' --include 'data/chunk-000/*'
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import sys
from collections import defaultdict

DEFAULT_REPO = os.environ.get(
    "OPENH_REPO_ID", "nvidia/PhysicalAI-Robotics-Open-H-Embodiment"
)
DEFAULT_DIR = os.environ.get(
    "OPENH_DATA_DIR", os.path.expanduser("~/data/open-h-embodiment")
)


def human(nbytes: float | None) -> str:
    if not nbytes:
        return "0B"
    v = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or unit == "TB":
            return f"{v:,.1f}{unit}"
        v /= 1024
    return f"{v:,.1f}TB"


def get_files(repo_id: str):
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit(
            "huggingface_hub 가 없습니다.\n"
            "  conda activate openh && pip install 'huggingface_hub[cli]'"
        )
    api = HfApi()
    try:
        info = api.repo_info(repo_id=repo_id, repo_type="dataset", files_metadata=True)
    except Exception as e:
        sys.exit(f"저장소 조회 실패: {repo_id}\n  {e}")
    return info.siblings or []


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def cmd_list(repo_id: str, depth: int):
    files = get_files(repo_id)
    groups: dict[str, dict] = defaultdict(lambda: {"n": 0, "bytes": 0})
    for f in files:
        parts = f.rfilename.split("/")
        key = "/".join(parts[:depth]) if len(parts) > depth else parts[0]
        groups[key]["n"] += 1
        groups[key]["bytes"] += getattr(f, "size", None) or 0

    print(f"\n=== {repo_id} — 서브셋 목록 ===\n")
    print(f"{'경로 패턴':<52} {'파일수':>8} {'용량':>12}")
    print("-" * 76)
    for key in sorted(groups, key=lambda k: -groups[k]["bytes"]):
        g = groups[key]
        print(f"{key + '/*':<52} {g['n']:>8,} {human(g['bytes']):>12}")
    print("-" * 76)
    total = sum(g["bytes"] for g in groups.values())
    print(f"{'합계':<52} {len(files):>8,} {human(total):>12}\n")
    print("받을 때:")
    print("  python tools/download_openh_subset.py --include '<위 패턴>' --dry-run\n")


def cmd_download(repo_id: str, patterns: list[str], out_dir: str, dry_run: bool):
    files = get_files(repo_id)
    selected = [f for f in files if match_any(f.rfilename, patterns)]

    if not selected:
        print(f"\n패턴에 맞는 파일이 없습니다: {patterns}")
        print("--list 로 사용 가능한 패턴을 먼저 확인하세요.\n")
        sys.exit(1)

    total = sum(getattr(f, "size", None) or 0 for f in selected)

    print(f"\n=== 다운로드 계획 ===\n")
    print(f"저장소   : {repo_id}")
    print(f"패턴     : {', '.join(patterns)}")
    print(f"대상 경로: {out_dir}")
    print(f"파일 수  : {len(selected):,}")
    print(f"예상 용량: {human(total)}")

    # 디스크 여유 확인
    check_dir = out_dir
    while check_dir and not os.path.isdir(check_dir):
        parent = os.path.dirname(check_dir)
        if parent == check_dir:
            break
        check_dir = parent
    if os.path.isdir(check_dir):
        free = shutil.disk_usage(check_dir).free
        print(f"디스크 여유: {human(free)} @ {check_dir}")
        if total > free * 0.9:
            print(
                f"\n  경고: 여유 공간이 부족합니다 "
                f"(필요 {human(total)} / 여유 {human(free)})"
            )
            print("  OPENH_DATA_DIR 를 다른 파티션으로 지정하거나 패턴을 좁히세요.")
            if not dry_run:
                sys.exit(1)

    if dry_run:
        print("\n[dry-run] 실제로 받지 않았습니다.\n")
        print("샘플 파일 (최대 20개):")
        for f in selected[:20]:
            print(f"  {human(getattr(f, 'size', None) or 0):>10}  {f.rfilename}")
        if len(selected) > 20:
            print(f"  ... 외 {len(selected) - 20:,}개")
        print()
        return

    reply = input(f"\n{human(total)} 를 받습니다. 계속할까요? [y/N] ").strip()
    if reply.lower() != "y":
        print("취소했습니다.")
        return

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit("huggingface_hub 가 필요합니다.")

    os.makedirs(out_dir, exist_ok=True)
    print(f"\n다운로드 시작 -> {out_dir}\n")
    path = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        allow_patterns=patterns,
        local_dir=out_dir,
    )
    print(f"\n완료: {path}\n")


def main():
    ap = argparse.ArgumentParser(description="Open-H-Embodiment 서브셋 다운로드")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"HF repo id (기본: {DEFAULT_REPO})")
    ap.add_argument("--dir", default=DEFAULT_DIR, help=f"저장 경로 (기본: {DEFAULT_DIR})")
    ap.add_argument("--include", action="append", default=[],
                    help="받을 파일 패턴 (여러 번 지정 가능). 예: 'data/chunk-000/*'")
    ap.add_argument("--list", action="store_true", help="서브셋 목록만 출력")
    ap.add_argument("--depth", type=int, default=2, help="--list 집계 깊이")
    ap.add_argument("--dry-run", action="store_true", help="용량만 계산하고 받지 않음")
    args = ap.parse_args()

    if args.list or not args.include:
        cmd_list(args.repo, args.depth)
        if not args.include and not args.list:
            print("--include 로 패턴을 지정하세요.\n")
        return

    cmd_download(args.repo, args.include, args.dir, args.dry_run)


if __name__ == "__main__":
    main()
