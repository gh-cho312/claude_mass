"""Ex 08 — 커스텀 의료 에셋 파이프라인 (해답)

밀리미터 단위의 장기 메쉬(STL)를 Isaac Sim에서 물리적으로 상호작용 가능한
USD 에셋으로 변환하고, 단위/충돌 근사/라벨을 검증한다.

핵심 학습 포인트
  1. ★ 단위 함정 — STL에는 단위 정보가 없다. 의료 메쉬는 거의 항상 mm.
  2. 충돌 근사 선택이 오목 형상 표현과 성능을 좌우한다
  3. numpy 배열 → UsdGeom.Mesh 직접 생성
  4. USD 저장 → 재로드 → 물리 검증의 왕복 파이프라인

실행:
    python solution.py --test --headless
    python solution.py --approx convexHull            # 오목부가 메워지는 것 관찰
    python solution.py --approx convexDecomposition   # 권장
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
                             "boundingCube", "boundingSphere", "meshSimplification", "sdf"],
                    help="충돌 근사 방식")
parser.add_argument("--subdiv", type=int, default=4, help="구 세분화 단계 (정점 수 제어)")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.materials import PhysicsMaterial  # noqa: E402
from isaacsim.core.api.objects import DynamicSphere, FixedCuboid  # noqa: E402
from isaacsim.core.prims import GeometryPrim, RigidPrim  # noqa: E402
from isaacsim.core.utils.semantics import add_labels, get_labels  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from pxr import Gf, Usd, UsdGeom, UsdPhysics, Vt  # noqa: E402

MM_TO_M = 0.001

# 성인 간의 대략적인 반경 (mm). 실제 간은 좌우 약 20~28 cm.
LIVER_RADII_MM = np.array([140.0, 90.0, 60.0])
LIVER_MASS_KG = 1.5

TABLE_TOP_Z = 0.75
LIVER_CENTER_Z = TABLE_TOP_Z + 0.10

# 해부학적 타당성 범위 (m)
PLAUSIBLE = {
    "x": (0.20, 0.32),
    "y": (0.12, 0.22),
    "z": (0.08, 0.16),
}


# ---------------------------------------------------------------------------
# 1단계 — 입력 메쉬 생성 (실제로는 CT 세그멘테이션 결과가 들어올 자리)
# ---------------------------------------------------------------------------
def make_organ_mesh(subdiv: int) -> tuple[np.ndarray, np.ndarray]:
    """정이십면체를 세분화한 뒤 타원체로 늘리고 노이즈를 주어 장기 유사 메쉬 생성.

    반환: (points (V, 3) mm 단위, faces (F, 3) int)
    """
    phi = (1.0 + 5.0 ** 0.5) / 2.0
    verts = np.array([
        [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
        [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
        [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
    ], dtype=np.float64)
    faces = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.int64)

    verts /= np.linalg.norm(verts, axis=1, keepdims=True)

    # Loop 방식의 단순 세분화: 각 삼각형을 4개로 쪼개고 중점을 구면에 투영
    for _ in range(subdiv):
        midpoint_cache: dict[tuple[int, int], int] = {}
        vert_list = verts.tolist()
        new_faces = []

        def midpoint(a: int, b: int) -> int:
            key = (min(a, b), max(a, b))
            if key not in midpoint_cache:
                m = (np.array(vert_list[a]) + np.array(vert_list[b])) / 2.0
                m /= np.linalg.norm(m)
                vert_list.append(m.tolist())
                midpoint_cache[key] = len(vert_list) - 1
            return midpoint_cache[key]

        for a, b, c in faces:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            new_faces += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]

        verts = np.array(vert_list)
        faces = np.array(new_faces, dtype=np.int64)

    # 타원체로 늘린다 (mm 단위)
    points = verts * LIVER_RADII_MM

    # 결정적(deterministic) 노이즈로 울퉁불퉁하게. 간의 엽(lobe) 느낌을 낸다.
    # 재현성을 위해 난수 대신 좌표의 함수를 쓴다.
    bumps = (0.06 * np.sin(3.0 * verts[:, 0] * np.pi)
             + 0.05 * np.cos(2.0 * verts[:, 1] * np.pi)
             + 0.04 * np.sin(4.0 * verts[:, 2] * np.pi))
    points *= (1.0 + bumps)[:, None]

    return points.astype(np.float64), faces


def write_binary_stl(path: str, points: np.ndarray, faces: np.ndarray) -> None:
    """의존성 없이 바이너리 STL을 쓴다. (실무에서는 trimesh를 쓰세요)"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tris = points[faces]                                       # (F, 3, 3)
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, np.where(lengths == 0, 1.0, lengths))

    with open(path, "wb") as fh:
        fh.write(b"synthetic liver mesh, millimetre units".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(faces)))
        for n, tri in zip(normals, tris):
            fh.write(struct.pack("<3f", *n.astype("float32")))
            for v in tri:
                fh.write(struct.pack("<3f", *v.astype("float32")))
            fh.write(struct.pack("<H", 0))


