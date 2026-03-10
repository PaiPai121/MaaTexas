"""
MaaTexas 规划模块异常定义。

定义规划层特有的异常类型，用于处理行为决策、任务调度等错误。
"""

from src.core.exceptions import MaaTexasError


class PlanningError(MaaTexasError):
    """规划模块基础异常类。

    所有规划层异常都应继承自此类，错误码以 'PLANNING_' 为前缀。

    Example:
        ```python
        raise PlanningError(
            code="PLANNING_001",
            message="无法生成有效行为序列",
            details={"current_state": "unknown_scene"}
        )
        ```
    """
    pass


class TaskNotFoundError(PlanningError):
    """任务未找到异常。

    当请求的任务或行为在任务库中不存在时抛出此异常。
    """
    pass


class TaskExecutionError(PlanningError):
    """任务执行失败异常。

    当任务执行过程中发生不可恢复的错误时抛出此异常。
    """
    pass


class InvalidActionError(PlanningError):
    """无效行为异常。

    当规划的行为不合法或无法执行时抛出此异常。
    """
    pass


class DependencyError(PlanningError):
    """依赖检查失败异常。

    当任务前置条件不满足时抛出此异常。
    """
    pass
