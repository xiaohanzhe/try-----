# -*- coding: utf-8 -*-
"""训练期间阻止系统休眠（不改系统电源设置，进程一停就自动恢复）。

为什么不用 `powercfg /change standby-timeout-ac 0`：
  那是**永久改设置**，用户以后还得自己改回来。`SetThreadExecutionState`
  只对"本进程存活期间"生效，进程退出即刻失效 ⇒ 有余地，符合"只禁用不删"。

★ 局限（必须写清，不许假装全覆盖）：
  · `ES_SYSTEM_REQUIRED` 挡的是**空闲自动休眠**；
    合盖休眠（lid close action）**不归它管** —— 那个只能改电源计划。
  · 所以它解决的是"人走开、机器闲置 15 分钟就睡"这一类，也就是本次丢了 10 小时的那种。
"""
import ctypes
import sys
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_k32 = ctypes.windll.kernel32


def hold():
    """返回上一次的状态位（失败返回 None）。"""
    return _k32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def release():
    return _k32.SetThreadExecutionState(ES_CONTINUOUS)


def main(argv):
    secs = int(argv[argv.index('--secs') + 1]) if '--secs' in argv else 0
    print('[keepawake] start %s 上限=%s'
          % (time.strftime('%H:%M:%S'), ('%d 分钟' % (secs // 60)) if secs else '不限'),
          flush=True)
    if hold() is None:
        print('[keepawake] FAIL：SetThreadExecutionState 返回 None（拿不到句柄）', flush=True)
        return 2
    t0 = time.time()
    n = 0
    while True:
        # 每 60s 重申一次：某些情况下状态位会被别的程序重置
        hold()
        n += 1
        if n % 30 == 0:
            print('[keepawake] 已守 %.1f 小时（%s）'
                  % ((time.time() - t0) / 3600.0, time.strftime('%H:%M:%S')), flush=True)
        if secs and (time.time() - t0) > secs:
            break
        time.sleep(60)
    release()
    print('[keepawake] release，休眠限制已解除', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
