"""
对 TV weight 扫描的 5 个 μ 图分别做 05 后处理 + 06 评估.
不修改 05_postprocess.py (避免影响正常流程).
"""
import os
import sys
import json
import numpy as np
import SimpleITK as sitk
import warnings
import importlib.util
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
post_dir = os.path.join(base_dir, "output", "real_ct", "05_post")
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
scan_dir = os.path.join(base_dir, "output", "real_ct", "04_recon", "_tv_scan")
out_dir = os.path.join(base_dir, "output", "real_ct", "06_eval")
err_dir = os.path.join(out_dir, "error_maps")
os.makedirs(err_dir, exist_ok=True)

TRUTH_CT = os.path.join(calib_dir, "ct_volume_hu.mhd")
TRUTH_MASK = os.path.join(calib_dir, "mask_volume.mhd")
Z_INDEX = 43
FOV_RADIUS_PX = 100
TV_WEIGHTS = [0.01, 0.03, 0.05, 0.1, 0.2]

# 加载 05_postprocess 模块
spec = importlib.util.spec_from_file_location("post", os.path.join(os.path.dirname(__file__), "05_postprocess.py"))
post = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post)
spec2 = importlib.util.spec_from_file_location("eval06", os.path.join(os.path.dirname(__file__), "06_evaluate.py"))
ev = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ev)
from scipy.ndimage import median_filter, gaussian_filter


def fov_mask(h, w, r=FOV_RADIUS_PX):
    yy, xx = np.indices((h, w))
    cx, cy = w // 2, h // 2
    return ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2


# 读真值 + mask
truth = sitk.ReadImage(TRUTH_CT)
truth_arr = sitk.GetArrayFromImage(truth)
truth_z = truth_arr[Z_INDEX, :, :]
mask_img = sitk.ReadImage(TRUTH_MASK)
mask_arr = sitk.GetArrayFromImage(mask_img)
mask_z = mask_arr[Z_INDEX, :, :]
cy, cx = truth_z.shape[0] // 2, truth_z.shape[1] // 2
truth_2d = truth_z[cy - 128:cy + 128, cx - 128:cx + 128]
mask_2d_full = mask_z[cy - 128:cy + 128, cx - 128:cx + 128]
H, W = truth_2d.shape
fov = fov_mask(H, W)
truth_2d_fov = np.where(fov, truth_2d, -1000)
mask_2d_fov = np.where(fov, mask_2d_full, 0)

results = {}
for tv_w in TV_WEIGHTS:
    src_mhd = os.path.join(scan_dir, f"ct_recon_sart_tv_w{tv_w}.mhd")
    if not os.path.exists(src_mhd):
        print(f"  ⚠ 缺失 {src_mhd}")
        continue
    print(f"\n===== TV_WEIGHT = {tv_w} =====")
    img = sitk.ReadImage(src_mhd)
    mu_arr = sitk.GetArrayFromImage(img).astype(np.float32)
    # 05 步骤: μ → HU 校准
    hu_cal, calib = post.mu_to_hu_with_mask_cal(mu_arr, mask_2d_full)
    mu_air_pred, a, b, organ_stats = calib
    # 降噪 + clip
    hu_denoise = median_filter(hu_cal, size=3)
    hu_denoise = gaussian_filter(hu_denoise, sigma=0.7)
    hu_denoise = np.clip(hu_denoise, -1100, 3000)
    # 评估 (复用 evaluate_one 但跳过其 mhd 读)
    err = float(np.mean(np.abs(hu_denoise - truth_2d_fov)))
    p = float(20 * np.log10(max(hu_denoise.max(), truth_2d_fov.max()) /
                              np.sqrt(np.mean((hu_denoise - truth_2d_fov) ** 2))))
    mu1 = hu_denoise.mean(); mu2 = truth_2d_fov.mean()
    var1 = hu_denoise.var(); var2 = truth_2d_fov.var()
    cov = ((hu_denoise - mu1) * (truth_2d_fov - mu2)).mean()
    C1 = (0.01 * (hu_denoise.max() - hu_denoise.min())) ** 2
    C2 = (0.03 * (hu_denoise.max() - hu_denoise.min())) ** 2
    ssim_v = ((2 * mu1 * mu2 + C1) * (2 * cov + C2)) / ((mu1 ** 2 + mu2 ** 2 + C1) * (var1 + var2 + C2))
    lesion_mask = (mask_2d_fov == 1)
    bg_mask = (mask_2d_fov == 0) & (hu_denoise > -1100)
    hu_lesion = hu_denoise[lesion_mask].mean() if lesion_mask.sum() > 0 else 0
    hu_bg = hu_denoise[bg_mask].mean() if bg_mask.sum() > 0 else 0
    sigma_bg = hu_denoise[bg_mask].std() if bg_mask.sum() > 0 else 1
    cnr_v = float(abs(hu_lesion - hu_bg) / sigma_bg) if sigma_bg > 0 else 0.0
    soft_mask = (hu_denoise > -200) & (hu_denoise < 200) & (mask_2d_fov > 0)
    roi = hu_denoise[soft_mask]
    snr_v = float(roi.mean() / roi.std()) if roi.std() > 0 else 0.0
    print(f"  TV={tv_w}: MAE={err:.2f}, PSNR={p:.2f}, SSIM={ssim_v:.3f}, CNR={cnr_v:.2f}, SNR={snr_v:.2f}")
    print(f"    a={a:.3f}, b={b:.5f}, mu_air_pred={mu_air_pred:.4f}, n_organs={len(organ_stats) - 1}")
    print(f"    HU range = [{hu_denoise.min():.1f}, {hu_denoise.max():.1f}]")
    results[f"w{tv_w}"] = {
        "MAE_HU": err, "PSNR_dB": p, "SSIM": float(ssim_v),
        "CNR": cnr_v, "SNR": snr_v,
        "a": a, "b": b, "mu_air_pred": mu_air_pred,
        "n_organs": len(organ_stats) - 1,
        "hu_range": [float(hu_denoise.min()), float(hu_denoise.max())],
    }

# 写结果
out_json = os.path.join(out_dir, "_tv_scan_metrics.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n扫描结果 -> {out_json}")

# 打印表格
print("\n===== TV weight 扫描对比表 =====")
print(f"{'TV_w':<8} {'MAE_HU':<10} {'PSNR_dB':<10} {'SSIM':<8} {'CNR':<8} {'SNR':<8} {'a':<6}")
for k, v in results.items():
    print(f"{k:<8} {v['MAE_HU']:<10.2f} {v['PSNR_dB']:<10.2f} {v['SSIM']:<8.3f} {v['CNR']:<8.2f} {v['SNR']:<8.2f} {v['a']:<6.3f}")

# 选最佳: CNR 最高 且 SSIM ≥ 0.95
candidates = [(k, v) for k, v in results.items() if v["SSIM"] >= 0.95]
if candidates:
    best = max(candidates, key=lambda x: x[1]["CNR"])
    print(f"\n最佳 (CNR 最高且 SSIM≥0.95): {best[0]} CNR={best[1]['CNR']:.2f} MAE={best[1]['MAE_HU']:.2f}")
else:
    best = max(results.items(), key=lambda x: x[1]["CNR"])
    print(f"\n无满足 SSIM≥0.95, 选 CNR 最高: {best[0]} CNR={best[1]['CNR']:.2f} MAE={best[1]['MAE_HU']:.2f}")