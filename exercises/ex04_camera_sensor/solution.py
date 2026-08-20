"""Ex 04 — 카메라 센서와 내부 파라미터: 복강경 뷰 (해답)

실제 카메라의 OpenCV intrinsics(fx, fy, cx, cy)를 Isaac Sim의 렌즈 파라미터로
변환해 시야각을 실물과 일치시키고, RGB + 깊이를 캡처해 검증한다.

핵심 학습 포인트
  1. Camera prim 생성 → initialize() → 렌즈 파라미터 설정 순서
  2. OpenCV intrinsics → focal_length / aperture 변환식 (그리고 /10.0 관례)
  3. distance_to_image_plane 깊이 채널
  4. 캡처 전에 render=True로 워밍업이 필요한 이유

실행:
    python solution.py --test --headless
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np

parser = argparse.ArgumentParser(description="Ex04: 카메라 센서")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false", help="GUI로 실행")
parser.add_argument("--test", action="store_true")
parser.add_argument("--out", default="_out_ex04", help="이미지 저장 폴더")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import isaacsim.core.utils.numpy.rotations as rot_utils  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402
from isaacsim.sensors.camera import Camera  # noqa: E402
from pxr import Sdf, UsdLux  # noqa: E402

# ── 실제 카메라 스펙 (Intel RealSense D435i 컬러 스트림 계열) ────────────────
IMG_W, IMG_H = 640, 480
FX, FY = 612.418, 612.362
CX, CY = 309.723, 245.359
PIXEL_SIZE_UM = 1.4          # 센서 픽셀 크기(µm). 데이터시트에서 가져온다.

# ── 씬 상수 ────────────────────────────────────────────────────────────────
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H          # 0.93
CAMERA_Z = 1.20                                   # 팬텀 위 0.27 m
EXPECTED_MIN_DEPTH = CAMERA_Z - PHANTOM_TOP_Z     # 0.27 m


def build_scene() -> tuple[World, Camera]:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    stage = omni.usd.get_context().get_stage()
    # 조명이 없으면 이미지가 새까맣게 나온다. 복강경은 자체 광원이 있으므로
    # 실제로는 카메라 위치에 SphereLight를 두는 게 더 현실적이다.
    key = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
    key.CreateIntensityAttr(2500.0)
    fill = UsdLux.SphereLight.Define(stage, Sdf.Path("/World/ScopeLight"))
    fill.CreateIntensityAttr(30000.0)
    fill.CreateRadiusAttr(0.02)
    fill.AddTranslateOp().Set((0.0, 0.0, CAMERA_Z - 0.02))

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.4, 0.8, TABLE_TOP_Z]), size=1.0,
        color=np.array([70, 80, 95]),
    ))
    world.scene.add(FixedCuboid(
        prim_path="/World/Phantom", name="phantom",
        position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_H / 2.0]),
        scale=np.array([0.45, 0.30, PHANTOM_H]), size=1.0,
        color=np.array([240, 200, 180]),
    ))

    # 서로 다른 높이의 도구 3개 — 깊이맵에 층이 생기는지 확인용
    for i, (x, y, h, color) in enumerate([
        (-0.10, -0.06, 0.03, [210, 215, 220]),
        (0.00, 0.05, 0.06, [180, 60, 60]),
        (0.11, -0.02, 0.09, [60, 140, 200]),
    ]):
        world.scene.add(DynamicCuboid(
            prim_path=f"/World/Tools/Tool{i}", name=f"tool{i}",
            position=np.array([x, y, PHANTOM_TOP_Z + h]),
            scale=np.array([0.02, 0.02, 0.02]), size=1.0,
            color=np.array(color), mass=0.02,
        ))

    # ── 카메라 생성 ────────────────────────────────────────────────────────
    # 카메라는 자기 로컬 -Z 방향을 본다. Y축 +90°로 수직 하향으로 만든다.
    camera = Camera(
        prim_path="/World/Endoscope",
        position=np.array([0.0, 0.0, CAMERA_Z]),
        orientation=rot_utils.euler_angles_to_quats(np.array([0, 90, 0]), degrees=True),
        frequency=30,
        resolution=(IMG_W, IMG_H),
    )
    return world, camera


def apply_opencv_intrinsics(camera: Camera) -> dict[str, float]:
    """OpenCV intrinsics를 Isaac Sim 렌즈 파라미터로 변환해 적용한다.

    변환식:
        aperture[mm]     = pixel_size[µm] × 1e-3 × 픽셀수
        focal_length[mm] = ((fx + fy) / 2) × pixel_size[µm] × 1e-3

    ★ Kit 내부 단위가 cm 기반이라 세터에 넣을 때 10으로 나눈다.
      (NVIDIA 공식 예제 camera_ros.py의 관례)
    """
    horizontal_aperture = PIXEL_SIZE_UM * 1e-3 * IMG_W       # mm
    vertical_aperture = PIXEL_SIZE_UM * 1e-3 * IMG_H         # mm
    focal_length = ((FX + FY) / 2.0) * PIXEL_SIZE_UM * 1e-3  # mm

    camera.set_focal_length(focal_length / 10.0)
    camera.set_horizontal_aperture(horizontal_aperture / 10.0)
    camera.set_vertical_aperture(vertical_aperture / 10.0)
    camera.set_clipping_range(0.01, 20.0)
    camera.set_focus_distance(EXPECTED_MIN_DEPTH)
    camera.set_lens_aperture(0.0)     # f-stop 0 = 피사계심도 끔 → 전부 선명

    hfov_deg = 2.0 * math.degrees(math.atan(horizontal_aperture / (2.0 * focal_length)))

    print("\n--- 렌즈 파라미터 변환 ---")
    print(f"horizontal_aperture = {horizontal_aperture:.4f} mm   → set {horizontal_aperture / 10:.5f}")
    print(f"vertical_aperture   = {vertical_aperture:.4f} mm   → set {vertical_aperture / 10:.5f}")
    print(f"focal_length        = {focal_length:.4f} mm   → set {focal_length / 10:.5f}")
    print(f"계산된 HFOV = {hfov_deg:.1f}°")
    # 교차검증: intrinsics로부터 직접 구한 HFOV와 일치해야 한다.
    hfov_from_fx = 2.0 * math.degrees(math.atan(IMG_W / (2.0 * FX)))
    print(f"intrinsics 직접 계산 HFOV = {hfov_from_fx:.1f}°  (두 값이 같아야 정상)")

    return {"hfov": hfov_deg, "focal_length": focal_length,
            "horizontal_aperture": horizontal_aperture}


def save_images(rgba: np.ndarray, depth: np.ndarray, out_dir: str) -> None:
    """PIL이 있으면 PNG로 저장한다. 없으면 .npy로 대체 저장."""
    os.makedirs(out_dir, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        np.save(os.path.join(out_dir, "endoscope_rgb.npy"), rgba)
        np.save(os.path.join(out_dir, "endoscope_depth.npy"), depth)
        print(f"[알림] Pillow가 없어 .npy로 저장했습니다: {out_dir}")
        print("       설치: pip install pillow  (바이너리 설치면 ./python.sh -m pip install pillow)")
        return

    Image.fromarray(rgba[:, :, :3]).save(os.path.join(out_dir, "endoscope_rgb.png"))

    # 깊이는 그대로 보면 아무것도 안 보인다. 유효 범위로 정규화해 8비트로 변환.
    finite = np.isfinite(depth)
    vis = np.zeros(depth.shape, dtype=np.uint8)
    if finite.any():
        lo, hi = float(depth[finite].min()), float(depth[finite].max())
        if hi - lo > 1e-9:
            norm = np.clip((depth - lo) / (hi - lo), 0.0, 1.0)
            vis = ((1.0 - norm) * 255).astype(np.uint8)   # 가까울수록 밝게
    Image.fromarray(vis).save(os.path.join(out_dir, "endoscope_depth.png"))
    print(f"저장 완료: {out_dir}/endoscope_rgb.png, {out_dir}/endoscope_depth.png")


def main() -> int:
    world, camera = build_scene()

    world.reset()
    # ★ initialize()는 reset() 이후에. 렌더 프로덕트를 만들고 어노테이터를 붙인다.
    camera.initialize()
    camera.add_distance_to_image_plane_to_frame()

    lens = apply_opencv_intrinsics(camera)

    # 워밍업: RTX 렌더러는 프레임을 누적한다. 첫 프레임은 노이즈투성이라
    # 반드시 render=True로 몇십 스텝 돌린 뒤에 읽어야 한다.
    warmup = 40 if args.test else 90
    for _ in range(warmup):
        world.step(render=True)

    rgba = camera.get_rgba()
    frame = camera.get_current_frame()
    depth = frame.get("distance_to_image_plane")

    print("\n--- 캡처 결과 ---")
    ok = True

    # 시야각이 실제 카메라 스펙(D435i 컬러 ≈ 55~58°)과 맞는지 확인.
    # 여기가 틀어지면 시뮬에서 학습한 비전 모델이 실물에서 안 돈다.
    if not (50.0 <= lens["hfov"] <= 62.0):
        print(f"  [실패] HFOV {lens['hfov']:.1f}° 가 기대 범위(50~62°)를 벗어났습니다.")
        print("         → set_focal_length / set_horizontal_aperture 의 /10.0 변환을 확인하세요.")
        ok = False

    if rgba is None or rgba.size == 0:
        print("RGB  : <비어 있음>  → 조명/렌더 스텝을 확인하세요")
        return 1
    mean_brightness = float(rgba[:, :, :3].mean())
    print(f"RGB   shape={rgba.shape} dtype={rgba.dtype}  mean={mean_brightness:.1f}")
    if rgba.shape[:2] != (IMG_H, IMG_W):
        print(f"  [실패] 기대 shape ({IMG_H}, {IMG_W}, 4)")
        ok = False
    if mean_brightness < 20:
        print("  [실패] 이미지가 너무 어둡습니다 — 조명을 추가하거나 강도를 올리세요")
        ok = False

    if depth is None:
        print("Depth : <없음> → add_distance_to_image_plane_to_frame() 호출을 확인하세요")
        return 1

    depth = np.asarray(depth)
    finite = np.isfinite(depth) & (depth > 0)
    valid_ratio = float(finite.mean())
    print(f"Depth shape={depth.shape} dtype={depth.dtype}")
    print(f"  유효 픽셀 비율: {valid_ratio * 100:.1f}%")
    if finite.any():
        dmin, dmax = float(depth[finite].min()), float(depth[finite].max())
        print(f"  최소 거리 {dmin:.4f} m / 최대 거리 {dmax:.4f} m")
        print(f"  카메라 z={CAMERA_Z:.2f}, 팬텀 상단 z={PHANTOM_TOP_Z:.2f} "
              f"→ 기대 최소 거리 {EXPECTED_MIN_DEPTH - 0.09:.2f} m (가장 높은 도구 기준)")
        # 가장 높은 도구(h=0.09) 윗면까지가 최소 거리여야 한다.
        expected = EXPECTED_MIN_DEPTH - 0.09 - 0.01
        if abs(dmin - expected) > 0.05 * max(expected, 1e-3) + 0.02:
            print(f"  [경고] 최소 거리가 기대값 {expected:.3f} m 와 차이가 큽니다.")
            print("         카메라 방향(쿼터니언)이나 높이를 확인하세요.")
    else:
        print("  [실패] 유효한 깊이 픽셀이 없습니다 — 카메라가 허공을 보고 있습니다")
        ok = False

    save_images(rgba, depth, args.out)

    print("-" * 60)
    if ok:
        print("PASS: 카메라 캘리브레이션과 캡처가 정상입니다.")
        return 0
    print("FAIL: 위 [실패] 항목을 확인하세요.")
    return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        simulation_app.close()
    raise SystemExit(exit_code)
