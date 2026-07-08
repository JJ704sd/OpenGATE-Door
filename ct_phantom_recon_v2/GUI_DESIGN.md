# CT 重建项目 GUI 实现设计文档

> **项目**: D:\OpenGATE\ct_phantom_recon_v2  
> **当前版本**: **v14.1 baseline** (含 Web Dashboard)  
> **目标**: 桌面 GUI 应用（Streamlit 快速原型 → PySide6 生产级）  
> **设计日期**: 2026-06-23  
> **最后更新**: 2026-06-27 (Web GUI 已实施, 桌面 GUI 仍等指令)  
> **作者**: mavis (mvs_a39c7ca1dab949c68d9394df11958761)

---

## 实施状态 (2026-06-27)

### ✅ Web GUI 已实施 (v14.1, 替代 CLI + dashboard.html)

**实施位置**: `gui/` 目录  
**技术栈**: 静态 HTML + Chart.js 4.4 (CDN) + http.server  
**功能** (7 区块):
1. Hero stats — FBP/SART/SART+TV 5 切片 MAE 均值
2. §1 v13 → v14 跨切片 MAE 改善柱状图
3. §2 5 切片 MAE 详情 + Fallback 标记
4. §2.5 三通道详细 5 指标对比 (3 表 × 5 切片 × 5 维)
5. §3 当前 Z 切片详情 (随 Z 选择器联动)
6. §4 器官 overlay (261 PNG, 全 87 切片 × 3 通道)
7. §5 残差诊断 + §6 临床目标进度条

**Z 切片选择器**: 87 选项 (5 P1 + 82 其他), optgroup 分组, 切 Z 实时 fetch  
**Lightbox**: 滚轮缩放 (0.2x - 8x) + 拖拽平移 + 双击复位 + 快捷键 +/-/0/ESC  
**启动**: `python -m http.server 8765 --bind 127.0.0.1` → 浏览器 `http://127.0.0.1:8765/gui/`

详见: [`gui/README.md`](./gui/README.md)

### ⏸ 桌面 GUI 仍暂停 (用户已声明等指令)

- **阶段 1: Streamlit 快速原型** (1 天开发) — 等指令
- **阶段 2: PySide6 生产级桌面应用** (3 天开发) — 等指令
- **替代方案**: Web GUI 已覆盖 80% 用户场景 (内部研究 / 调试 / 数据探索)

本文档保留 2026-06-23 原始设计内容,作为"未来桌面 GUI 实施"的参考。

---

## 1. 现状分析

### 1.1 现有界面形态
- **CLI 命令行**: 通过 PowerShell 执行 Python 脚本（`scripts/01-06`）
- **dashboard.html**: 静态可视化（双击浏览器打开）
- **PNG 截图**: `output/real_ct/05_post/windows/*.png`

### 1.2 用户痛点
1. **状态查看不便**: 每次要看当前 metrics 必须 `cat metrics.json`
2. **流程控制繁琐**: 跑 03→04→05→06 需要手动逐个执行
3. **参数调节困难**: N_ANGLES / CG_ITER / sigma 等需要改源码
4. **版本对比不直观**: 切换 v4→v13 历史版本需手动 Copy-Item
5. **结果可视化分散**: 不同窗口位 PNG 在不同目录，需手动打开

### 1.3 设计目标
- ✅ 一键启动，自动加载 v13 baseline 状态
- ✅ 实时显示三通道指标 + 临床目标达成
- ✅ 按钮触发 01-06 任意步骤（带进度条）
- ✅ 可视化重建 HU 图（多窗位切换）
- ✅ 器官 HU 对比（真值 vs 预测）
- ✅ 历史版本切换（一键回退）
- ✅ 离线运行，不依赖外部服务

---

## 2. 技术栈选型

### 2.1 候选对比