def read_binary_stl(path: str) -> tuple[np.ndarray, np.ndarray]:
    """바이너리 STL을 읽어 (points, faces)로 반환. 중복 정점은 병합하지 않는다."""
    with open(path, "rb") as fh:
        fh.read(80)
        (count,) = struct.unpack("<I", fh.read(4))
        raw = np.frombuffer(fh.read(count * 50), dtype=np.uint8)

    # 각 삼각형 레코드는 50바이트: 법선 12 + 정점 36 + 속성 2
    records = raw.reshape(count, 50)
    verts = records[:, 12:48].copy().view("<f4").reshape(count * 3, 3).astype(np.float64)
    faces = np.arange(count * 3, dtype=np.int64).reshape(count, 3)
    return verts, faces


# ---------------------------------------------------------------------------
# 2단계 — USD 변환
# ---------------------------------------------------------------------------
def create_usd_mesh(stage, prim_path: str, points_mm: np.ndarray,
                    faces: np.ndarray) -> UsdGeom.Mesh:
    """mm 단위 메쉬를 stage 단위(m)로 변환해 UsdGeom.Mesh로 만든다."""
    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
    # stage가 1 unit = 1 m 이면 mm 값에 0.001을 곱해야 한다.
    scale = MM_TO_M / meters_per_unit
    print(f"stage metersPerUnit = {meters_per_unit}  →  mm 메쉬에 {scale} 스케일 적용")

    points_m = points_mm * scale

    UsdGeom.Xform.Define(stage, "/World/Organs")
    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points_m.astype("float32")))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray.FromNumpy(faces.ravel().astype("int32")))
    mesh.CreateFaceVertexCountsAttr(
        Vt.IntArray.FromNumpy(np.full(len(faces), 3, dtype="int32")))
    # 세분화를 끄지 않으면 렌더 시 표면이 다시 쪼개져 성능이 떨어진다.
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(0.45, 0.16, 0.13)]))

    xformable = UsdGeom.Xformable(mesh.GetPrim())
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, LIVER_CENTER_Z))
    return mesh


def world_bbox_size(prim) -> np.ndarray:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
    size = rng.GetSize()
    return np.array([size[0], size[1], size[2]])


