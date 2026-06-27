"""
install_deps.py - 安装 GUI 所需依赖
=====================================
⚠️ 等待用户批准后再执行

阶段 1 (Streamlit):
    streamlit, plotly, pandas

阶段 2 (PySide6):
    PySide6, pyqtgraph

打包 (可选):
    pyinstaller
"""

import subprocess
import sys

PYTHON = r"D:\OpenGATE\env\python.exe"


def install(packages: list[str], stage: str):
    """安装指定 stage 的依赖"""
    print(f"\n=== 安装 {stage} ===")
    print(f"命令: {PYTHON} -m pip install {' '.join(packages)}")
    print(f"包: {', '.join(packages)}\n")

    # 询问确认（实际运行时由用户授权）
    confirm = input(f"确认安装 {len(packages)} 个包? [y/N]: ")
    if confirm.lower() != "y":
        print("已取消")
        return

    cmd = [PYTHON, "-m", "pip", "install", "--no-cache-dir"] + packages
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print(f"\n✓ {stage} 安装成功")
    else:
        print(f"\n✗ {stage} 安装失败 (returncode={result.returncode})")


if __name__ == "__main__":
    print("CT 重建 GUI 依赖安装")
    print("=" * 40)
    print("[1] 阶段 1: Streamlit (~50 MB)")
    print("    streamlit, plotly, pandas")
    print()
    print("[2] 阶段 2: PySide6 (~500 MB)")
    print("    PySide6, pyqtgraph")
    print()
    print("[3] 全部安装")
    print("[0] 退出")

    choice = input("\n请选择 [0/1/2/3]: ")

    STAGE1 = ["streamlit", "plotly", "pandas"]
    STAGE2 = ["PySide6", "pyqtgraph"]
    ALL = STAGE1 + STAGE2

    if choice == "1":
        install(STAGE1, "阶段 1: Streamlit")
    elif choice == "2":
        install(STAGE2, "阶段 2: PySide6")
    elif choice == "3":
        install(STAGE2, "阶段 2: PySide6")
        install(STAGE1, "阶段 1: Streamlit")
    else:
        print("退出")
