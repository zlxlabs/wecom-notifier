"""
企业微信通知器 / 多平台通知库

一个功能完善的通知组件，支持：
- 企业微信 (WeComNotifier)
- 飞书 (FeishuNotifier)

功能特性：
- 多种消息格式（text、markdown、image、card）
- 频率控制
- 长文本自动分段
- 同步/异步发送
- 内容审核（可选）

日志配置：
    本库默认不配置日志，由用户控制。详见 README.md 的日志配置章节。

向后兼容：
    v0.3.0+ 引入了 core/ 模块架构，但保持完全向后兼容。
    所有现有的导入路径和API保持不变。
"""

# 企业微信通知器（主要入口）
from .notifier import WeComNotifier

# 飞书通知器
from .platforms.feishu import FeishuNotifier

# 数据模型
from .models import Message, SendResult, SegmentInfo

# 异常类
from .exceptions import (
    # 核心异常
    NotificationError,
    ConfigurationError,
    ModerationError,
    # 企微异常（向后兼容）
    WeComError,
    NetworkError,
    WebhookInvalidError,
    RateLimitError,
    SegmentError,
    InvalidParameterError,
)

# 日志工具
from .logger import setup_logger, disable_logger, enable_logger, get_logger

# 核心模块（新增导出）
from .core import RateLimiter, MessageSegmenter

__version__ = "0.3.2"

__all__ = [
    # 主要入口
    "WeComNotifier",
    "FeishuNotifier",

    # 数据模型
    "Message",
    "SendResult",
    "SegmentInfo",

    # 核心异常
    "NotificationError",
    "ConfigurationError",
    "ModerationError",

    # 企微异常（向后兼容）
    "WeComError",
    "NetworkError",
    "WebhookInvalidError",
    "RateLimitError",
    "SegmentError",
    "InvalidParameterError",

    # 日志工具
    "setup_logger",
    "disable_logger",
    "enable_logger",
    "get_logger",

    # 核心模块
    "RateLimiter",
    "MessageSegmenter",
]
