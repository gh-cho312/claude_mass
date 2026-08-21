#!/usr/bin/env python3
"""
explore_openh.py — Open-H-Embodiment 데이터셋을 다운로드 없이 탐색

전체 780시간을 받기 전에, 무엇이 들어있는지 먼저 봅니다.
- 저장소에 어떤 서브셋/디렉터리가 있는지 나열
- 크기를 집계해 다운로드 계획을 세울 수 있게 함
- 가능하면 LeRobot 스트리밍으로 샘플 프레임 구조를 확인

주의: HuggingFace 데이터셋 카드에서 실제 디렉터리 구조와 포맷을
      직접 확인하는 편이 가장 정확합니다. 공개된 v1 과 GitHub 에
      기술된 v2 스펙(LeRobot v3.0)이 다를 수 있습니다.

사용법:
    python tools/explore_openh.py                 # 구조 요약
    python tools/explore_openh.py --tree          # 디렉터리 트리
    python tools/explore_openh.py --sample        # 스트리밍 샘플 1건
    python tools/explore_openh.py --repo <id>     # 다른 repo 지정
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

DEFAULT_REPO = os.environ.get(
    "OPENH_REPO_ID", "nvidia/PhysicalAI-Robotics-Open-H-Embodiment"
)


def human(nbytes: int | None) -> str:
    if not nbytes:
        return "?"
    v = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or unit == "TB":
            return f"{v:,.1f}{unit}"
        v /= 1024
    return f"{v:,.1f}TB"


def list_files(repo_id: str):
    """데이터셋 저장소의 파일 목록과 크기를 가져옵니다."""
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
        sys.exit(
            f"저장소 정보를 가져오지 못했습니다: {repo_id}\n"
            f"  원인: {e}\n"
            f"  - 네트워크 또는 프록시 문제일 수 있습니다.\n"
            f"  - 접근에 로그인이 필요하면:  hf auth login"
        )
    return info.siblings or []


def summarize(files, top_level_depth: int = 2):
    """경로 앞부분으로 묶어 크기를 집계합니다."""
    groups: dict[str, dict] = defaultdict(lambda: {"n": 0, "bytes": 0, "ext": defaultdict(int)})
    total_bytes = 0
    for f in files:
        path = f.rfilename
        size = getattr(f, "size", None) or 0
        total_bytes += size
        parts = path.split("/")
        key = "/".join(parts[:top_level_depth]) if len(parts) > top_level_depth else parts[0]
        g = groups[key]
        g["n"] += 1
        g["bytes"] += size
        ext = os.path.splitext(path)[1] or "(없음)"
        g["ext"][ext] += 1
    return groups, total_bytes


def cmd_summary(repo_id: str, depth: int):
    print(f"\n=== 저장소: {repo_id} ===\n")
    files = list_files(repo_id)
    if not files:
        print("파일 목록이 비어 있습니다.")
        return

    groups, total = summarize(files, depth)
    print(f"전체 파일 수 : {len(files):,}")
    print(f"전체 용량    : {human(total)}")
    print(f"\n{'서브셋 (상위 %d단계)' % depth:<50} {'파일수':>9} {'용량':>12}")
    print("-" * 75)

    for key in sorted(groups, key=lambda k: -groups[k]["bytes"]):
        g = groups[key]
        print(f"{key:<50} {g['n']:>9,} {human(g['bytes']):>12}")

    print("-" * 75)
    print(f"{'합계':<50} {len(files):>9,} {human(total):>12}\n")

    # 확장자 분포 — 포맷 파악용
    ext_all: dict[str, int] = defaultdict(int)
    for g in groups.values():
        for e, c in g["ext"].items():
            ext_all[e] += c
    print("파일 형식 분포:")
    for e, c in sorted(ext_all.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {e:<12} {c:>8,}")

    # LeRobot 포맷 힌트
    names = {f.rfilename for f in files}
    print("\n포맷 판정:")
    if any(n.endswith("meta/info.json") or n == "meta/info.json" for n in names):
        print("  LeRobot 데이터셋으로 보입니다 (meta/info.json 존재)")
    if any(".parquet" in n for n in names):
        print("  Parquet 데이터 파일 있음 (LeRobot v2/v3 공통)")
    if any(n.endswith(".mp4") for n in names):
        print("  MP4 비디오 있음")

    print(
        "\n다운로드 계획:\n"
        "  전체를 받지 마세요. 위 목록에서 필요한 서브셋을 골라:\n"
        "    python tools/download_openh_subset.py --include '<서브셋>/*'\n"
    )


def cmd_tree(repo_id: str, max_lines: int):
    files = list_files(repo_id)
    paths = sorted(f.rfilename for f in files)
    print(f"\n=== 파일 목록 (최대 {max_lines}줄) ===\n")
    for p in paths[:max_lines]:
        print(" ", p)
    if len(paths) > max_lines:
        print(f"\n  ... 외 {len(paths) - max_lines:,}개")
    print()


def cmd_sample(repo_id: str):
    """스트리밍으로 첫 프레임 하나를 읽어 구조를 확인합니다."""
    print(f"\n=== 스트리밍 샘플: {repo_id} ===\n")
    try:
        from lerobot.datasets.streaming_dataset import StreamingLeRobotDataset
    except ImportError:
        try:
            from lerobot.common.datasets.streaming_dataset import (  # type: ignore
                StreamingLeRobotDataset,
            )
        except ImportError:
            sys.exit(
                "StreamingLeRobotDataset 를 import 하지 못했습니다.\n"
                "  lerobot>=0.6.0 이 필요합니다:\n"
                "    conda activate openh && pip install -U 'lerobot>=0.6.0'\n"
                "  (모듈 경로는 lerobot 버전에 따라 다를 수 있습니다.)"
            )

    try:
        ds = StreamingLeRobotDataset(repo_id)
    except Exception as e:
        sys.exit(
            f"스트리밍 데이터셋을 열지 못했습니다: {e}\n"
            "  - repo_id 가 맞는지 확인하세요.\n"
            "  - 이 저장소가 LeRobot v3.0 포맷이 아닐 수 있습니다.\n"
            "    HuggingFace 데이터셋 카드에서 포맷을 직접 확인하세요."
        )

    print("데이터셋 메타:")
    for attr in ("num_episodes", "num_frames", "fps", "features"):
        val = getattr(ds, attr, None)
        if val is None and hasattr(ds, "meta"):
            val = getattr(ds.meta, attr, None)
        if val is not None:
            if attr == "features" and isinstance(val, dict):
                print(f"  {attr}:")
                for k, v in val.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {attr}: {val}")

    print("\n첫 프레임:")
    try:
        it = iter(ds)
        frame = next(it)
        for k, v in frame.items():
            shape = getattr(v, "shape", None)
            dtype = getattr(v, "dtype", None)
            desc = f"shape={tuple(shape)}" if shape is not None else f"{type(v).__name__}"
            if dtype is not None:
                desc += f" dtype={dtype}"
            print(f"  {k:<40} {desc}")
    except StopIteration:
        print("  (프레임이 없습니다)")
    except Exception as e:
        print(f"  프레임을 읽지 못했습니다: {e}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Open-H-Embodiment 데이터셋 탐색 (다운로드 없음)"
    )
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"HF repo id (기본: {DEFAULT_REPO})")
    ap.add_argument("--depth", type=int, default=2, help="집계할 경로 깊이 (기본 2)")
    ap.add_argument("--tree", action="store_true", help="파일 목록 출력")
    ap.add_argument("--max-lines", type=int, default=200, help="--tree 최대 출력 줄 수")
    ap.add_argument("--sample", action="store_true", help="스트리밍으로 샘플 프레임 확인")
    args = ap.parse_args()

    if args.tree:
        cmd_tree(args.repo, args.max_lines)
    elif args.sample:
        cmd_sample(args.repo)
    else:
        cmd_summary(args.repo, args.depth)


if __name__ == "__main__":
    main()
