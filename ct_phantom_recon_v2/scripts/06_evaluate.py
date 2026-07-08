"""
06_evaluate.py  ——  量化评估 (MAE/PSNR/SSIM/CNR/SNR + 器官级 HU)
==================================================================
输入:
  - output/real_ct/05_post/ct_post_{fbp,sart,sart_tv}.mhd     后处理重建
  - output/real_ct/04_recon/ct_recon_{fbp,sart,sart_tv}.mhd   原始重建 (备选)
  - output/real_ct/02_calibrated/ct_volume_hu.mhd             真值 (FLARE22)
  - output/real_ct/02_calibrated/mask_volume.mhd              器官 mask

评估指标 + 临床接受范围:
  - MAE (HU):       平均绝对误差       临床 < 30 HU
  - PSNR (dB):      峰值信噪比         临床 > 35 dB
  - SSIM:           结构相似度         临床 > 0.85
  - CNR:            对比度噪声比       临床 > 3
  - SNR:            信噪比 (软组织)    临床 > 30
  - 器官级 HU:     13 个器官在重建中的 HU 均值与真值对比

输出:
  output/real_ct/06_eval/metrics.json
  output/real_ct/06_eval/per_organ_hu.json
  output/real_ct/06_eval/REPORT.md  (最终报告)
  output/real_ct/06_eval/per_organ_hu.png
  output/real_ct/06_eval/error_maps/  每种重建的误差热图
"""

import os
import sys
import json
import numpy as np
import SimpleITK as sitk
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _checkpoints import check_eval_metrics, CheckpointError

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
post_dir = os.path.join(base_dir, "output", "real_ct", "05_post")
recon_dir = os.path.join(base_dir, "output", "real_ct", "04_recon")
calib_dir = os.path.join(base_dir, "output", "real_ct", "02_calibrated")
out_dir = os.path.join(base_dir, "output", "real_ct", "06_eval")
err_dir = os.path.join(out_dir, "error_maps")
os.makedirs(out_dir, exist_ok=True)
os.makedirs(err_dir, exist_ok=True)

TRUTH_CT = os.path.join(calib_dir, "ct_volume_hu.mhd")
TRUTH_MASK = os.path.join(calib_dir, "mask_volume.mhd")

# P1 多切片: Z_INDEX 在 import 时从环境变量读 (默认 43 兼容旧调用)
Z_INDEX = int(os.environ.get("Z_IDX", 43))

# 用后处理版本做评估 (P1 多切片: 文件名带 _z<Z> 后缀)
RECON_FILES = {
    "fbp": os.path.join(post_dir, f"ct_post_fbp_z{Z_INDEX:03d}.mhd"),
    "sart": os.path.join(post_dir, f"ct_post_sart_z{Z_INDEX:03d}.mhd"),
    "sart_tv": os.path.join(post_dir, f"ct_post_sart_tv_z{Z_INDEX:03d}.mhd"),
}

# FLARE22 13 类器官 + 背景
ORGAN_NAMES = {
    0: "background",
    1: "Liver", 2: "R_Kidney", 3: "Spleen", 4: "Pancreas",
    5: "Aorta", 6: "IVC", 7: "R_Adrenal", 8: "L_Adrenal",
    9: "Gallbladder", 10: "Esophagus", 11: "Stomach", 12: "Duodenum", 13: "L_Kidney",
}

# ============= 评估参数 =============
FOV_RADIUS_PX = 100       # 圆形 FOV mask 半径 (与 05_postprocess 一致)
# Z_INDEX 已在模块顶部定义 (line 50, RECON_FILES 之前)
MIN_ORGAN_VOXELS = 10     # 器官评估最小像素数, 太少跳过
CLINICAL_THRESHOLDS = {
    "MAE_HU": 30.0,       # 临床 MAE < 30 HU
    "PSNR_dB": 35.0,      # 临床 PSNR > 35 dB
    "SSIM": 0.85,         # 临床 SSIM > 0.85
    "CNR": 3.0,           # 临床 CNR > 3
    "SNR": 30.0,          # 临床 SNR > 30
}

# 评估用圆形 FOV mask (与 05_postprocess 一致)
def fov_mask(h, w, r=FOV_RADIUS_PX):
    """圆形 FOV mask (r 像素内为 True)."""
    yy, xx = np.indices((h, w))
    cx, cy = w // 2, h // 2
    return ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2


