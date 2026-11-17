# -*- coding: utf-8 -*-
r"""第193轮：给 `D:\RalseiMemory` 拍一份最终状态快照（只读，产物写 _evidence）。

为什么不用第一次迁移的过程日志：`migrate193.py` 的 OUT_TXT/OUT_JSON 是覆盖写，
幂等复跑时把首轮明细冲掉了。**快照反映的是最终状态**，比过程日志更可靠。
"""
import hashlib
import io
import json
import os
import sys

DST = r'D:\RalseiMemory'
EVID = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第193轮-记忆迁D盘\_evidence'
OUT = os.path.join(EVID, 'dst_snapshot193.txt')


def walk(root):
    stack = [(root, '')]
    out = []
    while stack:
        absd, reld = stack.pop()
        for n in sorted(os.listdir(absd)):
            ap = os.path.join(absd, n)
            rp = os.path.join(reld, n) if reld else n
            if os.path.isdir(ap):
                stack.append((ap, rp))
            else:
                out.append((ap, rp))
    return out


def main():
    lines = []

    def say(s=''):
        lines.append(str(s))
        print(s)

    files = walk(DST)
    say('=== D:\\RalseiMemory 最终状态快照 ===')
    say('文件数 = %d' % len(files))
    say('')
    normal = corrupt = 0
    total = 0
    for ap, rp in sorted(files, key=lambda x: x[1]):
        with io.open(ap, 'rb') as fh:
            data = fh.read()
        total += len(data)
        isbad = data[:4] == b'USBC' or rp.startswith('_corrupt_archive\\')
        if isbad:
            corrupt += 1
        else:
            normal += 1
        say('%-8s %-56s %9d B  %s'
            % ('归档' if rp.startswith('_corrupt_archive\\') else '正常',
               rp, len(data), hashlib.sha1(data).hexdigest()[:12]))
    say('')
    say('--- 汇总 ---')
    say('正常件   = %d' % normal)
    say('归档坏件 = %d' % corrupt)
    say('总字节   = %d' % total)

    # 主记忆单列断言
    mp = os.path.join(DST, 'memory.json')
    with io.open(mp, 'rb') as fh:
        raw = fh.read()
    j = json.loads(raw.decode('utf-8', 'replace'))
    say('')
    say('--- 主记忆 ---')
    say('sha1=%s bytes=%d usbc=%s'
        % (hashlib.sha1(raw).hexdigest()[:12], len(raw), raw[:4] == b'USBC'))
    say('schema=%r saved_at=%r' % (j.get('schema'), j.get('saved_at')))
    say('fragments=%d keys=%d assoc=%d'
        % (len(j.get('fragments') or []), len(j.get('keys') or []),
           len(j.get('assoc') or [])))

    os.makedirs(EVID, exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('')
    print('快照已写：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
