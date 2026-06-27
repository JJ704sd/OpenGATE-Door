"""
CT 转台旋转仿真
- 使用 DynamicGeometryActor 实现转台旋转
- 多角度采集投影数据
"""

import opengate as gate
from opengate.utility import g4_units
from scipy.spatial.transform import Rotation
import os

# 单位
m = gate.g4_units.m
cm = gate.g4_units.cm
mm = gate.g4_units.mm
keV = gate.g4_units.keV
second = gate.g4_units.second

# 路径
output_dir = "D:/OpenGATE/output"
os.makedirs(output_dir, exist_ok=True)

# 创建仿真
sim = gate.Simulation()
sim.g4_verbose = False
sim.visu = False
sim.number_of_threads = 1
sim.output_dir = output_dir

# ========== 世界 ==========
world = sim.world
world.size = [1 * m, 1 * m, 1 * m]
world.material = "G4_AIR"

# ========== Phantom (水模) ==========
phantom = sim.add_volume("Box", "phantom")
phantom.size = [10 * cm, 10 * cm, 10 * cm]
phantom.material = "G4_WATER"
phantom.color = [0, 1, 1, 0.5]  # 青色半透明

# ========== X 射线源 ==========
source = sim.add_source("GenericSource", "xray_source")
source.particle = "gamma"
source.energy.mono = 120 * keV
source.position.type = "point"
source.position.translation = [0, 0, -30 * cm]
source.direction.type = "momentum"
source.direction.momentum = [0, 0, 1]
source.n = 2000

# ========== 探测器 (记录投影) ==========
# 探测器放在 phantom 对侧
detector = sim.add_volume("Box", "detector")
detector.size = [30 * cm, 30 * cm, 0.5 * cm]
detector.translation = [0, 0, 25 * cm]
detector.material = "G4_AIR"

# ========== PhaseSpace Actor (记录穿过探测器的粒子) ==========
phase_space = sim.add_actor("PhaseSpaceActor", "phase_space")
phase_space.output_filename = "ct_projections.root"
phase_space.attributes = [
    "PostPosition",
    "KineticEnergy",
    "TrackID",
    "ParticleName"
]
phase_space.steps_to_store = "exiting"  # 只记录离开时的位置
phase_space.attached_to = "detector"

# ========== 统计 Actor ==========
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.output_filename = os.path.join(output_dir, "stats.txt")

# ========== 设置旋转角度 ==========
n_angles = 36  # 每10°采集一次
interval_length = 1 * second / 10  # 每个角度的持续时间
sim.run_timing_intervals = [
    (i * interval_length, (i + 1) * interval_length) for i in range(n_angles)
]

# 计算旋转参数 (绕 Y 轴旋转)
gantry_angles_deg = [i * (360 / n_angles) for i in range(n_angles)]

# 使用 helper 函数计算变换矩阵
# phantom 初始位置在原点，旋转时保持位置不变，只改变方向
# 实际上是源和探测器围绕 phantom 旋转

# 但更简单的方式是: 让 phantom 固定，旋转源和探测器
# 这里演示的是让 phantom 旋转 (相当于患者旋转)

# 如果要模拟源/探测器旋转，需要创建两个 rotation changer

# 计算旋转
rotations = []
for angle in gantry_angles_deg:
    rot = Rotation.from_euler('y', angle, degrees=True)
    rotations.append(rot.as_matrix())

# ========== 创建动态几何 Actor ==========
dyn_geo = sim.add_actor("DynamicGeometryActor", "gantry_rotation")

# 创建旋转 Changer
rotation_changer = gate.actors.dynamicactors.VolumeRotationChanger(name="phantom_rotator")
rotation_changer.attached_to = phantom  # 使用 volume 对象，不是字符串
rotation_changer.rotations = rotations

# 添加到动态几何 Actor
dyn_geo.geometry_changers.append(rotation_changer)

# ========== 运行 ==========
print(f"开始 CT 旋转扫描，共 {n_angles} 个角度...")
print(f"角度范围: 0° - {360 - 360/n_angles:.1f}°")
sim.run()
print("仿真完成！")

# ========== 输出信息 ==========
print(f"\n输出文件:")
print(f"  - ct_projections.root")
print(f"  - stats.txt")