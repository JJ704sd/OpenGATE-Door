import opengate as gate

sim = gate.Simulation()

sim.g4_verbose = False
sim.visu = False
sim.number_of_threads = 1

# 世界空间
world = sim.world
world.size = [1.0, 1.0, 1.0]  # m
world.material = "G4_AIR"

# 探测器：一个水盒子
detector = sim.add_volume("Box", "detector")
detector.size = [10, 10, 10]  # cm
detector.translation = [0, 0, 0]
detector.material = "G4_WATER"

# 粒子源
source = sim.add_source("GenericSource", "gamma_source")
source.particle = "gamma"
source.energy.mono = 511  # keV
source.position.type = "point"
source.position.translation = [0, 0, -30]  # cm
source.direction.type = "momentum"
source.direction.momentum = [0, 0, 1]
source.n = 1000

# 统计 actor
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.output_filename = "stats.txt"

sim.run()

print("仿真完成！结果已保存到 stats.txt")
