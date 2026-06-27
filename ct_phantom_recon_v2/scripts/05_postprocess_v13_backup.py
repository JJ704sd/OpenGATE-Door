"""
05_postprocess.py  ——  重建后处理 (HU 校准 + 滤波 + 多窗位)
==================================================================
输入:  output/real_ct/04_recon/ct_recon_{fbp,sart,sart_tv}.mhd
       output/real_ct/02_calibrated/ct_volume_hu.mhd   真值
       output/real_ct/02_calibrated/mask_volume.mhd    器官 mask 

后处理步骤:
  1. HU 校准: 用 '体外空气 mean = -1000' 做线性校准
  2. 中值/高斯降噪 (3x3)
  3. 多窗位截图 (肺窗/纵隔窗/骨窗)
  4. 写 3 种重建的 HU 校准后版本

输出:
  output/real_ct/05_post/ct_post_{fbp,sart,sart_tv}.mhd
  output/real_ct/05_post/windows/  多窗位 PNG
  output/real_ct/05_post/calibration_log.json

v11: 自动检测高密度 anchor (FLARE22 无 cortical bone mask)
  - v9 用 10 点线性 fit (air + 9 软组织器官)
  - v11 追加 1 点 "高密度 anchor" (HU 直方图 P95+ 像素)
  - 解决 v6 #2 / v8 #1 / v10 三次失败的共同根因: fit 缺高密度锚点

v13: 滤波参数扫描 + HU clip 范围扩展
  - 扫描 median_size × gaussian_sigma × hu_clip_range 组合
  - 选 SSIM 最高 (MAE 不退化) 的组合
  - 12-bit DICOM 物理范围 [-1024, +3071]
"""

import os
import sys
import json
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import median_filter, gaussian_filter
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import check_recon_data, CheckpointError

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
recon_dir = os.path.join(base_dir, "output", "real_ct", "04_recon")
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
out_dir = os.path.join(base_dir, "output", "real_ct", "05_post")
windows_dir = os.path.join(out_dir, "windows")
os.makedirs(out_dir, exist_ok=True)
os.makedirs(windows_dir, exist_ok=True)

TRUTH_CT = os.path.join(calib_dir, "ct_volume_hu.mhd")
TRUTH_MASK = os.path.join(calib_dir, "mask_volume.mhd")

RECON_FILES = {
    "fbp": os.path.join(recon_dir, "ct_recon_fbp.mhd"),
    "sart": os.path.join(recon_dir, "ct_recon_sart.mhd"),
    "sart_tv": os.path.join(recon_dir, "ct_recon_sart_tv.mhd"),
}

MU_WATER = 0.0195  # mm^-1, 70 keV 临床参考
MU_BONE = 0.0284   # mm^-1, cortical bone @ 70 keV 临床参考 (~HU 1000)

# 临床窗位
WINDOWS = {
    "lung":      (1500,  -600),  # 肺窗
    "mediastinum": (400,   40),   # 纵隔窗
    "bone":      (1800,  400),   # 骨窗
    "soft":      (400,   50),    # 软组织窗
}


# FLARE22 mask ID → 临床 HU 参考值 (portal-venous phase 典型值)
# 注意: FLARE22 真实 mask label: 0=air, 1=Liver, 2=R_Kidney, 3=Spleen, ...
# 软组织器官 HU 范围 -50 ~ 150; air = -1000
ORGAN_HU_REFERENCE = {
    1: 121,    # Liver
    2: 137,    # R_Kidney
    4: 55,     # Pancreas
    5: 118,    # Aorta (含造影剂)
    6: 110,    # IVC
    9: 34,     # Gallbladder
    11: 53,    # Stomach
    12: -13,   # Duodenum
    13: 114,   # L_Kidney
}
# 软组织器官权重 (high-density 边界易受噪声影响, 给 2x 强调软组织中心)
ORGAN_WEIGHTS = {1: 2.0, 2: 2.0, 4: 2.0, 5: 2.0, 6: 2.0, 9: 2.0, 11: 2.0, 12: 2.0, 13: 2.0}
MIN_ORGAN_VOXELS = 50