| 维度 | **Streamlit** | **PySide6 (Qt)** | **PySimpleGUI** |
|---|---|---|---|
| **安装大小** | ~50 MB | ~500 MB | ~20 MB |
| **开发速度** | ⚡ 快（声明式） | 🐢 慢（手动布局） | ⚡ 中等 |
| **界面美观** | ⭐⭐⭐ 现代 | ⭐⭐⭐⭐⭐ 专业 | ⭐⭐ 简陋 |
| **跨平台** | ✓ 浏览器 | ✓ 原生 | ✓ 原生 |
| **离线运行** | ✓ 本地服务器 | ✓ 桌面应用 | ✓ 桌面应用 |
| **打包发布** | 难（需 WebView） | 易（PyInstaller） | 易（PyInstaller）|
| **学习曲线** | 低（Pythonic）| 中（Qt 概念）| 低 |
| **科学计算集成** | ✓ Plotly/Matplotlib | ✓ Matplotlib/QtCharts | ✓ Matplotlib |
| **适合场景** | 快速原型 / 内部工具 | 生产级 / 商业软件 | 简单工具 |

### 2.2 推荐方案：分阶段实施

#### **阶段 1: Streamlit 快速原型（1 天开发）**
- **目标**: 立即可用，覆盖 80% 功能
- **优点**: 开发快、Python 生态、Plotly 交互可视化
- **缺点**: 需启动本地 Web 服务器（端口 8501）
- **用户场景**: 内部研究 / 调试 / 数据探索

#### **阶段 2: PySide6 生产级桌面应用（3 天开发）**
- **目标**: 原生 .exe 桌面应用，可分发
- **优点**: 原生体验、离线运行、专业外观
- **缺点**: Qt 学习曲线、布局繁琐
- **用户场景**: 临床医生 / 教学 / 商业分发

---

## 3. 功能模块设计

### 3.1 模块总览

```
┌─────────────────────────────────────────────┐
│  CT 重建项目 GUI                              │
├─────────────────────────────────────────────┤
│  [1] 状态仪表板   [2] 流程控制   [3] 可视化    │
│  [4] 参数调节    [5] 版本管理    [6] 设置     │
└─────────────────────────────────────────────┘
       ↓             ↓             ↓
   metrics.json   实时进度     多窗位 PNG
   临床目标       步骤日志     器官 HU 对比
   历史趋势       错误捕获     差分热图
```

### 3.2 模块 [1] 状态仪表板

**功能**:
- 顶部 KPI 卡片：当前 MAE / SSIM / CNR / SNR
- 临床目标进度条（4/5）
- 三通道表格（FBP/SART/SART+TV）
- v4 → v13 演进时间线
- 历史版本切换器

**Streamlit 实现**:
```python
import streamlit as st
import json
from pathlib import Path

@st.cache_data
def load_metrics():
    path = Path("output/real_ct/06_eval/metrics.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

st.title("🏥 CT 重建项目状态仪表板")

# KPI 卡片
metrics = load_metrics()
if metrics:
    cols = st.columns(4)
    for col, (method, m) in zip(cols, metrics.items()):
        col.metric(
            label=f"{method.upper()} MAE",
            value=f"{m['MAE_HU']:.2f}",
            delta=f"{m['MAE_HU'] - 30:.1f} vs 临床"
        )

# 临床目标进度
st.subheader("🎯 临床目标达成")
goals = {
    "SSIM > 0.85": metrics["fbp"]["SSIM"] > 0.85,
    "MAE < 30": metrics["fbp"]["MAE_HU"] < 30,
    "CNR > 3": metrics["fbp"]["CNR"] > 3,
    "SNR > 30": metrics["fbp"]["SNR"] > 30,
}
for goal, achieved in goals.items():
    st.progress(1.0 if achieved else 0.5,
                text=f"{'✓' if achieved else '✗'} {goal}")
```

### 3.3 模块 [2] 流程控制

**功能**:
- 步骤按钮：01 下载 / 02 标定 / 03 投影 / 04 重建 / 05 后处理 / 06 评估
- 实时进度条 + 步骤日志
- 取消按钮（中止长时间运行的步骤）
- 完整流程一键执行

