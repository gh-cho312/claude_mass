"""Ex 08 — 커스텀 의료 에셋 파이프라인 (뼈대 코드)

TODO를 채우세요. 요구사항과 두 가지 함정(단위 / 충돌 근사)은 README.md 참고.
실행: python starter.py --test --headless
"""

from __future__ import annotations

import argparse
import os
import struct
import time

import numpy as np

parser = argparse.ArgumentParser(description="Ex08: 커스텀 의료 에셋 파이프라인")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--test", action="store_true")
parser.add_argument("--out", default="_out_ex08")
parser.add_argument("--approx", default="convexDecomposition",
                    choices=["none", "convexHull", "convexDecomposition",
                             "boundingCube", "boundingSphere", "meshSimplification", "sdf"])
parser.add_argument("--subdiv", type=int, default=4)
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

# TODO: import
#   omni.usd
#   isaacsim.core.api.World
#   isaacsim.core.api.materials.PhysicsMaterial
#   isaacsim.core.api.objects.{DynamicSphere, FixedCuboid}
#   isaacsim.core.prims.{GeometryPrim, RigidPrim}
#   isaacsim.core.utils.semantics.{add_labels, get_labels}
#   pxr.{Gf, Usd, UsdGeom, UsdPhysics, Vt}

MM_TO_M = 0.001
LIVER_RADII_MM = np.array([140.0, 90.0, 60.0])
LIVER_MASS_KG = 1.5
TABLE_TOP_Z = 0.75
LIVER_CENTER_Z = TABLE_TOP_Z + 0.10
PLAUSIBLE = {"x": (0.20, 0.32), "y": (0.12, 0.22), "z": (0.08, 0.16)}


def make_organ_mesh(subdiv: int):
    """정이십면체 세분화 → 타원체 변형 → (points_mm, faces).

    (이 함수는 실제 CT 세그멘테이션 결과를 대신하는 것이므로
     해답의 구현을 그대로 가져다 써도 좋습니다. 학습 대상은 아래 단계입니다.)
    """
    raise NotImplementedError


def write_binary_stl(path, points, faces):
    # TODO: 80바이트 헤더 + uint32 삼각형 수 + (법선 3f + 정점 9f + uint16) × N
    raise NotImplementedError


def read_binary_stl(path):
    # TODO: 위 포맷을 역으로 파싱해 (points, faces) 반환
    raise NotImplementedError


def create_usd_mesh(stage, prim_path, points_mm, faces):
    """★ 단위 변환의 핵심. mm 메쉬를 stage 단위로 스케일해서 넣는다."""
    # TODO: meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
    # TODO: scale = MM_TO_M / meters_per_unit;  points_m = points_mm * scale
    # TODO: UsdGeom.Mesh.Define + CreatePointsAttr / FaceVertexIndices / FaceVertexCounts
    # TODO: CreateSubdivisionSchemeAttr("none"), displayColor
    # TODO: Xformable로 LIVER_CENTER_Z에 배치
    raise NotImplementedError


def world_bbox_size(prim) -> np.ndarray:
    # TODO: UsdGeom.BBoxCache(...).ComputeWorldBound(prim).ComputeAlignedRange().GetSize()
    raise NotImplementedError


def main() -> int:
    os.makedirs(args.out, exist_ok=True)

    # 1단계: 메쉬 생성 + STL 저장/재로드, mm 바운딩박스 출력
    # TODO

    # 2단계: World 생성 후 create_usd_mesh 호출, m 바운딩박스가 PLAUSIBLE 범위인지 검증
    # TODO

    # 3단계: GeometryPrim.apply_collision_apis() + set_collision_approximations([args.approx])
    #        MassAPI, PhysicsMaterial 적용. 소요 시간 측정
    # TODO

    # 4단계: add_labels(prim, ["liver"], "class") + stage.GetRootLayer().Export(usd_path)
    # TODO

    # 5단계: 프로브(DynamicSphere)를 떨어뜨려 관통 여부 확인, 스텝 시간 측정
    #        저장한 USD를 add_reference_to_stage로 재로드해 크기 유지 확인
    # TODO

    return 0


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