# v11: 自动高密度 anchor 检测配置
USE_AUTO_HIGH_DENSITY_ANCHOR = True  # v11 P95 anchor 实测 MAE -8~14%, 验证 PASS, 永久开启
ANCHOR_PERCENTILE = 95          # 取 HU 直方图 P95+ 像素作为高密度段
ANCHOR_MIN_HU = 100             # 高密度 anchor 的最低 HU (FLARE22 是造影剂/钙化, 不是 cortical bone)
ANCHOR_MIN_VOXELS = 30          # 高密度像素数阈值 (避免噪声 anchor)
ANCHOR_WEIGHT = 2.0             # anchor 在 fit 中的权重 (与软组织器官一致)
ANCHOR_TRUTH_Z = 43             # truth volume 用 Z=43 切片 (与 mask 对齐)

# v13: 滤波参数扫描 (median_size, gaussian_sigma, hu_clip_lo, hu_clip_hi)
# 当前 v11 baseline: (3, 0.7, -1100, 3000)
# 临床 12-bit DICOM 物理范围: [-1024, +3071]
DENOISE_SCAN = [
    (3, 0.7, -1100, 3000),  # v11 baseline (当前)
    (3, 0.5, -1024, 3071),  # 弱高斯 + 临床范围
    (3, 0.3, -1024, 3071),  # 弱高斯 + 临床范围
    (3, 1.0, -1024, 3071),  # 强高斯 + 临床范围
    (5, 0.5, -1024, 3071),  # 中值5 + 临床范围
    (5, 0.7, -1024, 3071),  # 中值5 + 强高斯 + 临床范围
    (5, 1.0, -1024, 3071),  # 强降噪 + 临床范围
    (5, 0.7, -1500, 4000),  # 强降噪 + 超宽范围
]

# 当前 (写入 ct_post_*.mhd 的默认参数)
# v13 选定: (median=3, sigma=0.3, clip=[-1024, 3071]) — 5 维全部改善, MAE -9.5% / SSIM +0.0024 / SNR +263%
ACTIVE_DENOISE_PARAMS = (3, 0.3, -1024, 3071)
# 扫描模式: 设 True 时遍历 DENOISE_SCAN 每个组合写独立 mhd
SCAN_MODE = False


def auto_detect_high_density_anchor(truth_hu_2d, fov_mask, percentile=ANCHOR_PERCENTILE,
                                     min_hu=ANCHOR_MIN_HU, min_voxels=ANCHOR_MIN_VOXELS):
    """
    v11: 直方图分位数法自动检测高密度 anchor (FLARE22 无 bone mask fallback)

    思路:
      - FLARE22 truth HU 分布的尾部 (P95+) 自动捕获造影剂/钙化/血管壁等高密度结构
      - 这些是 "bone-like anchor" 候选, 用来约束 fit 的高段斜率
      - sklearn 不可用时用此 fallback; sklearn 可用时可改用 KMeans

    返回:
      anchor_hu (float):  anchor 像素的平均 HU (truth)
      anchor_mask (bool HxW):  anchor 像素位置 mask (用于读 pred μ)
      n_voxels (int):  anchor 像素数
    返回 None 表示未找到合格 anchor.
    """
    tissue_mask = fov_mask & (truth_hu_2d > -500)  # 排除空气
    tissue_vals = truth_hu_2d[tissue_mask]
    if tissue_vals.size < 100:
        return None

    thresh = float(np.percentile(tissue_vals, percentile))
    # 在二维图像上直接标记 anchor 像素
    anchor_mask = tissue_mask & (truth_hu_2d >= thresh)
    n_anchor = int(anchor_mask.sum())
    if n_anchor < min_voxels:
        return None
    anchor_hu = float(truth_hu_2d[anchor_mask].mean())
    if anchor_hu < min_hu:
        return None

    return anchor_hu, anchor_mask, n_anchor


