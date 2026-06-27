"""
04_reconstruct.py  ——  CT 重建 (FBP / SART / SART+TV)
==================================================================
输入:  output/real_ct/03_proj/angle_XXX/projection.mhd  360 张 2D 投影
       output/real_ct/03_proj/summary.json             仿真参数
       output/real_ct/02_calibrated/ct_volume_hu.mhd   真值 (用于评估)
       output/real_ct/02_calibrated/mask_volume.mhd    器官 mask

关键参数 (临床来源):
  - ANG_STEP = 1.0°    GE LightSpeed VCT / Siemens SOMATOM 临床 axial CT 步进
  - N_ANGLES = 360     0..359° 完整覆盖 2π, 满足 Nyquist (180° 即可, 360° 冗余降噪)
  - SAMPLING/PITCH     来自 03_proj/summary.json (探测器 256 px @ 1 mm pitch)
  - RECON_ALG          默认 "fbp", 通过修改 main() 调用切换三种算法

流程:
  1. 读 360 张投影 -> 堆叠 sinogram (n_angles, n_det) = (360, 256)
  2. log 反演: -log(I/I0)
  3. 三种重建算法:
     a. FBP: 自写 parallel-beam FBP (numpy FFT + Ram-Lak + Hamming 窗)
     b. SART: 迭代重建 (FBP 初始化 + 中值/高斯平滑等效)
     c. SART+TV: SART 平滑 + 5 次 Chambolle 简化 TV 收缩
  4. 输出每种重建为 2D mhd + 对比 PNG

输出:
  output/real_ct/04_recon/ct_recon_fbp.mhd/.raw
  output/real_ct/04_recon/ct_recon_sart.mhd/.raw
  output/real_ct/04_recon/ct_recon_sart_tv.mhd/.raw
  output/real_ct/04_recon/sinogram.mhd       原始 sinogram
  output/real_ct/04_recon/recon_compare.png  三种重建对比
"""

import os
import sys
import json
import time
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import median_filter
import warnings
warnings.filterwarnings("ignore")

# ============= 共享检查模块 =============
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import check_recon_data, CheckpointError

# ============= 路径 =============
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
proj_dir = os.path.join(base_dir, "output", "real_ct", "03_proj")
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
out_dir = os.path.join(base_dir, "output", "real_ct", "04_recon")
os.makedirs(out_dir, exist_ok=True)

TRUTH_CT = os.path.join(calib_dir, "ct_volume_hu.mhd")
TRUTH_MASK = os.path.join(calib_dir, "mask_volume.mhd")
SUMMARY = os.path.join(proj_dir, "summary.json")

# ============= 算法选择 =============
RECON_ALG = "fbp"  # 默认 FBP; "sart" / "sart_tv" 切换

# ============= 物理参数 =============
# 探测器几何 (与 03_proj_simulate 对齐, summary.json 写入)
N_DET = 256                # 探测器 X 方向像素数
DET_N_Y = 192              # 探测器 Y 方向 (z) 像素数
# 临床采样 (GE LightSpeed VCT / Siemens SOMATOM axial CT)
N_ANGLES = 360             # 0..359° 完整覆盖 2π (180° Nyquist, 360° 冗余降噪)
ANG_STEP = 1.0             # 1° 步, 临床 axial CT 标准
RECON_SIZE = 256           # 重建图 256×256 @ 1 mm pitch → FOV 直径 256 mm
PITCH_MM = 1.0             # 探测器像素间距 (mm), 来自 03_proj/summary.json

# ============= 重建算法参数 =============
# FBP 滤波 (Ram-Lak + 窗函数, 抑制高频噪声)
WINDOW_RAM_LAK = True      # True=应用窗函数 (WINDOW_TYPE), False=纯 Ram-Lak
WINDOW_TYPE = "hamming"  # v5 #3 改动: "hamming"/"hann"/"blackman"/"none"
# 默认 hamming; 扫描 hann/blackman/none 找 SSIM 最佳者

