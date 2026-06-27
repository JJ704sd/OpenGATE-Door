"""
CT 投影可视化
- 读取 ct_projections.root
- 可视化不同角度的投影
"""

import uproot
import pyvista as pv
import numpy as np

# 读取数据
with uproot.open('D:/OpenGATE/output/ct_projections.root') as f:
    tree = f['phase_space;1']
    data = tree.arrays(library='np')

print(f"总击中数: {len(data['PostPosition_X'])}")
print(f"TrackIDs: {np.unique(data['TrackID'])}")

# 创建可视化
plotter = pv.Plotter(off_screen=True, title="CT 投影数据", window_size=[1200, 800])

# 获取唯一 TrackID (区分不同粒子类型)
track_ids = np.unique(data['TrackID'])
colors = ['cyan', 'yellow']

for idx, track_id in enumerate(track_ids):
    mask = data['TrackID'] == track_id
    x = data['PostPosition_X'][mask]
    y = data['PostPosition_Y'][mask]
    z = data['PostPosition_Z'][mask]

    points = np.column_stack([x, y, z])
    plotter.add_points(points, color=colors[idx % len(colors)], point_size=5)

# 添加探测器位置 (Z ≈ 250 cm)
detector_bounds = [-15, 15, -15, 15, 24.75, 25.25]  # 30cm x 30cm detector
detector_mesh = pv.Box(bounds=detector_bounds)
plotter.add_mesh(detector_mesh, style="wireframe", color="red", opacity=0.5)

# 添加 phantom 位置 (原点，10cm cube)
phantom_bounds = [-5, 5, -5, 5, -5, 5]
phantom_mesh = pv.Box(bounds=phantom_bounds)
plotter.add_mesh(phantom_mesh, style="wireframe", color="green", opacity=0.3)

plotter.add_axes()
plotter.add_title("CT 投影数据 (36 角度扫描)")
plotter.camera_position = 'iso'
plotter.camera.zoom(0.8)

# 保存截图
plotter.screenshot("D:/OpenGATE/output/ct_projections.png", return_img=False)
print("截图已保存: D:/OpenGATE/output/ct_projections.png")

plotter.close()

# 打印投影统计
print("\n投影统计:")
print(f"  X 范围: {data['PostPosition_X'].min():.1f} ~ {data['PostPosition_X'].max():.1f} cm")
print(f"  Y 范围: {data['PostPosition_Y'].min():.1f} ~ {data['PostPosition_Y'].max():.1f} cm")
print(f"  Z 范围: {data['PostPosition_Z'].min():.1f} ~ {data['PostPosition_Z'].max():.1f} cm")
print(f"  能量范围: {data['KineticEnergy'].min():.1f} ~ {data['KineticEnergy'].max():.1f} keV")