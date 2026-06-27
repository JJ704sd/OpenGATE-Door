import opengate as gate
from opengate.utility import g4_units

m = g4_units.m
cm = g4_units.cm
keV = g4_units.keV

sim = gate.Simulation()

sim.g4_verbose = False
sim.visu = True          # ✅ 开启可视化
sim.number_of_threads = 1

# 世界
world = sim.world
world.size = [1*m, 1*m, 1*m]
world.material = "G4_AIR"

# 探测器
detector = sim.add_volume("Box", "detector")
detector.size = [10*cm, 10*cm, 10*cm]
detector.translation = [0, 0, 0]
detector.material = "G4_WATER"

# 粒子源
source = sim.add_source("GenericSource", "gamma_source")
source.particle = "gamma"
source.energy.mono = 511*keV
source.position.type = "point"
source.position.translation = [0, 0, -30*cm]
source.direction.type = "momentum"
source.direction.momentum = [0, 0, 1]
source.n = 100

# 统计
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.output_filename = "stats.txt"

sim.run()

print("可视化仿真完成")