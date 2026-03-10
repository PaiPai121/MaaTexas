"""
MaaFramework 相机管道测试 - 基于 Win32Controller 的游戏画面采集

运行方式：python tests/test_mf_camera.py
退出方式：在显示窗口中按 'q' 键
"""
import asyncio
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
import win32gui

# 添加 src 到路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.toolkit import Toolkit
from maa.controller import Win32Controller, MaaWin32ScreencapMethodEnum
from maa.resource import Resource
from maa.tasker import Tasker

logger = logging.getLogger(__name__)


def find_window_by_title(title: str) -> int:
    """
    根据窗口标题查找窗口句柄

    Args:
        title: 窗口标题（支持模糊匹配）

    Returns:
        int: 窗口句柄，未找到返回 0
    """
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if title.lower() in window_title.lower():
                return hwnd
        return True

    hwnd = 0
    win32gui.EnumWindows(callback, None)

    # 重新枚举获取实际句柄
    def enum_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if title.lower() in window_title.lower():
                results.append(hwnd)
        return True

    results = []
    win32gui.EnumWindows(enum_callback, results)

    if results:
        return results[0]
    return 0


async def test_camera_pipeline(target_window: str | None = None) -> None:
    """
    测试 MaaFramework 相机管道

    Args:
        target_window: 目标窗口标题，为 None 时捕获整个桌面
    """
    logger.info("启动 MaaFramework 相机管道测试...")

    hwnd = 0
    if target_window:
        logger.info(f"正在查找窗口：{target_window}")
        hwnd = find_window_by_title(target_window)

        if hwnd == 0:
            logger.error(f"未找到窗口：{target_window}")
            logger.info("请确保目标窗口已打开")
            return

        logger.info(f"找到窗口句柄：{hwnd:#x}")
    else:
        logger.info("未指定窗口，将捕获整个桌面")

    # 实例化 Win32 控制器
    # hWnd=0 表示捕获整个桌面，非零则捕获指定窗口
    # 使用 GDI 截图方法（兼容性更好）
    controller = Win32Controller(
        hWnd=hwnd,
        screencap_method=MaaWin32ScreencapMethodEnum.GDI,
    )

    # 初始化资源和任务器
    resource = Resource()
    tasker = Tasker()

    # 关联资源和控制器（新版 API）
    tasker.bind(resource, controller)

    logger.info("控制器已初始化，开始捕获画面...")
    frame_count = 0

    try:
        while True:
            # 执行截图（异步作业）
            job = controller.post_screencap()

            # 等待作业完成（done 是属性不是方法）
            while not job.done:
                await asyncio.sleep(0.01)
            
            # 获取缓存的截图
            try:
                img_bgr = controller.cached_image
            except RuntimeError:
                # cached_image 在无图像时会抛异常
                img_bgr = None

            if img_bgr is not None:
                frame_count += 1
                title = "MaaTexas - Desktop Feed" if not target_window else f"MaaTexas - {target_window}"
                cv2.imshow(title, img_bgr)

                # 监听退出信号
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("检测到退出信号 'q'")
                    break

            # 限制帧率
            await asyncio.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("检测到用户中断 (Ctrl+C)")
    finally:
        cv2.destroyAllWindows()
        logger.info(f"相机管道测试结束，共接收 {frame_count} 帧")


async def main() -> None:
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="MaaFramework 相机管道测试")
    parser.add_argument(
        "-w", "--window",
        type=str,
        default=None,
        help="目标窗口标题（模糊匹配），不指定则捕获桌面"
    )
    args = parser.parse_args()

    Toolkit.init()
    await test_camera_pipeline(args.window)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        cv2.destroyAllWindows()
