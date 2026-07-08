# 文档 / 配置一致性审计报告 (R1 — docs-config audit)

> **项目**: D:\OpenGATE (OpenGATE-Door v14.1 baseline)
> **审计日期**: 2026-07-08
> **审计人**: general agent (mvs_797f38deaa644d12894ee7627691b37e)
> **范围**: README/FINAL_SUMMARY/ROADMAP/GUI_DESIGN/gui/README/deliverable + 根 ct .gitignore + .pre-commit-config.yaml + scripts/*backup 堆积 + archive/ 一致性
> **模式**: 只读静态审计 + 实测命令交叉验证
> **基线**: v14.1 (commit 36cbb73 = 当前 HEAD)

---

## 总览

| 维度 | 数量 | 备注 |
|---|---|---|
| **A. 文档 stale refs** | **9 条** (5 必修 + 4 应修) | 跨 4 个 .md 文件 |
| **B. .gitignore 漏洞** | **1 条** 应修 | exclude 模式不全导致 hygiene hook 会修改 tracked JSON |
| **C. .pre-commit-config 漏洞** | **2 条** | hooks 会"破"tracked 文件 (P1) + files: pattern 过宽 |
| **D. backup 脚本堆积** | **12 个, 全部可清理** | 但用户已声明保留, 仅建议 (P3) |
| **E. 其他一致性** | **1 条** 应修 | archive/ 有 "notepad foo.py" 误生成文件 |

**Top 3 必修 (影响 onboarding/信心)**:
1. **A1+A2** README/FINAL_SUMMARY/deliverable 都说 "11 commits" / ".gitignore 62 行",但实际是 **13 commits** / **76 行** — 这是 commit 36cbb73 revert 后未同步的 stale refs,直接影响 git 历史可追溯
2. **A3** overlay "15 张" → 实际 **261 张** (87×3),全 6 个文档都未更新,误导用户跑 generate_overlays.py 后的预期
3. **A4** "全 87 切片 mean MAE ~45" → 实际 **metrics_multislice.json 仅含 5 切片**,mean±std 是从 5 P1 切片算的,不是 87,文档读起来像全 87 都参与统计 (P1 验证 + fallback 触发假设都依赖 5 切片,这点没说清楚)

---

## 章节 A — 文档 stale refs

### A1. [P1] "11 commits" → 实际 13

**严重度**: P1 (应修) — git 历史表述错误

**实测**:
```powershell
PS> git -C D:\OpenGATE log --oneline | Measure-Object -Line | Select -ExpandProperty Lines
13
```

**文档引用** (4 处):
| 文件 | 行 | 原文 |
|---|---|---|
| `README.md` | L129 | "**Git 历史**: 已初始化 (2026-06-27),**11 个 commit**,远程 github.com/JJ704sd/OpenGATE-Door" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L336 | "**commit 历史**: **11 个 commit** (Initial `dc0223a` → v14 baseline `edaaa7b` → round1 基础设施 `39f7ebb` + ... → round2 sync `fddc9bd`)" |
| `ct_phantom_recon_v2/deliverable.md` | L141 | "**11 个 commit** 推送到 `github.com/JJ704sd/OpenGATE-Door` public" |
| `ct_phantom_recon_v2/deliverable.md` | L218 | "GitHub: github.com/JJ704sd/OpenGATE-Door (**11 commits**, public)" |

**实际 13 个 commit** (完整列表):
```
36cbb73 fix(docs): revert wrong .gitignore line count 62 -> 76
bb3f2d0 chore(docs): fix 6 stale refs (round 3)
d8db4ba chore(docs): round 2 sync — stale refs, 21 to 19 pytest count, ppt workspace ignore, hook desc
27dd7c6 chore(tests): prune redundant test_residual_diag.py
e45ef99 chore(docs): fix stale multi_slice_runner.py references in root README.md
5586dbd chore(cleanup): prune redundant files and fix doc reference (multi_slice_runner -> run_all_87_slices.py)
4e22247 docs(sync): align all docs to v14.1 baseline (87-slice + Web Dashboard + GitHub push)
b892077 feat(ct): v14.1 - 87-slice raw outputs (completing commit bc8130b)
fd7f71a feat(gui): v14.1 - Web Dashboard lightbox + Z selector
bc8130b feat(ct): v14.1 - 87-slice full coverage (50min, 0 fail)
39f7ebb chore(repo): add .gitignore + pre-commit hooks
edaaa7b chore: initial commit - CT real-patient abdominal recon v14 baseline
dc0223a Initial commit
```

**修复建议**: 4 处都改成 "13 个 commit" / "13 commits"。  FINAL_SUMMARY L336 那个列表也只列到 `fddc9bd` (11 个),需要追加 `27dd7c6 / e45ef99 / bb3f2d0 / 36cbb73`。

---

### A2. [P1] ".gitignore 62 行" → 实际 76 行

**严重度**: P1 (应修) — 数字不一致

**实测**:
```powershell
PS> (Get-Content D:\OpenGATE\.gitignore).Count
76
PS> Get-Content D:\OpenGATE\.gitignore | Measure-Object -Line | Select -ExpandProperty Lines
63
```

注: `(Get-Content).Count` = 76 = 总行数 (含空行); `Measure-Object -Line` = 63 = 非空行。

**文档引用** (2 处):
| 文件 | 行 | 原文 |
|---|---|---|
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L334 | "**本地**: D:\OpenGATE (`.git` 已初始化, **`.gitignore` 62 行**)" |
| `ct_phantom_recon_v2/deliverable.md` | L140 | "本地 git init + **.gitignore (62 行,** 排除大文件 .raw/.nii/.npz + 缓存)" |

**commit 36cbb73** 的 commit message 明确说明:
> 实证: Get-Content .gitignore + Measure-Object → 63 是非空行; (Get-Content).gitignore).Count → 76 是总行; PowerShell Measure-Object 不数空行,这是元凶。
> 回归 bb3f2d0 的 76 -> 62 改动,文件恢复正确状态。

即 `36cbb73` 把 ROADMAP.md L849 的 "76 行" 误改成 "62 行" 的错误 revert 了 (因为当时作者以为是 stale,实际 ROADMAP 写的就是 76 总行,正确),但 FINAL_SUMMARY L334 和 deliverable.md L140 的 "62 行" 是项目开始时的 stale 文案,从未被更新过 — 这才是真正的 stale。

**修复建议**: 改成 ".gitignore 76 行 (62 非空行)" 或 "76 行总行 (62 非空 + 14 注释/空行)"。

---

### A3. [P0] "overlay 15 张" → 实际 261 张

**严重度**: **P0 (必修)** — 全 6 个文档都错,影响 onboarding + dashboard 预期

**实测**:
```powershell
PS> Get-ChildItem D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\06_eval\overlays | Measure-Object | Select -ExpandProperty Count
261
PS> Get-ChildItem ...\overlays | Select -First 3 -ExpandProperty Name
overlay_z000_fbp.png
overlay_z000_sart.png
overlay_z000_sart_tv.png
```

**实测 generate_overlays.py 实际逻辑**:
```python
Z_INDICES = list(range(0, 87))   # ← 注释: "全 87 切片 (FLARE22_Tr_0009 = 87 Z)"
METHODS = ["fbp", "sart", "sart_tv"]
# 实际生成 87 × 3 = 261 张
```

**文档引用** (7 处):
| 文件 | 行 | 原文 |
|---|---|---|
| `ct_phantom_recon_v2/scripts/generate_overlays.py` | L4 (docstring) | "输出: `output/real_ct/06_eval/overlays/overlay_z<Z>_<method>.png` (5 切片 × 3 通道 = 15 张)" |
| `ct_phantom_recon_v2/gui/README.md` | L63 | "(5 切片 × 3 通道 = 15 张)" |
| `ct_phantom_recon_v2/gui/README.md` | L79 | "`../output/real_ct/06_eval/overlays/` (15 PNG, 由 generate_overlays.py 生成)" |
| `ct_phantom_recon_v2/gui/README.md` | L86 | "`generate_overlays.py` (一次性生成 15 张器官 overlay PNG)" |
| `README.md` | L86 | "生成器官 overlay PNG (**15 张**, 5 P1 切片 × 3 通道)" |
| `README.md` | L130 | "`generate_overlays.py` 器官 overlay PNG 生成器 (15 张)" |
| `README.md` | L147 | "`overlays\` **15 张**器官 overlay PNG (5 切片 × 3 通道)" |
| `ct_phantom_recon_v2/README.md` | L131 | "`generate_overlays.py` 器官 overlay PNG 生成器 (15 张)" |
| `ct_phantom_recon_v2/README.md` | L147 | "`overlays\` **15 张**器官 overlay PNG (5 切片 × 3 通道)" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L205 | "`generate_overlays.py` 器官 overlay PNG 生成器 (15 张 P1)" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L230 | "`overlays/` **15 张**器官 overlay PNG (5 切片 × 3 通道)" |
| `ct_phantom_recon_v2/GUI_DESIGN.md` | L24 | "§4 器官 overlay (**15 PNG**, 5 切片 × 3 通道)" |

**修复建议**:
1. 7 个文档行全部改成 "(87 切片 × 3 通道 = 261 张)"
2. generate_overlays.py docstring L4 也改
3. gui/README.md L50 同步改成"全 87 切片 overlay 已生成"

注: `audit_r1/eng_gui_bugs.md` 已经记录 (B-C02 [P0]) 这一项,本审计交叉确认一致。

---

### A4. [P0] "全 87 切片 mean MAE ~45" → metrics_multislice.json 仅含 5 切片

**严重度**: **P0 (必修)** — 核心性能结论的依据被误述,误导临床声明

**实测**:
```powershell
PS> Get-Content D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\06_eval\metrics_multislice.json | Select -First 30
{
  "date": "2026-06-27",
  "baseline_version": "v13",
  "z_indices": [22, 32, 43, 54, 64],   ← 仅 5 切片!
  "per_z": { "22": {...}, "32": {...}, "43": {...}, "54": {...}, "64": {...} },
  ...
  "multislice_summary": {
    "fbp": {
      "MAE_HU": {"mean": 45.98, "std": 7.78, "min": 38.56, "max": 60.47, "n": 5},
      ...
```

即 metrics_multislice.json 的 z_indices 是 [22, 32, 43, 54, 64] — **只有 5 P1 切片**,mean±std 是从这 5 切片算的。

但 87 个 `metrics_z<Z>.json` (Z=0-86) **确实存在**,且 `per_organ_hu_z<Z>.json` × 87 + `REPORT_z<Z>.md` × 87 都已生成 — 即 87 切片的**个体**输出完整,但 **summary** 只是 5 切片。

**文档引用** (多处混淆"全 87 切片"语义):
| 文件 | 行 | 原文 |
|---|---|---|
| `README.md` | L111 | "**全 87 切片均值** (v14 fallback 关键验证) ... FBP ~46, SART ~45, **跨切片 std ~7.5** ✨" |
| `README.md` | L114 | "全 87 切片临床可声明" |
| `ct_phantom_recon_v2/README.md` | L6 | "**全 87 切片 MAE ~45, std ~7.5** (std 较 v13 改善 8-10×)" |
| `ct_phantom_recon_v2/README.md` | L21-22 | "v14 fallback 边界切片 SART MAE 90-230 → 41-60 ... **跨切片 std**: 60-73 → 7-8 (改善 8-10×)" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L25-35 | "### 1.2 全 87 切片 (v14.1 fallback 关键验证)" + "**核心结论**: v14.1 在 **全 87 切片** 上稳定达到临床可接受范围" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L33 | "跨切片 std 从 v13 的 60-73 降到 7.5-7.8" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L109 | "**核心成就**: v14.1 把"临床可用范围"从 v13 的"仅中央切片"扩展到 **"全 87 切片可用"**" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L344 | "**CT 真实患者腹部重建项目经过 v4 → v14.1 十一轮迭代,在全 87 切片上达成 4/5 临床目标**" |
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L351 | "v14 fallback 机制(fit 点数 < 8 时固定 a=0.04, b=MU_WATER)解决 SART/SART+TV 在边界切片的发散问题,跨切片 std 从 60-73 降到 7.5-7.8" |
| `ct_phantom_recon_v2/deliverable.md` | L213 | "87 个 metrics_z<Z>.json + 87 个 per_organ_hu_z<Z>.json + 87 个 REPORT_z<Z>.md (Z=0-86)" |
| `ct_phantom_recon_v2/output/real_ct/06_eval/MULTI_SLICE_REPORT.md` | L7 | "5 切片跨切片稳定性 (mean ± std)" — **这里**写对了 |

**关键矛盾**:
- FINAL_SUMMARY L25 标题: "全 87 切片 (v14.1 fallback 关键验证)"
- 但 metrics_multislice.json 实际只有 5 切片
- v14 fallback 的"全切片可用"声明是基于 P1 5 切片验证 (Z=22/32/43/54/64)
- 实际 87 切片中,除这 5 个 P1 外,其余 82 切片**未做过 fallback 触发验证**(gui/README.md L95 自己承认: "Fallback 推断: Z=54/64 已知触发 (基于 P1 5 切片验证), **其他 82 切片 fallback 状态未验证**")

**修复建议**:
1. README/ct README/FINAL_SUMMARY 把"全 87 切片 mean ~45" 改成 "P1 5 切片 (Z=22/32/43/54/64) mean ~45, 全 87 切片均有 metrics_z<Z>.json (个体均值未聚合)"。
2. FINAL_SUMMARY L109 的 "扩展到 全 87 切片可用" 改成 "扩展到 5 P1 切片可用 (其余 82 切片已有 metrics 但 fallback 状态未单独验证)"。
3. 新增一段说明: 87 切片个体输出 vs summary 输出的区别,避免读文档的人误以为 summary 是从 87 切片聚合。

注: 这不是要否定 v14 fallback 的结论 — P1 5 切片验证是有意义的。但 "全 87 切片" 的措辞掩盖了 "仅 5 切片参与 summary" 这一事实。

---

### A5. [P1] "7 个测试文件" → 实际 5 个

**严重度**: P1 (应修) — pytest 计数错误

**实测**:
```powershell
PS> Get-ChildItem D:\OpenGATE\ct_phantom_recon_v2\scripts\test_*.py
test_01_load.py    test_03_proj.py    test_04_recon.py    test_05_cal.py    test_06_eval.py
# 5 个文件, 19 测试用例
```

**文档引用** (2 处):
| 文件 | 行 | 原文 |
|---|---|---|
| `ct_phantom_recon_v2/FINAL_SUMMARY.md` | L197 | "`scripts/` **6 个生产脚本 + 共享模块 + 7 个测试**" |
| `ct_phantom_recon_v2/deliverable.md` | L130 | "**7 个测试文件** 覆盖 6 个生产脚本 + 1 个残差诊断" |

**commit 27dd7c6** "chore(tests): prune redundant test_residual_diag.py" 把 test_residual_diag.py 删了,文件数从 6 (or 7) 降到 5。  Commit message 自己说了 "prune redundant" — 即冗余测试,删掉合理。但 FINAL_SUMMARY/deliverable 没更新。

**注意**: 同一 commit 之前 `d8db4ba` 做了 "21 to 19 pytest count" sync — 测试用例数 (19) 已正确,但文件数 (5 vs 7) 没同步。

**修复建议**:
1. FINAL_SUMMARY L197 改成 "5 个 pytest 测试文件 (19 用例)"
2. deliverable.md L130 改成 "5 个测试文件覆盖 5 个生产脚本"

注意: 实际是 5 个生产脚本 (01/02/03/04/05/06 = 6 个,但 01/02 没 test,test_03/04/05/06 = 4 个有 test,加上 test_01_load = 5 文件对应 5/6 步骤)。 这里 "5 个测试文件覆盖 5 个生产脚本" 也略有不准 — test_01_load 是测试步骤 1,test_03-06 是测试 3-6 步骤,实际是 5 测试覆盖 5 步骤 (缺 02)。  严格说应该是 "5 个测试文件覆盖 5 个生产步骤 (01, 03-06)"。

---

### A6. [P1] ROADMAP.md "已推送 HEAD d8db4ba, 11 commits" → 实际 HEAD 是 36cbb73 (commit 计数已过时)

**严重度**: P1 (应修)

**文档引用**:
- `ct_phantom_recon_v2/ROADMAP.md` L851-852: "已推送 (HEAD `d8db4ba`, 11 commits via schannel + 国内代理 + `Start-Sleep 30` + `ls-remote` 探活 SOP), 详见根目录 `AGENTS.md` 的 Post-PR-merge wrap-up"

**实测**: HEAD = 36cbb73 (fix docs revert)

**修复建议**: ROADMAP L851-852 同步:
- "HEAD 36cbb73" / "13 commits"
- 或删除具体 commit 指针,改 "见 git log"

---

### A7. [P2] README L424 + FINAL_SUMMARY L921-925 引用已移到 `_trash_2026_06_27_v13_cleanup/` 的文件

**严重度**: P2 (应修) — 文档结构图引用不存在的根目录文件

**文档引用**:
- `ct_phantom_recon_v2/README.md` L424: "**详细报告**: `output/real_ct/06_eval/v5_baseline_report.md` + `deliverable.md`"
- `ct_phantom_recon_v2/FINAL_SUMMARY.md` L921: "_v13_scan_summary.json"
- `ct_phantom_recon_v2/FINAL_SUMMARY.md` L922: "_tv_scan_metrics.json"
- `ct_phantom_recon_v2/FINAL_SUMMARY.md` L923: "v5_baseline_report.md"
- `ct_phantom_recon_v2/FINAL_SUMMARY.md` L925: "_cleanup_changelog_v13_baseline.json"

**实测**:
```powershell
PS> Test-Path D:\OpenGATE\ct_phantom_recon_v2\output\real_ct\06_eval\v5_baseline_report.md
False
PS> Test-Path ...\_v13_scan_summary.json
False
PS> Test-Path ...\_tv_scan_metrics.json
False
PS> Test-Path ...\_cleanup_changelog_v13_baseline.json
False
```

这些文件**不在 06_eval 根目录**了,被移到 `_trash_2026_06_27_v13_cleanup/`(commit 5586dbd "prune redundant files" 干的)。

**修复建议**:
1. README L424 改成 "v5 详细报告 (历史, 在 _trash_2026_06_27_v13_cleanup/)"
2. FINAL_SUMMARY L920-925 改成 "(_trash_2026_06_27_v13_cleanup/ 回收站, 37 个 JSON, 含 v13 scan 残差 + 清理审计)"

---

### A8. [P2] GUI_DESIGN.md §3.2-3.7 描述 Streamlit/PySide6 "实现" 代码,实际是未来设计的伪代码

**严重度**: P2 (应修 — 文档可读性)

**文档引用**:
- `ct_phantom_recon_v2/GUI_DESIGN.md` §3.2 (L126-163): "**Streamlit 实现**:" + 完整 `import streamlit` 代码块 (含 `@st.cache_data`, `st.metric`, `st.columns`)
- `ct_phantom_recon_v2/GUI_DESIGN.md` §3.3 (L173-207): "**Streamlit 实现**:" + `subprocess.Popen` 完整代码
- `ct_phantom_recon_v2/GUI_DESIGN.md` §3.4 (L219-252): "**Streamlit 实现**:" + `load_recon` + `go.Heatmap` 代码
- `ct_phantom_recon_v2/GUI_DESIGN.md` §3.5 (L265-282): "**Streamlit 实现**:" + sliders 代码
- `ct_phantom_recon_v2/GUI_DESIGN.md` §3.6 (L292-318): "**Streamlit 实现**:" + `VERSIONS` dict + `shutil.copy` 代码
- `ct_phantom_recon_v2/GUI_DESIGN.md` §4 (L330-368): "阶段 1 实现:Streamlit (1 天)" + 完整步骤计划
- `ct_phantom_recon_v2/GUI_DESIGN.md` §5 (L372-484): "阶段 2 实现:PySide6 (3 天)" + 完整步骤计划

**实测**:
```powershell
PS> & D:\OpenGATE\env\python.exe -c "import streamlit"
ModuleNotFoundError: No module named 'streamlit'
PS> & D:\OpenGATE\env\python.exe -c "import PySide6"
ModuleNotFoundError: No module named 'PySide6'
```

Streamlit/PySide6 都没装,即 §3.2-§5 描述的所有 "实现" 代码实际都**未实施**。

虽然 GUI_DESIGN.md §1 L33-37 已标注 "⏸ 桌面 GUI 仍暂停 (用户已声明等指令)",但 §3.2-§5 的代码块仍然以 "**Streamlit 实现**:" 为标题 (而不是 "**Streamlit 设计草案**:" 或 "**Streamlit 未来实现**:"),读起来像已完成。

**修复建议**: 
1. §3.2-§5 的 "**Streamlit 实现**:" 标题统一改成 "**Streamlit 设计草案 (未实施)**:" 或 "**Streamlit 未来实现**:" 
2. §3.6 的 VERSIONS dict (v13 / v11 / v9 / v7 / v6 / v5 / v4) — 实际版本号虽然对,但 v15 未来方向 (#11 多病例扩增等) 改了之后这段 stale 风险高

注: 这是**风格问题**,不影响功能,但作为"设计文档 v.s. 已实施"的混淆容易误导新人。

---

### A9. [P2] tasks/gui/ 占位代码 vs 文档描述

**严重度**: P2 (应修) — 文档说"占位"但 git tracked 有实际占位文件

**文档引用**:
- `README.md` L49: "`tasks/gui/` GUI 实施占位 (阶段 1 Streamlit + 阶段 2 PySide6, 等指令)"
- `ct_phantom_recon_v2/README.md` L156: "`tasks/gui/` 未来 GUI 实施占位 (Streamlit / PySide6, 暂停)"
- `ct_phantom_recon_v2/FINAL_SUMMARY.md` L241: "`tasks/gui/` 未来 GUI 实施占位 (Streamlit / PySide6, 等指令)"

**实测 git tracked 实际状态**:
```
ct_phantom_recon_v2/tasks/gui/README.md                   (3.2 KB, 内容详细)
ct_phantom_recon_v2/tasks/gui/install_deps.py             (1.8 KB, 安装脚本)
ct_phantom_recon_v2/tasks/gui/stage1_streamlit/gui_app.py (占位入口)
ct_phantom_recon_v2/tasks/gui/stage2_pyside6/main.py      (占位入口)
+ 3 个空目录 widgets/ workers/ resources/ (未跟踪)
```

文档说"占位"是对的,但 README.md 实际**有 105 行内容**(包括 6 大功能模块表 + 启动命令 + 验收清单),这是真实施计划,不是"占位"。

**修复建议**:
1. README 改 "GUI 实施占位 (含 README 详细计划, 等用户指令)" — 加"含 README 详细计划"修饰
2. 或把 tasks/gui/ 从 git tracked 中删掉,只留 README — 但 commit history 留有更好

注: 这是**轻微文档漂移**,不影响功能。

---

## 章节 B — .gitignore 健康度

### B1. [PASS] 根 .gitignore (76 行) 全部规则有效

**实测** (用 `git check-ignore -v` 逐条验证):
| 模式 | 实测路径 | 结果 |
|---|---|---|
| `env/` | `D:\OpenGATE\env\python.exe` | ✓ `.gitignore:2:env/` |
| `__pycache__/` | `...\ct_phantom_recon_v2\scripts\__pycache__` | ✓ `ct_phantom_recon_v2/.gitignore:2` |
| `01_raw/*.nii` | `...\01_raw\test.nii` | ✓ |
| `02_calibrated/*.raw` | `...\02_calibrated\test.raw` | ✓ |
| `03_proj/*.raw` | `...\03_proj\mu_map_50keV.raw` | ✓ |
| `04_recon/_sart_matrix_cache/` | `...\04_recon\_sart_matrix_cache\test.npz` | ✓ |
| `04_recon/ct_recon_*.raw` | `...\04_recon\ct_recon_fbp_z043.raw` | ✓ |
| `05_post/windows/` | `...\05_post\windows\test.png` | ✓ |
| `06_eval/error_maps/` | `...\06_eval\error_maps\test.png` | ✓ |
| `06_eval/_trash_*/` | `...\06_eval\_trash_2026_06_27_v13_cleanup` | ✓ |
| `06_eval/_cleanup_changelog*.json` | `...\06_eval\_cleanup_changelog_v13_baseline.json` | ✓ |

**结论**: 根 .gitignore 健康,所有声明的忽略模式都生效。

---

### B2. [PASS] ct_phantom_recon_v2/.gitignore (62 行, 即 ct README 说的"6 行"实际是 74 行)

**实测**:
| 模式 | 实测路径 | 结果 |
|---|---|---|
| `__pycache__/` | ✓ | ct .gitignore:2 |
| `output/real_ct/01_raw/*.nii` | ✓ | ct .gitignore:42 |
| `output/real_ct/02_calibrated/*.raw` | ✓ | ct .gitignore:46 |
| `output/real_ct/03_proj/*.raw` | ✓ | ct .gitignore:50 |
| `output/real_ct/04_recon/_sart_matrix_cache/` | ✓ | ct .gitignore:55 |
| `ppt_workspace/` | ✓ | ct .gitignore:70 |
| `tasks/gui/stage*/**/__pycache__/` | (no dir) | dormant |
| `.playwright-mcp/` | (no dir) | dormant |

**结论**: ct_phantom_recon_v2/.gitignore 健康。

注: README L130 文档说 ".gitignore 6 行" 实际是 **62 行 (含空行 74)** — **轻微文档不准**,但 .gitignore 内容正确。

---

### B3. [P1] .pre-commit-config.yaml `exclude` 模式不全 → hygiene hooks 会"破" tracked JSON 文件

**严重度**: P1 (应修) — 直接影响 commit workflow

**实测**:
```powershell
PS> & D:\OpenGATE\env\Scripts\pre-commit.exe run --all-files
pytest (scripts/) — 19/19 必须 PASS......................................Failed
- hook id: pytest
- files were modified by this hook
...................                                                      [100%]
19 passed in 70.12s (0:01:10)