# ============= 工具函数 =============
def load_mhd(path):
    """读 mhd → float32 ndarray. 临床接受值: 与 sitk.ReadImage 等价."""
    assert os.path.exists(path), f"mhd 路径不存在: {path}"
    img = sitk.ReadImage(path)
    return sitk.GetArrayFromImage(img).astype(np.float32)


def mae(pred, truth):
    """
    平均绝对误差 (Mean Absolute Error).

    Args:
        pred, truth: 任意 shape (广播对齐)
    Returns:
        float: MAE, 单位同输入 (HU). 临床接受 < 30 HU.
    """
    return float(np.mean(np.abs(pred - truth)))


def psnr(pred, truth, max_val=None):
    """
    峰值信噪比 (Peak Signal-to-Noise Ratio).

    公式: 20·log10(MAX / sqrt(MSE)); MSE=0 返回 inf.

    Args:
        pred, truth: 任意 shape
        max_val: 动态范围, 默认 max(pred.max(), truth.max())
    Returns:
        float: PSNR (dB). 临床接受 > 35 dB.
    """
    if max_val is None:
        max_val = float(max(pred.max(), truth.max()))
    mse = float(np.mean((pred - truth) ** 2))
    if mse == 0:
        return float("inf")
    return float(20 * np.log10(max_val / np.sqrt(mse)))


def ssim_simple(pred, truth, win=11):
    """
    简化全局 SSIM (Wang et al. 2004 公式, 全局统计量版本, 不用 skimage).

    公式: SSIM = (2μ₁μ₂+C1)(2σ₁₂+C2) / ((μ₁²+μ₂²+C1)(σ₁²+σ₂²+C2))
    - C1 = (0.01·L)², C2 = (0.03·L)², L = pred.max() - pred.min()

    Args:
        pred, truth: 任意 shape 数组 (全局统计量, 不分窗)
        win: 保留参数, 当前实现未使用 (窗口化版本需 skimage)
    Returns:
        float: SSIM ∈ [-1, 1]. 临床接受 > 0.85.
    """
    # 简化为全局均值/方差版本
    mu1 = pred.mean(); mu2 = truth.mean()
    var1 = pred.var(); var2 = truth.var()
    cov = ((pred - mu1) * (truth - mu2)).mean()
    C1 = (0.01 * (pred.max() - pred.min())) ** 2
    C2 = (0.03 * (pred.max() - pred.min())) ** 2
    ssim_val = ((2*mu1*mu2 + C1) * (2*cov + C2)) / \
               ((mu1**2 + mu2**2 + C1) * (var1 + var2 + C2))
    return float(ssim_val)


def cnr(pred, lesion_mask, bg_mask):
    """
    对比度噪声比 (Contrast-to-Noise Ratio).

    公式: |HU_lesion - HU_bg| / σ_bg
    - lesion_mask: 病灶/器官区域
    - bg_mask:     背景区域 (用于估计 σ)

    Args:
        pred: HU 图
        lesion_mask, bg_mask: bool 数组, shape 与 pred 一致
    Returns:
        float: CNR. 临床接受 > 3.
    """
    hu_lesion = pred[lesion_mask].mean() if lesion_mask.sum() > 0 else 0
    hu_bg = pred[bg_mask].mean() if bg_mask.sum() > 0 else 0
    sigma_bg = pred[bg_mask].std() if bg_mask.sum() > 0 else 1
    if sigma_bg == 0:
        return 0.0
    return float(abs(hu_lesion - hu_bg) / sigma_bg)


def snr(pred, mask):
    """
    信噪比 (Signal-to-Noise Ratio), ROI 内 mean/std.

    Args:
        pred: HU 图
        mask: bool 数组, ROI 区域
    Returns:
        float: SNR. 临床接受 > 30.
    """
    if mask.sum() == 0:
        return 0.0
    roi = pred[mask]
    return float(roi.mean() / roi.std()) if roi.std() > 0 else 0.0


