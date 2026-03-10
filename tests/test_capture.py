"""
桌面/窗口捕获工具 - 使用纯 pywin32 实现

不依赖 MaaFramework，用于快速验证画面采集功能
"""
import asyncio
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32api

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from utils.toolkit import Toolkit

logger = logging.getLogger(__name__)


def find_window_by_title(title: str) -> int:
    """根据窗口标题查找窗口句柄（模糊匹配）"""
    results = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if title.lower() in window_title.lower():
                results.append(hwnd)
        return True

    win32gui.EnumWindows(enum_callback, None)
    return results[0] if results else 0


def capture_desktop() -> np.ndarray:
    """捕获整个桌面"""
    hwnd = win32gui.GetDesktopWindow()
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    rect = win32gui.GetClientRect(hwnd)
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]

    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)

    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return img_bgr


def capture_window(hwnd: int) -> np.ndarray | None:
    """捕获指定窗口"""
    if not win32gui.IsWindow(hwnd):
        return None

    rect = win32gui.GetWindowRect(hwnd)
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

    bmpstr = bitmap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return img_bgr


async def run_capture_feed(target_window: str | None = None) -> None:
    """
    运行画面采集流

    Args:
        target_window: 目标窗口标题，为 None 时捕获桌面
    """
    logger.info("启动画面采集流...")

    if target_window:
        hwnd = find_window_by_title(target_window)
        if hwnd == 0:
            logger.error(f"未找到窗口：{target_window}")
            return
        logger.info(f"目标窗口句柄：{hwnd:#x}")
        capture_func = lambda: capture_window(hwnd)
    else:
        logger.info("捕获模式：桌面")
        capture_func = capture_desktop

    frame_count = 0

    try:
        while True:
            frame = capture_func()

            if frame is not None:
                frame_count += 1
                title = "MaaTexas - Desktop Feed" if not target_window else f"MaaTexas - {target_window}"
                cv2.imshow(title, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("检测到退出信号 'q'")
                    break

            await asyncio.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("检测到用户中断 (Ctrl+C)")
    finally:
        cv2.destroyAllWindows()
        logger.info(f"采集结束，共接收 {frame_count} 帧")


async def main() -> None:
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="桌面/窗口画面采集测试")
    parser.add_argument(
        "-w", "--window",
        type=str,
        default=None,
        help="目标窗口标题（模糊匹配），不指定则捕获桌面"
    )
    args = parser.parse_args()

    Toolkit.init()
    await run_capture_feed(args.window)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        cv2.destroyAllWindows()
