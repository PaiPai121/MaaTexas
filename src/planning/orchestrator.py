"""
MaaTexas 规划模块 - 任务编排器。

实现任务流水线功能，让 Agent 能够根据用户指令自动循环执行任务直到完成。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from src.control.executor import ActionExecutor
from src.perception import MaaSensor
from src.perception.cv_pipeline import FastPerceptionPipeline
from src.perception.models import GameState, PerceptionResult
from src.planning.models import ActionCommand, ActionType
from src.planning.vlm_client import VLMPlanner

logger = logging.getLogger(__name__)


class OrchestratorStatus(Enum):
    """编排器状态枚举。"""
    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    STOPPED = "stopped"  # 已停止


@dataclass
class StepResult:
    """单步执行结果。"""
    step_number: int
    thought: str
    action_type: str
    target_coords: Optional[tuple[int, int]]
    executed: bool = False
    success: bool = False


@dataclass
class TaskResult:
    """任务执行结果。"""
    status: OrchestratorStatus
    total_steps: int = 0
    steps: list[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None


class TaskOrchestrator:
    """任务编排器。

    实现任务流水线功能，让 Agent 能够根据用户指令自动循环执行任务。

    Attributes:
        planner: VLM 规划器实例。
        executor: 动作执行器实例。
        sensor: 感知传感器实例。
        pipeline: 感知管线实例。
        hwnd: 目标窗口句柄。

    Example:
        ```python
        orchestrator = TaskOrchestrator(planner, executor, sensor, pipeline)
        result = await orchestrator.run_task("领取邮件并返回")
        ```
    """

    def __init__(
        self,
        planner: VLMPlanner,
        executor: ActionExecutor,
        sensor: MaaSensor,
        pipeline: FastPerceptionPipeline,
        hwnd: int = 0
    ) -> None:
        """初始化任务编排器。

        Args:
            planner: VLM 规划器实例。
            executor: 动作执行器实例。
            sensor: 感知传感器实例。
            pipeline: 感知管线实例。
            hwnd: 目标窗口句柄。
        """
        self.planner = planner
        self.executor = executor
        self.sensor = sensor
        self.pipeline = pipeline
        self.hwnd = hwnd

        # 任务状态
        self.status = OrchestratorStatus.IDLE
        self.current_step = 0
        self.steps_history: list[StepResult] = []

        # 状态回调
        self.on_step_callback: Optional[Callable[[StepResult], None]] = None
        self.on_status_callback: Optional[Callable[[OrchestratorStatus], None]] = None

        logger.info(f"TaskOrchestrator 已初始化，窗口：0x{hwnd:x}")

    def set_callbacks(
        self,
        on_step: Optional[Callable[[StepResult], None]] = None,
        on_status: Optional[Callable[[OrchestratorStatus], None]] = None
    ) -> None:
        """设置状态回调函数。

        Args:
            on_step: 每步执行后的回调，接收 StepResult 参数。
            on_status: 状态变化时的回调，接收 OrchestratorStatus 参数。
        """
        self.on_step_callback = on_step
        self.on_status_callback = on_status

    def _update_status(self, status: OrchestratorStatus) -> None:
        """更新任务状态并触发回调。

        Args:
            status: 新的任务状态。
        """
        self.status = status
        logger.info(f"任务状态变更：{status.value}")
        if self.on_status_callback:
            try:
                self.on_status_callback(status)
            except Exception as e:
                logger.error(f"状态回调失败：{e}")

    def _trigger_step_callback(self, step_result: StepResult) -> None:
        """触发步骤回调。

        Args:
            step_result: 步骤执行结果。
        """
        if self.on_step_callback:
            try:
                self.on_step_callback(step_result)
            except Exception as e:
                logger.error(f"步骤回调失败：{e}")

    async def run_task(
        self,
        user_command: str,
        max_steps: int = 10
    ) -> TaskResult:
        """运行任务流水线。

        Args:
            user_command: 用户自然语言指令。
            max_steps: 最大执行步数。

        Returns:
            TaskResult: 任务执行结果。
        """
        logger.info(f"开始执行任务：{user_command}，最大步数：{max_steps}")
        self._update_status(OrchestratorStatus.RUNNING)
        self.current_step = 0
        self.steps_history = []

        result = TaskResult(status=OrchestratorStatus.RUNNING)

        try:
            # 连接传感器
            if not self.sensor.is_connected:
                self.sensor.connect()

            if not self.sensor.is_connected:
                raise RuntimeError("传感器连接失败")

            logger.info("传感器已连接，开始任务循环...")

            # 任务主循环
            while self.current_step < max_steps:
                if self.status == OrchestratorStatus.STOPPED:
                    logger.info("任务被手动停止")
                    result.status = OrchestratorStatus.STOPPED
                    break

                self.current_step += 1
                logger.info(f"=== 第 {self.current_step} 步 / 共 {max_steps} 步 ===")

                # a. 调用 sensor.capture_frame() 获取画面
                frame = self.sensor.capture_frame()
                if frame is None:
                    logger.warning("捕获画面失败，跳过此步")
                    time.sleep(1)
                    continue

                # b. 调用 pipeline.process() 获取 UI 元素
                perception = self.pipeline.process(frame)
                if perception is None or not perception.ui_elements:
                    logger.warning("感知处理失败，跳过此步")
                    time.sleep(1)
                    continue

                # 构建游戏状态
                game_state = GameState(
                    current_scene="unknown",
                    hp_percent=100.0,
                    sanity_percent=100.0
                )

                # c. 调用 planner.generate_action() 获取下一步动作
                action = self.planner.generate_action(perception, game_state, user_command)

                # d. 检查 VLM 是否认为任务已完成
                if action.action_type == ActionType.WAIT or not action.target_coords:
                    logger.info("VLM 认为任务已完成")
                    self._update_status(OrchestratorStatus.COMPLETED)
                    result.status = OrchestratorStatus.COMPLETED
                    break

                # 记录步骤
                step_result = StepResult(
                    step_number=self.current_step,
                    thought=action.params.get("thought", "无思考过程"),
                    action_type=action.action_type.value,
                    target_coords=action.target_coords
                )

                # e. 调用 executor.execute() 执行动作
                success = self.executor.execute(action)
                step_result.executed = True
                step_result.success = success

                # 记录到历史
                self.steps_history.append(step_result)
                result.steps.append(step_result)

                # 触发步骤回调（实时传回 UI）
                self._trigger_step_callback(step_result)

                if not success:
                    logger.warning(f"第 {self.current_step} 步执行失败")

                # f. 强制等待 2 秒（等待游戏动画或界面加载）
                logger.info("等待 2 秒...")
                await asyncio.sleep(2)

            # 任务结束
            if result.status not in [OrchestratorStatus.STOPPED, OrchestratorStatus.COMPLETED]:
                if self.current_step >= max_steps:
                    logger.info("达到最大步数，任务结束")
                    result.status = OrchestratorStatus.COMPLETED
                else:
                    result.status = self.status

        except Exception as e:
            logger.error(f"任务执行异常：{type(e).__name__}: {e}")
            self._update_status(OrchestratorStatus.FAILED)
            result.status = OrchestratorStatus.FAILED
            result.error_message = str(e)

        finally:
            # 清理资源
            try:
                self.sensor.disconnect()
            except Exception:
                pass

        # 更新结果统计
        result.total_steps = self.current_step

        logger.info(f"任务结束，状态：{result.status.value}, 执行步数：{result.total_steps}")
        return result

    def stop(self) -> None:
        """手动停止任务。"""
        logger.info("手动停止任务...")
        self._update_status(OrchestratorStatus.STOPPED)