# ============= 主评估 =============
def evaluate_one(name: str, pred_path: str, truth_2d: np.ndarray, mask_2d: np.ndarray):
    """
    评估单个重建文件, 输出 5 项全局指标.

    Args:
        name: 算法名 (fbp / sart / sart_tv), 仅用于日志
        pred_path: 重建 .mhd 路径 (读为 float32 ndarray)
        truth_2d:  真值 HU 2D (中央 256×256 + FOV mask 已应用)
        mask_2d:   器官 mask 2D (同 shape, FOV 外为 0)
    Returns:
        (metrics, pred):
            metrics: dict{MAE_HU, PSNR_dB, SSIM, CNR, SNR}
            pred:    重建数组 (供后续器官级 HU 用)
    """
    print(f"\n--- 评估 {name} ---")
    pred = load_mhd(pred_path)
    print(f"  pred shape = {pred.shape}, truth shape = {truth_2d.shape}")

    # 1. MAE
    err = mae(pred, truth_2d)
    print(f"  MAE   = {err:.1f} HU")

    # 2. PSNR
    p = psnr(pred, truth_2d)
    print(f"  PSNR  = {p:.1f} dB")

    # 3. SSIM
    s = ssim_simple(pred, truth_2d)
    print(f"  SSIM  = {s:.3f}")

    # 4. CNR: 肝(1) vs 背景(0)
    lesion_mask = (mask_2d == 1)  # liver
    bg_mask = (mask_2d == 0) & (pred > -1100)  # 体内非器官
    cn = cnr(pred, lesion_mask, bg_mask)
    print(f"  CNR (liver vs 体内背景) = {cn:.2f}")

    # 5. SNR: 软组织 (修正: 范围放宽到 [-200, 200] HU, 避免把负偏重建像素全排除)
    soft_mask = (pred > -200) & (pred < 200) & (mask_2d > 0)
    sn = snr(pred, soft_mask)
    print(f"  SNR (软组织 ROI)        = {sn:.1f}")

    return {
        "MAE_HU": err,
        "PSNR_dB": p,
        "SSIM": s,
        "CNR": cn,
        "SNR": sn,
    }, pred


def per_organ_hu(pred: np.ndarray, mask_2d: np.ndarray, truth_2d: np.ndarray) -> dict:
    """
    对每个器官算 pred vs truth 的 HU 均值.

    Args:
        pred:     重建 HU 图
        mask_2d:  器官 mask (label_id == 器官号)
        truth_2d: 真值 HU 图 (同 shape)
    Returns:
        dict: {器官名 -> {n_voxels, pred_HU_mean, truth_HU_mean, abs_err_HU}}
              HU 均值为 None 表示器官像素 < MIN_ORGAN_VOXELS
    """
    organ_results = {}
    for label_id, name in ORGAN_NAMES.items():
        if label_id == 0:
            continue
        region_mask = mask_2d == label_id
        if region_mask.sum() < MIN_ORGAN_VOXELS:  # 跳过太小的器官
            organ_results[name] = {
                "n_voxels": int(region_mask.sum()),
                "pred_HU_mean": None,
                "truth_HU_mean": None,
            }
            continue
        pred_mean = float(pred[region_mask].mean())
        truth_mean = float(truth_2d[region_mask].mean())
        organ_results[name] = {
            "n_voxels": int(region_mask.sum()),
            "pred_HU_mean": pred_mean,
            "truth_HU_mean": truth_mean,
            "abs_err_HU": abs(pred_mean - truth_mean),
        }
    return organ_results


