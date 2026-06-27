"""
main.py - CT 重建项目 PySide6 桌面应用入口
============================================
启动方式:
    D:\OpenGATE\env\python.exe tasks/gui/stage2_pyside6/main.py

打包方式:
    pyinstaller --onefile --windowed --name CT-Recon-GUI main.py
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar, QLabel
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    """主窗口 - 5 个 Tab 容器"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CT 重建项目 — v13 baseline")
        self.resize(1400, 900)

        # Tab 控件（占位）
        tabs = QTabWidget()
        tabs.addTab(self._placeholder("📊 状态仪表板"), "📊 仪表板")
        tabs.addTab(self._placeholder("⚙️ 流程控制"), "⚙️ 流程")
        tabs.addTab(self._placeholder("🖼️ 可视化"), "🖼️ 可视化")
        tabs.addTab(self._placeholder("🎛️ 参数调节"), "🎛️ 参数")
        tabs.addTab(self._placeholder("📚 版本管理"), "📚 版本")
        self.setCentralWidget(tabs)

        # 状态栏
        status_bar = QStatusBar()
        status_bar.addPermanentWidget(QLabel("● v13 baseline 已加载 · MAE 38.56 · SSIM 0.989"))
        self.setStatusBar(status_bar)

    def _placeholder(self, name: str):
        """占位 Tab"""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"{name} - 待实现（见 GUI_DESIGN.md）"))
        widget.setLayout(layout)
        return widget


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Qt 现代主题

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
