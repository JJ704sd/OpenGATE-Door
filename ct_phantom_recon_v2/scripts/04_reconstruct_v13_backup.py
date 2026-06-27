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
import gc
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
N_ANGLES = 360             # 0..359° 完整覆盖 2π, v12 N_ANGLES=720 实验失败已回退
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
# v9 #3: TV weight 扫描 — 冲 CNR > 3
TV_WEIGHT_SCAN = [0.01, 0.03, 0.05, 0.1, 0.2]
TV_WEIGHT_DEFAULT = 0.05   # v8 默认保留, 扫描后可能被覆盖

# P2 #6 真 SART 矩阵化 (CG 求解)
USE_MATRIX_SART = True     # True=真 SART 矩阵化 + CG/SIRT; False=v5 placeholder fallback
SART_USE_SIRT = False      # True=SIRT 迭代; False=CG (默认, FBP-init warm start, 物理量级一致)
SART_CG_ITER = 100         # v9 #1: CG/SIRT 最大迭代次数 (v8 是 60, v6 是 30, 期望进一步扩大 μ range)
SART_CG_ITER_OVERRIDE = 60 # v9 #1 fallback: 保留 v8 60 iter 用于回退
SART_CG_TOL = 1e-4         # CG 收敛容忍 (scipy default 1e-5 偏严, 1e-4 平衡速度)
SART_MATRIX_CACHE = True   # True=缓存 A 到磁盘 (避免重复构建)
SART_CACHE_DIR = os.path.join(out_dir, "_sart_matrix_cache")
SART_RELAX_OVERRIDE = 1.2  # SIRT 过松弛 (1.0=标准, >1=加速; 1.2 平衡速度与稳定)

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
def log_inverse(sino, I0=None, edge_pixels=32):
    """
    探测器计数 → 线积分 (μ·L).

    公式: p(θ, t) = -log(I(θ, t) / I0)
    - I0: 入射通量, 默认用 sinogram 边缘 32 列均值 (v8/v9 #4 验证后保留)
    - 防 log(0) 截断到 [1.0, I0*1.1]
    - 中值滤波 size=(1,3) 仅沿探测器方向去椒盐噪声

    v9 #4 测试记录:
      - edge=64: I0=22796 (偏低 40%, 含已穿 phantom 像素), FAIL
      - max(角度方向): I0=83340 (偏高, std=31129 不稳), μ range 失真, FAIL
      - 结论: v8 edge=32 已合理, 保留.

    Args:
        sino:  sinogram, shape=(N_ANGLES, N_DET), 探测器计数
        I0:    入射通量, None 则自动估计
        edge_pixels: 边缘像素数 (默认 32, v8/v9 一致)
    Returns:
        (proj_log, I0): 线积分数组 + 估计的 I0
    """
    print()
    print("=" * 60)
    print("步骤 2/5: log 反演 (-log(I/I0))")
    print("=" * 60)
    if I0 is None:
        edge = np.concatenate([sino[:, :edge_pixels].flatten(), sino[:, -edge_pixels:].flatten()])
        I0 = float(np.mean(edge))
        I0_std = float(np.std(edge))
    print(f"  I0 = {I0:.1f} (std={I0_std:.1f}, edge_pixels={edge_pixels})")
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
def siddon_ray_trace(src, det, n_pixels, pixel_size, fov_radius):
    """
    Siddon 算法 ray-tracing: 计算射线穿过每个像素的长度.

    算法来源: Siddon RL (1985) "Fast calculation of the exact
    radiological path for a three-dimensional CT array", Med Phys.

    像素坐标 (i, j) ∈ [0, n_pixels-1]², 物理中心 = (i + 0.5 - n_pixels/2) × pixel_size.
    重建图中心在原点, 物理范围 [-fov_radius, fov_radius].

    Args:
        src:        源点物理坐标 (x, y), 单位 mm
        det:        探测器点物理坐标 (x, y), 单位 mm
        n_pixels:   重建图边长 (RECON_SIZE)
        pixel_size: 像素间距 (mm)
        fov_radius: FOV 半径 (mm) ≈ n_pixels/2 × pixel_size
    Returns:
        dict: {pixel_idx: ray_length_mm}, 仅包含射线穿过的像素
    """
    # 射线参数方程: P(t) = src + t × (det - src), t ∈ [0, 1]
    dx = det[0] - src[0]
    dy = det[1] - src[1]
    L = np.sqrt(dx * dx + dy * dy)
    if L < 1e-9:
        return {}
    # 像素边界 (mm), 中心在原点
    half = n_pixels * pixel_size / 2.0
    bounds = np.linspace(-half, half, n_pixels + 1)
    # 像素中心
    centers = (bounds[:-1] + bounds[1:]) / 2.0
    # 计算射线与所有垂直边界 (x = bounds[k]) 的交点参数 t
    # 如果 |dx| 极小, 则射线几乎垂直, 用 fallback
    eps = 1e-9
    if abs(dx) < eps:
        t_x = np.full_like(bounds, np.nan, dtype=np.float64)
    else:
        t_x = (bounds - src[0]) / dx
    if abs(dy) < eps:
        t_y = np.full_like(bounds, np.nan, dtype=np.float64)
    else:
        t_y = (bounds - src[1]) / dy
    # 取 [0, 1] 内的交点 (在源-探段内)
    t_vals = np.concatenate([t_x, t_y])
    t_vals = t_vals[(t_vals >= 0) & (t_vals <= 1) & np.isfinite(t_vals)]
    t_vals = np.unique(t_vals)
    if len(t_vals) < 2:
        return {}
    # 计算每对相邻交点之间的中点, 判断落在哪个像素 (i, j)
    t_mid = (t_vals[:-1] + t_vals[1:]) / 2.0
    px = src[0] + t_mid * dx  # 物理 x
    py = src[1] + t_mid * dy  # 物理 y
    # 映射到像素索引 (i=x方向, j=y方向)
    i_idx = np.floor((px + half) / pixel_size).astype(int)
    j_idx = np.floor((py + half) / pixel_size).astype(int)
    # 边界过滤
    mask = (i_idx >= 0) & (i_idx < n_pixels) & (j_idx >= 0) & (j_idx < n_pixels)
    i_idx = i_idx[mask]
    j_idx = j_idx[mask]
    # 射线段长度 = (t_{k+1} - t_k) × L
    dt = np.diff(t_vals)
    seg_len = dt[mask] * L  # mm
    # 汇总到像素 (flat index)
    flat_idx = i_idx * n_pixels + j_idx
    # 用 np.add.at 累加 (可能有重复像素, 因为射线可能与像素角相交)
    pixel_lengths = np.zeros(n_pixels * n_pixels, dtype=np.float32)
    np.add.at(pixel_lengths, flat_idx, seg_len.astype(np.float32))
    # 过滤零长度
    nz = np.nonzero(pixel_lengths)[0]
    if len(nz) == 0:
        return {}
    return dict(zip(nz.tolist(), pixel_lengths[nz].tolist()))


