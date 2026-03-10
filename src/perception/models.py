"""
MaaTexas 感知模块数据模型。

定义游戏状态、图像捕获结果等感知层数据契约。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GameState(BaseModel):
    """游戏状态数据契约。

    描述当前游戏的可观测状态，用于决策层进行行为规划。

    Attributes:
        current_scene: 当前场景标识符，如 'main_menu', 'battle', 'recruit'。
        hp_percent: 生命值百分比，范围 [0.0, 100.0]。
        sanity_percent: 理智值百分比，范围 [0.0, 100.0]。
        current_level: 当前关卡标识，可选。
        is_battling: 是否处于战斗中。
        last_update: 状态最后更新时间。
    """
    current_scene: str = Field(..., description="当前场景标识符")
    hp_percent: float = Field(..., ge=0.0, le=100.0, description="生命值百分比")
    sanity_percent: float = Field(default=100.0, ge=0.0, le=100.0, description="理智值百分比")
    current_level: Optional[str] = Field(default=None, description="当前关卡标识")
    is_battling: bool = Field(default=False, description="是否处于战斗中")
    last_update: datetime = Field(default_factory=datetime.now, description="最后更新时间")

    class Config:
        """Pydantic 模型配置。"""
        json_schema_extra = {
            "example": {
                "current_scene": "battle",
                "hp_percent": 85.5,
                "sanity_percent": 60.0,
                "current_level": "1-7",
                "is_battling": True,
                "last_update": "2026-03-09T10:00:00"
            }
        }


class CaptureResult(BaseModel):
    """图像捕获结果数据契约。

    封装屏幕/窗口捕获操作的返回值。

    Attributes:
        success: 捕获是否成功。
        image_path: 捕获图像保存路径，可选。
        image_data: 原始图像数据（numpy array 的序列化表示），可选。
        width: 图像宽度（像素）。
        height: 图像高度（像素）。
        capture_time_ms: 捕获耗时（毫秒）。
        timestamp: 捕获时间戳。
    """
    success: bool = Field(..., description="捕获是否成功")
    image_path: Optional[str] = Field(default=None, description="图像保存路径")
    width: int = Field(default=0, description="图像宽度")
    height: int = Field(default=0, description="图像高度")
    capture_time_ms: float = Field(default=0.0, description="捕获耗时（毫秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="捕获时间")

    class Config:
        """Pydantic 模型配置。"""
        extra = "forbid"


class UIElement(BaseModel):
    """UI 元素识别结果。

    描述通过模板匹配或 OCR 识别出的 UI 元素。

    Attributes:
        element_id: 元素唯一标识。
        element_type: 元素类型，如 'button', 'text', 'icon'。
        confidence: 识别置信度，范围 [0.0, 1.0]。
        bbox: 边界框坐标 (x, y, width, height)。
        text_content: 识别出的文本内容，可选。
    """
    element_id: str = Field(..., description="元素唯一标识")
    element_type: str = Field(..., description="元素类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="识别置信度")
    bbox: tuple[int, int, int, int] = Field(..., description="边界框 (x, y, w, h)")
    text_content: Optional[str] = Field(default=None, description="文本内容")


class PerceptionResult(BaseModel):
    """感知管线处理结果数据契约。

    封装 OpenCV 感知管线的输出结果，包含标注图像和检测到的 UI 元素。

    Attributes:
        timestamp: 处理时间戳（Unix 时间戳）。
        annotated_image: 标注后的图像（带 SoM 标记）。
        ui_elements: 检测到的 UI 元素列表。
    """
    timestamp: float = Field(..., description="处理时间戳（Unix 时间戳）")
    annotated_image: Any = Field(..., description="标注后的图像（numpy 数组）")
    ui_elements: list[UIElement] = Field(default_factory=list, description="检测到的 UI 元素列表")

    class Config:
        """Pydantic 模型配置。"""
        arbitrary_types_allowed = True  # 允许 numpy 数组类型
