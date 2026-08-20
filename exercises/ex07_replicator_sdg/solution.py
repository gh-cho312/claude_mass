"""Ex 07 — Replicator 합성 데이터 생성: 수술 도구 검출 데이터셋 (해답)

도구 3종에 시맨틱 라벨을 붙이고, 포즈·조명·카메라를 랜덤화하며
RGB + 세그멘테이션 + 바운딩박스 + 깊이를 동시에 캡처한다.

핵심 학습 포인트
  1. Replicator의 with 블록은 "실행"이 아니라 "등록"이다
  2. add_labels() — 5.x의 새 시맨틱 API (add_update_semantics는 deprecated)
  3. render_product + AnnotatorRegistry + BasicWriter
  4. asyncRendering을 끄지 않으면 이미지와 라벨이 어긋난다

실행:
    python solution.py --test --frames 3
    python solution.py --frames 50 --out _out_ex07
"""

from __future__ import annotations

import argparse
import os

import numpy as np

parser = argparse.ArgumentParser(description="Ex07: Replicator SDG")
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--gui", dest="headless", action="store_false")
parser.add_argument("--test", action="store_true")
parser.add_argument("--frames", type=int, default=20, help="생성할 프레임 수")
parser.add_argument("--out", default="_out_ex07")
parser.add_argument("--subframes", type=int, default=8, help="캡처 전 렌더 누적 횟수")
args, _ = parser.parse_known_args()

if args.test:
    args.frames = min(args.frames, 3)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": args.headless})

import carb  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.objects import FixedCuboid  # noqa: E402
from isaacsim.core.utils.semantics import add_labels, get_labels  # noqa: E402

RESOLUTION = (640, 480)
TABLE_TOP_Z = 0.75
PHANTOM_H = 0.18
PHANTOM_TOP_Z = TABLE_TOP_Z + PHANTOM_H          # 0.93

# 도구 3종: (이름, 크기, 색)
TOOLS = [
    ("scalpel", np.array([0.015, 0.015, 0.13]), np.array([210, 215, 225])),
    ("forceps", np.array([0.012, 0.050, 0.10]), np.array([170, 175, 185])),
    ("clamp", np.array([0.035, 0.020, 0.07]), np.array([140, 145, 155])),
]

# 랜덤화 범위 — 팬텀 상단 위 좁은 영역
POSE_MIN = (-0.16, -0.09, PHANTOM_TOP_Z + 0.012)
POSE_MAX = (0.16, 0.09, PHANTOM_TOP_Z + 0.030)


def configure_sdg_settings() -> None:
    """NVIDIA 공식 SDG 예제가 항상 켜는 설정.

    ★ asyncRendering을 끄지 않으면 랜덤화가 반영되기 전 프레임이 캡처되어
      이미지와 라벨이 한 프레임씩 어긋난다. 조용히 데이터셋을 망치는 버그다.
    """
    s = carb.settings.get_settings()
    s.set("/omni/replicator/captureOnPlay", False)
    s.set("/omni/replicator/asyncRendering", False)
    s.set("/app/asyncRendering", False)
    s.set("rtx/post/dlss/execMode", 2)      # 0=Performance 1=Balanced 2=Quality 3=Auto


def build_scene() -> World:
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    world.scene.add(FixedCuboid(
        prim_path="/World/Table", name="table",
        position=np.array([0.0, 0.0, TABLE_TOP_Z / 2.0]),
        scale=np.array([1.2, 0.7, TABLE_TOP_Z]), size=1.0,
        color=np.array([60, 70, 85]),
    ))
    world.scene.add(FixedCuboid(
        prim_path="/World/Phantom", name="phantom",
        position=np.array([0.0, 0.0, TABLE_TOP_Z + PHANTOM_H / 2.0]),
        scale=np.array([0.50, 0.30, PHANTOM_H]), size=1.0,
        color=np.array([240, 200, 180]),
    ))

    for name, scale, color in TOOLS:
        world.scene.add(FixedCuboid(
            prim_path=f"/World/Tools/{name}", name=name,
            position=np.array([0.0, 0.0, PHANTOM_TOP_Z + 0.02]),
            scale=scale, size=1.0, color=color,
        ))

    return world