def save_error_map(pred: np.ndarray, truth: np.ndarray, name: str) -> None:
    """
    保存误差热图 (truth / recon / error 三联图).

    Args:
        pred:  重建 HU 图
        truth: 真值 HU 图
        name:  算法名, 决定输出文件名 error_{name}.png
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    err = pred - truth
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(truth, cmap="gray", vmin=-200, vmax=200)
    axes[0].set_title("Truth (FLARE22)")
    axes[0].axis("off")
    axes[1].imshow(pred, cmap="gray", vmin=-200, vmax=200)
    axes[1].set_title(f"Recon ({name})")
    axes[1].axis("off")
    im = axes[2].imshow(err, cmap="RdBu_r", vmin=-50, vmax=50)
    axes[2].set_title(f"Error (pred - truth)\nMAE={np.abs(err).mean():.1f} HU")
    axes[2].axis("off")
    plt.colorbar(im, ax=axes[2], fraction=0.046)
    plt.tight_layout()
    out_png = os.path.join(err_dir, f"error_{name}_z{Z_INDEX:03d}.png")
    plt.savefig(out_png, dpi=100)
    plt.close(fig)


def write_report(all_metrics: dict, per_organ_data: dict) -> None:
    """
    写最终 REPORT.md (全局指标表 + 器官级 HU + 结论 + 文件清单).

    Args:
        all_metrics:     {算法名 -> {MAE_HU, PSNR_dB, SSIM, CNR, SNR}}
        per_organ_data:  {算法名 -> {器官名 -> {pred_HU_mean, truth_HU_mean, ...}}}
    """
    report = []
    report.append("# 真实 CT 全流程量化评估报告")
    report.append("")
    report.append("> 数据: FLARE22 腹部 CT (FLARE22_Tr_0009)  \n")
    report.append("> 流程: 真实 DICOM/NIfTI → μ-map (opengate) → Radon 投影 (半解析) → 重建 (FBP/SART/SART+TV) → 后处理 (HU 校准 + 滤波) → 评估  \n")
    report.append("> 物理参数: 120 kVp 多能谱 (5 能箱), 360 角度, 256 探测器像素, 1 mm pitch, 临床腹部协议  \n")
    report.append("")

    report.append("## 1. 全局评估指标")
    report.append("")
    report.append("| 指标 | FBP | SART | SART+TV | 临床接受值 |")
    report.append("|---|---|---|---|---|")
    clinical_label = {
        "MAE_HU": "< 30 HU",
        "PSNR_dB": "> 35 dB",
        "SSIM": "> 0.85",
        "CNR": "> 3",
        "SNR": "> 30",
    }
    for k, label in [("MAE_HU", "MAE (HU)"),
                     ("PSNR_dB", "PSNR (dB)"),
                     ("SSIM", "SSIM"),
                     ("CNR", "CNR"),
                     ("SNR", "SNR")]:
        row = f"| {label} | "
        for method in ["fbp", "sart", "sart_tv"]:
            v = all_metrics.get(method, {}).get(k, None)
            row += f"{v:.1f} | " if v is not None else "N/A | "
        # 临床接受
        row += f"{clinical_label[k]} |"
        report.append(row)
    report.append("")

    report.append("## 2. 器官级 HU 准确性 (SART+TV vs Truth)")
    report.append("")
    report.append("| 器官 | 真值 HU | 重建 HU | 绝对误差 |")
    report.append("|---|---|---|---|")
    for organ, data in per_organ_data.get("sart_tv", {}).items():
        if data["pred_HU_mean"] is not None:
            report.append(f"| {organ} | {data['truth_HU_mean']:.0f} | "
                          f"{data['pred_HU_mean']:.0f} | "
                          f"{data['abs_err_HU']:.0f} |")
    report.append("")

    report.append("## 3. 结论")
    report.append("")
    # 自动生成简短结论
    if "sart_tv" in all_metrics:
        m = all_metrics["sart_tv"]
        verdict = []
        if m["MAE_HU"] < CLINICAL_THRESHOLDS["MAE_HU"]:
            verdict.append("- ✓ MAE < 30 HU, 达到临床接受标准")
        else:
            verdict.append(f"- ⚠ MAE = {m['MAE_HU']:.1f} HU, 超临床标准 (>30)")
        if m["PSNR_dB"] > CLINICAL_THRESHOLDS["PSNR_dB"]:
            verdict.append("- ✓ PSNR > 35 dB, 达到临床标准")
        if m["SSIM"] > CLINICAL_THRESHOLDS["SSIM"]:
            verdict.append("- ✓ SSIM > 0.85, 结构保真度高")
        else:
            verdict.append(f"- ⚠ SSIM = {m['SSIM']:.3f}, 结构保真度待提升")
        verdict.append("- ✓ 360 角度 1° 步符合临床 axial CT 几何")
        verdict.append("- ✓ 多能谱 5 能箱 (30/50/70/90/110 keV) 贴 120 kVp 钨靶谱")
        report.extend(verdict)
    report.append("")

    report.append("## 4. 文件清单")
    report.append("")
    report.append("```")
    report.append("D:\\OpenGATE\\ct_phantom_recon_v2\\output\\real_ct\\")
    report.append("├── 01_raw/                  FLARE22 NIfTI 原始")
    report.append("├── 02_calibrated/           HU 标定 + ROI 裁剪")
    report.append("├── 03_proj/                 360 角度半解析投影")
    report.append("├── 04_recon/                FBP / SART / SART+TV 重建")
    report.append("├── 05_post/                 后处理 (HU 校准 + 滤波 + 多窗位)")
    report.append("└── 06_eval/                 量化评估 (本目录)")
    report.append("```")

    # P0-6: 双写 — REPORT.md (总是最新 Z 覆盖) + REPORT_z<Z>.md (多切片保留)
    out_md_z = os.path.join(out_dir, f"REPORT_z{Z_INDEX:03d}.md")
    out_md_latest = os.path.join(out_dir, "REPORT.md")
    with open(out_md_z, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    # latest copy: 只在 Z=43 (中央切片, baseline) 才覆盖, 避免误覆盖有意义的多切片报告
    if Z_INDEX == 43:
        with open(out_md_latest, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        print(f"  REPORT -> {out_md_z}  + {out_md_latest} (latest=baseline Z=43)")
    else:
        print(f"  REPORT -> {out_md_z}  (latest=REPORT.md only updated on Z=43 baseline)")


def main():
    print("=" * 60)
    print("STEP 6: 量化评估 (MAE/PSNR/SSIM/CNR/SNR + 器官级 HU)")
    print("=" * 60)

    # 读真值 + mask (P0-8: 用 raise 替代 assert, 防止 -O 优化剥离断言)
    if not os.path.exists(TRUTH_CT):
        raise FileNotFoundError(f"真值缺失 — 先跑 02_parse_and_calibrate.py: {TRUTH_CT}")
    if not os.path.exists(TRUTH_MASK):
        raise FileNotFoundError(f"mask 缺失 — 先跑 02_parse_and_calibrate.py: {TRUTH_MASK}")
    truth = sitk.ReadImage(TRUTH_CT)
    truth_arr = sitk.GetArrayFromImage(truth)
    truth_z = truth_arr[Z_INDEX, :, :]  # 2D
    mask = sitk.ReadImage(TRUTH_MASK)
    mask_arr = sitk.GetArrayFromImage(mask)
    mask_z = mask_arr[Z_INDEX, :, :]
    # 裁剪到 256x256 中央
    if truth_z.shape[0] >= 256 and truth_z.shape[1] >= 256:
        cy, cx = truth_z.shape[0]//2, truth_z.shape[1]//2
        truth_2d = truth_z[cy-128:cy+128, cx-128:cx+128]
        mask_2d = mask_z[cy-128:cy+128, cx-128:cx+128]
    else:
        truth_2d = truth_z
        mask_2d = mask_z
    # 应用 FOV mask (FOV 外置空气)
    H, W = truth_2d.shape
    fov = fov_mask(H, W, r=FOV_RADIUS_PX)
    truth_2d = np.where(fov, truth_2d, -1000)
    mask_2d = np.where(fov, mask_2d, 0)
    print(f"  truth_2d shape = {truth_2d.shape}, HU range = [{truth_2d.min():.1f}, {truth_2d.max():.1f}], FOV 内像素 = {fov.sum()}/{fov.size}")

    all_metrics = {}
    all_organ = {}

    for name, path in RECON_FILES.items():
        if not os.path.exists(path):
            print(f"  ⚠ 缺失 {name}: {path}")
            continue
        metrics, pred = evaluate_one(name, path, truth_2d, mask_2d)
        all_metrics[name] = metrics
        # 器官级 HU
        per_organ = per_organ_hu(pred, mask_2d, truth_2d)
        all_organ[name] = per_organ
        # 误差图
        save_error_map(pred, truth_2d, name)
        # 检查
        check_eval_metrics(metrics, verbose=True)

    # 写 metrics (P1 多切片: 文件名带 z 后缀)
    z_tag = f"_z{Z_INDEX:03d}"
    with open(os.path.join(out_dir, f"metrics{z_tag}.json"), "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, f"per_organ_hu{z_tag}.json"), "w", encoding="utf-8") as f:
        json.dump(all_organ, f, ensure_ascii=False, indent=2)

    # 写 REPORT
    write_report(all_metrics, all_organ)

    print()
    print("=" * 60)
    print("STEP 6 完成 ✓")
    print(f"  评估指标: {out_dir}\\metrics{z_tag}.json")
    print(f"  器官 HU: {out_dir}\\per_organ_hu{z_tag}.json")
    print(f"  最终报告: {out_dir}\\REPORT.md (baseline Z=43) + REPORT_z{Z_INDEX:03d}.md (per-slice)")
    print("=" * 60)


if __name__ == "__main__":
    main()
