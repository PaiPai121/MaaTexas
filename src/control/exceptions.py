"""
MaaTexas 控制模块异常定义。

定义控制层特有的异常类型，用于处理输入模拟、设备交互等错误。
"""

from src.core.exceptions import MaaTexasError


class ControlError(MaaTexasError):
    """控制模块基础异常类。

    所有控制层异常都应继承自此类，错误码以 'CONTROL_' 为前缀。

    Example:
        ```python
        raise ControlError(
            code="CONTROL_001",
            message="点击操作执行失败",
            details={"coords": (500, 300), "reason": "窗口失焦"}
        )
        ```
    """
    pass


class InputExecutionError(ControlError):
    """输入执行失败异常。

    当模拟点击、滑动等输入操作失败时抛出此异常。
    """
    pass


class DeviceNotFoundError(ControlError):
    """设备未找到异常。

    当无法找到目标窗口或设备时抛出此异常。
    """
    pass


class CoordinateInvalidError(ControlError):
    """坐标无效异常。

    当提供的坐标超出屏幕/窗口范围时抛出此异常。
    """
    pass
