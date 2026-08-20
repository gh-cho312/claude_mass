# 02. API 치트시트 (Isaac Sim 5.x)

> 모든 import 경로는 `isaac-sim/IsaacSim` v5.1.0 소스에서 확인했습니다.
> 4.x 이하의 `omni.isaac.*` 경로는 5.x에서 `isaacsim.*`로 **전부 이름이 바뀌었습니다.**

## 0. 4.x → 5.x 이름 변경 대응표

| 4.x (구) | 5.x (신) |
|---|---|
| `omni.isaac.core` | `isaacsim.core.api` |
| `omni.isaac.core.utils.*` | `isaacsim.core.utils.*` |
| `omni.isaac.core.prims` | `isaacsim.core.prims` |
| `omni.isaac.nucleus.get_assets_root_path` | `isaacsim.storage.native.get_assets_root_path` |
| `omni.isaac.sensor` | `isaacsim.sensors.camera` / `isaacsim.sensors.physics` |
| `omni.isaac.motion_generation` | `isaacsim.robot_motion.motion_generation` |
| `omni.isaac.franka` | `isaacsim.robot.manipulators.examples.franka` |
| `omni.isaac.cloner` | `isaacsim.core.cloner` |

인터넷 튜토리얼 대부분이 아직 4.x 경로입니다. 위 표로 치환하면 대개 그대로 돌아갑니다.

---

## 1. 앱 부팅 / 종료

```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--headless", action="store_true")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": args.headless})

# --- 여기부터만 isaacsim.* / omni.* import 가능 ---
try:
    main()
finally:
    simulation_app.close()
```

`SimulationApp` 주요 설정:
```python
SimulationApp({
    "headless": True,
    "width": 1280, "height": 720,
    "renderer": "RayTracedLighting",   # 또는 "PathTracing"
    "physics_gpu": 0,
    "active_gpu": 0,
})
```

---

## 2. World / Scene

```python
from isaacsim.core.api import World

world = World(stage_units_in_meters=1.0)          # backend="numpy" / "torch"
world.scene.add_default_ground_plane()
world.reset()                                     # 물리 초기화 (필수)
world.step(render=True)

world.is_playing()   # 재생 중?
world.is_stopped()   # 정지됨?
world.current_time_step_index
world.get_physics_dt()
```

물리 디바이스 지정:
```python
from isaacsim.core.simulation_manager import SimulationManager
SimulationManager.set_physics_sim_device("cuda")   # "cpu" | "cuda"
```

---

## 3. 기본 도형 (프로토타이핑용)

```python
from isaacsim.core.api.objects import (
    DynamicCuboid, VisualCuboid, FixedCuboid,
    DynamicSphere, VisualSphere,
    DynamicCylinder, DynamicCapsule,
)
from isaacsim.core.api.objects.ground_plane import GroundPlane
import numpy as np

cube = world.scene.add(DynamicCuboid(
    prim_path="/World/Tool",
    name="tool",                       # scene에서 조회할 키
    position=np.array([0.0, 0.0, 0.5]),
    scale=np.array([0.02, 0.02, 0.15]),
    size=1.0,
    color=np.array([200, 200, 200]),
    mass=0.05,
))

cube.get_world_pose()          # (position, orientation(w,x,y,z))
cube.get_linear_velocity()
cube.set_world_pose(position=np.array([0, 0, 1.0]))
```

| 클래스 접두사 | 강체 물리 | 충돌체 | 용도 |
|---|:--:|:--:|---|
| `Visual*` | ❌ | ❌ | 시각 참조용 마커, 목표 위치 표시 |
| `Fixed*` | ❌ | ✅ | 테이블, 벽 등 고정 구조물 |
| `Dynamic*` | ✅ | ✅ | 떨어지고 굴러가는 물체 |

---

## 4. USD 직접 조작

```python
import omni.usd
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf, UsdLux

stage = omni.usd.get_context().get_stage()

xform = UsdGeom.Xform.Define(stage, "/World/Patient")
xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.8))
xform.AddScaleOp().Set(Gf.Vec3f(0.001, 0.001, 0.001))   # mm → m

light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
light.CreateIntensityAttr(1500)

prim = stage.GetPrimAtPath("/World/Patient")
UsdPhysics.CollisionAPI.Apply(prim)
mass_api = UsdPhysics.MassAPI.Apply(prim)
mass_api.CreateMassAttr(1.2)
```

메쉬 참조 붙이기:
```python
from isaacsim.core.utils.stage import add_reference_to_stage, get_stage_units, open_stage
add_reference_to_stage(usd_path="/path/liver.usd", prim_path="/World/Organs/Liver")
```

---

## 5. Prim 래퍼 (뷰 클래스 — 배치 차원 주의)

```python
from isaacsim.core.prims import Articulation, RigidPrim, GeometryPrim, XFormPrim

rb = RigidPrim(prim_paths_expr="/World/Tool")
rb.get_world_poses()                   # (positions (N,3), orientations (N,4))
rb.set_masses(np.array([0.05]))

geo = GeometryPrim(prim_paths_expr="/World/Tray")
geo.apply_collision_apis()
```

