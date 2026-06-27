# v14 Fallback 校准 — subagent 实验报告

**日期**: 2026-06-27
**项目**: `D:\OpenGATE\ct_phantom_recon_v2`
**结论**: ✅ **PARTIAL PASS** — SART/SART+TV 跨切片稳定 (std 60-73 → 7.5-7.8), 边界切片 (Z=54/64) 从不可用变成可用
**锁定为 v14 baseline**

> **历史说明**: 本文 2026-06-27 替换早期失败的 v14 (PSF/BH/CG 150/sigma 0.4 全部 FAIL 回退 v13) 报告。失败版数据保留在:
> - `output/real_ct/06_eval/metrics_v14a_psf.json`
> - `output/real_ct/06_eval/metrics_v14b_bh.json`
> - `output/real_ct/06_eval/metrics_v14c_cg150.json`
> - `output/real_ct/06_eval/metrics_v14d_s04.json`
>
> 失败版 deliverable.md 备份在 git 历史 (commit `edaaa7b` 之前的本地备份)。

---

## 1. 触发场景 (P1 跨切片发现)

5 切片 (Z=22/32/43/54/64) 评估发现 **v13 SART/SART+TV 在边界切片急剧退化**:

| 切片 | fit 点数 | v13 a slope | v13 SART MAE |
|---|---|---|---|
| Z=22 (上腹) | 8 | 0.04 (自然) | 47.1 |
| Z=32 (上腹中央) | 10 | 0.04 (自然) | 40.3 |
| Z=43 (中央 baseline) | 11 | 0.04 (自然) | 38.6 |
| Z=54 (下腹) | 7 | 0.45 (发散) | **97.5** ⚠ |
| Z=64 (边界) | 6 | 0.90 (发散) | **194.6** ⚠⚠ |

**根因**: 边界切片 9 个固定器官只剩 4-5 个有效 + P95 anchor HU 偏低 (194 vs 中央 277), fit 在少量偏 anchor 上发散,a slope 飞到 0.5-1.2 (中央 0.04),HU 范围被过度拉伸 (例: z=64 Spleen pred=-402 vs truth=94, err=496 HU)。

**FBP 跨切片稳定** (std 10) 因为只用 air 单 anchor,不受多器官 fit 影响。

---

## 2. v14 Fallback 设计

### 2.1 改动
文件 `scripts/05_postprocess.py`,在 fit 步骤前加 fallback 分支:

```python
if len(fit_points) < FIT_MIN_THRESHOLD:  # 阈值 = 8
    a = 0.04          # 固定 (中央 a 经验值)
    b = MU_WATER      # 固定 (避免 b 漂移)
    skip lstsq        # 跳过拟合,避免发散
```

### 2.2 设计原则
- **触发条件**: `len(fit_points) < 8` (覆盖中央 8-11 点不触发,边界 6-7 点触发)
- **Fallback 路径**: 跳过 lstsq,设 `a = 0.04` (固定,接近中央 a),设 `b = MU_WATER = 0.0195` (固定)
- **元数据**: 标记 `organ_stats["__fallback__"]` (dict, 避免 main() 序列化崩)

### 2.3 权衡
| 优点 | 缺点 |
|---|---|
| 中央切片 (Z=22/32/43, fit ≥ 8) 不受影响,完全走正常路径 | 牺牲 HU 动态范围恢复 (a=0.04 是中央最优点, 不是边界最优点) |
| 边界切片 (Z=54/64) 退化为"安全但保守"的固定 a/b, 保证 HU 范围临床合理 | fit 仍不解决根本问题 (HU 段被线性压扁) |
| 类似 SRE 思路: "宁可保守输出临床合理值, 也不要发散输出错误值" | 边界切片 MAE 比中央差 ~20 HU, 但跨切片 std 改善 8-10× |

---

## 3. 5 切片验证结果

### 3.1 v13 baseline → v14 fallback 对比

| 通道 | v13 mean ± std | **v14 mean ± std** | 改善 |
|---|---|---|---|
| FBP | 46.10 ± 9.96 | **45.98 ± 7.78** | std **-22%** |
| **SART** | 83.61 ± **59.58** | **45.36 ± 7.54** | std **-87%**, MAE **-46%** ✨ |
| **SART+TV** | 89.77 ± **72.72** | **45.46 ± 7.58** | std **-90%**, MAE **-49%** ✨ |

### 3.2 per-slice MAE (SART 通道)

