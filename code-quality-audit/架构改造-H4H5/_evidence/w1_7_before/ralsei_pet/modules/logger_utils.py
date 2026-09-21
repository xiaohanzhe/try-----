#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志模块 — 替代散落各处的 print() 调用。

设计目标：
- 零配置即可用：import 后直接 get_logger(__name__) 就能打
- 同时输出到控制台 + 文件（文件可选，默认开启）
- 线程安全（logging 模块本身是线程安全的）
- 不影响现有代码：旧 print 不动，新代码/重构代码用 logger
- 支持按天切割日志，自动清理旧日志（默认保留 7 天）

使用方式：
    from logger_utils import get_logger
    log = get_logger(__name__)  # 推荐用模块名
    log.info("程序启动")
    log.warning("配置缺失，使用默认值")
    log.error("加载失败: %s", e)
    log.debug("详细调试信息")  # 默认不显示，需要时改 level

级别（从低到高）：DEBUG < INFO < WARNING < ERROR < CRITICAL
默认级别：INFO（生产环境够用，开发时可以改成 DEBUG）
"""

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# ---------- 全局配置 ----------

# 日志目录：优先"最终存储"（E 盘，见 data_store），拿不到才回落程序目录。
# 第十二轮用户原则："所有它产生的文件在本地最多算中转站，只有 E 盘是最终存储"。
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FALLBACK_LOG_DIR = os.path.join(_APP_DIR, "logs")
_LOG_DIR = None          # 惰性解析（import 期不碰磁盘）
_LOG_FILENAME = "ralsei_pet.log"
_DEFAULT_LEVEL = logging.INFO
_BACKUP_DAYS = 7  # 保留几天的日志

# 全局初始化标记
_initialized = False
_initializing = False    # 重入保护，见 _init_logging 的文档字符串
_root_logger = None


def _log_dir():
    """解析日志目录：data_store（E 盘优先）→ 程序目录兜底。**绝不抛。**

    **兜底值不缓存**：解析失败有一种可能是"`data_store` 模块还没初始化完"
    （初始化环，见 `lazy_log.LazyLogger` 的说明）。那种情况下缓存兜底会把目录
    永久钉错，所以只在**成功解析**时才记住结果，失败就下次再试。
    """
    global _LOG_DIR
    if _LOG_DIR:
        return _LOG_DIR
    try:
        import data_store
        d = data_store.artifact_path('logs')
        if d:
            _LOG_DIR = d
            return _LOG_DIR
    except Exception:
        pass
    return _FALLBACK_LOG_DIR


def _ensure_log_dir():
    """确保日志目录存在。"""
    try:
        target = _log_dir()
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
        return True
    except Exception:
        # 连日志目录都建不了（权限问题？），就只打控制台
        return False


def _init_logging():
    """初始化全局日志系统。只执行一次。

    `_initializing` 是**重入保护**：`_ensure_log_dir()` 会 `import data_store`，
    而 `data_store` 的模块体里会调用 `get_logger()` —— 又绕回这里。没有护栏会无限递归。
    """
    global _initialized, _initializing
    if _initialized or _initializing:
        return
    _initializing = True
    try:
        _init_logging_impl()
    finally:
        _initializing = False
        _initialized = True


def _init_logging_impl():
    global _root_logger
    _root_logger = logging.getLogger("ralsei_pet")
    _root_logger.setLevel(_DEFAULT_LEVEL)
    _root_logger.propagate = False  # 不往上传播，避免重复输出

    # 统一格式：时间 级别 名称 — 消息
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- 控制台输出 ---
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(_DEFAULT_LEVEL)
        console_handler.setFormatter(formatter)
        _root_logger.addHandler(console_handler)
    except Exception:
        pass  # 控制台失败就算了，不影响程序

    # --- 文件输出（按天切割，保留 7 天）---
    if _ensure_log_dir():
        log_file = os.path.join(_log_dir(), _LOG_FILENAME)
        try:
            file_handler = TimedRotatingFileHandler(
                log_file,
                when="midnight",   # 每天 0 点切割
                interval=1,
                backupCount=_BACKUP_DAYS,
                encoding="utf-8",
            )
            file_handler.setLevel(_DEFAULT_LEVEL)
            file_handler.setFormatter(formatter)
            file_handler.suffix = "%Y-%m-%d"  # 切割后的文件名后缀
            _root_logger.addHandler(file_handler)
        except Exception as e:
            # 文件日志失败就只打控制台，不打断主程序
            try:
                print(f"[日志] 文件日志初始化失败，仅使用控制台: {e}")
            except Exception:
                pass


def get_logger(name: str) -> logging.Logger:
    """
    获取一个命名 logger。推荐传入 __name__ 作为名称。

    所有 logger 都挂在 ralsei_pet 根 logger 下，共享 handler 和配置。
    子 logger 可以单独调整级别（比如调试某个模块时设为 DEBUG）。
    """
    _init_logging()
    # 统一加前缀，避免和第三方库的 logger 冲突
    full_name = f"ralsei_pet.{name}" if not name.startswith("ralsei_pet.") else name
    return logging.getLogger(full_name)


def set_level(level: int, name: str = None):
    """
    动态调整日志级别。

    Args:
        level: logging.DEBUG / logging.INFO / logging.WARNING 等
        name:  指定 logger 名称，None 表示调整全局级别
    """
    _init_logging()
    if name:
        logger = logging.getLogger(f"ralsei_pet.{name}")
        logger.setLevel(level)
    else:
        _root_logger.setLevel(level)
        for handler in _root_logger.handlers:
            handler.setLevel(level)


def get_log_dir() -> str:
    """返回日志目录路径。"""
    return _log_dir()


# 便捷函数：直接用模块名获取 logger（最常用的场景）
# 使用: from logger_utils import log
#       log.info("xxx")
log = get_logger("utils")
