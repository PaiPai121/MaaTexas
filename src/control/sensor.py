"""
传感器模块 - 基于 MaaFramework 实现画面采集
"""
import asyncio
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Sensor:
    """
    传感器类 - 负责从 MaaFramework 获取游戏画面
    作为系统的"眼睛"，提供持续的画面流
    """

    def __init__(self, device_id: str = "emulator-5554"):
        """
        初始化传感器

        Args:
            device_id: 设备标识符，默认为模拟器端口
        """
        self.device_id = device_id
        self._frame: Optional[np.ndarray] = None
        self._running = False
        logger.info(f"传感器初始化完成，目标设备：{device_id}")

    async def connect(self) -> bool:
        """
        连接到目标设备

        Returns:
            bool: 连接是否成功
        """
        logger.info(f"正在连接设备：{self.device_id}")
        # TODO: 接入 MaaFramework 的 Python API
        # 当前为模拟实现，后续会替换为真实的 Maa 连接逻辑
        await asyncio.sleep(0.5)  # 模拟连接延迟
        self._running = True
        logger.info("设备连接成功")
        return True

    async def capture(self) -> Optional[np.ndarray]:
        """
        捕获一帧画面

        Returns:
            np.ndarray: BGR 格式的游戏画面，失败返回 None
        """
        if not self._running:
            return None

        # TODO: 调用 MaaFramework 的截图 API
        # 当前返回模拟帧用于测试
        await asyncio.sleep(0.05)  # 模拟采集延迟
        self._frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(
            self._frame,
            "MaaTexas Sensor Feed",
            (50, 360),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        return self._frame

    async def disconnect(self) -> None:
        """断开设备连接"""
        self._running = False
        logger.info("传感器已断开连接")


async def run_sensor_feed() -> None:
    """
    运行传感器数据流

    持续从设备获取画面并显示，直到用户按下 'q' 键退出
    """
    logger.info("启动传感器数据流...")

    sensor = Sensor()

    if not await sensor.connect():
        logger.error("传感器连接失败，退出")
        return

    logger.info("开始接收画面数据...")
    frame_count = 0

    try:
        while sensor._running:
            frame = await sensor.capture()

            if frame is not None:
                frame_count += 1
                cv2.imshow("MaaTexas - Sensor Feed", frame)

                # 监听退出信号
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("检测到退出信号 'q'")
                    break

            # 限制采样率，避免过快循环
            await asyncio.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("检测到用户中断 (Ctrl+C)")
    finally:
        await sensor.disconnect()
        cv2.destroyAllWindows()
        logger.info(f"传感器数据流结束，共接收 {frame_count} 帧")
