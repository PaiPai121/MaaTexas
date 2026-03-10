"""
工具包模块 - 提供框架级初始化与环境管理
"""
import logging

logger = logging.getLogger(__name__)


class Toolkit:
    """框架工具类，负责环境初始化与资源管理"""

    @staticmethod
    def init() -> None:
        """
        初始化框架运行环境
        - 配置日志系统
        - 初始化必要的全局状态
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logger.info("MaaTexas 框架环境初始化完成")