def main() -> int:
    os.makedirs(args.out, exist_ok=True)
    stl_path = os.path.join(args.out, "liver_raw.stl")
    usd_path = os.path.abspath(os.path.join(args.out, "liver.usd"))

    # ── 1단계 ─────────────────────────────────────────────────────────────
    print("--- 1단계: 입력 메쉬 (mm 단위) ---")
    subdiv = min(args.subdiv, 2) if args.test else args.subdiv
    points_mm, faces = make_organ_mesh(subdiv)
    write_binary_stl(stl_path, points_mm, faces)
    points_mm, faces = read_binary_stl(stl_path)

    bbox_mm = points_mm.max(axis=0) - points_mm.min(axis=0)
    print(f"정점 {len(points_mm)}개, 삼각형 {len(faces)}개")
    print(f"바운딩박스(mm): [{bbox_mm[0]:.1f}, {bbox_mm[1]:.1f}, {bbox_mm[2]:.1f}]"
          "      ← 수백 단위 = mm")
    print(f"저장: {stl_path}")

    ok = True

    # ── 2단계 ─────────────────────────────────────────────────────────────
    print("\n--- 2단계: USD 변환 ---")
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    stage = omni.usd.get_context().get_stage()

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.2, 0.8, TABLE_TOP_Z]), size=1.0,
        color=np.array([60, 70, 85]),
    ))

    liver_path = "/World/Organs/Liver"
    create_usd_mesh(stage, liver_path, points_mm, faces)
    liver_prim = stage.GetPrimAtPath(liver_path)

    bbox_m = world_bbox_size(liver_prim)
    print(f"바운딩박스(m): [{bbox_m[0]:.3f}, {bbox_m[1]:.3f}, {bbox_m[2]:.3f}]")

    for axis, value in zip("xyz", bbox_m):
        lo, hi = PLAUSIBLE[axis]
        mark = "✓" if lo <= value <= hi else "✗"
        print(f"  {mark} {axis}: {value:.3f} m (타당 범위 {lo:.2f}~{hi:.2f})")
        if not (lo <= value <= hi):
            ok = False
    if not ok:
        print("  [실패] 단위 변환을 확인하세요. mm 값을 그대로 넣으면 100배 큽니다.")

    # ── 3단계: 물리 속성 ──────────────────────────────────────────────────
    print("\n--- 3단계: 충돌 근사 ---")
    geo = GeometryPrim(prim_paths_expr=liver_path, name="liver_geom")
    geo.apply_collision_apis()

    t0 = time.perf_counter()
    geo.set_collision_approximations([args.approx])
    elapsed = time.perf_counter() - t0
    print(f"approximation = {geo.get_collision_approximations()[0]}")
    print(f"적용 소요: {elapsed:.2f} s")
    if args.approx == "convexHull":
        print("  [주의] convexHull은 오목부를 메웁니다. 위/대장/심실에는 부적합합니다.")
    if args.approx == "none":
        print("  [주의] 삼각메쉬 충돌체는 정적 물체에만 쓸 수 있습니다 (동적 강체 불가).")

    UsdPhysics.MassAPI.Apply(liver_prim).CreateMassAttr(LIVER_MASS_KG)
    tissue = PhysicsMaterial(
        prim_path="/World/PhysicsMaterials/Tissue", name="tissue",
        static_friction=0.45, dynamic_friction=0.40, restitution=0.02,
    )
    geo.apply_physics_materials(tissue)

    # ── 4단계: 라벨 + 저장 ────────────────────────────────────────────────
    print("\n--- 4단계: 라벨 및 저장 ---")
    add_labels(liver_prim, labels=["liver"], instance_name="class")
    labels = get_labels(liver_prim)
    print(f"라벨: {labels}")
    if not labels:
        print("  [실패] 라벨이 붙지 않았습니다.")
        ok = False

    stage.GetRootLayer().Export(usd_path)
    size_kb = os.path.getsize(usd_path) / 1024.0
    print(f"저장: {usd_path} ({size_kb:.0f} KB)")

    # ── 5단계: 물리 검증 ──────────────────────────────────────────────────
    print("\n--- 5단계: 물리 검증 ---")
    liver_top_z = LIVER_CENTER_Z + bbox_m[2] / 2.0
    probe_start_z = liver_top_z + 0.40

    world.scene.add(DynamicSphere(
        prim_path="/World/Probe", name="probe",
        position=np.array([0.0, 0.0, probe_start_z]),
        radius=0.012, color=np.array([40, 120, 220]), mass=0.05,
    ))
    probe_view = RigidPrim(prim_paths_expr="/World/Probe", name="probe_view")
    world.scene.add(probe_view)

    set_camera_view(eye=[0.9, -0.9, 1.3], target=[0.0, 0.0, LIVER_CENTER_Z],
                    camera_prim_path="/OmniverseKit_Persp")

    world.reset()

    steps = 250 if args.test else 500
    render = not args.headless
    t0 = time.perf_counter()
    for _ in range(steps):
        world.step(render=render)
    step_ms = (time.perf_counter() - t0) / steps * 1000.0

    probe_z = float(probe_view.get_world_poses()[0][0][2])
    print(f"프로브 낙하: z {probe_start_z:.3f} → {probe_z:.3f} "
          f"(간 상단 {liver_top_z:.3f})")

    # 간 위에 얹혔으면 대략 liver_top_z + 반지름 근처에서 멈춘다.
    # 테이블 위(0.75)까지 떨어졌다면 간을 관통한 것.
    if probe_z > LIVER_CENTER_Z:
        print("✓ 관통 없음 — 충돌체가 정상 동작합니다")
    else:
        print("✗ 프로브가 간을 관통했습니다")
        print("   → apply_collision_apis() 호출, 근사 방식, 스케일을 확인하세요")
        ok = False

    print(f"평균 스텝 시간: {step_ms:.2f} ms  (근사: {args.approx})")

    # ── 왕복 검증: 저장한 USD를 다시 참조로 로드 ──────────────────────────
    from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
    add_reference_to_stage(usd_path=usd_path, prim_path="/World/ReloadCheck")
    reload_prim = stage.GetPrimAtPath("/World/ReloadCheck/Organs/Liver")
    if reload_prim.IsValid():
        reload_size = world_bbox_size(reload_prim)
        print(f"재로드 바운딩박스(m): [{reload_size[0]:.3f}, {reload_size[1]:.3f}, "
              f"{reload_size[2]:.3f}]")
        if np.allclose(reload_size, bbox_m, rtol=0.02):
            print("✓ 왕복 후에도 크기가 유지됩니다")
        else:
            print("✗ 재로드 후 크기가 달라졌습니다 — 스케일이 이중 적용됐을 수 있습니다")
            ok = False
    else:
        print("[알림] 재로드한 prim 경로를 찾지 못했습니다 (참조 계층 확인 필요)")

    print("-" * 60)
    if ok:
        print("PASS: 의료 에셋 파이프라인이 정상 동작합니다.")
        return 0
    print("FAIL: 위 [실패]/✗ 항목을 확인하세요.")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:
        print(f"[에러] {exc}")
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
