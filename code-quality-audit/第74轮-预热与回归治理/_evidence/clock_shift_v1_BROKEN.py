"""时钟平移注入（B11 回归体检用）。

把"绝对时间"整体平移 N 秒，用来验证套件是否**暗中依赖当前时刻**。

用法：
    CLOCK_SHIFT_SEC=115200 PYTHONPATH=E:\\Download\\_tmp\\_clock python run_all.py --only xxx

★ 只平移**绝对时间**（time.time / localtime / gmtime / ctime / datetime.datetime.now 等），
  刻意**不动** time.perf_counter / time.monotonic —— 那两个是"耗时"判据的底座，
  动了会把「耗时 < X」这类判据一起改掉，属误伤（第58轮已证：整体平移对 end-start 无影响，
  但那是因为它们本来就该测墙钟；这里更保险的做法是直接不碰）。
★ 注意"陷阱"：本注入只改 Python 看到的时钟；**新写文件的 mtime 仍由 OS 按真实时钟赋**。
  所以"用 time.time() 算一个过去时刻去 utime()"的写法，在平移下会自相矛盾 ——
  这正是 round12_store 暴露出来的那类问题。
"""
import os
import time as _time_mod

_OFF = float(os.environ.get('CLOCK_SHIFT_SEC') or 0)

if _OFF:
    import datetime as _dt

    _rt, _rl, _rg, _rc = _time_mod.time, _time_mod.localtime, _time_mod.gmtime, _time_mod.ctime

    def _shifted_now():
        return _rt() + _OFF

    _time_mod.time = _shifted_now
    _time_mod.localtime = lambda s=None: _rl(_shifted_now() if s is None else s + _OFF)
    _time_mod.gmtime = lambda s=None: _rg(_shifted_now() if s is None else s + _OFF)
    _time_mod.ctime = lambda s=None: _rc(_shifted_now() if s is None else s + _OFF)

    class _ShiftedDate(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date.fromtimestamp(_shifted_now())

    class _ShiftedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _dt.datetime.fromtimestamp(_shifted_now(), tz)

        @classmethod
        def utcnow(cls):
            return _dt.datetime.utcfromtimestamp(_shifted_now())

        @classmethod
        def today(cls):
            return cls.fromtimestamp(_shifted_now())

    _dt.date = _ShiftedDate
    _dt.datetime = _ShiftedDateTime