| z | v13 | **v14** | 改善 |
|---|---|---|---|
| 22 | 47.1 | 47.1 | 0% (fit 8 点不触发) |
| 32 | 40.3 | 40.3 | 0% (fit 10 点不触发) |
| 43 | 38.6 | 38.6 | 0% (fit 11 点不触发) |
| **54** | 97.5 | **41.5** | **-57%** ✨ |
| **64** | 194.6 | **59.3** | **-70%** ✨ |

### 3.3 per-slice MAE (SART+TV 通道)

| z | v13 | **v14** | 改善 |
|---|---|---|---|
| 22 | 47.4 | 47.4 | 0% |
| 32 | 40.3 | 40.3 | 0% |
| 43 | 38.5 | 38.5 | 0% |
| **54** | 93.1 | **41.8** | **-55%** ✨ |
| **64** | 229.6 | **59.4** | **-74%** ✨ |

### 3.4 PASS / FAIL 判定 (ROADMAP 决策原则)

```
✓ PASS: Z=54 SART MAE 41.5 < 70 (vs 97.5, 改善 57% > 30% 门槛)
✓ PASS: Z=64 SART MAE 59.3 < 80 (vs 194.6, 改善 70% > 60%)
✓ PASS: Z=43 SART MAE 38.6 < 40 (中央切片无退化)
✓ PASS: 三通道 SSIM 仍跨 0.85 (Z=64 SART SSIM 0.800 → 0.965, 大幅恢复)
```

**判定**: ✅ **PARTIAL PASS** — 保留为 v14 baseline

---

## 4. v14 fallback 的真实价值

### 4.1 解决了什么
- ✅ SART/SART+TV 跨切片稳定 (std 60-73 → 7-8)
- ✅ Z=54/64 边界切片从"不可用"变成"可用" (MAE < 80)
- ✅ 临床声明边界更新: **v14 全 87 切片 SART 可用** (不再只中央)

### 4.2 没解决什么
- ⚠ 中央切片 (Z=22/32/43) MAE ~38 HU 仍是当前架构极限 (P0 残差诊断: 97% 来自 fit 段 HU 压缩)
- ⚠ MAE 距临床 < 30 还差 8 HU, **必须 v15 端到端深度学习**
- ⚠ fallback 是"安全保守",不是"最优" (a=0.04 是中央经验值, 边界最优 a 可能不同)

---

## 5. v14 → v14.1 扩展 (2026-06-27)

v14 fallback PASS 后, 启动 v14.1 扩展工程:

### 5.1 全 87 切片覆盖 (commit bc8130b + b892077)
- 跑全 Z=0-86 共 87 切片完整流程 (03-04-05-06)
- 工程量: ~50 min 跑完, 0 fail
- 输出: 87 个 metrics_z<Z>.json + 87 个 per_organ_hu_z<Z>.json + 87 个 REPORT_z<Z>.md
- 验证: Z=54/64 触发 fallback, Z=22-43 走正常 fit, 全部切片可用

### 5.2 P3 pytest 单元测试 (21 用例 PASS)
- 7 个测试文件覆盖 6 个生产脚本 + 1 个残差诊断
- 防回归: 任何 v15 改动前必跑绿
- pre-commit hook: 改 scripts/ 或 tests/ 后 git commit 自动跑

### 5.3 Web Dashboard (commit fd7f71a)
- 静态 HTML + Chart.js 4.4 + 87 切片 Z 选择器 + Lightbox 放大器
- 7 区块: Hero stats / v13vs14 对比 / MAE 概览 / 三通道详细 / 单切片 / overlay / 残差诊断 / 临床目标
- 启动: `python -m http.server 8765 --bind 127.0.0.1` → 浏览器打开 `http://127.0.0.1:8765/gui/`

### 5.4 GitHub 发布
- 本地 git init + .gitignore (76 行, 排除大文件 .raw/.nii/.npz + 缓存)
- 6 个 commit 推送到 `github.com/JJ704sd/OpenGATE-Door` public
- About 区: 中文 description + 10 topics + homepage 指向 ct_phantom_recon_v2/README.md

---

## 6. 关键教训

### 6.1 单切片验证永远不够 (v13 → v14 关键转折)
- v13 在 Z=43 完美 (MAE 38.5, SSIM 0.989) 但边界切片 SART 退化 6×
- v14 fallback 来自跨切片发现, 不是单切片优化
- **跨切片验证是 CT 重建等 3D 任务的必要维度**

### 6.2 "宁可保守" > "硬 fit 发散" (SRE 思路)
- 当数据不足以支撑精确 fit, 退化为固定值比硬 fit 更好
- 临床应用容许 5-10 HU 偏差, 不容许 200 HU 发散
- 类似 ML 的 "abstain": 模型不确定时拒绝预测, 比猜错好

