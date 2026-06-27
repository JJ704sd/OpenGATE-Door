"""
CT 粒子轨迹可视化
- 使用 PhaseSpaceActor 记录粒子击中信息
- 使用 PyVista 可视化粒子轨迹
"""

import opengate as gate
from opengate.utility import g4_units
import pyvista as pv
import numpy as np
import os

# 单位
cm = g4_units.cm
mm = g4_units.mm
keV = g4_units.keV

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
world.size = [50 * cm, 50 * cm, 50 * cm]
world.material = "G4_AIR"

# ========== Phantom (水模) ==========
phantom = sim.add_volume("Box", "phantom")
phantom.size = [10 * cm, 10 * cm, 10 * cm]  # 缩小一点加快仿真
phantom.translation = [0, 0, 0]
phantom.material = "G4_WATER"

# ========== X 射线源 ==========
source = sim.add_source("GenericSource", "xray_source")
source.particle = "gamma"
source.energy.mono = 120 * keV
source.position.type = "point"
source.position.translation = [0, 0, -20 * cm]
source.direction.type = "momentum"
source.direction.momentum = [0, 0, 1]
source.n = 500  # 减少粒子数便于可视化

# ========== PhaseSpace Actor (记录粒子轨迹) ==========
phase_space = sim.add_actor("PhaseSpaceActor", "phase_space")
phase_space.output_filename = "particle_tracks.root"
phase_space.attributes = [
    "PostPosition",
    "PrePosition",
    "TotalEnergyDeposit",
    "TrackCreatorProcess",
    "ParticleName",
    "TrackID",
    "ParentID",
    "TrackLength",
    "KineticEnergy",
    "StepLength"
]
phase_space.steps_to_store = "all"

# ========== 统计 Actor ==========
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.output_filename = os.path.join(output_dir, "stats.txt")

# ========== 运行 ==========
print("开始粒子轨迹仿真...")
sim.run()
print("仿真完成！")

# ========== 可视化 ==========
print("\n可视化粒子轨迹...")

root_file = os.path.join(output_dir, "particle_tracks.root")
print(f"PhaseSpace 输出: {root_file}")

# 使用 uproot 读取 ROOT 文件
try:
    import uproot

    with uproot.open(root_file) as f:
        tree = f["phase_space;1"]
        print(f"粒子数量: {tree.num_entries}")

        # 读取所有数据
        data = tree.arrays(["PostPosition_X", "PostPosition_Y", "PostPosition_Z",
                            "TrackID", "ParticleName", "KineticEnergy"], library="np")

        post_x = data["PostPosition_X"]
        post_y = data["PostPosition_Y"]
        post_z = data["PostPosition_Z"]

        print(f"读取完成，数据点数量: {len(post_x)}")

        # 创建可视化
        plotter = pv.Plotter(off_screen=True, title="CT 粒子轨迹", window_size=[1200, 800])

        # 获取唯一的 TrackID
        track_ids = np.unique(data["TrackID"])
        print(f"轨迹数量: {len(track_ids)}")

        # 限制显示的轨迹数量
        max_tracks = 30
        colors = ["green", "cyan", "yellow", "orange", "blue"]

        for idx, track_id in enumerate(track_ids[:max_tracks]):
            mask = data["TrackID"] == track_id
            track_x = post_x[mask]
            track_y = post_y[mask]
            track_z = post_z[mask]

            if len(track_x) > 1:
                points = np.column_stack([track_x, track_y, track_z])

                # 创建线段: 连接相邻点
                lines = []
                for i in range(len(points) - 1):
                    lines.append([points[i], points[i+1]])

                for line in lines:
                    plotter.add_lines(np.array(line), color=colors[idx % len(colors)])

        # 添加水模轮廓 (线框)
        phantom_mesh = pv.Box(bounds=(-5, 5, -5, 5, -5, 5))
        plotter.add_mesh(phantom_mesh, style="wireframe", color="white", opacity=0.5)

        plotter.add_axes()
        plotter.add_title(f"CT 粒子轨迹 (显示 {max_tracks} 条轨迹, 500 光子)")
        plotter.camera_position = 'iso'
        plotter.camera.zoom(1.5)

        screenshot_path = os.path.join(output_dir, "particle_tracks.png")
        plotter.screenshot(screenshot_path, return_img=False)
        print(f"轨迹截图已保存: {screenshot_path}")
        plotter.close()

except Exception as e:
    print(f"可视化出错: {e}")
    import traceback
    traceback.print_exc()

print("\n可视化完成！")