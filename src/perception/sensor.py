"""
MaaTexas 感知传感器模块。

封装 MaaFramework 底层连接，提供统一的画面采集接口。
当 MaaFramework 不可用时，自动回退到 pywin32 进行桌面捕获。
"""

import asyncio
import logging
from typing import Optional

import numpy as np

from maa.controller import Win32Controller, MaaWin32ScreencapMethodEnum
from maa.resource import Resource
from maa.tasker import Tasker

from src.utils.toolkit import Toolkit

logger = logging.getLogger(__name__)


class MaaSensor:
    """MaaFramework 传感器类。

    封装 MaaFramework 的底层连接和画面采集逻辑，为上层提供同步接口。
    当 MaaFramework 截图失败时，自动回退到 pywin32 进行桌面捕获。

    Attributes:
        controller: MaaFramework 控制器实例。
        resource: MaaFramework 资源实例。
        tasker: MaaFramework 任务器实例。
        is_connected: 是否已连接到目标窗口/桌面。
        use_fallback: 是否使用 pywin32 回退方案。

    Example:
        ```python
        sensor = MaaSensor()
        sensor.connect()
        frame = sensor.capture_frame()
        if frame is not None:
            st.image(frame, channels="RGB")
        ```
    """

    def __init__(self) -> None:
        """初始化 MaaSensor。

        初始化 MaaFramework 环境，但不会立即建立连接。
        需要显式调用 connect() 方法。
        """
        self.controller: Optional[Win32Controller] = None
        self.resource: Optional[Resource] = None
        self.tasker: Optional[Tasker] = None
        self.is_connected: bool = False
        self.use_fallback: bool = False
        self._hwnd: int = 0

        logger.info("MaaSensor 实例已创建")

    def connect(self, window_title: Optional[str] = None) -> bool:
        """连接到目标窗口或桌面。

        Args:
            window_title: 目标窗口标题（支持模糊匹配）。
                         为 None 时捕获整个桌面。

        Returns:
            bool: 连接是否成功。
        """
        try:
            # 初始化框架环境
            Toolkit.init()

            # 查找窗口句柄
            hwnd = 0
            if window_title:
                hwnd = self._find_window_by_title(window_title)
                if hwnd == 0:
                    logger.warning(f"未找到窗口：{window_title}，将使用桌面捕获")

            self._hwnd = hwnd

            # 实例化控制器
            # hWnd=0 表示捕获整个桌面，非零则捕获指定窗口
            # 使用 GDI 截图方法（兼容性更好）
            self.controller = Win32Controller(
                hWnd=hwnd,
                screencap_method=MaaWin32ScreencapMethodEnum.GDI,
            )

            # 初始化资源和任务器
            self.resource = Resource()
            self.tasker = Tasker()

            # 关联资源和控制器（新版 API）
            self.tasker.bind(self.resource, self.controller)

            # 测试截图功能是否可用
            test_frame = self._test_screencap()
            if test_frame is None:
                logger.warning("MaaFramework 截图功能不可用，启用 pywin32 回退方案")
                self.use_fallback = True
            else:
                logger.info("MaaFramework 截图功能正常")
                self.use_fallback = False

            self.is_connected = True
            logger.info(f"MaaSensor 连接成功 - {'桌面' if hwnd == 0 else f'窗口句柄 {hwnd:#x}'} (回退模式：{self.use_fallback})")
            return True

        except Exception as e:
            logger.error(f"MaaSensor 连接失败：{e}")
            self.is_connected = False
            return False

    def _test_screencap(self) -> Optional[np.ndarray]:
        """测试 MaaFramework 截图功能是否可用。

        Returns:
            Optional[np.ndarray]: 成功返回图像数组，失败返回 None。
        """
        try:
            # 尝试截图
            job = self.controller.post_screencap()  # type: ignore

            # 等待作业完成（done 是属性不是方法）
            import time
            start_time = time.time()
            while not job.done and (time.time() - start_time) < 2.0:
                time.sleep(0.01)

            if not job.done:
                return None

            # 尝试获取图像
            try:
                img = self.controller.cached_image  # type: ignore
                if img is not None and isinstance(img, np.ndarray):
                    return img
            except RuntimeError:
                pass

            # 尝试从 job 获取
            try:
                result = job.get()
                if isinstance(result, np.ndarray):
                    return result
            except Exception:
                pass

            return None

        except Exception:
            return None

    def _find_window_by_title(self, title: str) -> int:
        """根据窗口标题查找窗口句柄。

        Args:
            title: 窗口标题（支持模糊匹配）。

        Returns:
            int: 窗口句柄，未找到返回 0。
        """
        import win32gui

        # 枚举所有匹配窗口
        results: list[int] = []

        def enum_callback(hwnd: int, results_list: list[int]) -> bool:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if title.lower() in window_title.lower():
                        results_list.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_callback, results)

        if results:
            logger.info(f"找到匹配窗口：{results[0]:#x}")
            return results[0]

        return 0

    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧画面（RGB 格式）。

        同步方法，优先使用 MaaFramework，失败时回退到 pywin32。
        使用 loop.run_until_complete() 避免 asyncio.run() 在高频调用下的内存泄漏风险。

        Returns:
            Optional[np.ndarray]: RGB 格式的 numpy 数组。
                                 截图失败返回 None。

        Example:
            ```python
            frame = sensor.capture_frame()
            if frame is not None:
                st.image(frame, channels="RGB")
            ```
        """
        if not self.is_connected:
            logger.warning("MaaSensor 未连接，无法截图")
            return None

        # 如果使用回退模式，直接用 pywin32
        if self.use_fallback:
            return self._capture_fallback()

        # 否则尝试使用 MaaFramework
        try:
            # 使用 loop.run_until_complete() 避免 asyncio.run() 的内存泄漏风险
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # 如果当前已经有运行的 loop（在 Streamlit 中较少见），直接回退
                logger.warning("检测到运行中的 event loop，使用回退方案")
                return self._capture_fallback()
            except RuntimeError:
                # 没有运行的 loop，创建一个新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._capture_frame_async())
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"MaaFramework 截图失败，切换到回退模式：{e}")
            self.use_fallback = True
            return self._capture_fallback()

    def _capture_fallback(self) -> Optional[np.ndarray]:
        """使用 pywin32 进行窗口/桌面捕获（回退方案）。

        当指定窗口句柄时捕获窗口，否则捕获整个桌面。
        桌面捕获使用 BitBlt，窗口捕获使用 PrintWindow API 以支持后台遮挡截图。

        Returns:
            Optional[np.ndarray]: RGB 格式的 numpy 数组。
        """
        try:
            import win32gui
            import win32ui
            import win32con
            import win32api
            import ctypes

            # 确定目标窗口
            hwnd = self._hwnd if self._hwnd != 0 else win32gui.GetDesktopWindow()
            is_desktop = (hwnd == win32gui.GetDesktopWindow())

            if is_desktop:
                # 桌面捕获 - 使用 BitBlt
                width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
                height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
                offset_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
                offset_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

                hwnd_dc = win32gui.GetWindowDC(hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()

                bitmap = win32ui.CreateBitmap()
                bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(bitmap)
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

                bmpstr = bitmap.GetBitmapBits(True)
                img = np.frombuffer(bmpstr, dtype='uint8')
                img = img.reshape((height, width, 4))

                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)

            else:
                # 窗口捕获 - 使用 PrintWindow API 支持后台遮挡截图
                # 获取窗口在屏幕上的位置（物理像素）
                window_rect = win32gui.GetWindowRect(hwnd)
                window_width = window_rect[2] - window_rect[0]
                window_height = window_rect[3] - window_rect[1]

                # 检查窗口是否最小化
                if win32gui.IsIconic(hwnd):
                    logger.warning(f"窗口 0x{hwnd:x} 已最小化，无法捕获")
                    return None

                logger.info(f"窗口捕获：0x{hwnd:x}, 尺寸={window_width}x{window_height}")

                # 获取窗口的 DC
                hwnd_dc = win32gui.GetWindowDC(hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()

                # 创建位图
                bitmap = win32ui.CreateBitmap()
                bitmap.CreateCompatibleBitmap(mfc_dc, window_width, window_height)
                save_dc.SelectObject(bitmap)

                # 使用 PrintWindow API 进行后台截图
                # PW_RENDERFULLCONTENT = 2 (Windows 8.1+ 支持硬件加速窗口后台截图)
                result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

                logger.info(f"PrintWindow 返回：{result}")

                if result == 1:
                    # PrintWindow 成功，获取位图数据
                    bmpstr = bitmap.GetBitmapBits(True)
                    img = np.frombuffer(bmpstr, dtype='uint8')
                    img = img.reshape((window_height, window_width, 4))
                    logger.info(f"PrintWindow 成功：图像均值={img.mean():.1f}")
                else:
                    # PrintWindow 失败，回退到桌面 BitBlt（但会被遮挡）
                    logger.warning(f"PrintWindow 失败 (0x{hwnd:x})，回退到桌面截取")
                    
                    # 从桌面截取窗口区域（物理像素坐标）
                    desktop_hwnd = win32gui.GetDesktopWindow()
                    desktop_dc = win32gui.GetWindowDC(desktop_hwnd)
                    mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
                    save_dc = mfc_dc.CreateCompatibleDC()
                    
                    bitmap2 = win32ui.CreateBitmap()
                    bitmap2.CreateCompatibleBitmap(mfc_dc, window_width, window_height)
                    save_dc.SelectObject(bitmap2)
                    
                    left = window_rect[0]
                    top = window_rect[1]
                    save_dc.BitBlt(
                        (0, 0),
                        (window_width, window_height),
                        mfc_dc,
                        (left, top),
                        win32con.SRCCOPY
                    )
                    
                    bmpstr = bitmap2.GetBitmapBits(True)
                    img = np.frombuffer(bmpstr, dtype='uint8')
                    img = img.reshape((window_height, window_width, 4))
                    
                    win32gui.DeleteObject(bitmap2.GetHandle())
                    save_dc.DeleteDC()
                    mfc_dc.DeleteDC()
                    win32gui.ReleaseDC(desktop_hwnd, desktop_dc)

                # 清理 PrintWindow 资源
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)

            # 转换为 RGB（去掉 alpha 通道）
            img_rgb = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2RGB)
            return img_rgb

        except Exception as e:
            logger.error(f"pywin32 回退截图失败：{e}")
            return None

    async def _capture_frame_async(self) -> Optional[np.ndarray]:
        """异步捕获一帧画面（使用 MaaFramework）。

        Returns:
            Optional[np.ndarray]: RGB 格式的 numpy 数组，失败返回 None。
        """
        if self.controller is None:
            return None

        try:
            # 执行截图（异步作业）
            job = self.controller.post_screencap()  # type: ignore

            # 等待作业完成（done 是属性不是方法）
            while not job.done:
                await asyncio.sleep(0.01)

            # 从 job 获取结果
            try:
                img_bgr = self.controller.cached_image  # type: ignore
                if img_bgr is not None and isinstance(img_bgr, np.ndarray):
                    # 将 BGR 转换为 RGB（Streamlit 需要 RGB 格式）
                    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                    return img_rgb
            except RuntimeError as e:
                if "Failed to get cached image" in str(e):
                    # 图像为空，尝试从 job.get() 获取
                    try:
                        result = job.get()
                        # 如果 result 是图像数组
                        if isinstance(result, np.ndarray):
                            img_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
                            return img_rgb
                    except Exception:
                        pass
                logger.warning(f"获取截图失败：{e}")
                return None

            return None

        except Exception as e:
            logger.error(f"异步截图失败：{e}")
            return None

    def disconnect(self) -> None:
        """断开连接并释放资源。

        调用后需要重新调用 connect() 才能继续使用。
        """
        try:
            # MaaFramework 的 Tasker 没有 stop() 方法
            # 只需将引用置为 None 让 GC 回收即可
            self.controller = None
            self.resource = None
            self.tasker = None
            self.is_connected = False
            self.use_fallback = False
            logger.info("MaaSensor 已断开连接")
        except Exception as e:
            logger.error(f"断开连接时出错：{e}")

    def __del__(self) -> None:
        """析构函数，确保资源被释放。"""
        if self.is_connected:
            self.disconnect()


# 延迟导入 cv2，避免模块加载时不必要的依赖
def _import_cv2():
    import cv2
    return cv2


cv2 = _import_cv2()
