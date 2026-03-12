"""
MaaTexas 控制模块 - 动作执行器。

使用 Windows PostMessage 实现后台无感点击，不占用物理鼠标。
"""

import logging
import time
from typing import Optional

import win32api
import win32con
import win32gui

from src.planning.models import ActionCommand, ActionType

logger = logging.getLogger(__name__)


class ActionExecutor:
    """动作执行器。

    使用 Windows PostMessage 发送后台鼠标消息，实现无感点击。
    不会强制将窗口拉到前台，也不会占用真实物理鼠标。

    Attributes:
        hwnd: 目标窗口句柄。0 表示全局桌面模式。

    Example:
        ```python
        executor = ActionExecutor(hwnd=12345)
        success = executor.execute(action_command)
        ```
    """

    def __init__(self, hwnd: int = 0) -> None:
        """初始化动作执行器。

        Args:
            hwnd: 目标窗口句柄。如果为 0，则默认作用于全局桌面。
        """
        self.hwnd = hwnd
        logger.info(f"ActionExecutor 已初始化，目标句柄：0x{hwnd:x}")

    def execute(self, command: ActionCommand) -> bool:
        """执行动作命令。

        Args:
            command: 要执行的动作命令。

        Returns:
            bool: 执行是否成功。
        """
        try:
            # 只处理 CLICK 类型动作
            if command.action_type != ActionType.CLICK:
                logger.warning(f"不支持的动作类型：{command.action_type}")
                return False

            # 检查坐标有效性
            if not command.target_coords or len(command.target_coords) != 2:
                logger.error("无效的点击坐标")
                return False

            x, y = command.target_coords
            logger.info(f"准备执行点击：({x}, {y})")

            # 根据是否有目标窗口选择不同的执行方式
            if self.hwnd == 0:
                # 全局桌面模式：使用物理鼠标
                return self._execute_global_click(x, y, command.duration_ms)
            else:
                # 特定窗口模式：使用 PostMessage 后台点击
                return self._execute_background_click(x, y, command.duration_ms)

        except Exception as e:
            logger.error(f"执行失败：{type(e).__name__}: {e}")
            return False

    def _execute_global_click(
        self,
        x: int,
        y: int,
        duration_ms: int = 100
    ) -> bool:
        """执行全局桌面点击（使用物理鼠标）。

        Args:
            x: 屏幕 X 坐标。
            y: 屏幕 Y 坐标。
            duration_ms: 点击持续时间（毫秒）。

        Returns:
            bool: 执行是否成功。
        """
        try:
            logger.info(f"[全局模式] 移动鼠标到 ({x}, {y})")

            # 移动物理鼠标
            win32api.SetCursorPos((x, y))
            time.sleep(0.01)  # 短暂延迟确保移动完成

            # 发送鼠标按下消息
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            logger.debug("鼠标左键按下")

            # 等待持续时间
            time.sleep(max(duration_ms / 1000.0, 0.05))

            # 发送鼠标抬起消息
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            logger.debug("鼠标左键抬起")

            logger.info("[全局模式] 点击完成")
            return True

        except Exception as e:
            logger.error(f"[全局模式] 执行失败：{e}")
            return False

    def _execute_background_click(
        self,
        x: int,
        y: int,
        duration_ms: int = 100
    ) -> bool:
        """执行后台窗口点击（使用 PostMessage，不影响物理鼠标）。

        Args:
            x: 窗口客户区 X 坐标（相对坐标）。
            y: 窗口客户区 Y 坐标（相对坐标）。
            duration_ms: 点击持续时间（毫秒）。

        Returns:
            bool: 执行是否成功。
        """
        try:
            # 检查窗口是否有效
            if not win32gui.IsWindow(self.hwnd):
                logger.error(f"窗口句柄 0x{self.hwnd:x} 无效")
                return False

            # 检查窗口是否可见
            if not win32gui.IsWindowVisible(self.hwnd):
                logger.warning(f"窗口 0x{self.hwnd:x} 不可见")

            # 将相对坐标打包为 lParam 格式 (低 16 位=X, 高 16 位=Y)
            lparam = win32api.MAKELONG(x, y)
            logger.info(f"[后台模式] 窗口 0x{self.hwnd:x} 坐标 ({x}, {y}) -> lParam={lparam}")

            # 发送 WM_LBUTTONDOWN 消息（后台鼠标按下）
            # wParam = MK_LBUTTON (0x0001) 表示左键按下
            win32api.PostMessage(
                self.hwnd,
                win32con.WM_LBUTTONDOWN,
                win32con.MK_LBUTTON,
                lparam
            )
            logger.debug("已发送 WM_LBUTTONDOWN")

            # 等待持续时间（保底 50ms）
            time.sleep(max(duration_ms / 1000.0, 0.05))

            # 发送 WM_LBUTTONUP 消息（后台鼠标抬起）
            # wParam = 0 表示左键释放
            win32api.PostMessage(
                self.hwnd,
                win32con.WM_LBUTTONUP,
                0,
                lparam
            )
            logger.debug("已发送 WM_LBUTTONUP")

            logger.info(f"[后台模式] 后台虚拟点击完成 (duration={duration_ms}ms)")
            return True

        except Exception as e:
            logger.error(f"[后台模式] 执行失败：{e}")
            return False
