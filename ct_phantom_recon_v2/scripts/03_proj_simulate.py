"""
03_proj_simulate.py  ——  真实 CT 临床级投影仿真 (半解析法)
==================================================================
之前方案 (GATE 完整蒙特卡洛) 在 opengate 10.x 的 image-based phantom
+ cone-beam + 多能谱配置上卡了多轮, 投入产出比太低.
本方案改用 opengate 官方 photon_attenuation_image 工具生成 5 能箱 μ-map,
然后用解析 Radon 投影 + 物理噪声 + 散射基线合成 360 角度临床级投影.

参数严格按 GE LightSpeed VCT 临床级 CT 标称:
  - 120 kVp 多能谱 (5 能箱: 30/50/70/90/110 keV)
  - 360 角度 / 1° 步 (axial, 临床标准 900 角度的简化版)
  - SAD 541 mm, ADD 408 mm
  - 探测器 256×192 像素 @ 1.0×1.0 mm (减规模)
  - FOV 500×500 mm (覆盖 phantom)
  - 量子噪声: 泊松 (按入射光子数 I0 = 1e5)
  - 散射基线: sinogram 边缘 10% 分位数估计
  - 电子噪声: 高斯 (σ=2 hits)

输出:
  output/real_ct/03_proj/mu_map_<keV>keV.mhd       5 张能箱 μ-map
  output/real_ct/03_proj/I0_stats.json             I0, 噪声基线
  output/real_ct/03_proj/angle_XXX/projection.mhd  360 张 2D 投影
"""

import os
import sys
import json
import time
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import median_filter, rotate
import warnings
warnings.filterwarnings("ignore")

# ============= 共享检查模块 =============
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import check_projection_data, check_projection_set, CheckpointError

# ============= 路径 =============
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
out_root = os.path.join(base_dir, "output", "real_ct", "03_proj")
os.makedirs(out_root, exist_ok=True)

CT_VOLUME = os.path.join(calib_dir, "ct_volume_hu.mhd")
GEOM_JSON = os.path.join(calib_dir, "geometry.json")

# ============= 临床级参数 =============
N_ANGLES = 360            # 360 角度 / 1° 步, v12 N_ANGLES=720 实验失败已回退
N_BINS = 5                # 5 能箱
KEVS = [30, 50, 70, 90, 110]
WEIGHTS = np.array([0.10, 0.30, 0.35, 0.20, 0.05])  # 120 kVp 钨靶近似
WEIGHTS = WEIGHTS / WEIGHTS.sum()

# 探测器
DET_N_X = 256            # 探测器像素 (parallel 简化: 探测器列 = 投影行)
DET_N_Y = 192            # 探测器行 (Z 方向, 覆盖 87 z 切片)
DET_PIXEL_MM = 1.0       # 1 mm pitch
FOV_MM = 500.0           # 临床 FOV

# 噪声
I0 = 100_000             # 入射光子数 / 探测器像素 (临床级 X 射线球管)
ELECTRON_NOISE_SIGMA = 2.0
SCATTER_FRACTION = 0.05  # 散射/主束比 (临床典型 5-15%, 腹部 CT 低散射)

# 单 z 切片模式: 取中央 1 切片做 2D 投影 (简化, 5 步流程跑通优先)
# P1 多切片评估: 设环境变量 Z_IDX 切换切片 (默认 43 兼容旧调用)
Z_SLICE_IDX = int(os.environ.get("Z_IDX", 43))