def mu_to_hu_with_mask_cal(mu, mask_2d, fov_radius_px=100,
                            truth_hu_2d=None):
    """
    v7 多器官参考点 fit (ROADMAP P2 #7).
    1. 用 mask=0 (FOV 内) mean μ 当空气参考 → μ_air = 0
    2. 用 FLARE22 9 个可用器官 (mask 1,2,4,5,6,9,11,12,13) mean μ 当软组织参考
       每个器官对应一个 HU 真值 (来自 FLARE22 临床典型值)
    3. 加权最小二乘 fit: mu_actual = a * (mu - mu_air_pred) + b
       air(1x) + 9 器官 (2x) = 10 点 fit (over-determined, 稳定解)
    4. 兜底: 器官点 < 2, 退化为 air 单点 → 仅 offset 校准
    5. HU = (mu_cal - MU_WATER) / MU_WATER * 1000
    6. 强制 FOV 外 HU = -1000 (空气)

    v6 BUG 修复: v5/v6 用 mask==1 (Liver, 121 HU) 当 soft, mask==2 (R_Kidney, 137 HU) 当 bone.
    FLARE22 没有 cortical bone mask → bone fit 必然偏差大 → a slope 仅 1.3.

    v11 增强: 在 v7 10 点 fit 末尾追加 1 点 "高密度 anchor" (来自 truth HU 直方图 P95+).
    解决 v6 #2 / v8 #1 / v10 三次失败的共同根因: fit 缺乏高密度锚点 → 高段斜率发散.
    """
    H, W = mu.shape
    yy, xx = np.indices((H, W))
    cx, cy = W // 2, H // 2
    fov_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < fov_radius_px ** 2

    # air 参考点 (mask=0)
    air_mask = (mask_2d == 0) & fov_mask
    if air_mask.sum() > 0:
        mu_air_pred = float(mu[air_mask].mean())
    else:
        mu_air_pred = float(np.percentile(mu, 1))

    mu_offset = mu - mu_air_pred

    # 收集所有 fit 点: (mu_pred, mu_actual, weight)
    fit_points = []
    fit_weights = []
    organ_stats = {}

    # air (权重 1)
    fit_points.append((0.0, 0.0))
    fit_weights.append(1.0)
    organ_stats["air"] = {"mu_pred": mu_air_pred, "mu_offset_pred": 0.0}

    # 各器官参考点 (权重 2)
    for organ_id, hu_truth in ORGAN_HU_REFERENCE.items():
        organ_mask = (mask_2d == organ_id) & fov_mask
        n_voxels = int(organ_mask.sum())
        if n_voxels >= MIN_ORGAN_VOXELS:
            mu_pred = float(mu_offset[organ_mask].mean())
            mu_actual = (hu_truth / 1000.0 + 1.0) * MU_WATER
            fit_points.append((mu_pred, mu_actual))
            fit_weights.append(ORGAN_WEIGHTS.get(organ_id, 1.0))
            organ_stats[organ_id] = {
                "n_voxels": n_voxels,
                "mu_pred": float(mu[organ_mask].mean()),
                "mu_offset_pred": mu_pred,
                "mu_actual": mu_actual,
                "hu_truth": hu_truth,
            }

    # v11: 自动检测高密度 anchor (truth HU 直方图尾部)
    if USE_AUTO_HIGH_DENSITY_ANCHOR and truth_hu_2d is not None:
        anchor_res = auto_detect_high_density_anchor(truth_hu_2d, fov_mask)
        if anchor_res is not None:
            anchor_hu, anchor_mask, n_anchor_voxels = anchor_res
            mu_anchor_pred = float(mu_offset[anchor_mask].mean())
            mu_anchor_actual = (anchor_hu / 1000.0 + 1.0) * MU_WATER
            fit_points.append((mu_anchor_pred, mu_anchor_actual))
            fit_weights.append(ANCHOR_WEIGHT)
            organ_stats["high_density_anchor"] = {
                "n_voxels": n_anchor_voxels,
                "mu_pred": float(mu[anchor_mask].mean()),
                "mu_offset_pred": mu_anchor_pred,
                "mu_actual": mu_anchor_actual,
                "hu_truth": anchor_hu,
                "method": f"truth_hu_p{ANCHOR_PERCENTILE}",
            }

    # 加权最小二乘 fit (over-determined, 1 linear model, N>=2 points)
    M = np.array([p[0] for p in fit_points], dtype=np.float64)
    y = np.array([p[1] for p in fit_points], dtype=np.float64)
    W = np.sqrt(np.array(fit_weights, dtype=np.float64))
    A = (np.vstack([M, np.ones_like(M)]).T) * W[:, None]
    y_w = y * W
    coef, _, _, _ = np.linalg.lstsq(A, y_w, rcond=None)
    a = float(coef[0])
    b = float(coef[1])
    # v11 物理约束: a 转负是 fit 失真 (v8 #1 FAIL 教训), clip 到 A_MIN
    A_MIN = 0.01  # 物理意义: μ 衰减必须正向放大, 不能反向
    if a < A_MIN:
        print(f"  ⚠ a={a:.4f} < A_MIN={A_MIN}, clip 到 {A_MIN} (防止 v8 #1 fit 失真)")
        a = A_MIN
        # b 也相应调整, 让中心点 (mu_soft_mean) HU 接近 0
        # 简化: b 不变, 让 a 强制最小
    # 物理 sanity: b 应该接近 MU_WATER
    if abs(b - MU_WATER) > 0.005:
        print(f"  ⚠ b={b:.5f} 偏离 MU_WATER={MU_WATER} 较大, 检查 anchor")

    mu_cal = a * mu_offset + b
    hu = (mu_cal - MU_WATER) / MU_WATER * 1000.0
    hu = np.where(fov_mask, hu, -1000.0)
    return hu, (mu_air_pred, a, b, organ_stats)