**Streamlit 实现**:
```python
import subprocess
from pathlib import Path

def run_step(step_name: str, script: str):
    """后台运行单个步骤，显示日志"""
    log_placeholder = st.empty()
    log_text = ""
    
    with st.status(f"运行 {step_name}...") as status:
        process = subprocess.Popen(
            ["D:\\OpenGATE\\env\\python.exe", f"scripts/{script}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in process.stdout:
            log_text += line
            log_placeholder.code(log_text[-3000:])  # 只显示最后 3000 字符
        process.wait()
        if process.returncode == 0:
            status.update(label=f"✓ {step_name} 完成", state="complete")
        else:
            status.update(label=f"✗ {step_name} 失败", state="error")

# UI
col1, col2, col3 = st.columns(3)
if col1.button("📥 01 下载", use_container_width=True):
    run_step("01 下载", "01_download_dicom.py")
if col2.button("🎯 02 标定", use_container_width=True):
    run_step("02 标定", "02_parse_and_calibrate.py")
if col3.button("📡 03 投影", use_container_width=True):
    run_step("03 投影", "03_proj_simulate.py")
# ... 04 / 05 / 06
```

### 3.4 模块 [3] 可视化

**功能**:
- 多窗位显示（肺窗 / 纵隔窗 / 骨窗 / 软组织窗）
- 通道切换（FBP / SART / SART+TV）
- 器官 HU 柱状图（真值 vs 预测）
- 差分热图（真值 - 预测）
- Z 切片切换（当前固定 z=43，可扩展）

**Streamlit 实现**:
```python
import numpy as np
import SimpleITK as sitk
import plotly.graph_objects as go

@st.cache_data
def load_recon(method: str, z: int = 43):
    """加载重建结果"""
    path = Path(f"output/real_ct/05_post/ct_post_{method}.mhd")
    if not path.exists():
        return None
    img = sitk.ReadImage(str(path))
    arr = sitk.GetArrayFromImage(img)
    return arr[0] if arr.ndim == 3 else arr  # 2D

# 窗位选择
window = st.sidebar.radio("窗位", ["肺", "纵隔", "骨", "软组织"])
WINDOWS = {"肺": (1500, -600), "纵隔": (400, 40), "骨": (1800, 400), "软组织": (400, 50)}
ww, wl = WINDOWS[window]

# 通道选择
method = st.sidebar.radio("通道", ["fbp", "sart", "sart_tv"])

# 显示图像
arr = load_recon(method)
if arr is not None:
    fig = go.Figure(data=go.Heatmap(
        z=arr, colorscale="Gray",
        zmin=wl - ww/2, zmax=wl + ww/2,
        colorbar=dict(title="HU")
    ))
    fig.update_layout(title=f"{method.upper()} - {window}窗 (WW={ww} WL={wl})")
    st.plotly_chart(fig, use_container_width=True)
```

### 3.5 模块 [4] 参数调节

**功能**:
- N_ANGLES 滑块（360 / 720）
- CG_ITER 滑块（30 / 60 / 100 / 200）
- median 滑块（3 / 5）
- gaussian sigma 滑块（0.3 / 0.5 / 0.7 / 1.0）
- HU clip 范围
- "应用并重跑" 按钮

**Streamlit 实现**:
```python
st.sidebar.header("⚙️ 参数调节")

n_angles = st.sidebar.slider("N_ANGLES", 180, 720, 360, 60)
cg_iter = st.sidebar.slider("CG 迭代次数", 30, 300, 100, 10)
median_size = st.sidebar.slider("中值滤波 size", 3, 7, 3, 2)
gauss_sigma = st.sidebar.slider("高斯 sigma", 0.1, 2.0, 0.3, 0.1)
clip_lo, clip_hi = st.sidebar.slider(
    "HU clip 范围", -1500, 4000, (-1024, 3071)
)

if st.sidebar.button("🔄 应用并重跑 03-06"):
    # 备份当前脚本
    # 修改参数
    # 重跑
    # 恢复脚本
    pass
```

### 3.6 模块 [5] 版本管理

