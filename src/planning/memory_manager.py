"""
MaaTexas 规划模块 - 记忆管理器。

实现 Agent 的长期记忆和知识地图功能，让 Agent 能够从历史经验中学习。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.planning.models import MemoryEntry

logger = logging.getLogger(__name__)


class KnowledgeMap:
    """知识地图。

    记录 UI 元素与其功能的对应关系，支持 Agent 学习和复用经验。

    Attributes:
        ui_knowledge: UI 元素 ID 到功能描述的映射。
        scene_knowledge: 场景特征到推荐操作的映射。
        failure_patterns: 失败模式记录（用于避免重复错误）。
    """

    def __init__(self) -> None:
        """初始化知识地图。"""
        self.ui_knowledge: dict[str, dict[str, Any]] = {}
        self.scene_knowledge: dict[str, dict[str, Any]] = {}
        self.failure_patterns: list[dict[str, Any]] = []

    def update_ui_knowledge(
        self,
        element_id: str,
        function: str,
        confidence: float = 1.0,
        last_verified: Optional[datetime] = None
    ) -> None:
        """更新 UI 元素知识。

        Args:
            element_id: UI 元素 ID。
            function: 功能描述（如"进入商店"、"关闭弹窗"）。
            confidence: 置信度（0.0-1.0）。
            last_verified: 最后验证时间。
        """
        self.ui_knowledge[element_id] = {
            "function": function,
            "confidence": confidence,
            "last_verified": last_verified.isoformat() if last_verified else datetime.now().isoformat(),
            "usage_count": self.ui_knowledge.get(element_id, {}).get("usage_count", 0) + 1
        }
        logger.info(f"更新 UI 知识：{element_id} -> {function} (置信度：{confidence})")

    def update_scene_knowledge(
        self,
        scene_feature: str,
        recommended_action: str,
        success_rate: float = 1.0
    ) -> None:
        """更新场景知识。

        Args:
            scene_feature: 场景特征描述。
            recommended_action: 推荐操作。
            success_rate: 成功率。
        """
        self.scene_knowledge[scene_feature] = {
            "recommended_action": recommended_action,
            "success_rate": success_rate,
            "last_updated": datetime.now().isoformat()
        }
        logger.info(f"更新场景知识：{scene_feature} -> {recommended_action}")

    def record_failure(
        self,
        element_id: str,
        action_type: str,
        reason: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """记录失败模式。

        Args:
            element_id: 失败的元素 ID。
            action_type: 失败的动作类型。
            reason: 失败原因。
            timestamp: 失败时间。
        """
        self.failure_patterns.append({
            "element_id": element_id,
            "action_type": action_type,
            "reason": reason,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "avoid_count": 1
        })
        logger.warning(f"记录失败模式：{element_id} + {action_type} -> {reason}")

    def get_ui_function(self, element_id: str) -> Optional[str]:
        """获取 UI 元素的功能描述。

        Args:
            element_id: UI 元素 ID。

        Returns:
            Optional[str]: 功能描述，未知返回 None。
        """
        if element_id in self.ui_knowledge:
            return self.ui_knowledge[element_id].get("function")
        return None

    def should_avoid(self, element_id: str, action_type: str) -> bool:
        """检查是否应该避免某个操作（基于历史失败）。

        Args:
            element_id: 元素 ID。
            action_type: 动作类型。

        Returns:
            bool: 是否应该避免。
        """
        for pattern in self.failure_patterns[-10:]:  # 只检查最近 10 条
            if (pattern["element_id"] == element_id and
                pattern["action_type"] == action_type):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。

        Returns:
            dict[str, Any]: 知识地图字典表示。
        """
        return {
            "ui_knowledge": self.ui_knowledge,
            "scene_knowledge": self.scene_knowledge,
            "failure_patterns": self.failure_patterns,
            "last_updated": datetime.now().isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeMap":
        """从字典加载知识地图。

        Args:
            data: 知识地图字典数据。

        Returns:
            KnowledgeMap: 知识地图实例。
        """
        km = cls()
        km.ui_knowledge = data.get("ui_knowledge", {})
        km.scene_knowledge = data.get("scene_knowledge", {})
        km.failure_patterns = data.get("failure_patterns", [])
        return km


class MemoryManager:
    """记忆管理器。

    管理 Agent 的长期记忆，包括历史操作记录和知识地图。

    Attributes:
        memory_file: 记忆文件路径。
        knowledge_map: 知识地图实例。
        memory_entries: 历史记忆条目列表。
        max_memory_size: 最大记忆条目数。
    """

    def __init__(
        self,
        memory_file: str = "experience.json",
        max_memory_size: int = 100
    ) -> None:
        """初始化记忆管理器。

        Args:
            memory_file: 记忆文件路径。
            max_memory_size: 最大记忆条目数。
        """
        self.memory_file = Path(memory_file)
        self.knowledge_map = KnowledgeMap()
        self.memory_entries: list[MemoryEntry] = []
        self.max_memory_size = max_memory_size

        # 加载已有记忆
        self.load()

        logger.info(f"MemoryManager 已初始化，文件：{self.memory_file}")

    def add_memory(self, entry: MemoryEntry) -> None:
        """添加记忆条目。

        Args:
            entry: 记忆条目。
        """
        self.memory_entries.append(entry)

        # 限制记忆大小
        if len(self.memory_entries) > self.max_memory_size:
            self.memory_entries = self.memory_entries[-self.max_memory_size:]

        # 从记忆中学习，更新知识地图
        self._learn_from_memory(entry)

        logger.info(f"添加记忆：{entry.user_command} -> {entry.reflection}")

    def _learn_from_memory(self, entry: MemoryEntry) -> None:
        """从记忆中学习，更新知识地图。

        Args:
            entry: 记忆条目。
        """
        if entry.target_element_id:
            if entry.success:
                # 成功操作：增加置信度
                self.knowledge_map.update_ui_knowledge(
                    element_id=entry.target_element_id,
                    function=entry.reflection or "未知功能",
                    confidence=0.9
                )
            else:
                # 失败操作：记录失败模式
                self.knowledge_map.record_failure(
                    element_id=entry.target_element_id,
                    action_type=entry.action_type,
                    reason=entry.reflection or "未知原因"
                )

    def get_recent_memories(self, count: int = 5) -> list[MemoryEntry]:
        """获取最近的记忆。

        Args:
            count: 获取数量。

        Returns:
            list[MemoryEntry]: 记忆条目列表。
        """
        return self.memory_entries[-count:]

    def get_memories_for_command(self, user_command: str) -> list[MemoryEntry]:
        """获取与特定指令相关的记忆。

        Args:
            user_command: 用户指令。

        Returns:
            list[MemoryEntry]: 相关记忆条目。
        """
        # 简单关键词匹配
        return [
            entry for entry in self.memory_entries
            if user_command.lower() in entry.user_command.lower()
        ][-10:]  # 最多返回 10 条

    def check_stuck_pattern(self, window_size: int = 3) -> bool:
        """检查是否陷入困境（连续原地踏步）。

        Args:
            window_size: 检查窗口大小。

        Returns:
            bool: 是否陷入困境。
        """
        if len(self.memory_entries) < window_size:
            return False

        recent = self.memory_entries[-window_size:]

        # 检查是否连续失败或原地踏步
        stuck_count = sum(
            1 for entry in recent
            if not entry.success or "原地踏步" in entry.reflection
        )

        return stuck_count >= window_size

    def save(self) -> None:
        """保存记忆到文件。"""
        try:
            data = {
                "memory_entries": [
                    entry.model_dump(mode="json")
                    for entry in self.memory_entries
                ],
                "knowledge_map": self.knowledge_map.to_dict(),
                "last_saved": datetime.now().isoformat()
            }

            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"记忆已保存：{len(self.memory_entries)} 条")
        except Exception as e:
            logger.error(f"保存记忆失败：{e}")

    def load(self) -> None:
        """从文件加载记忆。"""
        if not self.memory_file.exists():
            logger.info("未找到记忆文件，使用空记忆")
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 加载记忆条目
            self.memory_entries = [
                MemoryEntry.model_validate(entry)
                for entry in data.get("memory_entries", [])
            ]

            # 加载知识地图
            self.knowledge_map = KnowledgeMap.from_dict(
                data.get("knowledge_map", {})
            )

            logger.info(f"记忆已加载：{len(self.memory_entries)} 条")
        except Exception as e:
            logger.error(f"加载记忆失败：{e}")
            self.memory_entries = []
            self.knowledge_map = KnowledgeMap()

    def clear(self) -> None:
        """清空记忆。"""
        self.memory_entries = []
        self.knowledge_map = KnowledgeMap()
        logger.info("记忆已清空")
