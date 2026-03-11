#!/usr/bin/env python
"""VLM 闭环验证脚本。"""

import logging
logging.basicConfig(level=logging.INFO)

from src.planning.vlm_client import VLMPlanner
from src.perception.models import PerceptionResult, GameState, UIElement
import numpy as np

print("=" * 60)
print("VLM 闭环验证")
print("=" * 60)

# 1. 初始化 VLMPlanner
print("\n[1/5] 初始化 VLMPlanner...")
try:
    planner = VLMPlanner(model="glm-4.7-flash")
    print(f"    [OK] 模型：{planner.model}")
except Exception as e:
    print(f"    [FAIL] {e}")
    exit(1)

# 2. 创建测试数据
print("\n[2/5] 创建测试数据...")
game_state = GameState(
    current_scene="main_menu",
    hp_percent=95.0,
    sanity_percent=80.0
)

# 创建带标注的测试图像
test_image = np.zeros((480, 640, 3), dtype=np.uint8)
test_image[:, :] = (50, 50, 80)  # 深蓝色背景

# 画几个带编号的矩形模拟 SoM 标注
import cv2
cv2.rectangle(test_image, (50, 50), (150, 100), (0, 0, 255), 2)
cv2.putText(test_image, "[0]", (55, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
cv2.rectangle(test_image, (200, 150), (350, 250), (0, 0, 255), 2)
cv2.putText(test_image, "[1]", (205, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

ui_elements = [
    UIElement(
        element_id='ui_0',
        element_type='button',
        confidence=0.95,
        bbox=(50, 50, 100, 50),
        text_content='设置'
    ),
    UIElement(
        element_id='ui_1',
        element_type='button',
        confidence=0.92,
        bbox=(200, 150, 150, 100),
        text_content='开始任务'
    )
]

perception = PerceptionResult(
    timestamp=1234567890.0,
    annotated_image=test_image,
    ui_elements=ui_elements
)
print(f"    [OK] 图像：{test_image.shape[1]}x{test_image.shape[0]}")
print(f"    [OK] UI 元素：{len(ui_elements)} 个")

# 3. 调用 VLM
print("\n[3/5] 调用 VLM 进行决策...")
print(f"    用户指令：'点击开始任务按钮'")
try:
    action = planner.generate_action(perception, game_state, '点击开始任务按钮')
    print(f"    [OK] VLM 响应成功!")
except Exception as e:
    print(f"    [FAIL] {e}")
    exit(1)

# 4. 验证结果
print("\n[4/5] 验证结果...")
print(f"    行为类型：{action.action_type}")
print(f"    目标坐标：{action.target_coords}")
print(f"    目标 ID: {action.params.get('target_id')}")
print(f"    VLM 思考：{action.params.get('thought', 'N/A')[:50]}...")

if action.action_type.value == "click" and action.target_coords:
    print(f"    [OK] 生成了有效的点击命令")
else:
    print(f"    [WARN] 命令类型异常")

# 5. Dashboard 集成检查
print("\n[5/5] Dashboard 集成检查...")
try:
    import dashboard
    print(f"    [OK] get_planner 函数：{hasattr(dashboard, 'get_planner')}")
    print(f"    [OK] process_user_command 函数：{hasattr(dashboard, 'process_user_command')}")
    print(f"    [OK] 模型配置：{dashboard.get_planner().model}")
except Exception as e:
    print(f"    [WARN] {e}")

print("\n" + "=" * 60)
print("闭环验证完成!")
print("=" * 60)
print("\nDashboard: http://localhost:8501")
print("模型：glm-4.7-flash（视觉多模态）")