**功能**:
- 历史版本列表（v4-v13）
- 一键回退按钮
- 当前版本显示
- 回退前自动备份当前 metrics

**Streamlit 实现**:
```python
import shutil
from datetime import datetime

VERSIONS = {
    "v13": {"date": "2026-06-23", "mae": 38.5, "ssim": 0.989},
    "v11": {"date": "2026-06-23", "mae": 42.6, "ssim": 0.987},
    "v9": {"date": "2026-06-23", "mae": 49.1, "ssim": 0.983},
    "v7": {"date": "2026-06-23", "mae": 51.4, "ssim": 0.981},
    "v6": {"date": "2026-06-23", "mae": 272.2, "ssim": 0.622},
    "v5": {"date": "2026-06-23", "mae": 395.0, "ssim": 0.402},
    "v4": {"date": "2026-06-22", "mae": 422.7, "ssim": 0.376},
}

st.sidebar.header("📚 版本管理")
for v, info in VERSIONS.items():
    with st.sidebar.expander(f"{v} ({info['date']})"):
        st.write(f"FBP MAE: {info['mae']:.1f}")
        st.write(f"SSIM: {info['ssim']:.3f}")
        if st.button(f"回退到 {v}", key=f"revert_{v}"):
            shutil.copy(
                f"scripts/05_postprocess_{v}_backup.py",
                "scripts/05_postprocess.py"
            )
            st.success(f"已回退到 {v}，请重跑 05→06")
```

### 3.7 模块 [6] 设置

**功能**:
- Python 解释器路径（默认 `D:\OpenGATE\env\python.exe`）
- 工作目录
- 主题切换（浅色 / 深色）
- 日志级别

---

## 4. 阶段 1 实现：Streamlit（1 天）

### 4.1 安装依赖
```bash
D:\OpenGATE\env\python.exe -m pip install streamlit plotly pandas
```

### 4.2 项目结构
```
scripts/
├── gui_app.py                 # Streamlit 主入口
├── gui_modules/
│   ├── __init__.py
│   ├── dashboard.py            # 模块 [1] 状态仪表板
│   ├── pipeline.py             # 模块 [2] 流程控制
│   ├── visualization.py        # 模块 [3] 可视化
│   ├── parameters.py           # 模块 [4] 参数调节
│   └── version_mgr.py          # 模块 [5] 版本管理
```

### 4.3 启动命令
```bash
D:\OpenGATE\env\python.exe -m streamlit run scripts/gui_app.py --server.port 8501
```

### 4.4 用户访问
浏览器打开 `http://localhost:8501`

### 4.5 实现时间表
| 时间 | 任务 |
|---|---|
| 上午 9:00-10:00 | 环境配置 + 依赖安装 |
| 10:00-11:00 | 模块 [1] 状态仪表板 |
| 11:00-12:00 | 模块 [2] 流程控制 |
| 13:00-14:30 | 模块 [3] 可视化（HU 图 + 器官 HU） |
| 14:30-15:30 | 模块 [4] 参数调节 |
| 15:30-16:30 | 模块 [5] 版本管理 |
| 16:30-17:00 | 测试 + 文档 |
| **总计** | **8 小时（1 天）** |

---

## 5. 阶段 2 实现：PySide6（3 天）

### 5.1 安装依赖
```bash
D:\OpenGATE\env\python.exe -m pip install PySide6 matplotlib pyqtgraph
```

### 5.2 项目结构
```
scripts/
├── gui_pyside6/
│   ├── main.py                 # PySide6 主入口
│   ├── main_window.py          # QMainWindow 主窗口
│   ├── widgets/
│   │   ├── dashboard_tab.py    # 状态仪表板 Tab
│   │   ├── pipeline_tab.py     # 流程控制 Tab
│   │   ├── viz_tab.py          # 可视化 Tab
│   │   ├── params_tab.py       # 参数调节 Tab
│   │   └── version_tab.py      # 版本管理 Tab
│   ├── workers/
│   │   └── pipeline_worker.py  # QThread 后台运行
│   └── resources/
│       └── icons/              # 图标资源
```

