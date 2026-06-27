"""
CT 剂量计算仿真
- 锥形束 X 射线源
- 水模 Phantom
- DoseActor 计算剂量分布
- 旋转扫描
"""

import opengate as gate
from opengate.utility import g4_units
import os

# 单位
m = g4_units.m
cm = g4_units.cm
mm = g4_units.mm
keV = g4_units.keV

# 路径
output_dir = "D:/OpenGATE/output"
os.makedirs(output_dir, exist_ok=True)

# 创建仿真
sim = gate.Simulation()
sim.g4_verbose = False
sim.visu = False  # 关闭可视化
sim.number_of_threads = 1
sim.output_dir = output_dir

# ========== 世界 ==========
world = sim.world
world.size = [50 * cm, 50 * cm, 50 * cm]
world.material = "G4_AIR"

# ========== Phantom (水模) ==========
# 水模：20cm x 20cm x 20cm 的立方体水模
phantom = sim.add_volume("Box", "phantom")
phantom.size = [20 * cm, 20 * cm, 20 * cm]
phantom.translation = [0, 0, 0]
phantom.material = "G4_WATER"

# ========== X 射线源 (锥形束) ==========
source = sim.add_source("GenericSource", "xray_source")
source.particle = "gamma"
source.energy.mono = 120 * keV  # 120 keV X 射线

# 锥形束 - 从上方发射
source.position.type = "point"
source.position.translation = [0, 0, -30 * cm]  # 源位置

source.direction.type = "momentum"
source.direction.momentum = [0, 0, 1]  # 朝向 +z 方向

source.n = 1000  # 总粒子数

# ========== 探测器 ==========
# 平板探测器：40cm x 40cm，位于 phantom 下方
detector = sim.add_volume("Box", "detector")
detector.size = [40 * cm, 40 * cm, 0.5 * cm]
detector.translation = [0, 0, 20 * cm]
detector.material = "G4_AIR"

# ========== 剂量 Actor ==========
dose = sim.add_actor("DoseActor", "dose")
dose.output_filename = "dose.mhd"
dose.size = [100, 100, 50]  # 体素数量
dose.spacing = [2 * mm, 2 * mm, 2 * mm]
dose.translation = [0, 0, 0]

# ========== 统计 Actor ==========
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.output_filename = os.path.join(output_dir, "stats.txt")

# ========== 运行 ==========
print("开始 CT 剂量仿真...")
sim.run()
print("仿真完成！")
print(f"剂量结果: {sim.output_dir}/dose.mhd")
print(f"统计结果: {sim.output_dir}/stats.txt")