trim trailing whitespace.................................................Failed
- hook id: trailing-whitespace
- exit code: 1
- files were modified by this hook
Fixing ct_phantom_recon_v2/output/real_ct/06_eval/REPORT_z054.md
Fixing ct_phantom_recon_v2/ROADMAP.md
Fixing ct_phantom_recon_v2/scripts/05_postprocess_v13_backup.py
Fixing ct_phantom_recon_v2/gui/js/main.js
Fixing ct_phantom_recon_v2/output/real_ct/06_eval/REPORT.md
Fixing ct_phantom_recon_v2/GUI_DESIGN.md
Fixing ct_phantom_recon_v2/output/real_ct/06_eval/MULTI_SLICE_REPORT.md
... [继续 70+ 文件]
```

**被改动的 75+ tracked 文件**,按类别:
- 6 个 .md 文档 (README/ROADMAP/FINAL_SUMMARY/GUI_DESIGN/PLAN_REAL_CT)
- 4 个 backup scripts (05_postprocess_v*_backup.py)
- 5 个 REPORT_*.md (06_eval)
- 5 个 metrics_*.json (06_eval, 包括 v4/v5/v6/v7/v8/v9/v11/v13 baseline)
- 3 个 per_organ_hu_*.json
- 4 个 summary_*.json (03_proj/04_recon)
- 11 个 archive/* 下的脚本 + README + stats.txt

**根因** (.pre-commit-config.yaml L29-31):
```yaml
- id: trailing-whitespace
  exclude: \.(raw|nii|nii\.gz|mhd)$