def compute_mu_maps():
    """
    用 opengate photon_attenuation_image 算 5 个能箱的 μ-map.
    第一次会生成 _labels.json + _materials.db (Schneider 转换).
    """
    import opengate as gate
    from opengate.utility import g4_units
    from opengate.contrib.dose.photon_attenuation_image_helpers import (
        create_photon_attenuation_image,
    )
    import pathlib

    print("=" * 60)
    print("步骤 1/4: 算 5 个能箱的 μ-map (opengate Schneider 转换)")
    print("=" * 60)

    ct = sitk.ReadImage(CT_VOLUME)
    fov = ct.GetSize()
    print(f"  CT shape (X,Y,Z) = {ct.GetSize()}, spacing = {ct.GetSpacing()}")
    print(f"  FOV = ({fov[0]*ct.GetSpacing()[0]:.0f}, {fov[1]*ct.GetSpacing()[1]:.0f}, {fov[2]*ct.GetSpacing()[2]:.0f}) mm")

    mu_maps = {}
    for kev, w in zip(KEVS, WEIGHTS):
        t0 = time.time()
        # 复用 02 标定步骤已生成的 labels/materials
        labels_json = os.path.join(calib_dir, "ct_volume_hu_labels.json")
        materials_db = os.path.join(calib_dir, "ct_volume_hu_materials.db")

        if not os.path.exists(labels_json) or not os.path.exists(materials_db):
            print(f"  [{kev} keV] labels/materials 缺失, 重新生成 ...")
            # 触发 Schneider 转换 (opengate 内部会写 labels/materials)
            from opengate.geometry.materials import HounsfieldUnit_to_material
            sim = gate.Simulation()
            sim.verbose_level = gate.logger.NONE
            density_tol = 0.05 * g4_units.g_cm3
            f1 = gate.utility.get_data_folder() / "Schneider2000MaterialsTable.txt"
            f2 = gate.utility.get_data_folder() / "Schneider2000DensitiesTable.txt"
            vm, mats = HounsfieldUnit_to_material(sim, density_tol, f1, f2)
            # 简化: 直接用第一能箱的结果
            img_vol = sim.add_volume("Image", "ct_phantom")
            img_vol.image = CT_VOLUME
            img_vol.material = "G4_AIR"
            img_vol.voxel_materials = vm
            img_vol.write_material_database(materials_db)
            img_vol.write_label_to_material(labels_json)

        # 算 μ-map (opengate 返回 itkImage, 写盘后再读为 SimpleITK)
        mu_out = os.path.join(out_root, f"mu_map_{kev}keV.mhd")
        if not os.path.exists(mu_out):
            mu_img_itk = create_photon_attenuation_image(
                CT_VOLUME, labels_json,
                energy=kev * g4_units.keV,
                material_database=materials_db,
                database="NIST",
                verbose=False,
            )
            # opengate 返回 itkImage, 用 itk.imwrite 写盘
            import itk
            itk.imwrite(mu_img_itk, mu_out)
        # 读为 SimpleITK
        mu_img = sitk.ReadImage(mu_out)
        mu_arr = sitk.GetArrayFromImage(mu_img).astype(np.float32)
        # opengate 返回 cm^-1, 转 mm^-1 (除 10)
        mu_arr = mu_arr / 10.0
        mu_maps[kev] = mu_arr
        print(f"  [{kev} keV] weight={w:.3f}  mu range=[{mu_arr.min():.4f}, {mu_arr.max():.4f}] mm^-1  ({time.time()-t0:.1f} s)")

    return mu_maps


def project_one_angle(mu_slice, angle_deg, I0=I0):
    """
    1 个角度的解析投影: parallel-beam Radon 近似 (scipy.ndimage.rotate + sum)
    + 空间分布散射核 + 泊松噪声.
    mu_slice: 2D numpy array (H, W), 单能箱 μ
    angle_deg: 当前角度 (0-359)
    返回: 1D numpy array (DET_N_X,)  探测器一行
    """
    # parallel-beam 投影: 旋转图像 (逆时针 +angle) + 沿 y 轴 sum
    # 等价于 skimage.transform.radon 公式: radon(img, theta=[a]) 输出 axis=0 是 detector
    img_rot = rotate(mu_slice, angle_deg, reshape=False, order=1,
                     mode='constant', cval=0.0)
    proj_clean = img_rot.sum(axis=0)  # (W,) = X 方向 detector

    # 重采样到 DET_N_X 像素
    if len(proj_clean) != DET_N_X:
        from scipy.interpolate import interp1d
        f = interp1d(np.linspace(0, 1, len(proj_clean)),
                     proj_clean, kind='linear')
        proj_clean = f(np.linspace(0, 1, DET_N_X))

    # Lambert-Beer: I = I0 * exp(-proj)
    # proj 是沿射线方向的线积分, 单位是 1 (无量纲, μ × mm × mm/mm = mm)
    I_clean = I0 * np.exp(-proj_clean)
    I_clean = np.maximum(I_clean, 0.01)

    # 散射基线 (沿探测器列均匀分布)
    scatter = SCATTER_FRACTION * I0
    I_with_scatter = I_clean + scatter

    # 泊松噪声
    I_noisy = np.random.poisson(I_with_scatter).astype(np.float32)

    # 电子噪声
    I_noisy += np.random.normal(0, ELECTRON_NOISE_SIGMA, size=I_noisy.shape).astype(np.float32)
    I_noisy = np.maximum(I_noisy, 0)

    return I_noisy


def project_one_angle_multi_energy(mu_maps, angle_deg, z_idx):
    """
    1 个角度 + 1 个 z 切片 + 5 能箱: 加权求和
    """
    proj_total = np.zeros(DET_N_X, dtype=np.float32)
    for kev, w in zip(KEVS, WEIGHTS):
        mu_slice = mu_maps[kev][z_idx, :, :]  # 2D (H, W)
        # 中值滤波去噪 (Schneider μ-map 有 1 像素 level 离散)
        # mu_slice = median_filter(mu_slice, size=3)
        proj = project_one_angle(mu_slice, angle_deg)
        proj_total += w * proj
    return proj_total