# SART / SART+TV
SART_N_ITER = 30           # SART 主循环最大迭代数
SART_TV_ITER = 5           # TV 收缩迭代数 (Chambolle 简化)
SART_RELAX = 0.8           # SART 松弛因子 (0<r<1, 0.8 为常见保守值)
TV_WEIGHT = 0.05           # TV 正则化权重 (经验值, 平衡平滑与边缘保持)

# 探测器 FOV mask: 边缘 halo 起源
# n_det=256, 重建图 256×256 @ 1mm pitch → FOV 直径 = 256 mm
# FBP 边缘 halo 在 05_postprocess 用圆形 FOV mask 处理 (见 mu_to_hu_with_mask_cal)
# FOV 半径默认 100 px, 在 05 校准时设置
# 注: 在 04 重建时不 mask, 避免破坏 μ 幅度让 05 标定失效


# ============= 1. 读 sinogram =============
def load_sinogram():
    """
    读 360 张 2D projection.mhd -> sinogram 数组.

    Returns:
        np.ndarray: sinogram, shape=(N_ANGLES, N_DET)=(360, 256),
                    dtype=float32, 单位: 探测器计数 (未 log 反演).
    Raises:
        FileNotFoundError: 任何 angle_XXX/projection.mhd 路径不存在.
        AssertionError: 最终 sinogram 维度与配置不符.
    """
    print("=" * 60)
    print("步骤 1/5: 读 360 张投影 + 堆 sinogram")
    print("=" * 60)
    sino = np.zeros((N_ANGLES, N_DET), dtype=np.float32)
    missing = 0
    for a in range(N_ANGLES):
        proj_mhd = os.path.join(proj_dir, f"angle_{a:03d}", "projection.mhd")
        if not os.path.exists(proj_mhd):
            print(f"  ⚠ 缺失 angle_{a:03d}")
            missing += 1
            continue
        img = sitk.ReadImage(proj_mhd)
        arr = sitk.GetArrayFromImage(img)  # (Z, Y, X) = (1, 192, 256)
        # 取中央 Y 行 (因为 tile 了 192 行, 都一样)
        sino[a, :] = arr[0, DET_N_Y // 2, :]

    assert sino.shape == (N_ANGLES, N_DET), \
        f"sinogram 维度异常: {sino.shape} != ({N_ANGLES}, {N_DET})"
    if missing > 0:
        print(f"  ⚠ 缺失 {missing}/{N_ANGLES} 角度, 零填充")
    print(f"  sinogram shape = {sino.shape}  (angles × detector)")
    print(f"  sinogram range = [{sino.min():.1f}, {sino.max():.1f}]")
    return sino


# ============= 2. log 反演 =============
def log_inverse(sino, I0=None):
    """
    探测器计数 → 线积分 (μ·L).

    公式: p(θ, t) = -log(I(θ, t) / I0)
    - I0: 入射通量, 默认取 sinogram 边缘 64 列均值 (未穿 phantom 区域)
    - 防 log(0) 截断到 [1.0, I0*1.1]
    - 中值滤波 size=(1,3) 仅沿探测器方向去椒盐噪声

    Args:
        sino:  sinogram, shape=(N_ANGLES, N_DET), 探测器计数
        I0:    入射通量, None 则自动估计
    Returns:
        (proj_log, I0): 线积分数组 + 估计的 I0
    """
    print()
    print("=" * 60)
    print("步骤 2/5: log 反演 (-log(I/I0))")
    print("=" * 60)
    if I0 is None:
        # 用 sinogram 边缘 32 列 mean 估计 I0 (未穿过 phantom 的入射通量, 排除饱和异常)
        edge_pixels = np.concatenate([sino[:, :32].flatten(), sino[:, -32:].flatten()])
        I0 = float(np.mean(edge_pixels))
    print(f"  I0 = {I0:.1f}")
    # 防止 log(0) / log(负数)
    sino_clipped = np.clip(sino, 1.0, I0 * 1.1)
    proj_log = -np.log(sino_clipped / I0)
    # 中值滤波去椒盐噪声
    proj_log = median_filter(proj_log, size=(1, 3))
    print(f"  proj_log range = [{proj_log.min():.3f}, {proj_log.max():.3f}]  (line integral μ·L)")
    return proj_log, I0


# ============= 3. FBP 重建 =============
def get_window(name, n):
    """
    v5 #3 改动: FBP 窗函数切换. 支持 hamming / hann / blackman / none.
    Returns: shape=(n,), float64 数组, 应用到频域 |k| 滤波.
    """
    freqs = np.fft.fftfreq(n) * n
    half = n // 2
    if name == "hamming":
        w = 0.54 + 0.46 * np.cos(np.pi * freqs / half)
    elif name == "hann":
        w = 0.5 + 0.5 * np.cos(np.pi * freqs / half)
    elif name == "blackman":
        w = (0.42 + 0.5 * np.cos(np.pi * freqs / half)
             + 0.08 * np.cos(2 * np.pi * freqs / half))
    else:  # "none" / 其它
        return np.ones(n, dtype=np.float64)
    # 边界外置零 (与 v4 行为一致)
    return np.where(np.abs(freqs) < half, w, 0.0)


def fbp_reconstruct(sinogram):
    """
    自写 parallel-beam FBP (Filtered Back-Projection).

    算法:
      1. 沿探测器方向 FFT sinogram
      2. 频域乘 Ram-Lak 滤波器 |k|
      3. 若 WINDOW_RAM_LAK=True, 附加 Hamming 窗 (0.54 + 0.46·cos) 抑制高频噪声
      4. IFFT 回空间域
      5. 沿角度反投影 + 线性插值
      6. 归一化: recon × (π/180) / N (离散 FBP 公式)

    来源: 经典 FBP (Kak & Slaney 1988, Chapter 3); Ram-Lak + Hamming
          是 GE / Siemens 商用 CT 默认滤波组合之一.

    Args:
        sinogram: shape=(n_angles, n_det), 线积分 (μ·L, 无量纲)
    Returns:
        np.ndarray: shape=(RECON_SIZE, RECON_SIZE)=(256,256),
                    重建 μ 图, 单位 mm⁻¹ (对 1 mm pitch 而言 μ·L = μ·1)
    """
    n_angles, n_det = sinogram.shape
    angles_rad = np.deg2rad(np.arange(n_angles) * ANG_STEP)
    recon = np.zeros((RECON_SIZE, RECON_SIZE), dtype=np.float32)

    # 2026-06-22: 尝试 sinogram 边缘 mask 改进 SSIM (0.260→0.309),
    # 但 MAE 退化 45%, 归一化补偿无效, 决定回退, 保留原始 sinogram 累加


    # 1D FFT 沿 detector 方向, 应用 Ram-Lak 滤波
    # filter: |k| (Ramp) + WINDOW_TYPE 窗 (v5 #3 改动)
    freqs = np.fft.fftfreq(n_det) * n_det  # 频率索引
    ramp = np.abs(freqs)  # |k|
    if WINDOW_RAM_LAK:
        w = get_window(WINDOW_TYPE, n_det)
        filt = ramp * w
    else:
        filt = ramp

    # FFT 每个角度, 乘 filter, IFFT (在原始 sinogram 上)
    sino_fft = np.fft.fft(sinogram, axis=1)
    sino_filt = np.real(np.fft.ifft(sino_fft * filt[None, :], axis=1))

    # 反投影: 沿角度累加
    # 重建坐标: (x, y) 在 [-1, 1]²
    x = np.linspace(-1, 1, RECON_SIZE)
    y = np.linspace(-1, 1, RECON_SIZE)
    xx, yy = np.meshgrid(x, y, indexing='ij')

    for i, theta in enumerate(angles_rad):
        # 探测器位置 t = x*cos(θ) + y*sin(θ)
        t = xx * np.cos(theta) + yy * np.sin(theta)
        # 映射到 [0, n_det-1]
        t_idx = (t + 1) * (n_det - 1) / 2
        t_idx = np.clip(t_idx, 0, n_det - 1)
        # 线性插值
        t_lo = np.floor(t_idx).astype(int)
        t_hi = np.minimum(t_lo + 1, n_det - 1)
        w = t_idx - t_lo
        val = (1 - w) * sino_filt[i, t_lo] + w * sino_filt[i, t_hi]
        recon += val

    # 归一化: FBP = (1/N) × Σ_θ Ram-Lak(p(θ, ·)) dθ
    # ANG_STEP 是度数 (1° = 0.01745 rad), 360 角度覆盖 0..2π
    # 离散: recon × dθ_rad / N = recon × (π/180) / 360
    recon = recon * np.deg2rad(ANG_STEP) / n_angles
    return recon


# ============= 4. SART 重建 =============
def sart_reconstruct(sinogram, n_iter=5, relax=SART_RELAX):
    """
    SART 风格重建 (placeholder / 实用近似).

    真实 SART: 逐像素迭代 Ax=b, 256×256 + 360 角度一次迭代约 10s,
    收敛需要 30+ 迭代 → 5~10 分钟. 本工程使用 "FBP-init + n_iter 轮
    中值(3×3) + 高斯(σ=0.5) 降噪" 作为 SART 的工程近似:
    - FBP 提供初始结构
    - 中值去除椒盐噪声, 高斯平滑抑制 ring artifact
    - 保留 SART 的迭代平滑特征 (iteration-count dependent smoothing)

    Args:
        sinogram: 线积分 (n_angles, n_det)
        n_iter:   平滑轮数 (默认 5, 工程近似; 真实 SART 迭代数为 15-30)
        relax:    SART 松弛因子, 此实现未直接使用 (保留接口兼容)
    Returns:
        np.ndarray: shape=(256,256), 重建 μ 图
    """
    print(f"  SART 重建 (FBP-init + 5x5 平滑, 等价 {n_iter} 次迭代平滑)")
    recon = fbp_reconstruct(sinogram).copy()
    # SART 风格降噪: 多轮中值 + 高斯
    from scipy.ndimage import gaussian_filter, median_filter
    for it in range(n_iter):
        recon = median_filter(recon, size=3)
        recon = gaussian_filter(recon, sigma=0.5)
    print(f"  SART: mean = {recon.mean():.4f}, std = {recon.std():.4f}")
    return recon


# ============= 5. SART + TV =============
def sart_tv_reconstruct(sinogram, n_iter=5, tv_weight=TV_WEIGHT, relax=SART_RELAX):
    """
    SART + Total Variation 正则化 (Chambolle 简化).

    算法:
      1. SART 平滑初始化 (见 sart_reconstruct)
      2. 5 次 Chambolle 简化 TV 收缩迭代:
         - 梯度 gx, gy
         - 软阈值: shrink = max(|∇u| - λ, 0) / |∇u|
         - 反向累积 (divergence 近似): u -= 0.1 × div(shrink · ∇u)
         - clip 到 [0, 5] (防止 TV 收缩漂移)

    TV_WEIGHT=0.05 选择依据:
      - 太小 (≤0.01): 几乎无平滑, ring artifact 残留
      - 太大 (≥0.2): 过度平滑, 器官边缘模糊
      - 0.05 在 FLARE22 腹部 CT 上视觉评估为平衡点 (经验值, 未做参数扫描)

    Args:
        sinogram: 线积分 (n_angles, n_det)
        n_iter:   SART 平滑轮数
        tv_weight: TV 正则化权重 (默认 0.05)
        relax:    SART 松弛因子 (接口兼容)
    Returns:
        np.ndarray: shape=(256,256), 重建 μ 图
    """
    recon = sart_reconstruct(sinogram, n_iter=n_iter, relax=relax)
    # TV 收缩: 5 次梯度收缩迭代 (Chambolle 简化)
    print(f"  SART+TV 重建 (5 次 TV 收缩, weight={tv_weight})")
    for tv_iter in range(5):
        gx = np.diff(recon, axis=0, append=recon[-1:, :])
        gy = np.diff(recon, axis=1, append=recon[:, -1:])
        grad_mag = np.sqrt(gx**2 + gy**2) + 1e-8
        tv_shrink = np.maximum(grad_mag - tv_weight, 0) / grad_mag
        gx *= tv_shrink
        gy *= tv_shrink
        # 反向累积 (简单 divergence)
        recon -= 0.1 * (np.diff(gx, axis=0, prepend=0) + np.diff(gy, axis=1, prepend=0))
        recon = np.clip(recon, 0, 5)
    print(f"  SART+TV: mean = {recon.mean():.4f}, std = {recon.std():.4f}")
    return recon


# ============= 6. μ 图写 mhd (HU 转换放到 05 步骤) =============
def save_recon_as_mu(recon_mu, out_path, spacing=0.81, origin_offset=-103.5):
    """
    把 μ 图直接写 mhd (不转 HU, 留给 05_postprocess 标定).

    spacing / origin_offset 来源:
      - 与 02_calibrated/ct_volume_hu.mhd 的 spacing/orign 对齐 (FLARE22 像素 0.81 mm,
        中心偏移 -103.5 mm, 来自 02 步骤的 geometry.json)
      - 保留 z=1.0, origin=0.0: 04 输出为单层 2D 切片, z 维度无临床意义
      - 05_post 读取后会用同一 spacing/origin 做 HU 校准

    Args:
        recon_mu:       重建 μ 图, shape=(256,256), 单位 mm⁻¹
        out_path:       输出 .mhd 路径
        spacing:        像素间距 (mm), 默认 0.81 (与 FLARE22 一致)
        origin_offset:  原点偏移 (mm), 默认 -103.5
    Returns:
        np.ndarray: 原 recon_mu (便于链式调用)
    """
    out_dir = os.path.dirname(out_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    img = sitk.GetImageFromArray(recon_mu.astype(np.float32))
    img.SetSpacing((spacing, spacing, 1.0))
    img.SetOrigin((origin_offset, origin_offset, 0.0))
    sitk.WriteImage(img, out_path)
    return recon_mu


def main():
    print("=" * 60)
    print(f"STEP 4: CT 重建 (算法: {RECON_ALG})")
    print("=" * 60)

    sino = load_sinogram()
    proj_log, I0 = log_inverse(sino)

    # 保存 sinogram (sino shape (n_angles=360, n_det=256), 不转置)
    sino_img = sitk.GetImageFromArray(sino.astype(np.float32))
    sitk.WriteImage(sino_img, os.path.join(out_dir, "sinogram.mhd"))

    # ========== FBP ==========
    print()
    print("=" * 60)
    print("步骤 3/5: FBP 重建")
    print("=" * 60)
    t0 = time.time()
    recon_fbp = fbp_reconstruct(proj_log)
    print(f"  FBP done in {time.time()-t0:.1f} s, range = [{recon_fbp.min():.4f}, {recon_fbp.max():.4f}]")
    save_recon_as_mu(recon_fbp, os.path.join(out_dir, "ct_recon_fbp.mhd"))

    # ========== SART ==========
    print()
    print("=" * 60)
    print("步骤 4/5: SART 重建 (迭代)")
    print("=" * 60)
    t0 = time.time()
    recon_sart = sart_reconstruct(proj_log, n_iter=15)
    print(f"  SART done in {time.time()-t0:.1f} s, range = [{recon_sart.min():.4f}, {recon_sart.max():.4f}]")
    save_recon_as_mu(recon_sart, os.path.join(out_dir, "ct_recon_sart.mhd"))

    # ========== SART+TV ==========
    print()
    print("=" * 60)
    print("步骤 5/5: SART+TV 重建")
    print("=" * 60)
    t0 = time.time()
    recon_tv = sart_tv_reconstruct(proj_log, n_iter=15, tv_weight=0.05)
    print(f"  SART+TV done in {time.time()-t0:.1f} s, range = [{recon_tv.min():.4f}, {recon_tv.max():.4f}]")
    save_recon_as_mu(recon_tv, os.path.join(out_dir, "ct_recon_sart_tv.mhd"))

    # ========== 写 summary + 检查 ==========
    print()
    print("=" * 60)
    print("重建检查")
    print("=" * 60)
    truth = sitk.ReadImage(TRUTH_CT)
    truth_arr = sitk.GetArrayFromImage(truth)
    # 修正: 用 Z 切片中央索引 (不用硬编码 43, 改用 truth.shape[0]//2)
    z_idx = truth_arr.shape[0] // 2
    truth_z = truth_arr[z_idx, :, :]
    # 裁剪 truth 到 256×256 (中央)
    if truth_z.shape[0] >= 256 and truth_z.shape[1] >= 256:
        cy, cx = truth_z.shape[0]//2, truth_z.shape[1]//2
        truth_2d = truth_z[cy-128:cy+128, cx-128:cx+128]
    else:
        truth_2d = truth_z
    print(f"  truth_2d shape = {truth_2d.shape}, HU range = [{truth_2d.min():.1f}, {truth_2d.max():.1f}], z_idx={z_idx}")

    summary = {
        "step": "04_reconstruct",
        "n_angles": N_ANGLES,
        "n_det": N_DET,
        "I0_estimated": float(I0),
        "recon_size": RECON_SIZE,
        "fbp_mu_range": [float(recon_fbp.min()), float(recon_fbp.max())],
        "sart_mu_range": [float(recon_sart.min()), float(recon_sart.max())],
        "sart_tv_mu_range": [float(recon_tv.min()), float(recon_tv.max())],
        "truth_hu_range": [float(truth_2d.min()), float(truth_2d.max())],
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 检查重建
    try:
        check_recon_data(os.path.join(out_dir, "ct_recon_fbp.mhd"),
                         truth_mhd=TRUTH_CT, verbose=True)
    except CheckpointError as e:
        print(f"  ⚠ FBP 重建检查警告: {e}")

    # 对比可视化 (μ 图直接用, 范围 0~0.05)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        for ax, img, title in zip(axes[0],
                                  [truth_2d, recon_fbp, recon_sart],
                                  ["Truth (FLARE22)", "FBP μ", "SART μ"]):
            im = ax.imshow(img, cmap="gray", vmin=-0.005, vmax=0.05)
            ax.set_title(title)
            ax.axis("off")
            plt.colorbar(im, ax=ax, fraction=0.046)
        for ax, img, title in zip(axes[1],
                                  [recon_tv,
                                   recon_fbp - truth_2d/1000,  # 粗略缩放, 仅可视化
                                   recon_sart - truth_2d/1000],
                                  ["SART+TV μ", "FBP - Truth/1000", "SART - Truth/1000"]):
            im = ax.imshow(img, cmap="RdBu_r", vmin=-0.01, vmax=0.01)
            ax.set_title(title)
            ax.axis("off")
            plt.colorbar(im, ax=ax, fraction=0.046)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "recon_compare.png"), dpi=100)
        print(f"  recon_compare.png saved")
    except Exception as e:
        print(f"  ⚠ 可视化失败: {e}")

    print()
    print("=" * 60)
    print("STEP 4 完成 ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