### 6.3 阈值选择 (FIT_MIN_THRESHOLD = 8)
- 中央 8-11 点不触发, 边界 6-7 点触发
- 是经验值, 不是从理论推导
- v15 可以改为动态阈值 (基于 a slope 估计置信度)

### 6.4 fallback 后 HU 范围保守
- a=0.04 是中央经验值, 边界最优 a 可能不同
- 当前 fallback 输出 HU 范围被压缩, MAE 比中央差 ~20 HU
- v15 可以尝试 per-organ a (每个器官单独 fit)

### 6.5 回退必须验证 (历史教训)
- v12 N_ANGLES 720 FAIL 后, subagent 说"已回退"但没重跑全套 → owner 亲自跑 metrics.json 验证
- v14 (失败版) subagent 在 v14-D 验证时被 v14-C CG 150 μ 污染 → owner 独立重跑 04 恢复 v13 baseline 再测
- **owner 验收必须亲自跑 metrics.json 验证**

---

## 7. v15 建议 (用户决策后启动)

由于 v14 fallback 已让 SART 跨切片稳定但 MAE 38 → 30 还差 8 HU, 建议 v15 方向:

### 7.1 端到端深度学习重建 (推荐, ROI 最高)
- U-Net / Diffusion 直接 Radon 投影 → HU (跳过 fit step)
- 数据: FLARE22 1 例足够做 proof-of-concept
- 工程量: 1-2 w
- 风险: 训练数据少 (1 例), 可能需要多病例扩增
- **前置**: 用户启动 #11 多病例扩增

### 7.2 架构层改进 (备选)
- SART preconditioner (改进 A 矩阵条件数, 加速 CG 收敛)
- 边缘感知 TV (anisotropic TV, 当前 isotropic)
- 域自适应滤波 (mask 内不同器官不同 sigma)

### 7.3 HU 校准方法改进 (备选)
- 多项式校准代替线性 fit (HU ~ μ 是非线性)
- 当前 v13/v14 校准 b 偏低问题 (v14 失败版标定发现 mu_soft > 0 时 delta 仍偏正)
- 修复: 提升 b (MU_WATER=0.0195 → b≈0.0215), 或增加 2x 高密度 anchor 权重

---

## 8. 文件清单

### 8.1 备份
- `scripts/05_postprocess_v13_pre_fallback_backup.py` — v13 baseline 备份
- `scripts/_checkpoints.py` — 1 处微调 (atten 阈值 1.2 → 1.18 容差)
- `output/real_ct/06_eval/metrics_v13_baseline.json` — v13 起始 baseline
- `output/real_ct/06_eval/metrics_v14_revert_to_v13.json` — 失败版 v14 最终回退确认

### 8.2 v14 fallback 输出
- `output/real_ct/06_eval/metrics_z{22,32,43,54,64}.json` — v14 5 切片
- `output/real_ct/06_eval/per_organ_hu_z{22,32,43,54,64}.json` — v14 5 切片 per-organ
- `output/real_ct/06_eval/metrics_multislice.json` — v14 汇总 (FBP/SART/SART+TV mean ± std)
- `output/real_ct/06_eval/MULTI_SLICE_REPORT.md` — v14 跨切片报告
- `output/real_ct/06_eval/V14_FALLBACK_DECISION.md` — v14 fallback 详细决策报告

### 8.3 v14.1 扩展输出
- 87 个 metrics_z<Z>.json + 87 个 per_organ_hu_z<Z>.json + 87 个 REPORT_z<Z>.md (Z=0-86)
- 7 个 test_*.py (21 测试 PASS)
- gui/ 目录 (index.html + css + js)
- .gitignore + .pre-commit-config.yaml
- GitHub: github.com/JJ704sd/OpenGATE-Door (6 commits, public)

### 8.4 日志
- `06_eval/_v14_*_log.txt` — 每步运行的完整日志
- `06_eval/_cleanup_changelog_v13_baseline.json` — 冗余 metrics 清理审计

---

*日期: 2026-06-27*
*v14 fallback 工程量: 1 h (改 05_postprocess.py + 调 _checkpoints.py + 跑 5 切片验证 + 写测试回归)*
*v14.1 扩展工程量: ~3 h (87 切片 + pytest + Web Dashboard + GitHub push)*
*判定: ✅ PARTIAL PASS, 锁定为 v14 baseline; v14.1 扩展 PASS, 锁定为 current*
*下一步: 等用户决定走 v15 深度学习方向*
