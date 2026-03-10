"""
MaaTexas 框架核心异常模块。

定义框架的基础异常类和错误码体系，为各子模块提供统一的异常基类。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ErrorContext:
    """错误上下文信息。

    Attributes:
        code: 错误码，用于程序化识别错误类型。
        message: 人类可读的错误描述信息。
        details: 可选的详细错误信息，用于调试。
        timestamp: 错误发生的时间戳。
    """
    code: str
    message: str
    details: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)


class MaaTexasError(Exception):
    """MaaTexas 框架基础异常类。

    所有框架级异常都应继承自此类，确保异常处理的一致性。

    Attributes:
        code: 错误码字符串。
        message: 错误描述信息。
        details: 可选的详细错误信息。
        timestamp: 错误发生时间。

    Example:
        ```python
        raise MaaTexasError(
            code="PERCEPTION_001",
            message="截图捕获失败",
            details={"reason": "窗口句柄无效"}
        )
        ```
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Any] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """初始化 MaaTexasError。

        Args:
            code: 错误码，格式建议为 'MODULE_XXX'。
            message: 错误描述信息。
            details: 可选的详细错误信息，可以是任意类型。
            timestamp: 错误发生时间，默认为当前时间。
        """
        self.code = code
        self.message = message
        self.details = details
        self.timestamp = timestamp or datetime.now()
        self.context = ErrorContext(
            code=code,
            message=message,
            details=details,
            timestamp=self.timestamp
        )
        super().__init__(self.message)

    def __str__(self) -> str:
        """返回格式化的错误信息字符串。

        Returns:
            包含错误码和消息的格式化字符串。
        """
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """将错误信息转换为字典格式。

        Returns:
            包含所有错误信息的字典。
        """
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