---

## 6. 로봇 아티큘레이션

```python
from isaacsim.core.prims import Articulation
from isaacsim.core.utils.stage import add_reference_to_stage
from isaacsim.storage.native import get_assets_root_path

root = get_assets_root_path()
add_reference_to_stage(root + "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
                       "/World/Arm")
arm = Articulation(prim_paths_expr="/World/Arm", name="arm")
arm.set_world_poses(positions=np.array([[0.0, 0.0, 0.0]]))

world.reset()                          # ← 이후에만 아래가 동작

arm.num_dof                            # 9 (7 관절 + 2 그리퍼)
arm.dof_names                          # ['panda_joint1', ..., 'panda_finger_joint2']
arm.get_joint_positions()              # (1, 9)
arm.set_joint_positions([[0, -0.6, 0, -2.2, 0, 1.6, 0.8, 0.04, 0.04]])
arm.set_joint_velocities([[0.0]*9])
arm.get_measured_joint_efforts()
```

**★ 위치 제어: 배치형 vs 단일형 (API가 다릅니다)**

```python
# 배치형 Articulation 뷰 — get_articulation_controller() 없음. 직접 apply_action.
from isaacsim.core.utils.types import ArticulationActions          # 복수형
arm.apply_action(ArticulationActions(joint_positions=targets))     # targets: (N, num_dof)

# 단일형 SingleArticulation — 컨트롤러를 거친다
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction           # 단수형
single = SingleArticulation(prim_path="/World/Arm", name="arm")
ctrl = single.get_articulation_controller()
ctrl.apply_action(ArticulationAction(joint_positions=np.array([...])))   # (num_dof,)
```

| | `Articulation` (뷰) | `SingleArticulation` |
|---|---|---|
| shape | `(N, num_dof)` | `(num_dof,)` |
| 액션 타입 | `ArticulationActions` | `ArticulationAction` |
| 제어 호출 | `view.apply_action(...)` | `single.get_articulation_controller().apply_action(...)` |
| 모션 생성 모듈 | ❌ 사용 불가 | ✅ `RmpFlow`, `ArticulationKinematicsSolver`가 요구 |
| 용도 | 다중 환경 RL/배치 | 단일 로봇 + IK/모션 계획 |

**자주 쓰는 에셋 경로** (`get_assets_root_path()` 기준 상대 경로):
```
/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd
/Isaac/Robots/UniversalRobots/ur10/ur10.usd
/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd
/Isaac/Environments/Grid/default_environment.usd
/Isaac/Environments/Simple_Room/simple_room.usd
/Isaac/Environments/Hospital/hospital.usd
/Isaac/Props/YCB/Axis_Aligned/
```
> 경로는 릴리스마다 바뀝니다. GUI의 **Content** 브라우저에서 실제 경로를 확인하세요.

---

## 7. 모션 생성 / IK

```python
from isaacsim.robot_motion.motion_generation import (
    LulaKinematicsSolver,          # 해석적 IK/FK
    ArticulationKinematicsSolver,  # IK 결과를 관절 액션으로 변환
    RmpFlow,                       # 반응형 모션 정책 (충돌 회피 포함)
    ArticulationMotionPolicy,      # 정책 → 관절 액션
    interface_config_loader,
)

cfg = interface_config_loader.load_supported_lula_kinematics_solver_config("Franka")
ik = LulaKinematicsSolver(**cfg)
art_ik = ArticulationKinematicsSolver(arm, ik, "panda_hand")

action, ok = art_ik.compute_inverse_kinematics(
    target_position=np.array([0.4, 0.0, 0.4]),
    target_orientation=np.array([0.0, 1.0, 0.0, 0.0]),
)
if ok:
    arm.get_articulation_controller().apply_action(action)
```

RMPFlow (충돌 회피 + 부드러운 추종):
```python
rmp_cfg = interface_config_loader.load_supported_motion_policy_config("Franka", "RMPflow")
rmpflow = RmpFlow(**rmp_cfg)
policy = ArticulationMotionPolicy(arm, rmpflow, default_physics_dt=1/60.0)
rmpflow.set_end_effector_target(target_position=..., target_orientation=...)
ctrl.apply_action(policy.get_next_articulation_action())
```

Franka 전용 단축 경로:
```python
from isaacsim.robot.manipulators.examples.franka.controllers.rmpflow_controller import RMPFlowController
from isaacsim.robot.manipulators.examples.franka.tasks import FollowTarget
```

---

## 8. 카메라