def apply_semantic_labels() -> None:
    """도구 prim에 시맨틱 라벨을 붙인다.

    ★ 5.x는 UsdSemantics.LabelsAPI 기반의 add_labels()를 쓴다.
      옛 add_update_semantics()는 deprecated (경고가 뜬다).
    ★ 라벨은 메쉬를 가진 prim(또는 그 조상)에 붙여야 한다.
      빈 Xform에만 붙이면 세그멘테이션에 아무것도 안 나온다.
    """
    stage = omni.usd.get_context().get_stage()
    print("\n--- 시맨틱 라벨 ---")
    for name, _, _ in TOOLS:
        path = f"/World/Tools/{name}"
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            print(f"{path:24s} → [실패] prim이 없습니다")
            continue
        add_labels(prim, labels=[name], instance_name="class")
        print(f"{path:24s} → {get_labels(prim)}")


def setup_replicator_graph():
    """카메라, 렌더 프로덕트, 어노테이터, 랜덤화 그래프를 구성한다.

    ★ 아래 with 블록들은 "지금 실행"이 아니라 "매 프레임 이렇게 하라"는 등록이다.
      실제 랜덤화는 rep.orchestrator.step()을 부를 때마다 일어난다.
    """
    camera = rep.create.camera(position=(0.0, -0.9, 1.7), look_at=(0.0, 0.0, PHANTOM_TOP_Z))
    render_product = rep.create.render_product(camera, RESOLUTION)

    # 조명 두 개 — 강도와 색을 랜덤화할 대상
    light_key = rep.create.light(light_type="sphere", position=(0.5, -0.5, 1.9),
                                 scale=0.1, intensity=3000.0)
    light_fill = rep.create.light(light_type="sphere", position=(-0.5, 0.4, 1.7),
                                  scale=0.1, intensity=1200.0)

    annotators = {
        "rgb": rep.AnnotatorRegistry.get_annotator("rgb"),
        "semantic_segmentation": rep.AnnotatorRegistry.get_annotator("semantic_segmentation"),
        "bounding_box_2d_tight": rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight"),
        "distance_to_image_plane": rep.AnnotatorRegistry.get_annotator("distance_to_image_plane"),
    }
    for annotator in annotators.values():
        annotator.attach(render_product)

    # ── 랜덤화 그래프 등록 ────────────────────────────────────────────────
    with rep.trigger.on_frame():
        # ① 도구 포즈 — 팬텀 위 좁은 영역에서 균등 샘플링, z축 회전은 전방위
        with rep.get.prims(path_pattern="/World/Tools/.*"):
            rep.modify.pose(
                position=rep.distribution.uniform(POSE_MIN, POSE_MAX),
                rotation=rep.distribution.uniform((-15, -15, -180), (15, 15, 180)),
            )

        # ② 조명 — 수술등의 밝기·색온도 변화를 모사
        with rep.create.group([light_key, light_fill]):
            rep.modify.attribute("intensity", rep.distribution.uniform(500.0, 4000.0))
            rep.modify.attribute("color",
                                 rep.distribution.uniform((0.70, 0.70, 0.70), (1.0, 1.0, 1.0)))

        # ③ 카메라 — 팬텀 위 반구에서 시점 샘플링, 항상 팬텀 중심을 본다
        with camera:
            rep.modify.pose(
                position=rep.distribution.uniform((-0.55, -1.05, 1.35), (0.55, -0.45, 1.95)),
                look_at=(0.0, 0.0, PHANTOM_TOP_Z),
            )

    return render_product, annotators


def setup_writer(render_product):
    """BasicWriter로 데이터셋을 디스크에 자동 저장한다."""
    os.makedirs(args.out, exist_ok=True)
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=args.out,
        rgb=True,
        semantic_segmentation=True,
        bounding_box_2d_tight=True,
        distance_to_image_plane=True,
        colorize_semantic_segmentation=True,
    )
    writer.attach([render_product])
    return writer