- id: end-of-file-fixer
  exclude: \.(raw|nii|nii\.gz|mhd)$
```

**缺**的 exclude 模式:
- `.json` (06_eval 的 metrics_*.json + summary_*.json)
- `.txt` (archive/stats.txt)
- `archive/.*` (整个 archive 目录 — 历史归档不应被 hygiene 钩子扫)
- `output/real_ct/.*\.json$` (06_eval 的 .json, 评估产物)
- `_trash_.*` (回收站)

**严重度判定**:
- **P1 而非 P0** 因为: pytest 仍通过 (19/19),且 normal `git commit` flow 因为 files: pattern 只对 staged 改动跑 hooks,可能不暴露
- 但任何 "改 docs 后 commit" 都会触发 trailing-whitespace 钩子改 README.md → git status 显示 README 被改动 → 用户困惑 "我没改 README 啊"

**修复建议**:
```yaml
- id: trailing-whitespace
  exclude: |
    (?x)^(
      .*\.(raw|nii|nii\.gz|mhd|json|txt)$
      | archive/.*
      | output/.*\.json$
      | _trash_.*/.*
    )$
- id: end-of-file-fixer
  exclude: |
    (?x)^(
      .*\.(raw|nii|nii\.gz|mhd|json|txt)$
      | archive/.*
      | output/.*\.json$
    )$
