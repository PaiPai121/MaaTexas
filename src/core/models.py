"""
MaaTexas 框架核心数据模型模块。

定义框架通用的基础数据契约，供各子模块复用。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModuleStatus(str, Enum):
    """模块运行状态枚举。

    Attributes:
        IDLE: 空闲状态，模块已初始化但未执行任务。
        RUNNING: 运行状态，模块正在执行任务。
        PAUSED: 暂停状态，模块任务被临时挂起。
        ERROR: 错误状态，模块执行过程中发生错误。
    """
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class TaskResult(BaseModel):
    """任务执行结果数据契约。

    用于标准化各模块的任务执行返回值，确保接口一致性。

    Attributes:
        success: 任务是否成功执行。
        data: 任务返回的数据载荷，可选。
        error_code: 错误码，仅在失败时设置。
        error_message: 错误描述，仅在失败时设置。
        execution_time_ms: 任务执行耗时（毫秒）。
        timestamp: 任务完成时间。
    """
    success: bool = Field(..., description="任务执行是否成功")
    data: Optional[Any] = Field(default=None, description="任务返回的数据载荷")
    error_code: Optional[str] = Field(default=None, description="错误码")
    error_message: Optional[str] = Field(default=None, description="错误描述")
    execution_time_ms: float = Field(default=0.0, description="执行耗时（毫秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="完成时间")

    class Config:
        """Pydantic 模型配置。"""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"result": "ok"},
                "execution_time_ms": 150.5,
                "timestamp": "2026-03-09T10:00:00"
            }
        }


class ConfigBase(BaseModel):
    """配置基类。

    为各模块的配置类提供通用的字段和验证逻辑。

    Attributes:
        enabled: 模块是否启用。
        debug_mode: 是否开启调试模式。
        timeout_seconds: 操作超时时间（秒）。
    """
    enabled: bool = Field(default=True, description="模块是否启用")
    debug_mode: bool = Field(default=False, description="是否开启调试模式")
    timeout_seconds: float = Field(default=30.0, description="操作超时时间（秒）")

    class Config:
        """Pydantic 模型配置。"""
        extra = "forbid"  # 禁止额外字段
        validate_assignment = True  # 赋值时验证
