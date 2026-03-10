"""
MaaTexas 规划模块数据模型。

定义行为命令、任务计划等规划层数据契约。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """行为类型枚举。

    Attributes:
        CLICK: 点击操作。
        SWIPE: 滑动操作。
        PRESS: 按键操作。
        WAIT: 等待操作。
        NAVIGATE: 导航/跳转操作。
        CUSTOM: 自定义行为。
    """
    CLICK = "click"
    SWIPE = "swipe"
    PRESS = "press"
    WAIT = "wait"
    NAVIGATE = "navigate"
    CUSTOM = "custom"


class ActionCommand(BaseModel):
    """行为命令数据契约。

    描述单个可执行的行为指令，供控制层消费。

    Attributes:
        action_type: 行为类型，如 click, swipe, wait 等。
        target_coords: 目标坐标 (x, y)，对于点击/滑动操作。
        duration_ms: 行为持续时间（毫秒），用于等待或长按操作。
        params: 额外参数，用于自定义行为。
        priority: 命令优先级，数值越大优先级越高。
        timeout_seconds: 命令执行超时时间（秒）。
    """
    action_type: ActionType = Field(..., description="行为类型")
    target_coords: Optional[tuple[int, int]] = Field(default=None, description="目标坐标 (x, y)")
    duration_ms: int = Field(default=0, ge=0, description="持续时间（毫秒）")
    params: dict[str, Any] = Field(default_factory=dict, description="额外参数")
    priority: int = Field(default=0, description="命令优先级")
    timeout_seconds: float = Field(default=30.0, description="超时时间（秒）")

    class Config:
        """Pydantic 模型配置。"""
        json_schema_extra = {
            "example": {
                "action_type": "click",
                "target_coords": (500, 300),
                "duration_ms": 100,
                "params": {},
                "priority": 1,
                "timeout_seconds": 5.0
            }
        }


class TaskPlan(BaseModel):
    """任务计划数据契约。

    描述一个完整的任务执行计划，包含多个有序的行为命令。

    Attributes:
        task_id: 任务唯一标识。
        task_name: 任务名称。
        commands: 有序的行为命令列表。
        preconditions: 任务执行的前置条件。
        expected_result: 期望的执行结果描述。
        created_at: 计划创建时间。
    """
    task_id: str = Field(..., description="任务唯一标识")
    task_name: str = Field(..., description="任务名称")
    commands: list[ActionCommand] = Field(default_factory=list, description="行为命令列表")
    preconditions: list[str] = Field(default_factory=list, description="前置条件")
    expected_result: Optional[str] = Field(default=None, description="期望结果")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    class Config:
        """Pydantic 模型配置。"""
        extra = "forbid"


class TaskStatus(str, Enum):
    """任务状态枚举。

    Attributes:
        PENDING: 待执行。
        RUNNING: 执行中。
        COMPLETED: 已完成。
        FAILED: 已失败。
        CANCELLED: 已取消。
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
