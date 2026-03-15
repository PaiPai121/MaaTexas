#!/usr/bin/env python
"""
MaaTexas God's Eye - 可视化 Debug 看板。

基于 Streamlit 构建的实时调试界面，用于监控感知、规划和控制模块的运行状态。
遵循 "Separation of Concerns" 原则，此 UI 工具独立于 src/ 核心域。

传感器数据流：
- 使用 src.perception.MaaSensor 接入真实的 MaaFramework 画面采集
- 感知管线使用 OpenCV 进行 UI 元素检测（SoM 标注）
- 用户指令通过聊天输入组件接收，由 VLM 规划器生成决策
"""

import time
from datetime import datetime
from typing import Optional

import logging
import numpy as np
import streamlit as st

logger = logging.getLogger(__name__)

from src.perception import MaaSensor
from src.perception.models import GameState, PerceptionResult
from src.planning.models import ActionCommand, ActionType, MemoryEntry
from src.planning.vlm_client import VLMPlanner
from src.planning.orchestrator import (
    TaskOrchestrator,
    OrchestratorStatus,
    StepResult,
    TaskResult,
)
from src.planning.memory_manager import MemoryManager
from src.planning.exceptions import PlanningError
from src.utils.window import enumerate_windows, WindowInfo
from src.perception.cv_pipeline import FastPerceptionPipeline
from src.control.executor import ActionExecutor


# =============================================================================
# Windows DPI 感知设置（防止截图坐标错位）
# =============================================================================

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# =============================================================================
# 页面配置
# =============================================================================