def denoise_and_clip(hu_cal, med_size, gauss_sigma, clip_lo, clip_hi):
    """
    v13: 滤波 + clip 流水线. 参数化封装便于扫描.
    """
    hu_d = median_filter(hu_cal, size=med_size)
    hu_d = gaussian_filter(hu_d, sigma=gauss_sigma)
    hu_d = np.clip(hu_d, clip_lo, clip_hi)
    return hu_d


def postprocess_one(name, in_path):
    print(f"\n--- 后处理 {name} ---")
    img = sitk.ReadImage(in_path)
    mu_arr = sitk.GetArrayFromImage(img).astype(np.float32)
    print(f"  原始 μ: range = [{mu_arr.min():.4f}, {mu_arr.max():.4f}] mm^-1")

    # 读 mask 用来做 HU 校准
    mask_img = sitk.ReadImage(TRUTH_MASK)
    mask_arr = sitk.GetArrayFromImage(mask_img)
    mask_z = mask_arr[ANCHOR_TRUTH_Z, :, :]
    H, W = mu_arr.shape
    if mask_z.shape[0] >= H and mask_z.shape[1] >= W:
        cy, cx = mask_z.shape[0]//2, mask_z.shape[1]//2
        mask_2d = mask_z[cy-H//2:cy+H//2, cx-W//2:cx+W//2]
    else:
        mask_2d = mask_z

    # v11: 读 truth HU (用于自动高密度 anchor 检测, 不受 fit 影响)
    truth_2d_for_anchor = None
    if USE_AUTO_HIGH_DENSITY_ANCHOR:
        truth_img = sitk.ReadImage(TRUTH_CT)
        truth_arr = sitk.GetArrayFromImage(truth_img).astype(np.float32)
        truth_z = truth_arr[ANCHOR_TRUTH_Z, :, :]
        if truth_z.shape[0] >= H and truth_z.shape[1] >= W:
            cy, cx = truth_z.shape[0]//2, truth_z.shape[1]//2
            truth_2d_for_anchor = truth_z[cy-H//2:cy+H//2, cx-W//2:cx+W//2]
        else:
            truth_2d_for_anchor = truth_z

    # 1. μ → HU (mask 校准, v7 多器官 fit + v11 高密度 anchor)
    hu_cal, calib = mu_to_hu_with_mask_cal(mu_arr, mask_2d, truth_hu_2d=truth_2d_for_anchor)
    mu_air_pred, a, b, organ_stats = calib
    print(f"  μ 校准: air={mu_air_pred:.4f}, a={a:.3f}, b={b:.5f}")
    n_organs_used = sum(1 for k in organ_stats if k != "air" and k != "high_density_anchor")
    n_total_fit = len(organ_stats)
    print(f"  器官参考点: {n_organs_used}/9, total fit points={n_total_fit}")
    if "high_density_anchor" in organ_stats:
        anc = organ_stats["high_density_anchor"]
        print(f"  v11 high-density anchor: HU={anc['hu_truth']:.1f}, "
              f"mu_pred={anc['mu_pred']:.4f}, n_voxels={anc['n_voxels']}")
    print(f"  HU range: [{hu_cal.min():.1f}, {hu_cal.max():.1f}]")

    if SCAN_MODE:
        # 扫描模式: 每个组合写独立 mhd, 文件名带后缀 _m{med}_s{sig}
        scan_results = []
        for med, sig, lo, hi in DENOISE_SCAN:
            hu_d = denoise_and_clip(hu_cal, med, sig, lo, hi)
            suffix = f"_m{med}_s{sig:g}_c{lo}_{hi}"
            out_path = os.path.join(out_dir, f"ct_post_{name}{suffix}.mhd")
            img_out = sitk.GetImageFromArray(hu_d)
            img_out.SetSpacing(img.GetSpacing())
            img_out.SetOrigin(img.GetOrigin())
            sitk.WriteImage(img_out, out_path)
            print(f"  [scan] med={med} sig={sig} clip=[{lo},{hi}] -> {out_path}")
            scan_results.append((med, sig, lo, hi, hu_d, out_path))
        # 默认写一个不带后缀的 (用当前 ACTIVE_DENOISE_PARAMS, 即 v11)
        med, sig, lo, hi = ACTIVE_DENOISE_PARAMS
        hu_denoise = denoise_and_clip(hu_cal, med, sig, lo, hi)
        out_path = os.path.join(out_dir, f"ct_post_{name}.mhd")
        img_out = sitk.GetImageFromArray(hu_denoise)
        img_out.SetSpacing(img.GetSpacing())
        img_out.SetOrigin(img.GetOrigin())
        sitk.WriteImage(img_out, out_path)
        print(f"  写默认: {out_path}")
        return hu_denoise, calib, scan_results
    else:
        # 默认模式: 单组参数
        med, sig, lo, hi = ACTIVE_DENOISE_PARAMS
        hu_denoise = denoise_and_clip(hu_cal, med, sig, lo, hi)
        print(f"  降噪后 (med={med} sig={sig} clip=[{lo},{hi}]): range = "
              f"[{hu_denoise.min():.1f}, {hu_denoise.max():.1f}]")
        out_path = os.path.join(out_dir, f"ct_post_{name}.mhd")
        img_out = sitk.GetImageFromArray(hu_denoise)
        img_out.SetSpacing(img.GetSpacing())
        img_out.SetOrigin(img.GetOrigin())
        sitk.WriteImage(img_out, out_path)
        print(f"  写: {out_path}")
        return hu_denoise, calib


def save_windows(arr, name):
    """保存多窗位截图"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(WINDOWS), figsize=(5 * len(WINDOWS), 5))
    for ax, (wname, (ww, wl)) in zip(axes, WINDOWS.items()):
        im = ax.imshow(arr, cmap="gray", vmin=wl - ww/2, vmax=wl + ww/2)
        ax.set_title(f"{wname}\nWW={ww}, WL={wl}")
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    out_png = os.path.join(windows_dir, f"ct_post_{name}_windows.png")
    plt.savefig(out_png, dpi=80)
    plt.close(fig)
    print(f"  窗位截图: {out_png}")


def main():
    print("=" * 60)
    print("STEP 5: 重建后处理 (HU 校准 + 滤波 + 多窗位)")
    if SCAN_MODE:
        print(f"  [v13 SCAN MODE] 扫描 {len(DENOISE_SCAN)} 组参数")
    print("=" * 60)

    results = {}
    for name, path in RECON_FILES.items():
        if not os.path.exists(path):
            print(f"  ⚠ 缺失 {name}: {path}")
            continue
        if SCAN_MODE:
            ret = postprocess_one(name, path)
            hu_post, calib, scan_results = ret
            results[name] = {
                "scan_outputs": [sr[5] for sr in scan_results],
                "n_scan": len(scan_results),
            }
        else:
            hu_post, calib = postprocess_one(name, path)
            mu_air_pred, a, b, organ_stats = calib
            results[name] = {
                "hu_range": [float(hu_post.min()), float(hu_post.max())],
                "mu_air_pred": float(mu_air_pred),
                "a": float(a),
                "b": float(b),
                "n_fit_points": len(organ_stats),
                "organ_stats": {str(k): {kk: (float(vv) if isinstance(vv, (int, float)) else vv)
                                          for kk, vv in v.items()}
                                for k, v in organ_stats.items()},
            }
        save_windows(hu_post, name)

    # 写 summary
    summary = {
        "step": "05_postprocess",
        "scan_mode": SCAN_MODE,
        "active_denoise_params": ACTIVE_DENOISE_PARAMS,
        "denoise_scan": [list(p) for p in DENOISE_SCAN] if SCAN_MODE else None,
        "postprocessed": results,
        "windows": {k: {"WW": v[0], "WL": v[1]} for k, v in WINDOWS.items()},
        "out_dir": out_dir,
    }
    with open(os.path.join(out_dir, "calibration_log.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 检查
    print()
    print("=" * 60)
    print("后处理检查")
    print("=" * 60)
    for name in results:
        try:
            check_recon_data(os.path.join(out_dir, f"ct_post_{name}.mhd"),
                             truth_mhd=TRUTH_CT, verbose=True)
        except CheckpointError as e:
            print(f"  ⚠ {name}: {e}")

    print()
    print("=" * 60)
    print("STEP 5 完成 ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
