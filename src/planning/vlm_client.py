"""
MaaTexas 规划模块 - VLM (Vision Language Model) 客户端。

接入智谱 GLM-4V 视觉大语言模型，作为 Agent 的决策大脑。
根据 Set-of-Mark 画面和用户指令进行智能决策。
"""

import base64
import json
import logging
import os
from typing import Any, Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from src.perception.models import PerceptionResult, GameState, UIElement
from src.planning.models import ActionCommand, ActionType
from src.planning.exceptions import PlanningError

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class VLMPlanner:
    """VLM 规划器。

    使用智谱 GLM-4V 视觉大语言模型进行多模态推理，
    根据感知画面和游戏状态生成智能行为命令。

    Attributes:
        client: OpenAI 兼容的 API 客户端。
        model: 使用的模型名称。

    Example:
        ```python
        planner = VLMPlanner()
        action = planner.generate_action(perception_result, game_state, "领取邮件")
        controller.execute(action)
        ```
    """

    def __init__(self, model: str = "glm-4v-flash") -> None:
        """初始化 VLM 规划器。

        Args:
            model: 使用的模型名称，默认为 glm-4v-flash（视觉多模态模型）。
                   其他可选值：glm-4-flash（文本）。

        Raises:
            PlanningError: 当 API 密钥未配置时抛出。
        """
        # 尝试从环境变量获取 API 密钥
        api_key = os.environ.get("ZHIPU_API_KEY")

        if not api_key or api_key == "your_api_key_here":
            raise PlanningError(
                code="PLANNING_VLM_001",
                message="智谱 API 密钥未配置",
                details="请在项目根目录创建 .env 文件，并设置 ZHIPU_API_KEY 环境变量。"
                        "请前往 https://open.bigmodel.cn/ 申请免费额度。"
            )

        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/"
        )

        logger.info(f"VLMPlanner 已初始化，模型：{model}（视觉多模态）")

    def _image_to_base64(self, image: np.ndarray) -> str:
        """将图像转换为 base64 字符串。

        Args:
            image: numpy 数组格式的图像（RGB 或 BGR）。

        Returns:
            str: base64 编码的 JPEG 图像字符串（不含前缀）。
        """
        # 确保是 BGR 格式（OpenCV 默认）
        if len(image.shape) == 3 and image.shape[2] == 3:
            # 假设输入是 RGB，转换为 BGR 用于 JPEG 编码
            bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            bgr_image = image

        # 编码为 JPEG
        _, buffer = cv2.imencode('.jpg', bgr_image, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # 转换为 base64 字符串
        base64_str = base64.b64encode(buffer).decode('utf-8')

        return base64_str

    def _simplify_ui_elements(self, ui_elements: list[UIElement]) -> list[dict[str, Any]]:
        """简化 UI 元素列表，仅保留必要信息。

        Args:
            ui_elements: UI 元素列表。

        Returns:
            list[dict[str, Any]]: 简化后的元素列表，不包含绝对坐标。
        """
        simplified = []

        for elem in ui_elements:
            simplified.append({
                "id": elem.element_id,
                "type": elem.element_type,
                "text": elem.text_content,
                "confidence": round(elem.confidence, 2)
            })

        return simplified

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """解析 LLM 返回的 JSON 响应。

        处理可能的 Markdown 代码块包裹、JSON 格式不规范等情况。

        Args:
            response_text: LLM 返回的原始文本。

        Returns:
            dict[str, Any]: 解析后的 JSON 对象。

        Raises:
            PlanningError: 当解析失败时抛出。
        """
        text = response_text.strip()

        # 处理 Markdown 代码块包裹的情况
        if text.startswith("```"):
            # 移除 ```json 或 ``` 前缀
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 尝试直接解析 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 部分（如果响应包含额外文本）
        # 查找 { 和 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            json_text = text[start:end+1]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        # 尝试提取 target_id（如果响应只是元素 ID）
        # 查找类似 "target_id": "xxx" 或 "target_id": "ui_0"
        import re
        target_match = re.search(r'"?target_id"?\s*[:=]\s*"?(\w+)"?', text, re.IGNORECASE)
        thought_match = re.search(r'"?thought"?\s*[:=]\s*"?([^",}]+)"?', text, re.IGNORECASE)
        
        if target_match:
            return {
                "target_id": target_match.group(1),
                "thought": thought_match.group(1) if thought_match else "未提供思考过程"
            }

        # 如果响应看起来像一个 ID（如 ui_0, button_1 等）
        id_match = re.search(r'(ui_\d+|btn_\d+|button_\d+|element_\d+)', text, re.IGNORECASE)
        if id_match:
            return {
                "target_id": id_match.group(1),
                "thought": "根据画面分析选择的元素"
            }

        # 所有尝试都失败，抛出错误
        raise PlanningError(
            code="PLANNING_VLM_002",
            message="LLM 返回的 JSON 解析失败",
            details={
                "error": "无法从响应中提取 JSON",
                "raw_response": text[:500]  # 只保留前 500 字符
            }
        )

    def generate_action(
        self,
        perception: PerceptionResult,
        game_state: GameState,
        user_command: str
    ) -> ActionCommand:
        """根据感知结果和游戏状态生成行为命令。

        Args:
            perception: 感知管线输出结果（包含标注图像和 UI 元素）。
            game_state: 当前游戏状态。
            user_command: 用户自然语言指令。

        Returns:
            ActionCommand: 生成的行为命令（通常是点击操作）。

        Raises:
            PlanningError: 当 API 调用失败或响应解析失败时抛出。
        """
        # 1. 数据精简 - 构建 UI 元素简化列表
        simplified_ui = self._simplify_ui_elements(perception.ui_elements)

        # 2. 组装 System Prompt
        system_prompt = """你是一个二游自动化 Agent 的决策大脑（视觉多模态）。
你的任务是根据当前游戏画面和用户需求，选择最合适的 UI 元素进行交互。

**输出格式要求：**
直接返回 JSON，不要任何其他文字：
{{"thought": "你的思考过程", "target_id": "选中的元素 ID"}}

**重要说明：**
- 画面中已经用红色框和编号标注了检测到的 UI 元素
- 请根据画面内容和用户指令，选择最合适的元素 ID
- **如果任务已经达成，请返回 `"target_id": null` 并在 `"thought"` 中说明"任务已完成"**
- 如果画面中没有合适的元素，也请返回 `"target_id": null`"""

        # 3. 将图像转换为 base64
        base64_image = self._image_to_base64(perception.annotated_image)

        # 4. 组装 User Message（包含图像）
        user_message_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            },
            {
                "type": "text",
                "text": f"""当前游戏状态：
- 场景：{game_state.current_scene}
- 生命值：{game_state.hp_percent:.1f}%
- 理智值：{game_state.sanity_percent:.1f}%
- 关卡：{game_state.current_level or 'N/A'}
- 战斗中：{game_state.is_battling}

用户指令：{user_command}

检测到的 UI 元素（共{len(simplified_ui)}个）：
{json.dumps(simplified_ui, ensure_ascii=False, indent=2)}

请分析画面并选择要交互的元素 ID。如果任务已完成，请返回 target_id: null。"""
            }
        ]

        # 5. 发起请求
        try:
            logger.info(f"调用 VLM ({self.model}) 进行决策...")
            logger.info(f"图像尺寸：{perception.annotated_image.shape}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt.format(
                        ui_list=json.dumps(simplified_ui, ensure_ascii=False)
                    )},
                    {"role": "user", "content": user_message_content}
                ],
                temperature=0.1,  # 低温度确保输出稳定
                max_tokens=500,
                timeout=60  # 视觉模型可能需要更长时间
            )

            # 智谱 API 响应格式可能不同，使用安全方式访问
            response_text = None
            
            # 尝试使用 Pydantic 模型方式访问
            try:
                # OpenAI SDK v1.x 使用 Pydantic 模型
                if hasattr(response, 'choices') and response.choices:
                    # 检查 choices 是列表还是字典
                    if isinstance(response.choices, list):
                        choice = response.choices[0]
                    elif isinstance(response.choices, dict):
                        # 智谱可能返回字典格式
                        choice = list(response.choices.values())[0] if response.choices else None
                    else:
                        choice = response.choices
                    
                    if choice and hasattr(choice, 'message'):
                        msg = choice.message
                        if hasattr(msg, 'content'):
                            content = msg.content
                            # content 可能是字符串，直接返回
                            response_text = content if content else None
            except Exception as e:
                logger.warning(f"Pydantic 格式解析失败：{e}")
                import traceback
                logger.debug(traceback.format_exc())
            
            # 如果失败，尝试其他方式
            if not response_text:
                if isinstance(response, dict):
                    # 字典格式
                    choices = response.get('choices', [])
                    if choices:
                        response_text = choices[0].get('message', {}).get('content', '')
                    else:
                        response_text = response.get('result', '')
                elif hasattr(response, 'data'):
                    response_text = response.data.choices[0].message.content
                elif hasattr(response, 'result'):
                    response_text = response.result
                else:
                    response_text = str(response)

            logger.info(f"原始响应：{response_text[:300] if response_text else 'None'}...")

            if not response_text:
                raise PlanningError(
                    code="PLANNING_VLM_003",
                    message="VLM 返回空响应",
                    details={"response": str(response)}
                )

        except Exception as e:
            if isinstance(e, PlanningError):
                raise
            logger.error(f"API 调用异常：{type(e).__name__}: {e}")
            import traceback
            logger.error(f"堆栈跟踪：{traceback.format_exc()}")
            raise PlanningError(
                code="PLANNING_VLM_004",
                message="VLM API 调用失败",
                details={"error": f"{type(e).__name__}: {e}"}
            )

        # 5. 解析响应并映射坐标
        logger.info(f"开始解析响应...")
        parsed = self._parse_llm_response(response_text)
        logger.info(f"解析结果：{parsed}")

        # 提取思考过程（用于日志）
        thought = parsed.get("thought", "无思考过程")
        logger.info(f"VLM 思考：{thought}")

        # 提取目标 ID
        target_id = parsed.get("target_id")

        if target_id is None:
            logger.warning("VLM 未选择任何元素")
            # 返回空命令（不执行任何操作）
            return ActionCommand(
                action_type=ActionType.WAIT,
                target_coords=None,
                duration_ms=1000,
                params={"reason": "VLM 未选择元素", "thought": thought}
            )

        # 在 UI 元素列表中查找匹配的元素
        target_element: Optional[UIElement] = None
        for elem in perception.ui_elements:
            if elem.element_id == target_id:
                target_element = elem
                break

        if target_element is None:
            raise PlanningError(
                code="PLANNING_VLM_005",
                message=f"VLM 选择的元素 ID 不存在：{target_id}",
                details={
                    "available_ids": [e.element_id for e in perception.ui_elements]
                }
            )

        # 6. 计算中心点坐标并返回
        x, y, w, h = target_element.bbox
        cx = x + w // 2
        cy = y + h // 2

        logger.info(f"生成点击命令：({cx}, {cy}) -> {target_id}")

        return ActionCommand(
            action_type=ActionType.CLICK,
            target_coords=(cx, cy),
            duration_ms=100,
            params={
                "target_id": target_id,
                "thought": thought,
                "element_type": target_element.element_type
            }
        )
