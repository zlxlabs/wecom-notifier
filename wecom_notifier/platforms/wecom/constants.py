"""
企业微信平台常量定义
"""

# 从核心模块导入通用常量
from wecom_notifier.core.constants import (
    # 频率限制
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIME_WINDOW,
    # 分段设置
    DEFAULT_SEGMENT_INTERVAL,
    # 重试设置
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_BACKOFF_FACTOR,
    # HTTP设置
    DEFAULT_TIMEOUT,
    # Markdown语法标记
    MARKDOWN_LINK_PATTERN,
    MARKDOWN_IMAGE_PATTERN,
    MARKDOWN_CODE_BLOCK_PATTERN,
    MARKDOWN_TABLE_ROW_PATTERN,
    # 页码格式设置
    PAGE_INDICATOR_FORMAT,
    MAX_PAGE_INDICATOR_BYTES,
    # 通用消息类型
    MSG_TYPE_TEXT,
    MSG_TYPE_MARKDOWN,
)

# ===== 企业微信特定常量 =====

# 消息类型
MSG_TYPE_MARKDOWN_V2 = "markdown_v2"  # 企微特有
MSG_TYPE_IMAGE = "image"

# 分段预算（平台限制出处记录于 docs/sessions/261008-notifier-rootfix/platform-limits.md）
_MAX_BYTES_PER_TEXT = 2048  # 官方 text.content 上限
MAX_BYTES_PER_MESSAGE = 3800  # markdown_v2.content 缓冲预算（官方上限 4096）

# 服务端频控重试设置
RATE_LIMIT_MAX_RETRIES = 5  # 服务端频控最大重试次数
RATE_LIMIT_WAIT_TIME = 65  # 服务端频控等待时间（秒），略大于60秒以确保安全

# 企业微信API错误码
ERRCODE_SUCCESS = 0  # 成功
ERRCODE_WEBHOOK_INVALID = 93000  # webhook不存在
ERRCODE_RATE_LIMIT = 45009  # 频率限制

__all__ = [
    # 从核心导入的通用常量
    "DEFAULT_RATE_LIMIT",
    "DEFAULT_TIME_WINDOW",
    "DEFAULT_SEGMENT_INTERVAL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_TIMEOUT",
    "MARKDOWN_LINK_PATTERN",
    "MARKDOWN_IMAGE_PATTERN",
    "MARKDOWN_CODE_BLOCK_PATTERN",
    "MARKDOWN_TABLE_ROW_PATTERN",
    "PAGE_INDICATOR_FORMAT",
    "MAX_PAGE_INDICATOR_BYTES",
    "MSG_TYPE_TEXT",
    "MSG_TYPE_MARKDOWN",
    # 企微特定常量
    "MSG_TYPE_MARKDOWN_V2",
    "MSG_TYPE_IMAGE",
    "MAX_BYTES_PER_MESSAGE",
    "RATE_LIMIT_MAX_RETRIES",
    "RATE_LIMIT_WAIT_TIME",
    "ERRCODE_SUCCESS",
    "ERRCODE_WEBHOOK_INVALID",
    "ERRCODE_RATE_LIMIT",
]
