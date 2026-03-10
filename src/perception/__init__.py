"""
MaaTexas 感知模块。

负责游戏画面捕获、场景识别、UI 元素检测等感知任务。
"""

from src.perception.models import GameState, CaptureResult, UIElement
from src.perception.exceptions import (
    PerceptionError,
    CaptureFailedError,
    SceneRecognitionError,
    TemplateMatchError,
)
from src.perception.sensor import MaaSensor

__all__ = [
    # Models
    "GameState",
    "CaptureResult",
    "UIElement",
    # Sensor
    "MaaSensor",
    # Exceptions
    "PerceptionError",
    "CaptureFailedError",
    "SceneRecognitionError",
    "TemplateMatchError",
]