st.set_page_config(
    page_title="MaaTexas God's Eye",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 样式
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
    }
    .log-entry {
        font-family: 'Consolas', monospace;
        font-size: 0.9rem;
        background-color: #f5f5f5;
        padding: 8px;
        border-radius: 4px;
        margin: 4px 0;
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-connected { background-color: #28a745; }
    .status-disconnected { background-color: #dc3545; }
    .command-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .command-label {
        font-size: 0.85rem;
        opacity: 0.9;
        margin-bottom: 5px;
    }
    .command-text {
        font-size: 1.1rem;
        font-weight: 600;
    }
    .history-item {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 6px;
        margin: 8px 0;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# 传感器管理（使用 Streamlit 缓存机制）
# =============================================================================

@st.cache_resource
def get_sensor(_hwnd: int = 0) -> MaaSensor:
    """获取或创建 MaaSensor 单例实例。

    使用 @st.cache_resource 确保传感器只被实例化和连接一次，
    防止页面每次刷新都断开重连。

    Args:
        _hwnd: 目标窗口句柄，0 表示捕获桌面。（使用 _ 前缀让 streamlit 忽略此参数用于缓存）

    Returns:
        MaaSensor: 已连接的传感器实例。
    """
    sensor = MaaSensor()
    # 根据句柄连接（0 表示桌面）
    if _hwnd != 0:
        # 通过句柄查找窗口标题
        windows = enumerate_windows()
        target = next((w for w in windows if w.hwnd == _hwnd), None)
        if target:
            sensor.connect(window_title=target.title)
        else:
            sensor.connect()
    else:
        sensor.connect()
    return sensor


def get_sensor_for_hwnd(hwnd: int = 0) -> MaaSensor:
    """获取指定窗口的传感器实例（不缓存，每次创建新的）。

    Args:
        hwnd: 目标窗口句柄，0 表示捕获桌面。

    Returns:
        MaaSensor: 已连接的传感器实例。
    """
    # 清除缓存
    get_sensor.clear()
    # 创建新实例
    return get_sensor(hwnd)


def capture_sensor_frame(sensor: MaaSensor) -> Optional[np.ndarray]:
    """从传感器捕获一帧画面。

    Args:
        sensor: MaaSensor 实例。

    Returns:
        Optional[np.ndarray]: RGB 格式的画面数组，失败返回 None。
    """
    return sensor.capture_frame()


# =============================================================================
# OpenCV 感知管线（使用 Streamlit 缓存机制）
# =============================================================================

@st.cache_resource
def get_cv_pipeline() -> FastPerceptionPipeline:
    """获取或创建 FastPerceptionPipeline 单例实例。

    使用 @st.cache_resource 确保管线只被实例化一次。

    Returns:
        FastPerceptionPipeline: 感知管线实例。
    """
    return FastPerceptionPipeline(
        min_contour_area=100.0,
        max_contour_area_ratio=0.6,
        canny_low=50,
        canny_high=150
    )


@st.cache_resource
def get_planner() -> VLMPlanner:
    """获取或创建 VLMPlanner 单例实例。

    使用 @st.cache_resource 确保规划器只被实例化一次。

    Returns:
        VLMPlanner: VLM 规划器实例。
    """
    return VLMPlanner(model="glm-4v-flash")  # 使用视觉多模态模型


# =============================================================================
# 用户指令管理（使用 Session State）
# =============================================================================

# 初始化指令历史
if "command_history" not in st.session_state:
    st.session_state.command_history = []

# 最新指令（用于显示）
if "latest_command" not in st.session_state:
    st.session_state.latest_command = None

# 当前行为命令（由 VLM 生成）
if "current_action" not in st.session_state:
    st.session_state.current_action = None

# 自动驾驶模式状态
if "auto_pilot_mode" not in st.session_state:
    st.session_state.auto_pilot_mode = False
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
if "orchestrator_status" not in st.session_state:
    st.session_state.orchestrator_status = OrchestratorStatus.IDLE
if "orchestrator_steps" not in st.session_state:
    st.session_state.orchestrator_steps = []
if "max_auto_steps" not in st.session_state:
    st.session_state.max_auto_steps = 10
if "task_running" not in st.session_state:
    st.session_state.task_running = False

# 记忆管理器（全局单例）
@st.cache_resource
def get_memory_manager() -> MemoryManager:
    """获取或创建记忆管理器单例。"""
    return MemoryManager(memory_file="experience.json", max_memory_size=100)

memory_manager = get_memory_manager()


def process_user_command(
    command: str,
    perception: Optional[PerceptionResult],
    game_state: GameState
) -> None:
    """处理用户指令，使用 VLM 进行智能决策。

    Args:
        command: 用户输入的自然语言指令。
        perception: 感知管线输出结果（包含标注图像和 UI 元素）。
        game_state: 当前游戏状态。

    架构说明：
    1. 接收用户自然语言指令
    2. 检查感知数据有效性
    3. 调用 VLM 规划器进行意图理解和任务分解
    4. 生成 ActionCommand
    5. 保存到 session_state 供控制层使用
    """
    # 清空上一次的推理状态
    st.session_state.current_action = None

    # 将指令添加到历史
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.command_history.append({
        "command": command,
        "timestamp": timestamp,
        "status": "pending"  # pending, planning, executing, completed, failed
    })

    # 更新最新指令
    st.session_state.latest_command = {
        "command": command,
        "timestamp": timestamp
    }

    # 检查感知数据有效性
    if perception is None or not perception.ui_elements:
        st.error("⚠️ 当前没有有效的视觉感知数据，无法规划")
        # 更新状态为 failed
        if st.session_state.command_history:
            st.session_state.command_history[-1]["status"] = "failed"
        return

    # 检查是否为自动驾驶模式
    if st.session_state.auto_pilot_mode:
        # 自动驾驶模式：启动任务编排器
        _run_auto_pilot_task(command, perception, game_state)
    else:
        # 单步模式：调用 VLM 生成单步动作
        _run_single_step(command, perception, game_state)


def _run_single_step(
    command: str,
    perception: PerceptionResult,
    game_state: GameState
) -> None:
    """单步模式：调用 VLM 生成单步动作。

    Args:
        command: 用户指令。
        perception: 感知结果。
        game_state: 游戏状态。
    """
    # 显示等待提示
    st.toast("🤖 正在呼叫 VLM 大脑推理中...", icon="🧠")

    # 使用 spinner 显示加载状态
    with st.spinner("🔮 VLM 正在分析画面并生成决策..."):
        try:
            # 获取 VLM 规划器
            planner = get_planner()

            # 调用 VLM 生成行为命令
            action = planner.generate_action(perception, game_state, command)

            # 保存到 session_state
            st.session_state.current_action = action

            # 更新状态为 completed
            if st.session_state.command_history:
                st.session_state.command_history[-1]["status"] = "completed"

            # 显示成功提示
            st.success(f"✅ 决策完成：点击坐标 ({action.target_coords[0]}, {action.target_coords[1]})")
            if action.params.get("thought"):
                st.info(f"💭 VLM 思考：{action.params['thought'][:200]}...")

        except PlanningError as e:
            logger.error(f"VLM 规划失败：{e.code} - {e.message}")
            st.error(f"❌ 规划失败：{e.message}")
            if st.session_state.command_history:
                st.session_state.command_history[-1]["status"] = "failed"
        except Exception as e:
            logger.error(f"VLM 调用异常：{type(e).__name__}: {e}")
            st.error(f"❌ 调用失败：{type(e).__name__}: {e}")
            if st.session_state.command_history:
                st.session_state.command_history[-1]["status"] = "failed"


def _run_auto_pilot_task(
    command: str,
    perception: PerceptionResult,
    game_state: GameState
) -> None:
    """自动驾驶模式：启动任务编排器执行多步任务。

    Args:
        command: 用户指令。
        perception: 感知结果。
        game_state: 游戏状态。
    """
    logger.info(f"启动自动驾驶任务：{command}")

    # 检查是否已有任务在运行
    if st.session_state.task_running:
        st.warning("⚠️ 已有任务正在运行，请先停止当前任务")
        return

    # 获取窗口句柄
    current_hwnd = st.session_state.get("selected_hwnd", 0)

    # 获取组件实例
    sensor = get_sensor(current_hwnd)
    pipeline = get_cv_pipeline()
    planner = get_planner()
    executor = ActionExecutor(hwnd=current_hwnd)

    # 创建任务编排器（带记忆管理器）
    orchestrator = TaskOrchestrator(
        planner=planner,
        executor=executor,
        sensor=sensor,
        pipeline=pipeline,
        memory_manager=memory_manager,
        hwnd=current_hwnd,
        stuck_threshold=3  # 连续 3 次失败认为陷入困境
    )

    # 设置步骤回调（实时传回 UI）
    def on_step(step: StepResult) -> None:
        st.session_state.orchestrator_steps.append(step)
        logger.info(f"步骤 {step.step_number}: {step.thought[:50]}...")

    def on_status(status: OrchestratorStatus) -> None:
        st.session_state.orchestrator_status = status
        logger.info(f"任务状态：{status.value}")
        if status in [OrchestratorStatus.COMPLETED, OrchestratorStatus.FAILED, OrchestratorStatus.STOPPED]:
            st.session_state.task_running = False

    orchestrator.set_callbacks(on_step=on_step, on_status=on_status)

    # 保存到 session_state
    st.session_state.orchestrator = orchestrator
    st.session_state.orchestrator_status = OrchestratorStatus.RUNNING
    st.session_state.orchestrator_steps = []
    st.session_state.task_running = True

    # 显示提示
    st.info(f"🤖 自动驾驶任务已启动：{command}")
    st.info(f"最大步数：{st.session_state.max_auto_steps}")

    # 运行任务（同步执行，实际生产环境应该使用线程）
    try:
        # 使用 asyncio.run 运行异步任务
        import asyncio
        result = asyncio.run(orchestrator.run_task(command, max_steps=st.session_state.max_auto_steps))
        st.session_state.orchestrator_status = result.status

        if result.status == OrchestratorStatus.COMPLETED:
            st.success(f"✅ 任务完成！执行了 {len(result.steps)} 步")
        elif result.status == OrchestratorStatus.FAILED:
            st.error(f"❌ 任务失败：{result.error_message}")
        elif result.status == OrchestratorStatus.STOPPED:
            st.warning("⚠️ 任务被手动停止")

    except Exception as e:
        logger.error(f"自动驾驶任务异常：{type(e).__name__}: {e}")
        st.session_state.orchestrator_status = OrchestratorStatus.FAILED
        st.session_state.task_running = False
        st.error(f"❌ 任务异常：{type(e).__name__}: {e}")


# =============================================================================
# 侧边栏配置
# =============================================================================

with st.sidebar:
    st.header("⚙️ 控制面板")

    # 获取可用窗口列表（用于下拉选择）
    available_windows = enumerate_windows(
        visible_only=True,
        min_title_length=1,
        exclude_patterns=[
            "Program Manager",
            "Windows Input Experience",
            "NVIDIA",
            "Microsoft Text Input Application",
            "Search",
            "TaskBar",
        ]
    )

    # 构建下拉选项：桌面 + 所有窗口
    window_options = ["🖥️ 桌面（所有显示器）"] + [
        f"🪟 {w.title}" for w in available_windows
    ]
    window_values = [0] + [w.hwnd for w in available_windows]

    # 窗口选择下拉框 - 使用 session_state 跟踪变化
    if "selected_hwnd" not in st.session_state:
        st.session_state.selected_hwnd = 0
        st.session_state.last_sensor_hwnd = -1  # 用于检测变化

    selected_index = st.selectbox(
        "🎯 捕获目标",
        options=range(len(window_options)),
        format_func=lambda i: window_options[i],
        index=0,  # 默认选择桌面
        help="选择要捕获的窗口或桌面",
        key="window_selector"
    )

    # 获取选中的窗口句柄
    selected_hwnd = window_values[selected_index]

    # 后台点击提示
    if selected_hwnd == 0:
        st.caption("⚠️ 桌面模式无法使用后台点击，请选择具体窗口")
    else:
        st.caption("✅ 窗口模式支持后台无感点击")

    # 检测窗口变化，如果变化则清除缓存
    if selected_hwnd != st.session_state.last_sensor_hwnd:
        get_sensor.clear()
        st.session_state.last_sensor_hwnd = selected_hwnd
    
    st.session_state.selected_hwnd = selected_hwnd

    # 根据选择获取传感器（窗口变化时会重新创建）
    sensor = get_sensor(selected_hwnd)

    # 传感器状态显示
    status_class = "status-connected" if sensor.is_connected else "status-disconnected"
    status_text = "已连接" if sensor.is_connected else "未连接"

    st.markdown(
        f'<span class="status-indicator {status_class}"></span>'
        f'<strong>传感器状态:</strong> {status_text}',
        unsafe_allow_html=True
    )

    if sensor.is_connected:
        if sensor._hwnd != 0:
            # 查找窗口标题用于显示
            target_window = next(
                (w for w in available_windows if w.hwnd == sensor._hwnd),
                None
            )
            if target_window:
                st.caption(f"窗口：{target_window.title}")
            st.caption(f"句柄：{sensor._hwnd:#x}")
        else:
            st.caption("🖥️ 桌面捕获模式")

    st.divider()

    # 自动刷新开关（默认开启，10Hz）
    auto_refresh = st.toggle(
        "🔄 自动刷新 (10Hz)",
        value=True,
        help="开启后每 0.1 秒（10Hz）自动刷新一次数据"
    )

    # 刷新按钮（手动刷新窗口列表）
    if st.button("🔄 刷新窗口列表", use_container_width=True):
        # 清除传感器缓存
        get_sensor.clear()
        st.rerun()

    st.divider()

    # 自动驾驶模式开关
    st.subheader("🤖 自动驾驶模式")
    auto_pilot_mode = st.toggle(
        "开启自动驾驶模式 (Auto-Pilot)",
        value=st.session_state.auto_pilot_mode,
        help="开启后，Agent 将自动循环执行任务直到完成，无需手动点击执行按钮"
    )
    st.session_state.auto_pilot_mode = auto_pilot_mode

    if auto_pilot_mode:
        # 最大步数设置
        max_auto_steps = st.slider(
            "最大执行步数",
            min_value=1,
            max_value=20,
            value=st.session_state.max_auto_steps,
            help="达到最大步数后自动停止"
        )
        st.session_state.max_auto_steps = max_auto_steps

        # 任务状态显示
        status = st.session_state.orchestrator_status
        status_color = {
            OrchestratorStatus.IDLE: "⚪",
            OrchestratorStatus.RUNNING: "🟡",
            OrchestratorStatus.PAUSED: "🟠",
            OrchestratorStatus.COMPLETED: "🟢",
            OrchestratorStatus.FAILED: "🔴",
            OrchestratorStatus.STOPPED: "⚫"
        }.get(status, "⚪")

        st.markdown(f"**任务状态：** {status_color} {status.value}")

        if st.session_state.orchestrator_steps:
            st.markdown(f"**已执行：** {len(st.session_state.orchestrator_steps)} 步 / {st.session_state.max_auto_steps}")

        # 停止按钮
        if status == OrchestratorStatus.RUNNING:
            if st.button("⏹️ 停止任务", use_container_width=True, key="stop_task_btn"):
                if st.session_state.orchestrator:
                    st.session_state.orchestrator.stop()
                    st.session_state.orchestrator_status = OrchestratorStatus.STOPPED
                    st.session_state.task_running = False
                    st.rerun()

    st.divider()

    # 状态指示器
    st.subheader("📊 系统状态")
    st.metric("框架版本", "v0.1.0")
    st.metric("运行模式", "Debug" if auto_refresh else "Manual")

    st.divider()

    # 信息面板
    st.info("""
    **MaaTexas God's Eye** - 实时调试看板

    监控：
    - 📡 MaaFramework 传感器画面流
    - 🌍 世界模型状态
    - 🧠 LLM 推理日志
    - 🎮 用户指令中心
    """)

    # 技术信息
    with st.expander("ℹ️ 技术栈"):
        st.write("""
        - **框架**: MaaTexas
        - **UI**: Streamlit
        - **传感器**: MaaFramework (Win32)
        - **数据契约**: Pydantic v2
        """)


# =============================================================================
# 主页面布局
# =============================================================================

# 页面标题
st.markdown('<p class="main-header">👁️ MaaTexas God\'s Eye</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">实时调试与监控看板 | Real-time Debug Dashboard</p>', unsafe_allow_html=True)
st.divider()

# 从 session_state 获取当前选择的窗口句柄
current_hwnd = st.session_state.get("selected_hwnd", 0)

# 获取传感器实例（使用当前选择的窗口句柄）
sensor = get_sensor(current_hwnd)

# 获取 CV 管线实例
pipeline = get_cv_pipeline()

# 捕获真实画面（带帧缓存机制，避免黑框闪烁）
real_frame = capture_sensor_frame(sensor)

# 帧缓存：如果获取失败，使用上一帧
if real_frame is not None:
    st.session_state.last_valid_frame = real_frame
else:
    real_frame = st.session_state.get("last_valid_frame")

# 处理感知管线（如果有画面）
perception_result: Optional[PerceptionResult] = None
if real_frame is not None:
    perception_result = pipeline.process(real_frame)

# 获取真实数据（从 session_state 或感知结果）
game_state = GameState(
    current_scene="unknown",
    hp_percent=100.0,
    sanity_percent=100.0
)
# 优先使用 VLM 生成的行为命令
action_command = st.session_state.get("current_action")

# 创建左右两栏布局 (6:4 比例)
col1, col2 = st.columns([6, 4])

# -----------------------------------------------------------------------------
# 左栏：Sensor Feed（真实传感器画面流）
# -----------------------------------------------------------------------------
with col1:
    st.subheader("📡 Sensor Feed")

    if perception_result is not None and real_frame is not None:
        # 显示感知处理后的画面（带 SoM 标注）
        st.image(
            perception_result.annotated_image,
            caption=f"实时传感器画面 (SoM 标注) | 分辨率：{real_frame.shape[1]}x{real_frame.shape[0]} | 检测到 {len(perception_result.ui_elements)} 个 UI 元素",
            use_container_width=True
        )

        # 画面统计信息
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.metric("图像尺寸", f"{real_frame.shape[1]}x{real_frame.shape[0]}")
        with col_img2:
            st.metric("检测到 UI 元素", len(perception_result.ui_elements))
    elif real_frame is not None:
        # 感知处理失败但原始画面存在
        st.image(
            real_frame,
            caption=f"实时传感器画面 | 分辨率：{real_frame.shape[1]}x{real_frame.shape[0]}",
            use_container_width=True
        )
    else:
        # 占位提示（黑色背景）
        st.warning("⚠️ 等待传感器信号...")
        st.info("""
        **可能原因：**
        - 传感器正在初始化
        - 目标窗口未找到
        - 截图操作暂时失败

        请检查侧边栏的传感器状态，或尝试重新连接。
        """)

        # 显示占位图像
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        placeholder[:, :] = (30, 30, 40)
        st.image(placeholder, caption="等待中...", use_container_width=True)

# -----------------------------------------------------------------------------
# 右栏：World Model + LLM Reasoning + User Command Center
# -----------------------------------------------------------------------------
with col2:
    # 上部：User Command Center（用户指令中心）+ 指令输入
    st.subheader("🎮 User Command Center")

    # 聊天输入框（放在顶部，更显眼）
    user_input = st.chat_input(
        "请输入您想让 MaaTexas 执行的游戏任务...",
        key="command_input"
    )

    # 处理用户输入
    if user_input:
        # 检查是否有有效的感知数据
        if perception_result is None or not perception_result.ui_elements:
            st.error("⚠️ 当前没有有效的视觉感知数据，请先捕获画面")
        else:
            # 调用 VLM 规划器（在 process_user_command 内部处理）
            process_user_command(user_input, perception_result, game_state)
            # 注意：process_user_command 内部已经显示了成功/失败提示
            if auto_refresh:
                st.rerun()

    # 显示最新指令
    if st.session_state.latest_command:
        latest = st.session_state.latest_command
        st.markdown(f"""
            <div class="command-box">
                <div class="command-label">📍 当前指令</div>
                <div class="command-text">{latest["command"]}</div>
                <div style="margin-top: 8px; opacity: 0.8; font-size: 0.8rem;">
                    ⏰ {latest["timestamp"]}
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("💬 在上方输入框中输入指令，让 MaaTexas 执行游戏任务")

    # 指令历史（最近 5 条）
    if st.session_state.command_history:
        st.markdown("**📜 指令历史**")
        recent_history = st.session_state.command_history[-5:][::-1]
        for item in recent_history:
            status_icon = {
                "pending": "⏳",
                "planning": "🤔",
                "executing": "⚙️",
                "completed": "✅",
                "failed": "❌"
            }.get(item["status"], "⚪")
            st.markdown(f"""
                <div class="history-item">
                    <strong>{status_icon} [{item["timestamp"]}]</strong><br/>
                    {item["command"]}
                </div>
            """, unsafe_allow_html=True)

    st.divider()

    # 中部：World Model（世界模型）
    st.subheader("🌍 World Model")

    # 使用 Tabs 组织不同的模型视图
    tabs = ["GameState", "Action"]
    if perception_result is not None:
        tabs.append("Perception")
    tabs.append("🧠 记忆库")

    tab_objects = st.tabs(tabs)

    with tab_objects[0]:
        st.markdown("**当前游戏状态**")
        st.json(game_state.model_dump(mode="json", by_alias=True))

    with tab_objects[1]:
        st.markdown("**当前行为命令**")
        if action_command is not None:
            st.json(action_command.model_dump(mode="json", by_alias=True))
        else:
            st.info("暂无行为命令，等待用户指令...")

    # Perception Tab（感知结果）
    if perception_result is not None:
        with tab_objects[2]:
            st.markdown("**感知管线结果**")

            # 显示 UI 元素列表
            if perception_result.ui_elements:
                st.markdown(f"**检测到 {len(perception_result.ui_elements)} 个 UI 元素**")

                # 构建可序列化的数据结构
                ui_data = []
                for elem in perception_result.ui_elements:
                    ui_data.append({
                        "id": elem.element_id,
                        "type": elem.element_type,
                        "confidence": round(elem.confidence, 3),
                        "bbox": {
                            "x": elem.bbox[0],
                            "y": elem.bbox[1],
                            "width": elem.bbox[2],
                            "height": elem.bbox[3]
                        }
                    })

                st.json({"ui_elements": ui_data, "count": len(ui_data)})
            else:
                st.info("未检测到 UI 元素")

    # 记忆库 Tab
    with tab_objects[3]:
        st.markdown("**🧠 记忆库**")

        # 知识地图展示
        km = memory_manager.knowledge_map
        if km.ui_knowledge:
            st.markdown(f"**UI 知识** ({len(km.ui_knowledge)} 个元素)")
            for elem_id, info in list(km.ui_knowledge.items())[:10]:
                st.markdown(f"- `{elem_id}`: {info.get('function', '未知')} (置信度：{info.get('confidence', 0):.2f})")

        # 失败模式展示
        if km.failure_patterns:
            st.markdown(f"**失败模式** ({len(km.failure_patterns)} 条)")
            for pattern in km.failure_patterns[-5:]:
                st.markdown(f"- `{pattern['element_id']}` + {pattern['action_type']}: {pattern['reason']}")

        # 历史记忆展示
        recent_memories = memory_manager.get_recent_memories(count=5)
        if recent_memories:
            st.markdown(f"**历史记忆** ({len(recent_memories)} 条)")
            for mem in recent_memories:
                icon = "✅" if mem.success else "❌"
                st.markdown(f"{icon} **{mem.user_command}** - {mem.reflection[:50]}...")

        # 清空记忆按钮
        if st.button("🗑️ 清空记忆", use_container_width=True):
            memory_manager.clear()
            st.success("记忆已清空")
            st.rerun()

    # 下部：LLM Reasoning（推理日志）
    st.subheader("🧠 LLM Reasoning")

    with st.expander("📜 查看推理过程日志", expanded=True):
        # 检查是否有真实的 VLM 推理结果
        if action_command is not None and "thought" in action_command.params:
            # 展示真实的 VLM 推理日志
            real_thought = action_command.params["thought"]
            target_id = action_command.params.get("target_id", "未知")

            # VLM 推理日志
            st.markdown(
                f"""
                <div class="log-entry">
                    <code>🧠 [VLM 推理] {real_thought}</code>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 系统执行日志
            coords_str = f"{action_command.target_coords[0]}, {action_command.target_coords[1]}" if action_command.target_coords else "N/A"
            st.markdown(
                f"""
                <div class="log-entry">
                    <code>🎯 [系统执行] 决定点击 UI 元素 [{target_id}] -> 坐标 ({coords_str})</code>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 执行按钮（仅单步模式显示）
            if not st.session_state.auto_pilot_mode:
                st.divider()
                if st.button("🕹️ 执行此动作 (Execute)", type="primary", use_container_width=True):
                    with st.spinner("正在向目标窗口发送后台点击指令..."):
                        executor = ActionExecutor(hwnd=current_hwnd)
                        success = executor.execute(action_command)
                        if success:
                            st.success("✅ 后台动作下发成功！(如果游戏内无反应，可能是游戏引擎屏蔽了虚拟输入)")
                        else:
                            st.error("❌ 动作执行失败，请检查控制台日志。")
        else:
            # 无推理任务时的提示
            st.info("💤 暂无推理任务，等待用户下达指令...")

    # 自动驾驶任务步骤展示（如果正在运行）
    if st.session_state.auto_pilot_mode and st.session_state.orchestrator_steps:
        st.divider()
        st.subheader("📋 任务执行步骤")

        for step in st.session_state.orchestrator_steps[-5:]:  # 只显示最近 5 步
            status_icon = "✅" if step.success else "❌"
            st.markdown(f"**步骤 {step.step_number}** {status_icon}")
            st.markdown(f"- 思考：{step.thought[:100]}...")
            st.markdown(f"- 动作：{step.action_type} -> {step.target_coords}")


# =============================================================================
# 自动刷新机制
# =============================================================================

if auto_refresh:
    time.sleep(0.1)  # 10Hz 刷新
    st.rerun()
