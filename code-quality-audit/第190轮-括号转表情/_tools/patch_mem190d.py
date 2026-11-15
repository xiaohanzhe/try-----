# -*- coding: utf-8 -*-
u"""第190轮 · 速查本补丁 d（修 E2：**不造点路径令牌**）。

`recheck95mem.py` E2 报 `PreCreate.doorRoom` 是新增令牌且详版里查不到。
两种解法：
  A. 往详版补一句"自证" —— ★ 拒绝：那等于为了让判据变绿去写内容，
     令牌本身是我硬凑出来的（详版里 `PreCreate` 与 `doorRoom` 是分开的两个词）。
  B. **不造这个令牌**：改回 `` `PreCreate` 写 `doorRoom` ``，
     两个词各自都在详版里，E2 自然没有新增项。

走 B。多出来的字符从 Ralsei 那句省回来（`_FACE_MAP`→`6 条`，
`_FACE_MAP` 令牌在详版 §195.4 有，C2 的"移除令牌不许丢"不受影响）。

★ 先算后写；二进制替换，不碰 EOL。
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')

LIMIT_RAW = 10000

EDITS = [
    # ① 不造点路径令牌（E2 的根因）
    (u'拆开点路径',
     u'Any 目标在**每实例** `PreCreate.doorRoom`；',
     u'Any 目标在**每实例** `PreCreate` 写 `doorRoom`；'),

    # ② 省回字符（`_FACE_MAP` 在详版 §195.4 有，C2 不受影响）
    (u'Ralsei 省字',
     u'·Ralsei `_FACE_MAP` 补 short 键。',
     u'·Ralsei 补 6 条 short 键。'),
]


def lf_len(s):
    return len(s.replace(u'\r\n', u'\n'))


def head_text():
    try:
        b = subprocess.check_output(
            ['git', '-c', 'core.quotepath=false', 'show',
             'HEAD:.workbuddy/memory/MEMORY.md'], cwd=REPO)
        return b.decode('utf-8', 'replace')
    except Exception:  # noqa: BLE001
        return None


def main():
    write = '--write' in sys.argv[1:]
    raw = io.open(MEM, 'rb').read()
    s = raw.decode('utf-8')
    lf0, raw0 = lf_len(s), len(s)
    print(u'[当前] LF %d / 原始 %d / CRLF %d' % (lf0, raw0, s.count(u'\r\n')))

    cur = s
    bad = []
    for tag, old, new in EDITS:
        n = cur.count(old)
        if n != 1:
            bad.append((tag, n))
            print(u'  [锚点] %-12s 命中 %d 次' % (tag, n))
            continue
        print(u'  [改] %-12s ΔLF %+d' % (tag, lf_len(new) - lf_len(old)))
        cur = cur.replace(old, new)

    if bad:
        print(u'[停手] 锚点问题 %r ⇒ 不写' % (bad,))
        return 3

    lf1, raw1 = lf_len(cur), len(cur)
    print(u'')
    print(u'[预计] LF %d → %d (Δ%+d)' % (lf0, lf1, lf1 - lf0))
    print(u'[预计] 原始 %d → %d (Δ%+d)' % (raw0, raw1, raw1 - raw0))

    fail = []
    h = head_text()
    if h is not None:
        hl = lf_len(h)
        print(u'[HEAD] LF %d' % hl)
        if lf1 > hl:
            fail.append(u'E1 相对 HEAD +%d' % (lf1 - hl))
    if raw1 > LIMIT_RAW:
        fail.append(u'A1 原始 %d > %d' % (raw1, LIMIT_RAW))
    if fail:
        print(u'[停手] %s ⇒ 不写' % fail)
        return 4

    if not write:
        print(u'[dry] 过关，加 --write 落盘')
        return 0

    with io.open(MEM, 'wb') as fh:
        fh.write(cur.encode('utf-8'))
    back = io.open(MEM, 'rb').read().decode('utf-8')
    naked = back.count(u'\n') - back.count(u'\r\n')
    print(u'[写回] %d → %d 字节' % (len(raw), len(back.encode('utf-8'))))
    print(u'[EOL] 裸LF %d · CRLF==LF %s · 内容一致 %s'
          % (naked, back.count(u'\r\n') == back.count(u'\n'),
             u'OK' if back == cur else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
