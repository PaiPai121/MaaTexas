"""
MaaTexas 框架核心模块。

提供基础异常类、通用数据模型和框架级常量。
"""

from src.core.exceptions import MaaTexasError, ErrorContext
from src.core.models import ModuleStatus, TaskResult, ConfigBase

__all__ = [
    # Exceptions
    "MaaTexasError",
    "ErrorContext",
    # Models
    "ModuleStatus",
    "TaskResult",
    "ConfigBase",
]
