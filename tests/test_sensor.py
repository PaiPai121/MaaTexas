"""
传感器测试脚本 - 验证 MaaFramework 画面采集功能

运行方式：python tests/test_sensor.py
退出方式：在显示窗口中按 'q' 键
"""
import asyncio
import sys
from pathlib import Path

# 添加 src 到路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.toolkit import Toolkit
from control.sensor import run_sensor_feed


async def main() -> None:
    """主测试函数"""
    # 初始化框架环境
    Toolkit.init()

    # 运行传感器测试
    await run_sensor_feed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        import cv2

        cv2.destroyAllWindows()
