# -*- coding: utf-8 -*-
u"""第64轮 · 把 Spamton / Mike 的人设接进 `_registry.json`。

只做**字节级替换**（保持原 EOL 不变），每条替换前断言「目标串恰好出现 1 次」。
判据：W1 目标串唯一；W2 写回后仍是合法 JSON 且条数不变；
      W3 `needs_setting == (persona is None)` 主线全通；W4 只剩 knight 待设定。
"""
from __future__ import print_function

import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

REPO = u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本'
REG = os.path.join(REPO, u'ralsei_pet', u'assets', u'npc', u'_registry.json')

EDITS = [
    # (旧, 新, 说明)
    (u'   "needs_setting": true,\n   "escape_via_bubble": false,\n   "notes": "ch2 的隐藏 Boss；推销员口吻，全大写，神经质。",\n   "persona": null',
     u'   "needs_setting": false,\n   "escape_via_bubble": false,\n   "notes": "ch2 的隐藏 Boss；推销员口吻，全大写，神经质。★ 第64轮接线：设定已到（《其余人物设定.txt》「Spamton G. Spamton」）。",\n   "persona": "persona/spamton.txt"',
     u'spamton'),
    (u'   "needs_setting": true,\n   "escape_via_bubble": false,\n   "notes": "ch4 的对手/主持人；浮夸的节目腔。",\n   "persona": null',
     u'   "needs_setting": false,\n   "escape_via_bubble": false,\n   "notes": "ch4 的对手/主持人；浮夸的节目腔。★ 第64轮接线：设定已到（《其余人物设定.txt》「Mike」）。",\n   "persona": "persona/mike.txt"',
     u'mike'),
]


def main(argv):
    write = u'--write' in argv
    raw = io.open(REG, 'rb').read()
    txt = raw.decode('utf-8')
    eol = u'CRLF' if u'\r\n' in txt else u'LF'
    print(u'%s   %d 字节  行尾=%s' % (REG, len(raw), eol))

    # 原 EOL 探测：把目标串按原 EOL 重写
    nl = u'\r\n' if eol == u'CRLF' else u'\n'
    cur = txt
    ok = True
    for old, new, who in EDITS:
        o = old.replace(u'\n', nl)
        n = new.replace(u'\n', nl)
        c = cur.count(o)
        print(u'  [W1] %-9s 目标串出现 %d 次 %s' % (who, c, u'PASS' if c == 1 else u'FAIL'))
        if c != 1:
            ok = False
            continue
        cur = cur.replace(o, n)
    if not ok:
        print(u'★ 目标串不唯一 ⇒ 停手（不改）')
        return 3

    before = json.loads(raw.decode('utf-8'))
    after = json.loads(cur)
    print(u'  [W2] 写回后合法 JSON 且条数不变 = %s (%d -> %d)'
          % (u'PASS' if len(before[u'npcs']) == len(after[u'npcs']) else u'FAIL',
             len(before[u'npcs']), len(after[u'npcs'])))

    def inv(npcs):
        return [n[u'id'] for n in npcs
                if n[u'tier'] == u'main' and bool(n.get(u'needs_setting')) != (n.get(u'persona') is None)]
    print(u'  [W3] 主线 needs_setting ⇔ persona is None 反例 = %r' % inv(after[u'npcs']))
    waiting = sorted(n[u'id'] for n in after[u'npcs']
                     if n[u'tier'] == u'main' and n.get(u'needs_setting'))
    print(u'  [W4] 仍未拿到设定的主线 = %r' % waiting)

    if not write:
        print(u'（dry-run）')
        return 0
    io.open(REG, 'wb').write(cur.encode('utf-8'))
    print(u'写出 %d 字节' % len(cur.encode('utf-8')))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv[1:]))
