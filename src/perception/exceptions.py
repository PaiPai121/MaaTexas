"""
MaaTexas 感知模块异常定义。

定义感知层特有的异常类型，用于处理图像捕获、场景识别等错误。
"""

from src.core.exceptions import MaaTexasError


class PerceptionError(MaaTexasError):
    """感知模块基础异常类。

    所有感知层异常都应继承自此类，错误码以 'PERCEPTION_' 为前缀。

    Example:
        ```python
        raise PerceptionError(
            code="PERCEPTION_001",
            message="截图捕获失败",
            details={"window_handle": None}
        )
        ```
    """
    pass


class CaptureFailedError(PerceptionError):
    """屏幕/窗口捕获失败异常。

    当无法获取游戏画面时抛出此异常。
    """
    pass


class SceneRecognitionError(PerceptionError):
    """场景识别失败异常。

    当无法识别当前游戏场景或 UI 状态时抛出此异常。
    """
    pass


class TemplateMatchError(PerceptionError):
    """模板匹配失败异常。

    当图像模板匹配过程中发生错误时抛出此异常。
    """
    pass
