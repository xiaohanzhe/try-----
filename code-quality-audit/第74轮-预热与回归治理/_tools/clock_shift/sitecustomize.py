"""时钟平移注入（B11 回归体检用，v2）—— **仓库内副本**。

用法（把本文件所在目录放进 PYTHONPATH，Python 启动时会自动 import sitecustomize）：

    # 正/负各来一遍，看哪些套件"结果随墙上时钟漂移"
    CLOCK_SHIFT_SEC=115200  PYTHONPATH=<此目录> python regress/run_all.py
    CLOCK_SHIFT_SEC=-115200 PYTHONPATH=<此目录> python regress/run_all.py
    # 先自检（必须先过！）
    CLOCK_SHIFT_SEC=±115200 PYTHONPATH=<此目录> python <此目录>/selftest.py

★ v1 的坑（2026-10-01 实测，必须记住）
--------------------------------------------------
v1 把 `time.time/localtime/gmtime/ctime` 换成**普通函数**（lambda）。
但 `logging.Formatter.converter = time.localtime` 是**类属性**，
`Formatter.formatTime` 里写的是 `ct = self.converter(record.created)` ⇒
普通函数会被**描述符协议绑定**，Python 把 `self` 一起塞进去
⇒ `TypeError: <lambda>() takes 0-1 positional args but 2 given`
⇒ logging 的 `StreamHandler.emit` 把它转交 `handleError`，而本项目第54轮
把 `handleError` 改成了**静默计数** ⇒ **所有日志凭空消失**。

后果极具欺骗性：套件输出里日志行全没了 ⇒ 全量比对报 DIFF ⇒
看起来"这些套件依赖时钟"。**其实是被探针自己打死的** ——
最终 7 个套件里 **7 个都是假问题**，只有 `round12_store` 是真耦合。
⇒ 健康检查工具不保真，就会批量制造假问题（"探针不保真 = 报假问题"）。

v2 的处置：替换值一律用**可调用对象（实例）**，实例没有 `__get__`，
不会被当成描述符 ⇒ 绑定问题从根上消失。

★ 只平移**绝对时间**（time.time / localtime / gmtime / ctime、datetime 的
  now/utcnow/today），刻意**不动** time.perf_counter / time.monotonic ——
  那两个是"耗时"判据的底座，动了会把「耗时 < X」这类判据一起改掉（误伤）。

★ 已知局限（如实登记，别当成"全覆盖"）：
  ① `datetime.datetime.fromtimestamp(ts)` 走的是 C 层 localtime，**不受本注入影响**；
  ② 新写文件的 mtime 仍由 OS 按**真实**时钟赋 ⇒ "用 time.time() 算一个过去时刻去
     utime()" 的写法在平移下会自相矛盾 —— 这正是 `round12_store` 暴露的真问题
     （修法：基准改成**文件自身 mtime**，而不是 `time.time()`）。
"""
import os
import time as _t

_rt = _t.time          # 真·原生，永远指向真实时钟

_OFF = float(os.environ.get('CLOCK_SHIFT_SEC') or 0)


class _ShiftedClock(object):
    """可调用对象：把"绝对时刻"整体平移 `shift` 秒。

    `__call__` 只认**数值实参**（`localtime(1234)` / `localtime(record.created)`）；
    没有数值实参就当成"取当前时刻"。这样它既能当模块级函数用，也能安全地
    被当作类属性（如 `logging.Formatter.converter`）—— 属性查找不会绑定实例。
    """

    __slots__ = ('_orig', '_shift', '_is_now')

    def __init__(self, orig, shift, is_now=False):
        self._orig = orig
        self._shift = shift
        self._is_now = is_now

    def __call__(self, *args, **kwargs):
        num = None
        for a in args:
            if isinstance(a, (int, float)) and not isinstance(a, bool):
                num = a
        if num is None:
            if self._is_now:
                return _rt() + self._shift
            return self._orig(_rt() + self._shift)
        return self._orig(num + self._shift)


if _OFF:
    import datetime as _dt

    _t.time = _ShiftedClock(_rt, _OFF, is_now=True)
    _t.localtime = _ShiftedClock(_t.localtime, _OFF)
    _t.gmtime = _ShiftedClock(_t.gmtime, _OFF)
    _t.ctime = _ShiftedClock(_t.ctime, _OFF)

    def _shifted_epoch():
        # fromtimestamp 走的是 C 层 localtime，不经过上面的猴子补丁；
        # 这里显式用"平移后的 epoch"渲染日期，才是我们想要的语义。
        return _rt() + _OFF

    class _ShiftedDate(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date.fromtimestamp(_shifted_epoch())

    class _ShiftedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _dt.datetime.fromtimestamp(_shifted_epoch(), tz)

        @classmethod
        def utcnow(cls):
            return _dt.datetime.utcfromtimestamp(_shifted_epoch())

        @classmethod
        def today(cls):
            return cls.fromtimestamp(_shifted_epoch())

    _dt.date = _ShiftedDate
    _dt.datetime = _ShiftedDateTime
