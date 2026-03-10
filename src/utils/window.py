"""
MaaTexas 窗口管理工具。

提供窗口枚举、查找等功能。
"""

import logging
from dataclasses import dataclass
from typing import Optional

import win32gui
import win32con

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    """窗口信息数据类。

    Attributes:
        hwnd: 窗口句柄。
        title: 窗口标题。
        class_name: 窗口类名。
        is_visible: 是否可见。
    """
    hwnd: int
    title: str
    class_name: str
    is_visible: bool

    def display_name(self) -> str:
        """生成显示名称。

        Returns:
            str: 格式化的显示名称，包含标题和句柄。
        """
        return f"{self.title} (0x{self.hwnd:x})"


def enumerate_windows(
    visible_only: bool = True,
    min_title_length: int = 1,
    exclude_patterns: Optional[list[str]] = None
) -> list[WindowInfo]:
    """枚举系统中的窗口。

    Args:
        visible_only: 是否只枚举可见窗口。
        min_title_length: 窗口标题最小长度（过滤无标题窗口）。
        exclude_patterns: 要排除的窗口标题模式（支持子字符串匹配）。

    Returns:
        list[WindowInfo]: 窗口信息列表，按句柄排序。
    """
    if exclude_patterns is None:
        exclude_patterns = [
            "Program Manager",
            "Windows Input Experience",
            "NVIDIA",
            "Microsoft Text Input Application",
        ]

    results: list[WindowInfo] = []

    def enum_callback(hwnd: int, _: list[WindowInfo]) -> bool:
        try:
            # 检查可见性
            if visible_only and not win32gui.IsWindowVisible(hwnd):
                return True

            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)
            if len(title) < min_title_length:
                return True

            # 检查排除模式
            if any(pattern.lower() in title.lower() for pattern in exclude_patterns):
                return True

            # 获取窗口类名
            class_name = win32gui.GetClassName(hwnd)

            # 添加到结果
            results.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                is_visible=win32gui.IsWindowVisible(hwnd)
            ))

        except Exception as e:
            logger.debug(f"枚举窗口时出错：{e}")

        return True

    win32gui.EnumWindows(enum_callback, results)

    # 按标题排序
    results.sort(key=lambda w: w.title.lower())

    return results


def find_window_by_title(title: str, fuzzy: bool = True) -> Optional[int]:
    """根据窗口标题查找窗口句柄。

    Args:
        title: 窗口标题。
        fuzzy: 是否使用模糊匹配（子字符串匹配）。

    Returns:
        Optional[int]: 窗口句柄，未找到返回 None。
    """
    windows = enumerate_windows()

    for window in windows:
        if fuzzy:
            if title.lower() in window.title.lower():
                return window.hwnd
        else:
            if title.lower() == window.title.lower():
                return window.hwnd

    return None


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """获取窗口矩形区域。

    Args:
        hwnd: 窗口句柄。

    Returns:
        tuple[int, int, int, int]: (left, top, right, bottom) 坐标。
    """
    return win32gui.GetWindowRect(hwnd)


def get_window_size(hwnd: int) -> tuple[int, int]:
    """获取窗口尺寸。

    Args:
        hwnd: 窗口句柄。

    Returns:
        tuple[int, int]: (width, height) 尺寸。
    """
    rect = get_window_rect(hwnd)
    return (rect[2] - rect[0], rect[3] - rect[1])
