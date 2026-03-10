"""
MaaTexas 框架全局常量定义。

集中管理框架级的常量配置，便于统一维护和版本控制。
"""

# =============================================================================
# 框架版本信息
# =============================================================================

FRAMEWORK_NAME: str = "MaaTexas"
FRAMEWORK_VERSION: str = "0.1.0"
FRAMEWORK_AUTHOR: str = "MaaTexas Team"

# =============================================================================
# 目录结构常量
# =============================================================================

# 标准子目录名称
DIR_PERCEPTION: str = "perception"
DIR_PLANNING: str = "planning"
DIR_CONTROL: str = "control"
DIR_CORE: str = "core"
DIR_CONFIG: str = "config"
DIR_LOGS: str = "logs"
DIR_CACHE: str = "cache"
DIR_SCREENSHOTS: str = "screenshots"

# =============================================================================
# 时间常量（单位：秒）
# =============================================================================

DEFAULT_TIMEOUT: float = 30.0
SHORT_TIMEOUT: float = 5.0
LONG_TIMEOUT: float = 60.0

# 默认等待时间（单位：毫秒）
DEFAULT_WAIT_TIME: int = 500
SHORT_WAIT_TIME: int = 100
LONG_WAIT_TIME: int = 2000

# =============================================================================
# 图像/屏幕常量
# =============================================================================

# 默认屏幕捕获区域（全屏幕，具体值由运行时确定）
DEFAULT_SCREEN_WIDTH: int = 1920
DEFAULT_SCREEN_HEIGHT: int = 1080

# 模板匹配阈值
DEFAULT_MATCH_THRESHOLD: float = 0.8
HIGH_MATCH_THRESHOLD: float = 0.95
LOW_MATCH_THRESHOLD: float = 0.6

# =============================================================================
# 坐标常量
# =============================================================================

# 无效坐标标记
INVALID_COORDS: tuple[int, int] = (-1, -1)

# 屏幕中心相对坐标（归一化）
NORMALIZED_CENTER: tuple[float, float] = (0.5, 0.5)

# =============================================================================
# 日志常量
# =============================================================================

DEFAULT_LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL_DEBUG: str = "DEBUG"
LOG_LEVEL_INFO: str = "INFO"
LOG_LEVEL_WARNING: str = "WARNING"
LOG_LEVEL_ERROR: str = "ERROR"

# =============================================================================
# 错误码前缀
# =============================================================================

ERROR_PREFIX_CORE: str = "CORE"
ERROR_PREFIX_PERCEPTION: str = "PERCEPTION"
ERROR_PREFIX_PLANNING: str = "PLANNING"
ERROR_PREFIX_CONTROL: str = "CONTROL"

# =============================================================================
# 任务状态常量
# =============================================================================

TASK_STATUS_PENDING: str = "pending"
TASK_STATUS_RUNNING: str = "running"
TASK_STATUS_COMPLETED: str = "completed"
TASK_STATUS_FAILED: str = "failed"
TASK_STATUS_CANCELLED: str = "cancelled"

# =============================================================================
# 重试策略常量
# =============================================================================

DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_DELAY: float = 1.0
EXPONENTIAL_BACKOFF_BASE: float = 2.0