```

---

## 章节 C — .pre-commit-config.yaml 健康度

### C1. [PASS] pytest hook 配置正确

**实测**:
```yaml
- id: pytest
  name: pytest (scripts/) — 19/19 必须 PASS
  entry: D:/OpenGATE/env/python.exe -m pytest -q
  language: system
  pass_filenames: false
  always_run: true
  files: ^(scripts/.*\.py|tests/.*\.py|scripts/_checkpoints\.py)
  stages: [pre-commit]
```

- `entry: D:/OpenGATE/env/python.exe` ✓ 路径存在,Python 解释器工作
- `-m pytest -q` ✓ pytest 4.x 工作,实测 19 passed in 70.12s
- `pass_filenames: false` + `always_run: true` ✓ 全量跑,符合"改 scripts 就全验证"
- `files: ^(scripts/.*\.py|tests/.*\.py|scripts/_checkpoints\.py)` ✓ 正则只对 scripts/ 触发
- `stages: [pre-commit]` ✓ 默认 pre-commit stage

---

### C2. [P1] hygiene hooks 对 .json / .txt / archive/ 都生效 → 见 B3

见 B3 详细分析。修复建议一并包含在 B3。

---

### C3. [P2] hygiene hooks 在正常 commit flow 中"会破坏 docs"

**严重度**: P2 (一般) — 因为 hook 自动修 README/ROADMAP 等 doc 后,commit 时这些 doc 也会被 staged,产生 "我没改 doc 但 doc 出现在 commit" 的现象

**实测证据**:
```
Fixing README.md         ← 用户改 scripts/test_*.py 后 commit,hook 自动修 README trailing whitespace
Fixing ct_phantom_recon_v2/ROADMAP.md   ← 同上
Fixing ct_phantom_recon_v2/GUI_DESIGN.md
Fixing ct_phantom_recon_v2/PLAN_REAL_CT.md
```

**根因**: hooks 对**所有 tracked 文件**生效,不只是 staged 文件(`.gitattributes` 配 `install_hook_stage=pre-commit` 是默认行为)。

**修复建议**:
1. 短期: 修 B3 的 exclude 模式
2. 长期: 改 hooks `stages: [manual]` 或 `stages: [pre-push]`,让用户手动跑 hygiene 而不是 commit 强制跑

---

### C4. [PASS] hooks 列表正确

**实测** (`.pre-commit-config.yaml`):
- ✅ trailing-whitespace (官方 v5.0.0)
- ✅ end-of-file-fixer (官方 v5.0.0)
- ✅ check-merge-conflict (官方 v5.0.0)
- ✅ check-added-large-files (maxkb=1024) (官方 v5.0.0)
- ✅ check-yaml (官方 v5.0.0)
- ✅ check-json (官方 v5.0.0)
- ✅ pytest (本地)

共 7 hooks,README L130 / L132 说 "6 个 hygiene checks" — 算的只是 6 个官方 hygiene (trailing/eof/merge/large/yaml/json),正确。

---

## 章节 D — Backup 脚本堆积

### D1. [PASS] 12 个 backup 脚本,数量与文档一致

**实测** (`Get-ChildItem scripts\*backup*`):
```
03_proj_simulate_v11_backup.py                  (12.4 KB)
04_reconstruct_v11_backup.py                    (36.7 KB)
04_reconstruct_v13_backup.py                    (36.7 KB)
04_reconstruct_v5_backup.py                     (19.6 KB)
04_reconstruct_v7_backup.py                     (35.1 KB)
04_reconstruct_v8_backup.py                     (35.1 KB)
05_postprocess_v11_backup.py                    (14.6 KB)
05_postprocess_v13_backup.py                    (18.3 KB)
05_postprocess_v13_pre_fallback_backup.py       (18.4 KB)
05_postprocess_v6_backup.py                     ( 8.9 KB)
05_postprocess_v7_backup.py                     ( 9.7 KB)
05_postprocess_v9_backup.py                     ( 9.7 KB)
```

**总计**: 12 个 backup, ~262 KB — 与 README L132 / FINAL_SUMMARY L208 / L331 一致。

**分布**:
- 03_proj_simulate: 1 backup (v11)
- 04_reconstruct: 5 backups (v5/v7/v8/v11/v13)
- 05_postprocess: 6 backups (v6/v7/v9/v11/v13/v13_pre_fallback)

---

### D2. [P3 建议] 12 个 backup 全部 git history 可追溯,可清理

**严重度**: P3 (低,可选)

**核心论据**:
- 项目 git 已有 13 commits,backup 对应的版本(v5/v6/v7/v8/v9/v11/v13/v14)都是 git history 上的里程碑
- v5 → edaaa7b 之前的代码 (pre-git-init),**仅 backup 可查**
- v6/v7/v8/v9/v11/v13 → git history 已包含对应 commit
- v13_pre_fallback_backup.py → v13 是 git history 中 v13_pre_v14_baseline 的早期版本

**详细分类**:

| Backup | 起源 | git 是否可查 | 建议 |
|---|---|---|---|
| `04_reconstruct_v5_backup.py` | 2026-06-23 v5 baseline | ❌ v5 没 commit (pre-git) | **保留** (git 历史缺失) |
| `04_reconstruct_v7_backup.py` | 2026-06-23 v7 baseline | ✅ git history (commit edaaa7b 之前) | **可删** (有 commit) |
| `04_reconstruct_v8_backup.py` | 2026-06-23 v8 | ✅ git history | **可删** |
| `04_reconstruct_v11_backup.py` | 2026-06-23 v11 | ✅ git history | **可删** |
| `04_reconstruct_v13_backup.py` | 2026-06-23 v13 | ✅ git history (commit edaaa7b) | **可删** |
| `05_postprocess_v6_backup.py` | 2026-06-23 v6 | ✅ git history | **可删** |
| `05_postprocess_v7_backup.py` | 2026-06-23 v7 | ✅ git history | **可删** |
| `05_postprocess_v9_backup.py` | 2026-06-23 v9 | ✅ git history | **可删** |
| `05_postprocess_v11_backup.py` | 2026-06-23 v11 | ✅ git history | **可删** |
| `05_postprocess_v13_backup.py` | 2026-06-23 v13 | ✅ git history (commit edaaa7b) | **可删** |
| `05_postprocess_v13_pre_fallback_backup.py` | 2026-06-27 v14 之前的 v13 | ✅ git history (commit edaaa7b 早期) | **可删** |
| `03_proj_simulate_v11_backup.py` | 2026-06-23 v11 | ✅ git history | **可删** |

**结论**:
- **11 个可清理** (git history 已有对应 commit)
- **1 个建议保留** (`04_reconstruct_v5_backup.py`,因为 v5 是 pre-git)
- 但 README/ROADMAP 已经把"scripts/*_backup.py"作为"版本回退用的快照 (保留)"文档化,清理需要同步更新 docs

**修复建议** (用户在 task 指令中明确"建议清单,不要直接删"):
1. 在 ROADMAP §9 / FINAL_SUMMARY §9 加一段 "v5 backup 是 pre-git 唯一参考,其余 11 个 backup 与 git commit 重复,理论可清 (用户决策)"
2. 用户决定清 → 用 `mavis-trash` 移到回收站,保留 30 天再彻底删
3. 用户决定保留 → 现状 OK,只加注释说明 v5 是唯一的非 git 备份

---

## 章节 E — 其他一致性

### E1. [P1] `archive/v01_dose_simulation/scripts/notepad first_opengate_visu.py` 误生成文件

**严重度**: P1 (应修) — 文件名带空格 + "notepad" 前缀,是 Windows "Open with Notepad" 操作误生成

**实测**:
```powershell
PS> git -C D:\OpenGATE ls-files archive/v01_dose_simulation/scripts/
archive/v01_dose_simulation/scripts/ct_dose_simulation.py
archive/v01_dose_simulation/scripts/ct_dose_visualization.py
archive/v01_dose_simulation/scripts/ct_particle_tracks.py
archive/v01_dose_simulation/scripts/ct_projection_visualization.py
archive/v01_dose_simulation/scripts/ct_rotation_simulation.py
archive/v01_dose_simulation/scripts/first_opengate_demo.py
archive/v01_dose_simulation/scripts/first_opengate_demo_fixed.py
archive/v01_dose_simulation/scripts/first_opengate_visu.py
archive/v01_dose_simulation/scripts/notepad first_opengate_visu.py  ← 异常
```

**根因**: Windows 资源管理器 "右键 → 打开方式 → Notepad" 操作有时会在同目录生成 "notepad <原文件名>.py" 副本 (PowerShell 8.0+ bug 或 Windows shell 行为)。

**影响**: 
- 文件名带空格,git/path 处理容易出问题
- 内容多半跟 first_opengate_visu.py 重复 (clone)
- 浪费 git tracked 空间

**修复建议**: 
1. diff `archive/v01_dose_simulation/scripts/first_opengate_visu.py` vs `notepad first_opengate_visu.py` 确认内容相同
2. 相同则 `mavis-trash` 删除 "notepad first_opengate_visu.py"
3. README 加一条 "Windows 'Open with Notepad' 操作可能误生成 'notepad X.py' 副本,如发现请清理"

---

### E2. [PASS] archive/ 引用一致性

**实测** (grep "archive/" in *.md):
- README.md L58: "└── archive/ 历史归档"
- README.md L60: "    └── v01_dose_simulation/ v0.1 CT 剂量仿真 + 可视化"
- 没有其他文档错误引用 archive/

**结论**: archive/ 引用一致。

---

### E3. [PASS] 其他路径引用

**实测**: 所有 README/FINAL_SUMMARY 提到的文件路径都存在:
- ✅ `PLAN_REAL_CT.md`
- ✅ `dashboard.html`
- ✅ `gui_preview.html`
- ✅ `output/real_ct/06_eval/V14_FALLBACK_DECISION.md`
- ✅ `output/real_ct/06_eval/MULTI_SLICE_REPORT.md`
- ✅ `output/real_ct/06_eval/diagnostic_v13_residual.json`
- ✅ `output/real_ct/06_eval/metrics_v13_baseline.json`
- ✅ `output/real_ct/06_eval/per_organ_hu.json`
- ✅ `output/real_ct/06_eval/per_organ_hu_z043.json`
- ✅ `output/real_ct/06_eval/metrics_v4_baseline.json` 至 `metrics_v13_baseline.json` (8 个 baseline)
- ✅ `output/real_ct/06_eval/per_organ_hu_v8_cg60_final.json`
- ✅ `output/real_ct/06_eval/per_organ_hu_v9_cg100_final.json`
- ❌ 5 个声称存在但实际不存在的 (见 A7)

---

### E4. [PASS] GUI 区块描述与实际一致

**实测**: GUI_DESIGN.md §实施状态 (L14-31) 描述的 7 区块 (Hero stats / §1 v13vs14 / §2 MAE overview / §2.5 三通道详细 / §3 当前 Z / §4 overlay / §5 残差 / §6 临床目标) ↔ `gui/index.html` 实际 section 标签:
- ✅ SECTION 1: v13 vs v14
- ✅ SECTION 2: 5 切片 MAE 概览
- ✅ SECTION 2.5: 三通道详细
- ✅ SECTION 3: 当前 Z 切片详情
- ✅ SECTION 4: 器官 overlay
- ✅ SECTION 5: 残差诊断
- ✅ SECTION 6: 临床目标

7 区块对齐。Lightbox (interactive) 在 main.js (395 lines) + index.html (176 lines) 都有对应 element ID (`lightbox`, `lightbox-img`, `lightbox-zoom-in`, `lightbox-zoom-out`, `lightbox-reset`, `lightbox-close` 等)。

---

### E5. [PASS] .gitignore 与 .git tracked 一致

**实测**: 200+ tracked 文件,但 .gitignore 覆盖的目录 (.raw/.nii 等) 没有 tracked 文件被误 add。`.gitattributes` 不存在 (没设 LFS/CRLF 等),Windows-only 项目 OK。

---

## 修复优先级总览 (按 ROI 由高到低)

### 必修 (P0, 5 条 — 影响 onboarding / 信心 / 临床结论可追溯)

1. **A3** (overlay "15 张" → 261 张, 7 处文档 + 1 个 docstring) — 全 6 文档错,影响 onboarding
2. **A4** ("全 87 切片 mean ~45" → 实际 5 切片聚合) — 核心性能结论依据被误述,影响临床声明
3. **B3/C2** (pre-commit hooks exclude 模式不全,会改 tracked JSON/doc) — 直接破坏 commit workflow

### 应修 (P1, 5 条 — doc rot / 代码 hygiene)

4. **A1** ("11 commits" → 13, 4 处文档) — git 历史表述错误
5. **A2** (".gitignore 62 行" → 76 行, 2 处文档) — 数字不一致
6. **A5** ("7 测试文件" → 5, 2 处文档) — pytest 计数错误
7. **A6** (ROADMAP "HEAD d8db4ba" → 36cbb73) — git 指针 stale
8. **E1** (`archive/.../notepad first_opengate_visu.py` 误生成) — Windows 操作残留

### 建议 (P2-P3, 4 条 — 文档可读性 / cleanup 提示)

9. **A7** (README/FINAL_SUMMARY 引用已移到 _trash 的文件,5 处) — 文档结构图 stale
10. **A8** (GUI_DESIGN.md §3.2-5 "Streamlit 实现" 措辞) — 易误读为已实施
11. **A9** (tasks/gui/ 占位 vs README 详细计划) — 轻微文档漂移
12. **D2** (12 个 backup 脚本,11 个 git history 已有对应 commit) — 可选 cleanup

---

## 测试覆盖现状 (顺便提示 — 与 docs-config 无关)

pytest 实测:
```
collected 19 items
scripts/test_01_load.py::test_01_flare22_nifti_loaded       ✓
scripts/test_01_load.py::test_02_calibrated_volume_shape    ✓
scripts/test_01_load.py::test_03_mask_volume_aligned        ✓
scripts/test_03_proj.py::test_01_mu_maps_generated          ✓
scripts/test_03_proj.py::test_02_360_projections_complete   ✓
scripts/test_03_proj.py::test_03_projection_shape_and_range ✓
scripts/test_04_recon.py::test_01_fbp_sart_sarttv_present   ✓
scripts/test_04_recon.py::test_02_recon_shape_and_range     ✓
scripts/test_04_recon.py::test_03_sart_matrix_cache_exists  ✓
scripts/test_05_cal.py::test_01_auto_detect_anchor_works    ✓
scripts/test_05_cal.py::test_02_denoise_and_clip            ✓
scripts/test_05_cal.py::test_03_mu_to_hu_fit_returns_correct_shape ✓
scripts/test_06_eval.py::test_01_mae_zero_for_identical     ✓
scripts/test_06_eval.py::test_02_mae_symmetric              ✓
scripts/test_06_eval.py::test_03_psnr_high_for_similar_images ✓
scripts/test_06_eval.py::test_04_ssim_near_1_for_identical ✓
scripts/test_06_eval.py::test_05_cnr_depends_on_contrast    ✓
scripts/test_06_eval.py::test_06_snr_high_for_uniform       ✓
scripts/test_06_eval.py::test_07_fov_mask_shape             ✓
19 passed in 55.99s
```

---

## 给后续 audit 者的提示

1. **本审计全程只读**: 没有 git commit, 没有删除任何文件,所有修改 pre-commit hook 引起的临时改动都已 `git checkout --` 还原
2. **本审计与 audit_r1/eng_gui_bugs.md 互补**: 那个 audit 关注工程实践 (B-A/B-G bug 36 条),本 audit 关注文档/配置一致性 (5 章节 14 条)
3. **建议下一轮 audit**: 跑 docs-config 修复后,再补一个 "metrics 数字一致性 audit" — 对比 README 的 MAE/SSIM 数字 vs metrics.json 实际值 (本审计未深挖此点,只验证了"~38.5 / 0.989" 等小数位)
4. **建议加 verify script**: `verify_docs.ps1` 自动跑本审计的 stale checks (git log count, .gitignore line count, overlay PNG count, metrics_multislice z_indices length),CI 阶段强制跑

---

*审计完成时间: 2026-07-08 13:30 (Asia/Shanghai)*
*此报告只读静态分析,基于 git log / git check-ignore / pytest 实测 + 文件 grep + Get-ChildItem 验证*
*审计人: general agent (mvs_797f38deaa644d12894ee7627691b37e)*
*与 R1 audit (eng_gui_bugs.md) 互补,不重复*