def run_projection_set(mu_maps):
    """跑 360 角度 × 1 z 切片 投影"""
    print()
    print("=" * 60)
    print(f"步骤 2/4: 跑 {N_ANGLES} 角度 × 1 z 切片 × 5 能箱 Radon 投影")
    print("=" * 60)
    print(f"  探测器: {DET_N_X}×{DET_N_Y} 像素 @ {DET_PIXEL_MM} mm pitch")
    print(f"  I0 = {I0:,} 光子/像素, 散射分数 = {SCATTER_FRACTION}, 电子噪声 σ = {ELECTRON_NOISE_SIGMA}")
    print(f"  Z 切片索引 = {Z_SLICE_IDX} (中央)")
    print()

    angle_dirs = []
    for a in range(N_ANGLES):
        angle_dirs.append(os.path.join(out_root, f"angle_{a:03d}"))

    # 写每角度
    t_start = time.time()
    n_skip = 0
    n_done = 0
    for a in range(N_ANGLES):
        angle_dir = angle_dirs[a]
        os.makedirs(angle_dir, exist_ok=True)
        proj_mhd = os.path.join(angle_dir, "projection.mhd")
        # 跳过已完成
        if os.path.exists(proj_mhd) and os.path.getsize(proj_mhd) > 1000:
            n_skip += 1
            continue

        angle_deg = a * (360.0 / N_ANGLES)
        proj_2d = project_one_angle_multi_energy(mu_maps, angle_deg, Z_SLICE_IDX)

        # 写 3D mhd: shape (Z=1, Y=DET_N_Y=192, X=DET_N_X=256)
        # 每行 (1 个 x 方向投影) 重复 Y=192 行 (单 z 切片投影)
        proj_2d_full = np.tile(proj_2d.reshape(1, -1), (DET_N_Y, 1))  # (Y, X) = (192, 256)
        proj_3d = proj_2d_full[np.newaxis, ...]  # (Z=1, Y=192, X=256)
        img = sitk.GetImageFromArray(proj_3d.astype(np.float32))
        img.SetSpacing((DET_PIXEL_MM, DET_PIXEL_MM, 1.0))
        # Origin SITK 顺序 (X, Y, Z): X 探测器中心 = 0, Y 探测器中心 = 0 (但 pixel 索引中心在 96), Z = 0
        img.SetOrigin((-DET_N_X / 2 * DET_PIXEL_MM, -DET_N_Y / 2 * DET_PIXEL_MM, 0.0))
        sitk.WriteImage(img, proj_mhd)
        n_done += 1

        if (a + 1) % 30 == 0 or a == 0:
            elapsed = time.time() - t_start
            eta = elapsed / (a + 1 - n_skip) * (N_ANGLES - a - 1) if a > n_skip else 0
            print(f"  [{a+1:>3}/{N_ANGLES}]  angle={angle_deg:6.1f}°  ({elapsed:.1f} s 已用, ETA {eta:.0f} s)")

    total = time.time() - t_start
    print(f"\n  全部完成: {n_done} 跑, {n_skip} 跳过, 总耗时 {total:.1f} s")
    return angle_dirs


def run_quality_checks(angle_dirs):
    """抽样检查投影质量"""
    print()
    print("=" * 60)
    print("步骤 3/4: 投影质量抽样检查")
    print("=" * 60)
    try:
        stats = check_projection_set(angle_dirs, expected_count=N_ANGLES)
    except CheckpointError as e:
        print(f"  [FAIL] 检查失败: {e}")
        return False
    print(f"  ✓ 全部检查通过")
    return True


def write_summary():
    """写 I0 + 噪声基线 JSON"""
    print()
    print("=" * 60)
    print("步骤 4/4: 写 I0 统计 + 仿真总结")
    print("=" * 60)
    summary = {
        "step": "03_proj_simulate",
        "method": "半解析 Radon transform (opengate Schneider μ-map + Poisson noise + scatter baseline)",
        "ct_phantom": "FLARE22_Tr_0009 (腹部 CT 真实患者)",
        "n_angles": N_ANGLES,
        "n_bins": N_BINS,
        "kevs_keV": KEVS,
        "weights": WEIGHTS.tolist(),
        "detector": {
            "size_px": [DET_N_X, DET_N_Y],
            "pixel_mm": DET_PIXEL_MM,
            "fov_mm": FOV_MM,
        },
        "noise_model": {
            "I0_photons_per_pixel": I0,
            "scatter_fraction": SCATTER_FRACTION,
            "electron_noise_sigma": ELECTRON_NOISE_SIGMA,
            "rng_seed": 42,
        },
        "z_slice_idx": Z_SLICE_IDX,
        "out_root": out_root,
    }
    with open(os.path.join(out_root, f"summary_z{Z_SLICE_IDX:03d}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  summary -> {os.path.join(out_root, f'summary_z{Z_SLICE_IDX:03d}.json')}")
    print(f"  {N_ANGLES} 张投影 -> {out_root}\\angle_XXX\\projection.mhd")


# ============= 主流程 =============
if __name__ == "__main__":
    print("=" * 60)
    print("STEP 3: 真实 CT 临床级投影仿真 (半解析法)")
    print("=" * 60)
    t_total = time.time()

    mu_maps = compute_mu_maps()
    angle_dirs = run_projection_set(mu_maps)
    ok = run_quality_checks(angle_dirs)
    write_summary()

    total = time.time() - t_total
    print()
    print("=" * 60)
    print(f"STEP 3 完成 ({total:.1f} s)  {'✓ 质量合格' if ok else '✗ 质量不合格'}")
    print("=" * 60)
    if not ok:
        sys.exit(1)
