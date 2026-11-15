# -*- coding: utf-8 -*-
u"""第190轮 · UTMT 可执行文件的**统一解析**（所有脚本共用，别再各自写死路径）。

为什么必须有这个模块
--------------------
之前每个脚本都写死 `E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe`，
本轮实测踩了一次坑：

    System.ExecutionEngineException: In page error:
    Attempted to access a memory page that is not present, and the system
    is unable to load the page

  进程直接 FailFast（rc=3221225478 = 0xC0000602），日志里**只有这一句**，
  看起来像"csx 写错了 / 编译失败"，实际是 **E 盘坏点导致磁盘页读不出来**。
  实测 E 盘原件 md5 完好（213 个文件逐一比对全 OK）⇒ 属于**偶发**读坏。
  同一份 csx 改从 D 盘副本跑，rc=0、117/117 页全导出成功。

★ 所以：**一律优先 D 盘副本**，E 盘原件只当兜底。
★ 另配 `mkutmt190.py` 生成副本并逐字节校验（见该脚本 docstring）。
"""
import os

#: 优先 D 盘副本（避开 E 盘坏点），E 盘原件仅兜底
CANDIDATES = [
    u'D:\\_tmp190\\utmt\\UndertaleModCli.exe',
    u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe',
]


def resolve():
    """返回第一个真实存在的 UTMT 路径；都不存在则返回 None。"""
    for p in CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def require():
    p = resolve()
    if not p:
        raise SystemExit(u'[停手] 找不到 UTMT：%s' % ' / '.join(CANDIDATES))
    return p
