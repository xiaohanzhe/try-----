# -*- coding: utf-8 -*-
"""单点探针：模型是否在线 + 一次真实对话的首字耗时/吞吐 + 内存。

只读，不改任何产物。给训练重启前的"闸门"用。
"""
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common113 as C  # noqa: E402

import psutil  # noqa: E402


def main():
    vm = psutil.virtual_memory()
    print('avail_MB=%.0f  used_pct=%.1f' % (vm.available / 1e6, vm.percent), flush=True)
    print('model_loaded=%s' % (C.model_loaded(),), flush=True)
    t0 = time.time()
    try:
        r, st = C.chat([{'role': 'system', 'content': '你叫测试，说话很短。'},
                        {'role': 'user', 'content': '说一句话就行。'}],
                       seed=1, temperature=0.5, num_predict=40, timeout=300)
        dt = time.time() - t0
        n = len(r or '')
        print('OK 整轮 %.2fs  chars=%d  tps≈%.2f' % (dt, n, n / max(dt, 0.01)), flush=True)
        print('stats=%s' % (st,), flush=True)
        print(('reply=%r' % (r or ''))[:140], flush=True)
    except Exception as e:
        print('FAIL %s: %s' % (type(e).__name__, e), flush=True)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
