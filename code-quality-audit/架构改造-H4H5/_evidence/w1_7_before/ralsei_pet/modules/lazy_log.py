# -*- coding: utf-8 -*-
"""惰性日志器 —— 给"底层模块"用的：import 期**绝不**去 import `logger_utils`。

为什么需要它（第十二轮 + E 盘真机确认时复现的真 bug）
----------------------------------------------------
`logger_utils` 初始化时要解析日志目录，而目录由 `data_store` 决定；`data_store`
又要向 `memory_store` 问"最终存储设备（E 盘）在不在"。于是只要这几个模块里
**任何一个在 import 期回头去要 logger**，就会成环：

    logger_utils._log_dir() → import data_store
      → data_store.vault_root() → import memory_store
      → memory_store 模块级 _log = get_logger(...)  → 又回到 logger_utils

后果取决于**谁先被 import**：

  · 先 import `logger_utils`（真机 app 的顺序）：`_initializing` 重入护栏挡住，
    一切正常；
  · 先 import `data_store`（脚本 / 工具 / 探针的常见顺序）：此刻 `memory_store`
    是**半成品**（`find_device_dir` 还没定义）→ `AttributeError` → `vault_root()`
    误判"设备离线" → `data_root()` 降级到本地中转站 → 而且 `logger_utils._log_dir()`
    **把这个错误结果当成"解析成功"缓存了下来** —— 日志从此永远写在中转站，
    即使 E 盘就在线。实测复现见 `code-quality-audit/第十二轮/probe_cycle2.py`。

本模块的唯一职责：把 `get_logger` **推迟到第一次真正打日志那一刻**。只要底层
模块 import 期不碰它，环就断了。它**不 import 任何项目内模块**，因此可被任意
底层模块安全引用（包括被 `data_store` 反向依赖的 `memory_store`）。
"""
import logging


class LazyLogger(object):
    """延迟解析的 logger 代理：属性访问时才向 `logger_utils` 要真身。

    拿不到 `logger_utils`（例如它自己正在初始化）时**静默**退化为标准库 logger，
    且**不缓存失败**（下次访问再试），避免把错误结果钉死。
    """

    def __init__(self, name):
        self._name = name
        self._impl = None

    def __getattr__(self, attr):
        # 注意：`_impl` / `_name` 在 __init__ 里已写入实例字典，
        # 所以下面这两行正常查得到，不会递归回 __getattr__。
        impl = self._impl
        if impl is None:
            try:
                from logger_utils import get_logger
                impl = get_logger(self._name)
            except Exception:
                impl = logging.getLogger(self._name)
            else:
                # 只有真拿到 logger_utils 的 logger 才记住；退化值下次再试
                object.__setattr__(self, '_impl', impl)
        return getattr(impl, attr)
