# -*- coding: utf-8 -*-
"""
一键打包脚本
生成 dist/爱客服采集客户端/ 目录，可直接分发
"""
import subprocess
import sys
import os


def build():
    """使用 PyInstaller 打包应用"""
    project_root = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=爱客服采集客户端",
        "--windowed",
        "--onedir",
        "--noconfirm",
        "--clean",
        # 图标（如果存在）
        *(["--icon=assets/icon.ico"] if os.path.exists(os.path.join(project_root, "assets", "icon.ico")) else []),
        # 附加数据
        "--add-data=browser_plugin;browser_plugin",
        *(["--add-data=assets;assets"] if os.path.exists(os.path.join(project_root, "assets")) else []),
        # 隐式导入
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=qfluentwidgets",
        "--hidden-import=playwright",
        "--hidden-import=pymysql",
        "--hidden-import=sqlalchemy.dialects.mysql",
        "--hidden-import=sqlalchemy.dialects.mysql.pymysql",
        "--hidden-import=Crypto",
        "--hidden-import=aiohttp",
        "--hidden-import=websockets",
        # 收集整个包
        "--collect-all=qfluentwidgets",
        "--collect-all=playwright",
        # 主脚本
        "app.py",
    ]

    print("🔨 开始打包...")
    print("命令:", " ".join(cmd))

    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode == 0:
        print()
        print("✅ 打包完成！")
        print(f"📁 输出目录: {os.path.join(project_root, 'dist', '爱客服采集客户端')}")
    else:
        print("❌ 打包失败，请检查上方错误信息")
        sys.exit(1)


if __name__ == "__main__":
    build()
