# tasks/gui/ - CT 重建 GUI 实现目录

> 基于 v13 baseline (MAE 38.5 / SSIM 0.989) 的桌面 GUI 应用
> 详细设计: [GUI_DESIGN.md](../../GUI_DESIGN.md)
> 界面预览: [gui_preview.html](../../gui_preview.html)

---

## 目录结构

```
tasks/gui/
├── README.md                     本文件
├── stage1_streamlit/             阶段 1: Streamlit 快速原型 (1 天)
│   └── gui_app.py                入口（占位，待实现）
├── stage2_pyside6/               阶段 2: PySide6 桌面应用 (3 天)
│   ├── main.py                   入口（占位，待实现）
│   ├── widgets/                  5 个 Tab 控件
│   ├── workers/                  QThread 后台 Worker
│   └── resources/                图标资源
└── tests/                        单元 + 集成测试
```

---

## 启动方式

### 阶段 1: Streamlit (浏览器)

```powershell
# 1. 安装依赖
D:\OpenGATE\env\python.exe -m pip install streamlit plotly pandas

# 2. 启动 GUI
D:\OpenGATE\env\python.exe -m streamlit run tasks/gui/stage1_streamlit/gui_app.py --server.port 8501

# 3. 浏览器打开
# http://localhost:8501
```

### 阶段 2: PySide6 (桌面应用)

```powershell
# 1. 安装依赖
D:\OpenGATE\env\python.exe -m pip install PySide6 matplotlib pyqtgraph

# 2. 启动 GUI
D:\OpenGATE\env\python.exe tasks/gui/stage2_pyside6/main.py

# 3. 打包成 .exe (可选)
D:\OpenGATE\env\python.exe -m pip install pyinstaller
D:\OpenGATE\env\python.exe -m PyInstaller --onefile --windowed --name CT-Recon-GUI tasks/gui/stage2_pyside6/main.py
# 输出: dist/CT-Recon-GUI.exe (~200 MB)
```

---

## 当前状态 (2026-06-23)

- [x] 目录骨架创建
- [x] 阶段 1 占位入口 (gui_app.py)
- [x] 阶段 2 占位入口 (main.py)
- [x] 设计文档 (GUI_DESIGN.md)
- [x] 界面预览 (gui_preview.html)
- [ ] 模块 ①-⑥ 实现
- [ ] 单元测试 + 集成测试
- [ ] 打包分发

---

## 6 大功能模块

| # | 模块 | 关键功能 | 实现优先级 |
|---|---|---|---|
| ① | 状态仪表板 | KPI 卡片、临床目标进度、v4→v13 演进 | P0 |
| ② | 流程控制 | 6 步骤按钮、实时进度、日志输出 | P0 |
| ③ | 可视化 | 多窗位 HU 图、通道切换、器官 HU 对比 | P1 |
| ④ | 参数调节 | 滑块控件、应用重跑 | P2 |
| ⑤ | 版本管理 | v4-v13 一键回退、自动备份 | P1 |
| ⑥ | 设置 | 解释器路径、主题 | P3 |

---

## 验收清单

### 阶段 1 (Streamlit)
- [ ] 浏览器打开 `localhost:8501` 显示仪表板
- [ ] KPI 卡片正确显示 v13 MAE 38.56 / SSIM 0.989
- [ ] 临床目标进度条正确显示 4/5 达成
- [ ] 点击 "03 投影" 后台运行，进度条更新
- [ ] 多窗位切换正常显示重建 HU 图
- [ ] 点击 "回退到 v11" 文件替换成功
- [ ] 历史版本表格按时间倒序

### 阶段 2 (PySide6)
- [ ] 双击 `CT-Recon-GUI.exe` 启动原生窗口
- [ ] 5 个 Tab 切换无卡顿
- [ ] 后台 Worker 运行步骤时 UI 可操作
- [ ] pyqtgraph HU 图交互流畅（60 fps 缩放）
- [ ] 打包 .exe 在没装 Python 的电脑可运行

---

*创建日期: 2026-06-23 22:27*
*当前会话: mvs_a39c7ca1dab949c68d9394df11958761*
