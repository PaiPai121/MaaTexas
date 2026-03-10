"""
MaaTexas 控制模块数据模型。

定义输入事件、执行结果等控制层数据契约。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InputType(str, Enum):
    """输入类型枚举。

    Attributes:
        MOUSE_CLICK: 鼠标点击。
        MOUSE_DOUBLE_CLICK: 鼠标双击。
        MOUSE_PRESS: 鼠标按下。
        MOUSE_RELEASE: 鼠标释放。
        MOUSE_MOVE: 鼠标移动。
        MOUSE_SCROLL: 鼠标滚轮。
        KEY_PRESS: 按键按下。
        KEY_RELEASE: 按键释放。
        TOUCH: 触摸输入（移动端）。
    """
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"
    MOUSE_PRESS = "mouse_press"
    MOUSE_RELEASE = "mouse_release"
    MOUSE_MOVE = "mouse_move"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    TOUCH = "touch"


class InputEvent(BaseModel):
    """输入事件数据契约。

    描述一个待执行的输入事件。

    Attributes:
        event_type: 输入事件类型。
        coords: 事件坐标 (x, y)，适用于鼠标/触摸事件。
        key_code: 按键代码，适用于键盘事件。
        delta: 滚动增量，适用于滚轮事件。
        timestamp: 事件创建时间。
    """
    event_type: InputType = Field(..., description="输入事件类型")
    coords: Optional[tuple[int, int]] = Field(default=None, description="事件坐标")
    key_code: Optional[str] = Field(default=None, description="按键代码")
    delta: Optional[int] = Field(default=None, description="滚动增量")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间")

    class Config:
        """Pydantic 模型配置。"""
        json_schema_extra = {
            "example": {
                "event_type": "mouse_click",
                "coords": (500, 300),
                "timestamp": "2026-03-09T10:00:00"
            }
        }


class ExecutionResult(BaseModel):
    """执行结果数据契约。

    描述控制操作的执行结果。

    Attributes:
        success: 执行是否成功。
        event_id: 关联的输入事件 ID。
        actual_duration_ms: 实际执行耗时（毫秒）。
        error_message: 错误信息，失败时设置。
        retry_count: 重试次数。
        timestamp: 执行完成时间。
    """
    success: bool = Field(..., description="执行是否成功")
    event_id: Optional[str] = Field(default=None, description="事件 ID")
    actual_duration_ms: float = Field(default=0.0, description="实际耗时（毫秒）")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    timestamp: datetime = Field(default_factory=datetime.now, description="完成时间")

    class Config:
        """Pydantic 模型配置。"""
        extra = "forbid"


class DeviceConfig(BaseModel):
    """设备配置数据契约。

    定义目标窗口/设备的配置参数。

    Attributes:
        window_title: 窗口标题匹配模式。
        window_class: 窗口类名，可选。
        scale_factor: 显示缩放因子，用于坐标换算。
        offset_x: X 轴偏移量（像素）。
        offset_y: Y 轴偏移量（像素）。
    """
    window_title: str = Field(..., description="窗口标题匹配模式")
    window_class: Optional[str] = Field(default=None, description="窗口类名")
    scale_factor: float = Field(default=1.0, description="显示缩放因子")
    offset_x: int = Field(default=0, description="X 轴偏移量")
    offset_y: int = Field(default=0, description="Y 轴偏移量")

    class Config:
        """Pydantic 模型配置。"""
        extra = "forbid"
