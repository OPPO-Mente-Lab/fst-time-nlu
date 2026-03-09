"""
统一日志系统配置模块
提供全局的日志配置和获取接口
"""

import logging
import os
import sys
from typing import Optional


# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# 简化格式（用于生产环境）
SIMPLE_FORMAT = "%(levelname)s - %(name)s - %(message)s"

# 全局日志配置
_configured = False
_log_level = None


def setup_logging(
    level: str = None,
    log_file: Optional[str] = None,
    format_string: str = DEFAULT_FORMAT,
    console_output: bool = True,
):
    """
    配置全局日志系统

    Args:
        level: 日志级别，可选值: DEBUG, INFO, WARNING, ERROR, CRITICAL
               如果为None，从环境变量FST_LOG_LEVEL读取，默认为WARNING
        log_file: 日志文件路径，如果提供则同时输出到文件
        format_string: 日志格式字符串
        console_output: 是否输出到控制台
    """
    global _configured, _log_level

    # 如果已经配置过，不重复配置
    if _configured:
        return

    # 检查root logger是否已经有handler了，如果有则说明已被外部配置，不要覆盖
    root_logger = logging.getLogger()
    if root_logger.handlers and level is None:
        # 外部已配置，标记为已配置并返回，不覆盖现有配置
        _configured = True
        _log_level = root_logger.level
        return

    # 确定日志级别
    if level is None:
        level = os.environ.get("FST_LOG_LEVEL", "WARNING").upper()

    log_level = LOG_LEVELS.get(level, logging.WARNING)
    _log_level = log_level

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(format_string)

    # 添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 添加文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器

    Args:
        name: 日志器名称，通常使用 __name__

    Returns:
        logging.Logger: 配置好的日志器实例
    """
    global _configured

    # 如果还没配置过，使用默认配置
    if not _configured:
        setup_logging()

    return logging.getLogger(name)


def set_module_log_level(module_name: str, level: str):
    """
    为特定模块设置日志级别

    Args:
        module_name: 模块名称
        level: 日志级别
    """
    logger = logging.getLogger(module_name)
    log_level = LOG_LEVELS.get(level.upper(), logging.WARNING)
    logger.setLevel(log_level)


def disable_module_logging(module_name: str):
    """
    禁用特定模块的日志

    Args:
        module_name: 模块名称
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.CRITICAL + 1)


# 便捷函数：根据环境变量自动配置
def auto_setup():
    """
    根据环境变量自动配置日志系统

    环境变量:
        FST_LOG_LEVEL: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        FST_LOG_FILE: 日志文件路径
        FST_LOG_FORMAT: 日志格式 (default, simple)
    """
    log_level = os.environ.get("FST_LOG_LEVEL", "WARNING")
    log_file = os.environ.get("FST_LOG_FILE", None)
    log_format = os.environ.get("FST_LOG_FORMAT", "default")

    format_string = SIMPLE_FORMAT if log_format == "simple" else DEFAULT_FORMAT

    setup_logging(level=log_level, log_file=log_file, format_string=format_string)