### 5.3 主窗口布局
```python
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CT 重建项目 - v13 baseline")
        self.resize(1400, 900)
        
        # Tab 控件
        tabs = QTabWidget()
        tabs.addTab(DashboardTab(), "📊 仪表板")
        tabs.addTab(PipelineTab(), "⚙️ 流程控制")
        tabs.addTab(VizTab(), "🖼️ 可视化")
        tabs.addTab(ParamsTab(), "🎛️ 参数调节")
        tabs.addTab(VersionTab(), "📚 版本管理")
        self.setCentralWidget(tabs)
        
        # 状态栏
        self.statusBar().showMessage("✓ v13 baseline 已加载")
```

### 5.4 后台 Worker（避免 UI 卡顿）
```python
from PySide6.QtCore import QThread, Signal

class PipelineWorker(QThread):
    progress = Signal(str)  # 日志输出
    finished = Signal(bool)  # 成功/失败
    
    def __init__(self, step_name: str, script: str):
        super().__init__()
        self.step_name = step_name
        self.script = script
    
    def run(self):
        import subprocess
        process = subprocess.Popen(
            ["D:\\OpenGATE\\env\\python.exe", f"scripts/{self.script}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in process.stdout:
            self.progress.emit(line.rstrip())
        process.wait()
        self.finished.emit(process.returncode == 0)
```

### 5.5 可视化（PySideGraph + Matplotlib）
```python
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout

class HUImageWidget(pg.ImageView):
    """HU 图显示组件，支持多窗位"""
    def __init__(self):
        super().__init__()
        self.setColorMap(pg.colormap.get('gray', source='matplotlib'))
    
    def set_window(self, ww: int, wl: int):
        """设置窗宽窗位"""
        self.setLevels(wl - ww/2, wl + ww/2)
    
    def load_hu(self, arr):
        """加载 HU 数组"""
        self.setImage(arr)
```

### 5.6 打包为 .exe
```bash
D:\OpenGATE\env\python.exe -m pip install pyinstaller
D:\OpenGATE\env\python.exe -m PyInstaller --onefile --windowed \
    --name "CT-Recon-GUI" \
    --add-data "scripts;scripts" \
    scripts/gui_pyside6/main.py
```

输出: `dist/CT-Recon-GUI.exe` (~200 MB, 包含 Qt 运行时)

### 5.7 实现时间表
| 时间 | 任务 |
|---|---|
| **Day 1** | 主窗口骨架 + Tab 框架 + 状态仪表板 + 流程控制 |
| **Day 2** | 可视化（HU 图 + 窗位 + 器官 HU 对比）+ 参数调节 |
| **Day 3** | 版本管理 + Worker 线程 + 错误处理 + PyInstaller 打包 |
| **总计** | **3 天** |

---

## 6. 安全与稳定性

### 6.1 进程隔离
- 每个步骤用 subprocess 启动独立 Python 进程
- 失败不影响 GUI 主进程
- 长时间任务可取消（`process.terminate()`）

### 6.2 文件备份
- 修改参数前自动备份 `scripts/04_reconstruct.py` 和 `05_postprocess.py`
- 回退失败可一键恢复（`scripts/_restore_backup.py`）

### 6.3 错误捕获
```python
try:
    result = subprocess.run(..., timeout=600, check=True)
except subprocess.TimeoutExpired:
    st.error("⏰ 步骤超时（> 10 min），请检查 03 投影数据")
except subprocess.CalledProcessError as e:
    st.error(f"❌ 步骤失败: {e.stderr}")
```

### 6.4 数据一致性
- GUI 显示前先验证 `metrics.json` 时间戳
- 显示"⚠ 数据可能过期，请刷新"提示

---

## 7. 测试策略

### 7.1 单元测试（pytest）
```
tests/
├── test_dashboard.py       # 测试 metrics 加载
├── test_pipeline.py        # 测试 subprocess 调用
├── test_visualization.py   # 测试 HU 数组加载 + 窗位
└── test_version_mgr.py     # 测试回退逻辑
```

