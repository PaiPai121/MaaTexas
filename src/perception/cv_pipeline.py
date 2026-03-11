"""
MaaTexas 感知模块 - OpenCV 视觉处理管线。

实现快速图像感知管线，提取轮廓并标注 UI 元素。
"""

import logging
import time
from typing import Optional

import cv2
import numpy as np

from src.perception.models import PerceptionResult, UIElement

logger = logging.getLogger(__name__)


class FastPerceptionPipeline:
    """快速感知管线。

    使用 OpenCV 进行实时图像处理和 UI 元素检测。
    采用 Canny 边缘检测和轮廓提取算法，实现 Set-of-Mark(SoM) 标注。

    Attributes:
        min_contour_area: 最小轮廓面积阈值，过滤噪点。
        max_contour_area_ratio: 最大轮廓面积占比，过滤过大区域。
        canny_low: Canny 边缘检测低阈值。
        canny_high: Canny 边缘检测高阈值。

    Example:
        ```python
        pipeline = FastPerceptionPipeline()
        result = pipeline.process(frame)
        st.image(result.annotated_image, channels="RGB")
        ```
    """

    def __init__(
        self,
        min_contour_area: float = 50.0,
        max_contour_area_ratio: float = 0.5,
        canny_low: int = 50,
        canny_high: int = 150
    ) -> None:
        """初始化快速感知管线。

        Args:
            min_contour_area: 最小轮廓面积，小于此值的轮廓将被过滤。
            max_contour_area_ratio: 最大轮廓面积占比（相对于整张图像）。
            canny_low: Canny 边缘检测低阈值。
            canny_high: Canny 边缘检测高阈值。
        """
        self.min_contour_area = min_contour_area
        self.max_contour_area_ratio = max_contour_area_ratio
        self.canny_low = canny_low
        self.canny_high = canny_high

        logger.info("FastPerceptionPipeline 已初始化")

    def process(self, frame: np.ndarray) -> PerceptionResult:
        """处理输入图像，生成感知结果。

        Args:
            frame: 输入的 RGB 格式图像（numpy 数组）。

        Returns:
            PerceptionResult: 包含标注图像和 UI 元素列表的结果对象。

        Note:
            - 如果输入图像为空或无效，返回空结果。
            - 标注图像使用红色矩形框和带背景的编号标记。
        """
        start_time = time.time()

        # 检查输入图像有效性
        if frame is None or frame.size == 0:
            logger.warning("输入图像为空，返回空结果")
            return self._empty_result()

        try:
            # 拷贝原图用于标注
            annotated_image = frame.copy()

            # 提取轮廓
            contours = self._extract_contours(frame)

            # 过滤有效轮廓
            valid_contours = self._filter_contours(frame, contours)

            # 生成 UI 元素
            ui_elements = self._contours_to_ui_elements(valid_contours)

            # 在图像上绘制标注
            self._draw_annotations(annotated_image, valid_contours)

            # 计算处理时间
            processing_time = time.time() - start_time

            return PerceptionResult(
                timestamp=time.time(),
                annotated_image=annotated_image,
                ui_elements=ui_elements
            )

        except Exception as e:
            logger.error(f"感知管线处理失败：{e}")
            return self._empty_result()

    def _extract_contours(self, frame: np.ndarray) -> list[np.ndarray]:
        """从图像中提取轮廓。

        Args:
            frame: 输入的 RGB 格式图像。

        Returns:
            list[np.ndarray]: 轮廓列表。
        """
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # 应用高斯模糊减少噪声
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny 边缘检测
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)

        # 膨胀操作连接断开的边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated_edges = cv2.dilate(edges, kernel, iterations=2)

        # 查找轮廓
        contours, _ = cv2.findContours(
            dilated_edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        return list(contours)

    def _filter_contours(
        self,
        frame: np.ndarray,
        contours: list[np.ndarray]
    ) -> list[np.ndarray]:
        """过滤无效轮廓（过大或过小）。

        Args:
            frame: 原始图像，用于计算面积阈值。
            contours: 轮廓列表。

        Returns:
            list[np.ndarray]: 过滤后的轮廓列表。
        """
        image_area = frame.shape[0] * frame.shape[1]
        max_area = image_area * self.max_contour_area_ratio

        valid_contours = []

        for contour in contours:
            area = cv2.contourArea(contour)

            # 过滤过小或过大的轮廓
            if self.min_contour_area <= area <= max_area:
                valid_contours.append(contour)

        return valid_contours

    def _contours_to_ui_elements(
        self,
        contours: list[np.ndarray]
    ) -> list[UIElement]:
        """将轮廓转换为 UI 元素列表。

        Args:
            contours: 轮廓列表。

        Returns:
            list[UIElement]: UI 元素列表。
        """
        ui_elements = []

        for i, contour in enumerate(contours):
            # 获取边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 计算置信度（基于轮廓面积）
            area = cv2.contourArea(contour)
            confidence = min(1.0, area / 1000.0)  # 简单置信度计算

            ui_elements.append(UIElement(
                element_id=f"ui_{i}",
                element_type="detected_contour",
                confidence=confidence,
                bbox=(x, y, w, h),
                text_content=None
            ))

        return ui_elements

    def _draw_annotations(
        self,
        image: np.ndarray,
        contours: list[np.ndarray]
    ) -> None:
        """在图像上绘制标注（红色矩形框 + SoM 编号）。

        Args:
            image: 要标注的图像（原地修改）。
            contours: 轮廓列表。
        """
        for i, contour in enumerate(contours):
            # 获取边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 绘制红色矩形框
            cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # 绘制带背景的编号标签
            label = f"[{i}]"
            font_scale = 0.6
            thickness = 2

            # 获取文字尺寸
            (text_w, text_h), baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                thickness
            )

            # 边界检查：防止标号飞出屏幕顶部
            # 计算背景矩形的 Y 坐标
            bg_y1 = y - text_h - baseline - 5
            bg_y2 = y
            text_y = y - baseline - 2

            # 如果背景顶部超出屏幕，则将文字画在矩形框下方
            if bg_y1 < 0:
                bg_y1 = y + h
                bg_y2 = y + h + text_h + baseline + 5
                text_y = y + h + text_h + 2

            # 绘制背景矩形
            cv2.rectangle(
                image,
                (x, bg_y1),
                (x + text_w, bg_y2),
                (255, 0, 0),  # 红色背景
                -1  # 填充
            )

            # 绘制白色文字
            cv2.putText(
                image,
                label,
                (x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),  # 白色文字
                thickness,
                cv2.LINE_AA
            )

    def _empty_result(self) -> PerceptionResult:
        """生成空结果。

        Returns:
            PerceptionResult: 空的感知结果。
        """
        return PerceptionResult(
            timestamp=time.time(),
            annotated_image=np.zeros((480, 640, 3), dtype=np.uint8),
            ui_elements=[]
        )
