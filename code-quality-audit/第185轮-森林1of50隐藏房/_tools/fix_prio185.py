# -*- coding: utf-8 -*-
u"""第185轮 · 把两条手工边的 priority 从 7900/7901 挪到 9001/9002。

为什么要挪
----------
施工时我按"7900 段空着"取了 7900/7901，**当时判断错了**：`7901` 早被
`ch5.flower_castle.dw_fcastle_gloves_tower` 那条边（第172轮按实例创建代码补的）占着。
而且 7850~8262 整段是 `gen_routes44.py` 用 `110 + scene_ord * BAND + k` 生成的区间，
手工边塞在里面，**以后重跑生成器就会静默撞号**。

⇒ 手工边挪到生成器够不到的 **9001/9002**（当前全仓 max = 8262）。

做法：**字节级替换 + 三重自证**
1. 锚点必须**恰好命中 1 次**（带 `\r\n` 的字面量，不解析 JSON 再 dump）；
2. 改完 `dump2(parse(new)) == new` —— 证明除这两处外**其余一个字节没动**
   （`_routes.json` 的写法是 `indent=2` + CRLF + 无尾换行，第185轮 P1.2 已证无损）；
3. 改完再验：两条边的 priority 正确、`7901` 只剩 ch5 那条、**且全表无重复**。

幂等：已经是 9001/9002 ⇒ 直接 rc=0 空转。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RT = u'C:/Users/23002/Desktop/\u9879\u76ee\u6587\u4ef6\u5939/try - \u526f\u672c/ralsei_pet/assets/scenes/_routes.json'

OLD_A, NEW_A = 7900, 9001          # (area5, X) -> starwalker
OLD_B, NEW_B = 7901, 9002          # (room_man, X) -> bake_sale

_n = {'p': 0, 'f': 0}


def ck(desc, cond, extra=u''):
    _n['p' if cond else 'f'] += 1
    print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', desc,
                       (u'    ' + extra) if extra else u''))
    return cond


raw = io.open(RT, 'rb').read()
print(u'原文件 %d 字节 / CRLF %d 个' % (len(raw), raw.count(b'\r\n')))
ck(u'Z0 `_routes.json` 是 CRLF 存盘（锚点必须带 \\r\\n）', raw.count(b'\r\n') > 1000)

if (b'"priority": %d,' % NEW_A) in raw and (b'"priority": %d,' % NEW_B) in raw:
    print(u'\n已经是 %d/%d ⇒ 空转（幂等）rc=0' % (NEW_A, NEW_B))
    sys.exit(0)

# 锚点 1：(area5, X)。`7900` 全表只出现这一次 ⇒ 单行锚点就唯一。
P1 = b'"priority": %d,' % OLD_A
# 锚点 2：(room_man, X)。`7901` 出现两次（另一条是 ch5 的 Any 门）⇒ 带上上一行 `to`。
P2 = (b'      "to": "ch1.forest.forest_bake_sale",\r\n'
      b'      "priority": %d,' % OLD_B)

ck(u'Z1 锚点1（`"priority": 7900,`）恰好 1 处', raw.count(P1) == 1, u'实测 %d' % raw.count(P1))
ck(u'Z2 锚点2（`to bake_sale` + `priority 7901`）恰好 1 处', raw.count(P2) == 1,
   u'实测 %d' % raw.count(P2))
ck(u'Z3 `7901` 全表确实是 2 处（另一处是 ch5 Any 门，本轮不许碰）',
   raw.count(b'"priority": 7901,') == 2, u'实测 %d' % raw.count(b'"priority": 7901,'))

if _n['f']:
    print(u'\n★ 锚点不符 ⇒ 中止，一个字节都不写。')
    sys.exit(3)

new = raw.replace(P2, P2.replace(b'"priority": %d,' % OLD_B, b'"priority": %d,' % NEW_B), 1)
new = new.replace(P1, b'"priority": %d,' % NEW_A, 1)
ck(u'Z4 字节增量 == 0（7900→9001 / 7901→9002 同宽）', len(new) == len(raw),
   u'%d → %d' % (len(raw), len(new)))

# ---- 自证：其余一个字节没动
d = json.loads(new.decode('utf-8'))


def dump2(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False).replace('\n', '\r\n')


ck(u'Z5 ★ `dump2(parse(new)) == new` ⇒ 除这两处外**其余字节一字未动**',
   dump2(d).encode('utf-8') == new)

io.open(RT, 'wb').write(new)

# ---- 改后核验
d2 = json.loads(io.open(RT, encoding='utf-8', newline='').read())
ea = [r for r in d2['routes'] if r.get('when_scene') == u'ch1.forest.forest_area5'
      and r.get('when_door') == u'X']
eb = [r for r in d2['routes'] if r.get('when_scene') == u'ch1.forest.room_man'
      and r.get('when_door') == u'X']
ck(u'Z6 `(area5, X)` priority == %d' % NEW_A,
   len(ea) == 1 and ea[0].get('priority') == NEW_A,
   u'实测 %r' % ([r.get('priority') for r in ea],))
ck(u'Z7 `(room_man, X)` priority == %d' % NEW_B,
   len(eb) == 1 and eb[0].get('priority') == NEW_B,
   u'实测 %r' % ([r.get('priority') for r in eb],))

ch5 = [r for r in d2['routes'] if r.get('priority') == OLD_B]
ck(u'Z8 ch5 那条边**没被碰**（仍是 %d，且只剩它一个）' % OLD_B,
   len(ch5) == 1 and ch5[0].get('when_scene') == u'ch5.flower_castle.dw_fcastle_gloves_tower',
   u'%r' % ([(r.get('when_scene'), r.get('when_door')) for r in ch5],))

from collections import Counter
_c = Counter(r.get('priority') for r in d2['routes'])
_dup = {k: v for k, v in _c.items() if v > 1}
ck(u'Z9 ★ 全表 priority 只剩桌面那组 200（4 扇门，**施工前就有**）重复',
   set(_dup) == {200} and _dup[200] == 4,
   u'重复=%r' % ({k: v for k, v in sorted(_dup.items())},))
ck(u'Z10 边数仍是 2832', len(d2['routes']) == 2832, u'实测 %d' % len(d2['routes']))

print('')
print(u'结论：%s（%d/%d）' % ('PASS' if not _n['f'] else 'FAIL',
                            _n['p'], _n['p'] + _n['f']))
sys.exit(0 if not _n['f'] else 1)