### 7.2 集成测试
- 启动 GUI → 加载 metrics → 显示 OK
- 点击 "03 投影" → 后台运行 → 进度更新 → 完成
- 点击 "回退到 v11" → 文件替换 → 重跑 05→06 → metrics 变化

### 7.3 用户验收
- 5 个真实场景跑通
- 加载时间 < 3 sec
- 步骤执行时 UI 不卡顿

---

## 8. 部署与分发

### 8.1 Streamlit 部署
```bash
# 本地启动
D:\OpenGATE\env\python.exe -m streamlit run gui_app.py

# 局域网共享（其他电脑可访问）
D:\OpenGATE\env\python.exe -m streamlit run gui_app.py --server.address 0.0.0.0
```

### 8.2 PySide6 打包
```bash
# 单文件 .exe（200 MB）
pyinstaller --onefile --windowed --name CT-Recon-GUI main.py

# 文件夹模式（启动快，~150 MB 总）
pyinstaller --windowed --name CT-Recon-GUI main.py
```

### 8.3 系统要求
- **最低**: Windows 10, Python 3.11+, 4 GB RAM
- **推荐**: Windows 11, 8 GB RAM, GPU（深度学习扩展用）

---

## 9. 未来扩展

### 9.1 短期（v2.x）
- **多病例支持**: 下拉框切换 FLARE22_Tr_0001-0099
- **批量评估**: 10 例批量跑 + 统计图表
- **导出报告**: 一键生成 PDF 评估报告

### 9.2 长期（v3.0）
- **深度学习集成**: PyTorch 模型推理按钮（v15 端到端重建）
- **远程协作**: Web 部署 + 用户登录 + 多用户隔离
- **3D 可视化**: PyVista / VTK 体绘制（替代 2D HU 图）

---

## 10. 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-06-23 | 选择分阶段实施（Streamlit → PySide6）| 快速验证 + 生产级双轨 |
| 2026-06-23 | Streamlit 用 Plotly 而非 Matplotlib | 交互式可视化（缩放/平移/悬停）|
| 2026-06-23 | PySide6 用 pyqtgraph 而非 Matplotlib | 大图渲染更快（GPU 加速）|
| 2026-06-23 | 模块化设计（独立文件）| 便于测试 + 维护 + 替换 |

---

## 11. 验收清单

### 阶段 1（Streamlit）验收
- [ ] 浏览器打开 `localhost:8501` 显示仪表板
- [ ] KPI 卡片正确显示 v13 MAE 38.56 / SSIM 0.989
- [ ] 临床目标进度条正确显示 4/5 达成
- [ ] 点击 "03 投影" 后台运行，进度条更新
- [ ] 多窗位切换正常显示重建 HU 图
- [ ] 点击 "回退到 v11" 文件替换成功
- [ ] 历史版本表格按时间倒序

### 阶段 2（PySide6）验收
- [ ] 双击 `CT-Recon-GUI.exe` 启动原生窗口
- [ ] 5 个 Tab 切换无卡顿
- [ ] 后台 Worker 运行步骤时 UI 可操作
- [ ] pyqtgraph HU 图交互流畅（60 fps 缩放）
- [ ] 打包 .exe 在没装 Python 的电脑可运行

---

## 12. 下一步

1. **立即可启动（阶段 1，1 天）**: 用户批准后立即实施 Streamlit 原型
2. **可选（阶段 2，3 天）**: 用户需要原生桌面应用时启动 PySide6
3. **集成（1 周）**: 与 v15 深度学习端到端重建集成

请告诉我：
- 启动阶段 1（Streamlit）？
- 启动阶段 2（PySide6）？
- 还是先做更详细的某个模块设计？

---

*设计日期: 2026-06-23 22:25*  
*当前会话: mvs_a39c7ca1dab949c68d9394df11958761*  
*预计实施: 阶段 1 (1 天) + 阶段 2 (3 天) = 共 4 天*