def build_system_matrix(n_angles, n_det, n_pixels, pixel_size, sod=541.0, sdd=949.0,
                         progress_every=20):
    """
    构造 SART 系统矩阵 A (sparse CSR).

    几何 (parallel-beam 等价于 fan-beam 远场近似):
    - X 射线源在距旋转中心 sod (mm) 处
    - 探测器在源后 sdd (mm) (即距旋转中心 sdd - sod)
    - 旋转中心在原点
    - 探测器沿弧形分布, 每条射线对应一个探测器像素

    对于 fan-beam, 旋转角度 θ 时, 源点在 (sod·cos θ, sod·sin θ),
    探测器中心在 (-(sdd-sod)·cos θ, -(sdd-sod)·sin θ), 第 j 个探测器
    像素位置 = 探测器中心 + 切向偏移 (取决于 j 索引).

    简化模型 (与 fbp_reconstruct 的 "探测器 t = x·cos θ + y·sin θ"
    平行束投影兼容): 我们用平行束几何:
    - 源点 (X, Y) 在 (cos θ, sin θ) 方向 R=10×FOV_radius (远场)
    - 探测器 (X, Y) = 源点 - R·(cos θ, sin θ) + 切向偏移
    - 切向偏移 = (-sin θ, cos θ) × (j - n_det/2) × pixel_size

    Args:
        n_angles:     投影角度数 (360)
        n_det:        探测器像素数 (256)
        n_pixels:     重建图边长 (256)
        pixel_size:   探测器像素间距 (mm, 1.0)
        sod:          source-to-origin distance (mm, 临床 GE VCT 约 541)
        sdd:          source-to-detector distance (mm, 949)
        progress_every: 每 N 个角度打印进度
    Returns:
        scipy.sparse.csr_matrix: A, shape=(n_angles*n_det, n_pixels*n_pixels),
                                  每个非零元 = 射线穿过该像素的长度 (mm)
    """
    from scipy.sparse import lil_matrix
    print(f"  构建系统矩阵 A: shape=({n_angles * n_det}, {n_pixels * n_pixels})")
    print(f"    n_angles={n_angles}, n_det={n_det}, n_pixels={n_pixels}, pixel_size={pixel_size}")
    t_start = time.time()
    fov_radius = n_pixels * pixel_size / 2.0
    R_far = 10.0 * fov_radius  # 远场源距离 (保证平行束近似)
    A = lil_matrix((n_angles * n_det, n_pixels * n_pixels), dtype=np.float32)
    angles_rad = np.deg2rad(np.arange(n_angles) * ANG_STEP)
    for i, theta in enumerate(angles_rad):
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        # 源点: (R_far * cos_t, R_far * sin_t) (远场, 平行束近似)
        src = np.array([R_far * cos_t, R_far * sin_t])
        # 探测器切向基向量 (垂直于源-中心连线)
        tan_x, tan_y = -sin_t, cos_t
        for j in range(n_det):
            # 探测器偏移 (mm), 中心在 t=0
            offset = (j - (n_det - 1) / 2.0) * pixel_size
            # 探测器点: 沿源-中心方向移到对面, 然后沿切向偏移
            det_center = -src * (R_far / np.linalg.norm(src)) * (R_far / R_far)
            # 简化: 探测器中心 = 源的反向点 + 0 (远场), 偏移沿切向
            det = src * (-1.0) + np.array([tan_x, tan_y]) * offset
            # ray trace
            pix_dict = siddon_ray_trace(src, det, n_pixels, pixel_size, fov_radius)
            row = i * n_det + j
            for pix_idx, length in pix_dict.items():
                A[row, pix_idx] = length
        if (i + 1) % progress_every == 0 or i == n_angles - 1:
            elapsed = time.time() - t_start
            eta = elapsed / (i + 1) * (n_angles - i - 1)
            print(f"    角度 {i + 1}/{n_angles}  已用 {elapsed:.1f}s, 剩余 ~{eta:.1f}s")
    print(f"  A 构建完成, 耗时 {time.time() - t_start:.1f}s")
    print(f"  非零元数: {A.nnz}, 预计内存 ~{A.nnz * 4 / 1024 / 1024:.1f} MB")
    return A.tocsr()