```python
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.numpy.rotations as rot_utils

cam = Camera(
    prim_path="/World/Endoscope",
    position=np.array([0.0, 0.0, 1.2]),
    orientation=rot_utils.euler_angles_to_quats(np.array([0, 90, 0]), degrees=True),
    frequency=30,
    resolution=(640, 480),
)
cam.initialize()                              # world.reset() 이후에
cam.add_distance_to_image_plane_to_frame()    # 깊이 채널 활성화

# 렌즈 파라미터 (단위: Kit은 cm 기반이라 /10 변환이 자주 등장)
cam.set_focal_length(1.93)          # mm → Kit 단위
cam.set_horizontal_aperture(0.896)
cam.set_clipping_range(0.01, 10.0)
cam.set_focus_distance(0.15)
cam.set_lens_aperture(0.0)          # 0 = 피사계심도 끄기(선명한 이미지)

world.step(render=True)             # 렌더링 필수
rgba = cam.get_rgba()                                  # (H, W, 4) uint8
depth = cam.get_current_frame()["distance_to_image_plane"]
```

### OpenCV 내부 파라미터 → Isaac 렌즈 변환

```python
pixel_size_um = 1.4                                # 센서 픽셀 크기(µm)
horizontal_aperture = pixel_size_um * 1e-3 * width  # mm
focal_length = (fx + fy) / 2 * pixel_size_um * 1e-3 # mm

cam.set_focal_length(focal_length / 10.0)
cam.set_horizontal_aperture(horizontal_aperture / 10.0)
```

---

## 9. 접촉 센서

```python
from isaacsim.sensors.physics import ContactSensor

sensor = world.scene.add(ContactSensor(
    prim_path="/World/Arm/panda_hand/contact_sensor",
    name="probe_contact",
    min_threshold=0.0,
    max_threshold=1e7,
    radius=0.05,
    translation=np.array([0.0, 0.0, 0.05]),
))
sensor.add_raw_contact_data_to_frame()

world.reset()
frame = sensor.get_current_frame()
# {'time':…, 'value': <힘 크기 N>, 'in_contact': bool, 'contacts': [...]}
```

---

## 10. Replicator (합성 데이터)

```python
import omni.replicator.core as rep

cam = rep.create.camera(position=(0, 0, 2), look_at=(0, 0, 0))
rp = rep.create.render_product(cam, (640, 480))

rgb  = rep.AnnotatorRegistry.get_annotator("rgb")
seg  = rep.AnnotatorRegistry.get_annotator("semantic_segmentation")
bbox = rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight")
dep  = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
for a in (rgb, seg, bbox, dep):
    a.attach(rp)

with rep.trigger.on_frame():
    with rep.get.prims(path_pattern="/World/Tools/.*"):
        rep.modify.pose(
            position=rep.distribution.uniform((-0.2, -0.2, 0.8), (0.2, 0.2, 0.9)),
            rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
        )
    with rep.create.group([light]):
        rep.modify.attribute("intensity", rep.distribution.uniform(500, 3000))

rep.orchestrator.step(rt_subframes=8)
data = rgb.get_data()
```

파일로 자동 저장:
```python
writer = rep.WriterRegistry.get("BasicWriter")
writer.initialize(output_dir="_out", rgb=True, semantic_segmentation=True,
                  bounding_box_2d_tight=True, distance_to_image_plane=True)
writer.attach([rp])
for _ in range(100):
    rep.orchestrator.step(rt_subframes=8)
writer.detach()
```

SDG 품질 설정 (공식 예제 관례):
```python
import carb
s = carb.settings.get_settings()
s.set("/omni/replicator/captureOnPlay", False)
s.set("/omni/replicator/asyncRendering", False)
s.set("/app/asyncRendering", False)
s.set("rtx/post/dlss/execMode", 2)          # Quality
```

---

## 11. 시맨틱 라벨

```python
from isaacsim.core.utils.semantics import add_labels, get_labels

prim = stage.GetPrimAtPath("/World/Organs/Liver")
add_labels(prim, labels=["liver"], instance_name="class")
print(get_labels(prim))
```

---

## 12. 다중 환경 클로닝

```python
from isaacsim.core.cloner import GridCloner
from isaacsim.core.utils.prims import define_prim

cloner = GridCloner(spacing=2.0)
cloner.define_base_env("/World/envs")
define_prim("/World/envs/env_0")
# ... env_0 안에 씬 구성 ...

paths = cloner.generate_paths("/World/envs/env", num_envs)
env_pos = cloner.clone(source_prim_path="/World/envs/env_0", prim_paths=paths)

robots = Articulation(prim_paths_expr="/World/envs/*/Robot", name="robots")
world.scene.add(robots)
world.reset()
robots.get_joint_positions()          # (num_envs, num_dof)
```

---

## 13. 유틸 모음

```python
from isaacsim.core.utils.stage import add_reference_to_stage, get_stage_units, open_stage, create_new_stage
from isaacsim.core.utils.prims import define_prim, delete_prim, is_prim_path_valid, get_prim_at_path
from isaacsim.core.utils.viewports import set_camera_view
from isaacsim.core.utils.types import ArticulationAction
from isaacsim.storage.native import get_assets_root_path
import isaacsim.core.utils.numpy.rotations as rot_utils

set_camera_view(eye=[2.0, 2.0, 2.0], target=[0, 0, 0.8],
                camera_prim_path="/OmniverseKit_Persp")
```
