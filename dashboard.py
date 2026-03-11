#!/usr/bin/env python
"""
MaaTexas God's Eye - 可视化 Debug 看板。

基于 Streamlit 构建的实时调试界面，用于监控感知、规划和控制模块的运行状态。
遵循 "Separation of Concerns" 原则，此 UI 工具独立于 src/ 核心域。

传感器数据流：
- 使用 src.perception.MaaSensor 接入真实的 MaaFramework 画面采集
- 世界模型和推理日志暂时使用 Mock 数据（待后续接入 OCR）
- 用户指令通过聊天输入组件接收，未来将接入 LLM 规划器
"""

import random
import time
from datetime import datetime
from typing import Any, Optional

import logging
import numpy as np
import streamlit as st

logger = logging.getLogger(__name__)

from src.perception import MaaSensor
from src.perception.models import GameState, PerceptionResult
from src.planning.models import ActionCommand, ActionType, TaskPlan
from src.planning.vlm_client import VLMPlanner
from src.planning.exceptions import PlanningError
from src.utils.window import enumerate_windows, WindowInfo
from src.perception.cv_pipeline import FastPerceptionPipeline


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
    return VLMPlanner(model="glm-4v-flash")


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


# =============================================================================
# Mock 数据生成器（用于世界模型和推理日志）
# =============================================================================

def generate_mock_game_state() -> GameState:
    """生成模拟的游戏状态数据。

    Returns:
        GameState: 模拟的游戏状态实例。
    """
    scenes = ["main_menu", "battle", "recruit", "base", "shop"]
    return GameState(
        current_scene=random.choice(scenes),
        hp_percent=random.uniform(20.0, 100.0),
        sanity_percent=random.uniform(10.0, 100.0),
        current_level=f"{random.randint(1, 7)}-{random.randint(1, 8)}",
        is_battling=random.choice([True, False]),
        last_update=datetime.now()
    )


def generate_mock_action_command() -> ActionCommand:
    """生成模拟的行为命令数据。

    Returns:
        ActionCommand: 模拟的行为命令实例。
    """
    action_types = [ActionType.CLICK, ActionType.SWIPE, ActionType.WAIT, ActionType.NAVIGATE]
    return ActionCommand(
        action_type=random.choice(action_types),
        target_coords=(random.randint(100, 800), random.randint(100, 600)) if random.random() > 0.3 else None,
        duration_ms=random.randint(0, 2000),
        params={"source": "mock_generator"},
        priority=random.randint(0, 10),
        timeout_seconds=random.uniform(5.0, 30.0)
    )


def generate_mock_task_plan() -> TaskPlan:
    """生成模拟的任务计划数据。

    Returns:
        TaskPlan: 模拟的任务计划实例。
    """
    commands = [generate_mock_action_command() for _ in range(random.randint(1, 5))]
    return TaskPlan(
        task_id=f"TASK_{random.randint(1000, 9999)}",
        task_name=random.choice(["自动战斗", "资源收集", "日常任务", "关卡推进"]),
        commands=commands,
        preconditions=["场景已加载", "网络已连接"],
        expected_result="任务成功完成",
        created_at=datetime.now()
    )


def generate_llm_reasoning_log(game_state: GameState) -> list[dict[str, Any]]:
    """生成模拟的 LLM 推理过程日志。

    Args:
        game_state: 当前游戏状态，用于生成上下文相关的推理日志。

    Returns:
        list[dict[str, Any]]: 推理日志条目列表。
    """
    logs = [
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "message": "=== 开始新一轮决策循环 ==="
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "DEBUG",
            "message": f"感知输入：scene={game_state.current_scene}, hp={game_state.hp_percent:.1f}%"
        },
    ]

    # 根据游戏状态生成条件性推理
    if game_state.hp_percent < 30.0:
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "WARNING",
            "message": f"⚠️ 检测到 hp_percent ({game_state.hp_percent:.1f}%) < 0.3，准备触发治疗动作..."
        })
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "message": "规划策略：优先执行 [撤退] -> [使用治疗道具]"
        })
    elif game_state.is_battling:
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "message": "当前处于战斗状态，继续执行战斗策略..."
        })
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "DEBUG",
            "message": "检测到敌方单位，计算最优攻击目标..."
        })
    else:
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "message": "非战斗状态，检查日常任务队列..."
        })
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "DEBUG",
            "message": f"理智值剩余 {game_state.sanity_percent:.1f}%，评估是否继续作战"
        })

    logs.append({
        "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "level": "INFO",
        "message": "决策完成，下发行动指令至控制层"
    })

    return logs


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

# 捕获真实画面
real_frame = capture_sensor_frame(sensor)

# 处理感知管线（如果有画面）
perception_result: Optional[PerceptionResult] = None
if real_frame is not None:
    perception_result = pipeline.process(real_frame)

# 生成 Mock 数据（用于世界模型和推理）
game_state = generate_mock_game_state()
# 优先使用 VLM 生成的行为命令，如果没有则使用 Mock
action_command = st.session_state.get("current_action") or generate_mock_action_command()
task_plan = generate_mock_task_plan()
llm_logs = generate_llm_reasoning_log(game_state)

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
        st.warning("⚠️ 感知管线处理失败，显示原始画面")
    else:
        # 占位提示
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
    tabs = ["GameState", "Action", "TaskPlan"]
    if perception_result is not None:
        tabs.append("Perception")
    
    tab_objects = st.tabs(tabs)

    with tab_objects[0]:
        st.markdown("**当前游戏状态** (Mock)")
        st.json(game_state.model_dump(mode="json", by_alias=True))

    with tab_objects[1]:
        st.markdown("**当前行为命令** (Mock)")
        st.json(action_command.model_dump(mode="json", by_alias=True))

    with tab_objects[2]:
        st.markdown("**任务计划** (Mock)")
        st.json(task_plan.model_dump(mode="json", by_alias=True))

    # Perception Tab（感知结果）
    if perception_result is not None:
        with tab_objects[3]:
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

    # 下部：LLM Reasoning（推理日志）
    st.subheader("🧠 LLM Reasoning")

    with st.expander("📜 查看推理过程日志", expanded=True):
        for log_entry in llm_logs:
            # 根据日志级别设置颜色
            level_colors = {
                "INFO": "🔵",
                "DEBUG": "🟢",
                "WARNING": "🟡",
                "ERROR": "🔴"
            }
            icon = level_colors.get(log_entry["level"], "⚪")

            st.markdown(
                f"""
                <div class="log-entry">
                    <code>{icon} [{log_entry["timestamp"]}] {log_entry["level"]}: {log_entry["message"]}</code>
                </div>
                """,
                unsafe_allow_html=True
            )


# =============================================================================
# 自动刷新机制
# =============================================================================

if auto_refresh:
    time.sleep(0.1)  # 10Hz 刷新
    st.rerun()
