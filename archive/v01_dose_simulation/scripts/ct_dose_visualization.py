"""
CT 剂量分布 3D 可视化
- 读取 dose.mhd 文件
- 使用 PyVista 进行 3D 可视化
- 显示剂量热力图和等剂量面
"""

import pyvista as pv
import numpy as np
import os

# 输出目录
output_dir = "D:/OpenGATE/output"
dose_file = os.path.join(output_dir, "dose_edep.mhd")

# 读取 MHD 文件
print("读取剂量数据...")
reader = pv.get_reader(dose_file)
dose_grid = reader.read()

print(f"数据维度: {dose_grid.dimensions}")
print(f"数据范围: {dose_grid.bounds}")
print(f"最小值: {np.min(dose_grid['MetaImage']):.6e}")
print(f"最大值: {np.max(dose_grid['MetaImage']):.6e}")

# ========== 3D 体渲染 ==========
print("\n渲染剂量分布...")
plotter = pv.Plotter(off_screen=True, title="CT 剂量分布 3D 可视化", window_size=[1200, 800])

# 添加剂量体数据（半透明）
opacity = [0, 0.3, 0.6, 0.8, 1.0]

plotter.add_volume(
    dose_grid,
    scalars="MetaImage",
    opacity=opacity,
    cmap="jet",
    show_scalar_bar=True,
    scalar_bar_args={"title": "剂量 (MeV)", "vertical": True}
)

plotter.camera_position = 'iso'
plotter.camera.zoom(1.5)
plotter.add_axes()
plotter.add_title("CT 剂量分布 3D 可视化 (1000 光子, 120 keV)", font_size=14)

screenshot_path = os.path.join(output_dir, "dose_3d_view.png")
plotter.screenshot(screenshot_path, return_img=False)
print(f"3D 截图已保存: {screenshot_path}")
plotter.close()

# ========== 切片视图 ==========
print("\n创建切片视图...")
plotter2 = pv.Plotter(off_screen=True, title="CT 剂量切片视图", window_size=[1200, 800])

# 添加三个正交切片
plotter2.add_mesh_slice_orthogonal(dose_grid, scalars="MetaImage", cmap="jet")

plotter2.camera_position = 'iso'
plotter2.camera.zoom(1.5)
plotter2.add_axes()
plotter2.add_title("CT 剂量切片视图 (轴向/冠状/矢状)", font_size=14)

screenshot_path2 = os.path.join(output_dir, "dose_slices.png")
plotter2.screenshot(screenshot_path2, return_img=False)
print(f"切片截图已保存: {screenshot_path2}")
plotter2.close()

print("\n可视化完成！")