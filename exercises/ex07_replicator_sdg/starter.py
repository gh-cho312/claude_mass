"""Ex 07 — Replicator 합성 데이터 생성 (뼈대 코드)

TODO를 채우세요. 요구사항은 README.md 참고.
★ with 블록은 "실행"이 아니라 "등록"이라는 점을 기억하세요.

실행: python starter.py --test
"""

from __future__ import annotations

import argparse
import os

import numpy as np

parser = argparse.ArgumentParser(description="Ex07: Replicator SDG")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--test", action="store_true")
parser.add_argument("--frames", type=int, default=20)
parser.add_argument("--out", default="_out_ex07")
parser.add_argument("--subframes", type=int, default=8)
args, _ = parser.parse_known_args()

if args.test:
    args.frames = min(args.frames, 3)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   carb
#   omni.replicator.core as rep
#   omni.usd
#   isaacsim.core.api.World
#   isaacsim.core.api.objects.FixedCuboid
#   isaacsim.core.utils.semantics.{add_labels, get_labels}

RESOLUTION = (640, 480)
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H

TOOLS = [
    ("scalpel", np.array([0.015, 0.015, 0.13]), np.array([210, 215, 225])),
    ("forceps", np.array([0.012, 0.050, 0.10]), np.array([170, 175, 185])),
    ("clamp",   np.array([0.035, 0.020, 0.07]), np.array([140, 145, 155])),
]
POSE_MIN = (-0.16, -0.09, PHANTOM_TOP_Z + 0.012)
POSE_MAX = (0.16, 0.09, PHANTOM_TOP_Z + 0.030)


def configure_sdg_settings():
    """★ asyncRendering을 끄지 않으면 이미지와 라벨이 한 프레임씩 어긋난다."""
    # TODO: carb.settings.get_settings() 로
    #   /omni/replicator/captureOnPlay = False
    #   /omni/replicator/asyncRendering = False
    #   /app/asyncRendering = False
    #   rtx/post/dlss/execMode = 2
    raise NotImplementedError


def build_scene():
    # TODO: World + ground + 테이블 + 팬텀 + TOOLS 3종 (FixedCuboid)
    raise NotImplementedError


def apply_semantic_labels():
    """★ add_labels()를 쓸 것 (add_update_semantics는 deprecated)."""
    # TODO: stage.GetPrimAtPath(f"/World/Tools/{name}") 에
    #        add_labels(prim, labels=[name], instance_name="class")
    raise NotImplementedError


def setup_replicator_graph():
    # TODO: camera = rep.create.camera(...); rp = rep.create.render_product(camera, RESOLUTION)
    # TODO: 조명 2개 rep.create.light(...)
    # TODO: 어노테이터 4종 get_annotator + attach(rp)
    #
    # TODO: with rep.trigger.on_frame():
    #           with rep.get.prims(path_pattern="/World/Tools/.*"):
    #               rep.modify.pose(position=rep.distribution.uniform(POSE_MIN, POSE_MAX), ...)
    #           with rep.create.group([light_key, light_fill]):
    #               rep.modify.attribute("intensity", rep.distribution.uniform(500, 4000))
    #           with camera:
    #               rep.modify.pose(position=rep.distribution.uniform(...), look_at=...)
    raise NotImplementedError


def setup_writer(render_product):
    # TODO: rep.WriterRegistry.get("BasicWriter") → initialize(...) → attach([rp])
    raise NotImplementedError


def summarize_bboxes(bbox_data):
    """(검출 라벨 집합, 박스 중심 목록) 반환."""
    # TODO: bbox_data["data"] 순회, bbox_data["info"]["idToLabels"]로 라벨 매핑
    raise NotImplementedError


def main() -> int:
    configure_sdg_settings()
    world = build_scene()
    apply_semantic_labels()
    world.reset()

    render_product, annotators = setup_replicator_graph()
    writer = setup_writer(render_product)
    # TODO: rep.orchestrator.preview()   ← 첫 프레임 워밍업

    for frame in range(args.frames):
        # TODO: rep.orchestrator.step(rt_subframes=args.subframes)  ← 여기서 랜덤화 실행
        # TODO: annotators["rgb"].get_data(), ["bounding_box_2d_tight"].get_data()
        # TODO: 밝기 평균 / 검출 라벨 / 박스 중심 기록 및 출력
        pass

    # TODO: writer.detach()
    # TODO: 클래스별 검출률, 밝기 표준편차, bbox 위치 표준편차, 출력 파일 검증 → PASS/FAIL
    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
