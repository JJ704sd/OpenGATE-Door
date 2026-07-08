# v14 CT 重建 Dashboard — 启动指南

> **类型**: 静态 HTML + Chart.js + 器官 overlay PNG
> **依赖**: Python 3.x (内置 http.server)
> **数据源**: `output/real_ct/06_eval/*.json` + `overlays/*.png` (实时读)

---

## 1. 启动

```powershell
# 确保 server 没在跑 (不同 PID 会冲突)
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -like "*http.server*"}

# 启动
Start-Process -FilePath "D:\OpenGATE\env\python.exe" `
  -ArgumentList "-m","http.server","8765","--bind","127.0.0.1" `
  -WorkingDirectory "D:\OpenGATE\ct_phantom_recon_v2" `
  -PassThru -WindowStyle Hidden

# 浏览器打开
# http://127.0.0.1:8765/gui/
```

> ⚠️ **不能用 `file://` 直接打开 `index.html`** — 现代浏览器禁止 `file://` 协议下 fetch 本地 JSON, 必须通过 HTTP server.

---

## 2. 页面布局 (6 个区块)

| 区块 | 内容 | 数据源 | 交互 |
|---|---|---|---|
| Header | 标题 + 数据加载状态 | — | — |
| **Z 切片选择器** | **下拉选 87 切片 (P1 5 + 其他 82)** | — | **切换 Z 实时刷新** |
| Hero stats | FBP/SART/SART+TV 5 切片 MAE 均值 | metrics_multislice.json | — |
| §1 v13 → v14 对比 | 跨切片 MAE 改善柱状图 | 硬编码 (v13 baseline + v14 fallback) | — |
| §2 5 切片 MAE 详情 | per-slice 折线 + 表格 + Fallback 标记 + 位置标签 | metrics_multislice.json | — |
| **§2.5 三通道详细 5 指标对比** | **3 张表 (FBP/SART/SART+TV) × 5 切片 × 5 维 (MAE/PSNR/SSIM/CNR/SNR)** | metrics_multislice.json | **边界切片高亮** |
| **§3 当前 Z 切片详情** | **3 通道表格 (MAE/PSNR/SSIM/CNR/SNR)** | metrics_z<Z>.json | **随 Z 选择器联动** |
| **§4 器官 overlay** | **3 张 PNG (truth/pred/error/overlay)** | overlays/overlay_z<Z>_<method>.png | **随 Z 选择器联动** |
| §5 v13 残差诊断 | per-organ / per-HU-bucket / per-radial 三图 | diagnostic_v13_residual.json | — |
| §6 临床目标 | 4 进度条 (MAE/SSIM/PSNR/SNR) | metrics_multislice.json | — |

---

## 3. Z 切片选择器

**默认值**: Z=43 (中央 baseline)
**5 个 P1 切片**: 22, 32, 43, 54, 64 (有 overlay + 5 维 metrics)
**其他 82 切片**: 仅 metrics_z<Z>.json 存在 (overlay PNG 未生成, 显示提示)

切换后实时刷新:
- 单切片 3 通道表格 (MAE/PSNR/SSIM/CNR/SNR)
- Fallback 状态 pill (Z=54/64 已触发, 其他未触发)
- Overlay 3 张 PNG

---

## 4. 数据更新流程

如果重新跑了 `run_all_87_slices.py` 或 `06_evaluate.py`:
- **F5 刷新浏览器** (fetch 加了 `cache: no-store`)
- **新增 overlay PNG**: `D:\OpenGATE\env\python.exe scripts\generate_overlays.py` (全 87 切片 × 3 通道 = 261 张)

---

## 5. 文件清单

```
gui/
├── index.html          主页面 (6 区块 + Z 选择器)
├── css/
│   └── styles.css      美学 (对齐原 dashboard.html)
├── js/
│   ├── data_loader.js  动态 JSON fetch (含 Z 切片函数)
│   ├── charts.js       5 个 Chart.js 图
│   └── main.js         入口 + Z 选择器 + overlay grid
├── README.md           本文件
└── ../output/real_ct/06_eval/overlays/  (261 PNG, 全 87 切片 × 3 通道, 由 generate_overlays.py 生成)
```

后端脚本:
```
scripts/
├── 03_proj_simulate.py / 04_reconstruct.py / 05_postprocess.py / 06_evaluate.py
└── generate_overlays.py   (一次性生成 261 张器官 overlay PNG, 全 87 切片 × 3 通道)
```

---

## 6. 已知限制

- **静态 HTML, 无后端**: 不会触发 03-04-05-06 重跑, 只读已生成的 JSON + PNG
- **5 个 slice overlay**: 当前只 P1 选定的 [22, 32, 43, 54, 64] 有 PNG; 其他 82 切片需跑 `generate_overlays.py` 才会有
- **Fallback 推断**: Z=54/64 已知触发 (基于 P1 5 切片验证), 其他 82 切片 fallback 状态未验证
- **v13 vs v14 数字**: §1 柱状图 v13 baseline 数字硬编码在 `charts.js` (v14 fallback 时不会自动更新 v13 baseline)

---

## 7. 常见命令

```powershell
# 启动 server
Start-Process -FilePath "D:\OpenGATE\env\python.exe" `
  -ArgumentList "-m","http.server","8765","--bind","127.0.0.1" `
  -WorkingDirectory "D:\OpenGATE\ct_phantom_recon_v2" `
  -PassThru -WindowStyle Hidden

# 找 server PID
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object OwningProcess

# 停 server
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }

# 重新生成 overlay (改了 03-06 后)
D:\OpenGATE\env\python.exe D:\OpenGATE\ct_phantom_recon_v2\scripts\generate_overlays.py

# 重跑 5 切片 (改了 03-06 后)
D:\OpenGATE\env\python.exe D:\OpenGATE\ct_phantom_recon_v2\scripts\run_all_87_slices.py
```

---

## 8. 后续可扩展 (用户解锁后)

- [ ] 加 v15 深度学习端到端重建 (用户已声明等指令)
- [ ] 多病例对比 (FLARE22 0001~0099) — 需 #11 数据扩增 (等指令)
- [ ] 后端集成 (FastAPI) 支持"刷新页面自动跑 pipeline"
- [ ] 历史版本切换器 (v4 → v13 → v14)
- [ ] 87 切片全部生成 overlay (一次性跑完 generate_overlays.py 加循环)

---

*日期: 2026-06-27*
*v14 fallback 已生效, Z 切片选择器 + 器官 overlay 已加*
*作者: mavis direct*
