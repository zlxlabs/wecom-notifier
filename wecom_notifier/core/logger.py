"""
通知库 - 日志系统

本模块提供库专属的 logger 实例，不会污染全局日志配置。
用户可以通过标准方式控制本库的日志输出。

使用方式：
    from wecom_notifier.core.logger import get_logger

    logger = get_logger()
    logger.info("消息")
"""
import sys
from typing import Optional
from loguru import logger as loguru_logger


# 库专属的 logger 实例
# 使用 bind 创建带有库标识的 logger
_library_logger = loguru_logger.bind(library="wecom_notifier")


def get_logger():
    """
    获取库专属的 logger 实例

    Returns:
        Logger: loguru logger 实例
    """
    return _library_logger


def setup_logger(
    log_level: str = "INFO",
    add_console: bool = True,
    console_format: Optional[str] = None,
    add_file: bool = False,
    log_file: Optional[str] = None,
    file_format: Optional[str] = None,
    colorize: bool = True
):
    """
    可选的日志配置工具（用户显式调用）

    注意：此方法会配置全局 loguru logger，因为 loguru 的设计是全局的。
    如果你的应用已经配置了 loguru，建议不要调用此方法，而是在应用层统一配置。

    Args:
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        add_console: 是否添加控制台输出
        console_format: 控制台日志格式（None 则使用默认格式）
        add_file: 是否添加文件输出
        log_file: 日志文件路径
        file_format: 文件日志格式（None 则使用默认格式）
        colorize: 是否启用颜色（仅控制台）

    Examples:
        # 基础配置（仅控制台）
        setup_logger(log_level="INFO")

        # 同时输出到文件
        setup_logger(
            log_level="DEBUG",
            add_console=True,
            add_file=True,
            log_file="wecom.log"
        )

        # 自定义格式
        setup_logger(
            log_level="INFO",
            console_format="{time} | {level} | {message}"
        )
    """
    # 默认格式
    if console_format is None:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[library]}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    if file_format is None:
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{extra[library]} | "
            "{name}:{function}:{line} - "
            "{message}"
        )

    # 添加控制台输出
    if add_console:
        # 只输出本库的日志
        loguru_logger.add(
            sys.stdout,
            format=console_format,
            level=log_level.upper(),
            colorize=colorize,
            diagnose=False,
            filter=lambda record: record["extra"].get("library") == "wecom_notifier"
        )

    # 添加文件输出
    if add_file and log_file:
        loguru_logger.add(
            log_file,
            format=file_format,
            level=log_level.upper(),
            encoding="utf-8",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            diagnose=False,
            filter=lambda record: record["extra"].get("library") == "wecom_notifier"
        )


def disable_logger():
    """
    禁用本库的日志输出

    Examples:
        from wecom_notifier.core.logger import disable_logger

        # 完全静默
        disable_logger()
    """
    loguru_logger.disable("wecom_notifier")


def enable_logger():
    """
    启用本库的日志输出（如果之前被禁用）

    Examples:
        from wecom_notifier.core.logger import enable_logger

        enable_logger()
    """
    loguru_logger.enable("wecom_notifier")