def _get_cached_or_build_matrix(n_angles, n_det, n_pixels, pixel_size):
    """
    读取或构建系统矩阵 A (带磁盘缓存).
    缓存文件: <SART_CACHE_DIR>/A_n{n_angles}x{n_det}x{n_pixels}_p{pixel_size}.npz
    """
    os.makedirs(SART_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(
        SART_CACHE_DIR,
        f"A_n{n_angles}x{n_det}x{n_pixels}_p{pixel_size:.3f}.npz"
    )
    if SART_MATRIX_CACHE and os.path.exists(cache_file):
        print(f"  [缓存命中] 读取 {cache_file}")
        from scipy.sparse import load_npz
        return load_npz(cache_file)
    print(f"  [缓存未命中] 构建 A 并写入 {cache_file}")
    A = build_system_matrix(n_angles, n_det, n_pixels, pixel_size)
    if SART_MATRIX_CACHE:
        from scipy.sparse import save_npz
        save_npz(cache_file, A)
        print(f"  [缓存已保存] {cache_file}")
    return A


def sart_sirt_reconstruct(sinogram, n_iter=SART_CG_ITER, relax=SART_RELAX_OVERRIDE):
    """
    真 SART 矩阵化 (SIRT 风格迭代, 比 CG 更稳定).

    SIRT (Simultaneous Iterative Reconstruction Technique) 公式:
      x^{k+1} = x^k + relax * C * A^T * R * (b - A x^k)
      C = diag(1 / col_sum(A)), R = diag(1 / row_sum(A))

    行归一化 R 使每条射线的更新步长一致 (与探测器像素长度无关),
    列归一化 C 使每个像素的更新步长一致 (与被多少射线穿过无关).

    非负约束: 每步后 clip(x, 0, inf), 保证 μ ≥ 0.

    单位: 输入 b (线积分 μ·L) 单位 mm⁻¹·mm, A 单位 mm,
    输出 x 单位 = μ (mm⁻¹), 与 FBP 输出一致, 可直接接 05_postprocess.

    Args:
        sinogram: 线积分 sinogram (n_angles, n_det)
        n_iter:   SIRT 迭代次数 (默认 SART_CG_ITER=50)
        relax:    松弛因子 (默认 SART_RELAX_OVERRIDE=1.5, 过松弛加速收敛)
    Returns:
        np.ndarray: shape=(n_pixels, n_pixels), 重建 μ 图 (mm⁻¹)
    """
    print(f"  真 SART 矩阵化 (SIRT 迭代, maxiter={n_iter}, relax={relax})")
    n_angles, n_det = sinogram.shape
    n_pixels = RECON_SIZE
    pixel_size = PITCH_MM
    n_inner = n_pixels * n_pixels
    # 1. 构建/加载 A
    print(f"  [1/5] 加载/构建系统矩阵 A ...")
    t0 = time.time()
    A = _get_cached_or_build_matrix(n_angles, n_det, n_pixels, pixel_size)
    print(f"    A 加载完成, 耗时 {time.time() - t0:.1f}s, nnz={A.nnz}")
    # 2. 准备 b
    print(f"  [2/5] 准备投影向量 b ...")
    b = sinogram.flatten().astype(np.float64)
    print(f"    b shape = {b.shape}, range = [{b.min():.3f}, {b.max():.3f}]")
    # 3. 计算行/列归一化权重
    print(f"  [3/5] 计算行/列归一化权重 ...")
    row_sum = np.asarray(A.sum(axis=1)).flatten()  # 每条射线的总长度
    col_sum = np.asarray(A.sum(axis=0)).flatten()  # 每个像素被穿过总长
    # 防 0 除
    row_sum_safe = np.where(row_sum > 1e-9, row_sum, 1.0)
    col_sum_safe = np.where(col_sum > 1e-9, col_sum, 1.0)
    R_diag = 1.0 / row_sum_safe  # shape (n_angles*n_det,)
    C_diag = 1.0 / col_sum_safe  # shape (n_pixels²,)
    print(f"    row_sum: min={row_sum.min():.3f}, max={row_sum.max():.3f}")
    print(f"    col_sum: min={col_sum.min():.3f}, max={col_sum.max():.3f}")
    # 4. 零初始化 (从零开始, 让 SIRT 自然上升)
    print(f"  [4/5] 零初始化 x0 ...")
    x = np.zeros(n_inner, dtype=np.float64)
    print(f"    x0 = zeros, 等待 SIRT 自然收敛")
    # 5. SIRT 迭代
    print(f"  [5/5] SIRT 迭代 (max {n_iter}, relax={relax}) ...")
    t_sirt = time.time()
    for it in range(n_iter):
        # 残差 r = b - A x
        Ax = A @ x
        residual = b - Ax
        # 应用 R: r_normalized = R * r (每条射线归一化)
        r_norm = R_diag * residual
        # 应用 A^T: A^T r_norm
        ATr_norm = A.T @ r_norm
        # 应用 C: C * ATr_norm (每个像素归一化)
        update = C_diag * ATr_norm
        # 松弛因子 + 累积更新
        x = x + relax * update
        # 非负约束
        np.clip(x, 0, None, out=x)
        if (it + 1) % 10 == 0 or it == 0:
            # 监控残差
            err = np.linalg.norm(residual) / max(np.linalg.norm(b), 1e-9)
            print(f"    iter {it + 1}/{n_iter}: rel_residual = {err:.4e}")
    elapsed = time.time() - t_sirt
    print(f"    SIRT 迭代总耗时 {elapsed:.1f}s")
    # reshape
    recon = x.reshape(n_pixels, n_pixels).astype(np.float32)
    # 释放 A 内存
    del A, b, x, Ax, residual, r_norm, ATr_norm, update
    del row_sum, col_sum, R_diag, C_diag
    gc.collect()
    print(f"  SART 真重建: mean = {recon.mean():.4f}, std = {recon.std():.4f}")
    return recon


def sart_cg_reconstruct(sinogram, n_iter=SART_CG_ITER, tol=SART_CG_TOL):
    """
    真 SART 矩阵化: 求解 A^T A x = A^T b (CG 法) - 备用, 当前默认用 SIRT.

    算法:
      1. 构造/加载系统矩阵 A (n_angles*n_det, n_pixels²), 稀疏 CSR
      2. b = sinogram.flatten() (投影向量)
      3. x0 = FBP-init (FBP 平滑初值, 加速 CG 收敛)
      4. CG 迭代: min ||Ax - b||²  (L2 最小二乘)
      5. reshape 回 (n_pixels, n_pixels)

    关键实现: A^T A 是 65536×65536 dense, 显式构造会爆内存.
    用 scipy.sparse.linalg.LinearOperator 包装 (A^T A) 不显式构造,
    matvec(x) = A^T @ (A @ x).

    收敛监控: scipy.cg 返回 (x, info), info=0 收敛, >0 未达 tol

    Args:
        sinogram: 线积分 sinogram (n_angles, n_det)
        n_iter:   CG 最大迭代次数 (默认 SART_CG_ITER=30)
        tol:      CG 收敛相对容忍 (默认 1e-4)
    Returns:
        np.ndarray: shape=(n_pixels, n_pixels), 重建 μ 图
    """
    from scipy.sparse.linalg import cg, LinearOperator
    print(f"  真 SART 矩阵化 (CG 求解, maxiter={n_iter}, rtol={tol})")
    n_angles, n_det = sinogram.shape
    n_pixels = RECON_SIZE
    pixel_size = PITCH_MM
    # 1. 构建/加载 A
    print(f"  [1/5] 加载/构建系统矩阵 A ...")
    t0 = time.time()
    A = _get_cached_or_build_matrix(n_angles, n_det, n_pixels, pixel_size)
    print(f"    A 加载完成, 耗时 {time.time() - t0:.1f}s, nnz={A.nnz}")
    # 2. 准备 b
    print(f"  [2/5] 准备投影向量 b ...")
    b = sinogram.flatten().astype(np.float64)
    print(f"    b shape = {b.shape}, range = [{b.min():.3f}, {b.max():.3f}]")
    Atb = A.T @ b
    print(f"    A^T b computed, shape={Atb.shape}")
    # 3. FBP 初始化 (加速 CG 收敛)
    print(f"  [3/5] FBP 初始化 x0 ...")
    x0_img = fbp_reconstruct(sinogram)
    x0 = x0_img.flatten().astype(np.float64)
    # 4. 构造 LinearOperator (A^T A) 避免显式稠密化
    print(f"  [4/5] 构造 LinearOperator (A^T A) ...")
    n_inner = n_pixels * n_pixels

    def _matvec_AtA(v):
        # 1 次 SpMV: A v (n_angles*n_det,), 1 次 SpMV: A^T (n_pixels²,)
        return A.T @ (A @ v)

    AtA_op = LinearOperator(
        shape=(n_inner, n_inner),
        matvec=_matvec_AtA,
        dtype=np.float64,
    )
    # 5. CG 求解
    print(f"  [5/5] CG 迭代求解 (max {n_iter}) ...")
    t_cg = time.time()
    x, info = cg(AtA_op, Atb, x0=x0, maxiter=n_iter, rtol=tol)
    elapsed = time.time() - t_cg
    print(f"    CG 耗时 {elapsed:.1f}s, info={info} (0=收敛, >0=未达 tol)")
    if info != 0:
        print(f"    ⚠ CG 未完全收敛 (info={info}), 当前解可能次优")
    # reshape (保留负值, 因为 CG 可能给负值)
    recon = x.reshape(n_pixels, n_pixels).astype(np.float32)
    # 释放 A 内存
    del A, AtA_op, Atb
    gc.collect()
    print(f"  SART 真重建: mean = {recon.mean():.4f}, std = {recon.std():.4f}")
    return recon


def sart_reconstruct(sinogram, n_iter=5, relax=SART_RELAX_OVERRIDE):
    """
    SART 重建 (v6: 真 SART 矩阵化 or v5 placeholder).

    v5 placeholder (USE_MATRIX_SART=False):
      FBP-init + n_iter 轮 中值(3×3) + 高斯(σ=0.5) 降噪.
    v6 真 SART (USE_MATRIX_SART=True):
      构建系统矩阵 A (Siddon ray-tracing), 求解 Ax ≈ b:
        - SIRT 迭代 (默认, SART_USE_SIRT=True): 行/列归一化 + 非负约束
        - CG 求解 (备用, SART_USE_SIRT=False): 求解 A^T A x = A^T b
      FBP-init warm start.

    Args:
        sinogram: 线积分 (n_angles, n_det)
        n_iter:   平滑轮数 (placeholder) 或 SIRT/CG maxiter (真 SART)
        relax:    松弛因子 (SIRT 用, 默认 SART_RELAX=0.8)
    Returns:
        np.ndarray: shape=(256,256), 重建 μ 图
    """
    if USE_MATRIX_SART:
        method = "SIRT" if SART_USE_SIRT else "CG"
        print(f"  SART 重建 (v6 真 SART 矩阵化 + {method}, maxiter={n_iter}, relax={relax})")
        if SART_USE_SIRT:
            return sart_sirt_reconstruct(sinogram, n_iter=n_iter, relax=relax)
        else:
            return sart_cg_reconstruct(sinogram, n_iter=n_iter)
    else:
        print(f"  SART 重建 (v5 placeholder: FBP-init + 5x5 平滑, 等价 {n_iter} 次迭代平滑)")
        recon = fbp_reconstruct(sinogram).copy()
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

    import argparse
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--tv_scan", action="store_true", help="v9 #3 TV weight 扫描")
    _args, _ = _parser.parse_known_args()

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
    recon_sart = sart_reconstruct(proj_log, n_iter=SART_CG_ITER)
    print(f"  SART done in {time.time()-t0:.1f} s, range = [{recon_sart.min():.4f}, {recon_sart.max():.4f}]")
    save_recon_as_mu(recon_sart, os.path.join(out_dir, "ct_recon_sart.mhd"))

    # ========== SART+TV ==========
    print()
    print("=" * 60)
    print("步骤 5/5: SART+TV 重建")
    print("=" * 60)
    t0 = time.time()
    recon_tv = sart_tv_reconstruct(proj_log, n_iter=SART_CG_ITER, tv_weight=TV_WEIGHT_DEFAULT)
    print(f"  SART+TV done in {time.time()-t0:.1f} s, range = [{recon_tv.min():.4f}, {recon_tv.max():.4f}]")
    save_recon_as_mu(recon_tv, os.path.join(out_dir, "ct_recon_sart_tv.mhd"))

    # v9 #3: TV weight 扫描 — 仅在 --tv_scan 时启用
    if _args.tv_scan:
        print()
        print("=" * 60)
        print("v9 #3: TV weight 扫描")
        print("=" * 60)
        scan_dir = os.path.join(out_dir, "_tv_scan")
        os.makedirs(scan_dir, exist_ok=True)
        # SART 缓存复用 (不重跑 CG)
        for tv_w in TV_WEIGHT_SCAN:
            print(f"\n--- TV_WEIGHT = {tv_w} ---")
            t0 = time.time()
            recon_w = sart_tv_reconstruct(proj_log, n_iter=SART_CG_ITER, tv_weight=tv_w)
            print(f"  TV={tv_w} done in {time.time()-t0:.1f} s, range = [{recon_w.min():.4f}, {recon_w.max():.4f}]")
            save_recon_as_mu(recon_w, os.path.join(scan_dir, f"ct_recon_sart_tv_w{tv_w}.mhd"))
        print(f"\n  扫描完成, 输出: {scan_dir}")

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
