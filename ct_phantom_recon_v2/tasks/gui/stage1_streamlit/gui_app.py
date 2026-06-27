"""
gui_app.py - CT 重建项目 Streamlit GUI 入口
=============================================
启动方式:
    D:\OpenGATE\env\python.exe -m streamlit run scripts/gui_app.py --server.port 8501

然后浏览器打开 http://localhost:8501
"""

import streamlit as st

st.set_page_config(
    page_title="CT 重建 v13 baseline",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 主入口占位
st.title("🏥 CT 重建项目 — v13 baseline")
st.markdown("""
**当前状态**: v13 baseline (MAE 38.5 / SSIM 0.989 / SNR 11.0)

**实现计划**: 见 `GUI_DESIGN.md` (分阶段: Streamlit 1 天 → PySide6 3 天)

**当前文件**: 占位入口，待实现 6 大模块：
- ① 状态仪表板 · ② 流程控制 · ③ 可视化
- ④ 参数调节 · ⑤ 版本管理 · ⑥ 设置
""")

with st.expander("📋 实施任务清单（点击展开）"):
    st.markdown("""
### 阶段 1: Streamlit 快速原型 (1 天)

- [ ] 模块 ① 状态仪表板（KPI + 临床目标进度条）
- [ ] 模块 ② 流程控制（6 步骤按钮 + 实时进度）
- [ ] 模块 ③ 可视化（HU 图 + 多窗位 + 器官 HU 对比）
- [ ] 模块 ④ 参数调节（滑块 + 应用重跑）
- [ ] 模块 ⑤ 版本管理（v4-v13 历史回退）
- [ ] 模块 ⑥ 设置（解释器路径 / 主题）
- [ ] 单元测试 + 集成测试
- [ ] 部署文档

### 阶段 2: PySide6 桌面应用 (3 天)

- [ ] QMainWindow 骨架 + 5 个 Tab
- [ ] QThread 后台 Worker（避免 UI 卡顿）
- [ ] pyqtgraph HU 图（GPU 加速交互）
- [ ] PyInstaller 打包 .exe
- [ ] 用户验收测试
""")

# 占位 KPI 卡片
col1, col2, col3, col4 = st.columns(4)
col1.metric("FBP MAE", "38.56", "-89% vs v4")
col2.metric("SSIM", "0.989", "+107% vs v4")
col3.metric("SNR (SART+TV)", "11.00", "from -0.2")
col4.metric("临床目标", "4 / 5", "SSIM ✓ · MAE ~ · CNR ✗")

st.info("👆 这是占位入口。完整实现请参见 `GUI_DESIGN.md` 设计文档。")