def summarize_bboxes(bbox_data) -> tuple[set[str], list[tuple[float, float]]]:
    """bounding_box_2d_tight 출력에서 (검출 라벨 집합, 박스 중심 목록)을 뽑는다.

    반환 구조:
      data["data"] : 구조화 배열, 필드에 semanticId, x_min, y_min, x_max, y_max 등
      data["info"]["idToLabels"] : {semanticId: {"class": "scalpel"}} 형태의 매핑
    """
    labels: set[str] = set()
    centers: list[tuple[float, float]] = []
    if not bbox_data:
        return labels, centers

    boxes = bbox_data.get("data")
    id_to_labels = (bbox_data.get("info") or {}).get("idToLabels", {}) or {}
    if boxes is None or len(boxes) == 0:
        return labels, centers

    for box in boxes:
        try:
            sem_id = int(box["semanticId"])
            x0, y0 = float(box["x_min"]), float(box["y_min"])
            x1, y1 = float(box["x_max"]), float(box["y_max"])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        centers.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0))

        entry = id_to_labels.get(sem_id) or id_to_labels.get(str(sem_id))
        if isinstance(entry, dict):
            labels.add(str(entry.get("class", entry)))
        elif entry is not None:
            labels.add(str(entry))
    return labels, centers


def main() -> int:
    configure_sdg_settings()
    world = build_scene()
    apply_semantic_labels()
    world.reset()

    render_product, annotators = setup_replicator_graph()
    writer = setup_writer(render_product)

    # 첫 프레임은 렌더러가 아직 데워지지 않았다. 미리보기로 한 번 돌려준다.
    rep.orchestrator.preview()

    print(f"\n--- 캡처 ({args.frames} 프레임) ---")
    brightness: list[float] = []
    all_centers: list[tuple[float, float]] = []
    detected_count = {name: 0 for name, _, _ in TOOLS}

    for frame in range(args.frames):
        # ★ 여기서 비로소 랜덤화가 실행되고 프레임이 캡처된다.
        rep.orchestrator.step(rt_subframes=args.subframes)

        rgb = annotators["rgb"].get_data()
        bbox = annotators["bounding_box_2d_tight"].get_data()

        rgb_mean = float(np.asarray(rgb)[:, :, :3].mean()) if rgb is not None and np.size(rgb) else 0.0
        brightness.append(rgb_mean)

        labels, centers = summarize_bboxes(bbox)
        all_centers.extend(centers)
        for name in detected_count:
            if name in labels:
                detected_count[name] += 1

        print(f"frame {frame:2d}: rgb mean={rgb_mean:6.1f}  "
              f"bbox {len(centers)}개  labels={sorted(labels) if labels else '{}'}")

    writer.detach()      # ★ 잊으면 마지막 프레임이 flush되지 않을 수 있다

    # ── 검증 ──────────────────────────────────────────────────────────────
    print("\n--- 검증 ---")
    ok = True

    detect_line = "  ".join(f"{n} {c}/{args.frames}" for n, c in detected_count.items())
    print(f"클래스별 검출 프레임 수: {detect_line}")
    min_ratio = min(detected_count.values()) / max(args.frames, 1)
    if min_ratio < 0.5:
        print("  [실패] 절반 이상의 프레임에서 안 잡히는 클래스가 있습니다.")
        print("         → 라벨이 메쉬 prim에 붙었는지, 도구가 시야 안인지 확인하세요.")
        ok = False

    bright_std = float(np.std(brightness)) if len(brightness) > 1 else 0.0
    print(f"RGB 밝기 표준편차: {bright_std:.1f}", end="  ")
    if bright_std > 3.0 or args.frames < 2:
        print("(조명 랜덤화 작동 중)")
    else:
        print("\n  [실패] 프레임 간 밝기가 거의 같습니다 — 조명 랜덤화가 등록되지 않았습니다.")
        ok = False

    if len(all_centers) > 3:
        centers_arr = np.array(all_centers)
        pos_std = float(centers_arr.std(axis=0).mean())
        print(f"bbox 위치 표준편차: {pos_std:.1f} px", end="  ")
        if pos_std > 10.0:
            print("(포즈 랜덤화 작동 중)")
        else:
            print("\n  [실패] 박스 위치가 거의 고정입니다 — 포즈 랜덤화를 확인하세요.")
            ok = False

    produced = sorted(os.listdir(args.out)) if os.path.isdir(args.out) else []
    print(f"출력 폴더 `{args.out}`: {produced if produced else '<비어 있음>'}")
    if not produced:
        print("  [실패] BasicWriter가 파일을 쓰지 않았습니다. writer.attach()를 확인하세요.")
        ok = False

    print("-" * 60)
    if ok:
        print("PASS: 라벨이 딸린 합성 데이터셋이 생성되었습니다.")
        return 0
    print("FAIL: 위 [실패] 항목을 확인하세요.")
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
