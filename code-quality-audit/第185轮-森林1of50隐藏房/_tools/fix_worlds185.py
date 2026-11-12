# -*- coding: utf-8 -*-
u"""第185轮 · 给 `_worlds.json` 补 `ch1 / 142 → dark`（`room_man` 的世界归属）。

为什么是 dark，不是猜的
------------------------
`_worlds.json` 里 ch1 的**森林族**（rid 79~100）**逐条都是 `dark`**（实测全量打印过），
`room_man` 是同一片猩红森林（`_zone.ch1.forest.json`，区域表 `forest`）里的一间，
rid 142 只是唯一缺少登记的那个 —— 所以按"同区域同世界"补，并且**只补这一个**。

做法：**行级插入**（不做整文件 dump）
--------------------------------------
`_worlds.json` 是 `indent=1` + CRLF 的生成物，整文件重写会把 134 行全部重排（diff 全红）。
这里只在 `"rooms": { "ch1": { … } }` 里按**字符串序**插一行，然后三重自证：
1. 插完 `json.dumps(parse(new), indent=1, ensure_ascii=False)`（CRLF 化）== new ⇒ 写法没变；
2. **其余行逐行未动**：new 的行序列里"老行"按原相对顺序全部保留，且只多 1 行；
3. 值对：`rooms['ch1']['142'] == 'dark'`，且 79~100 那 22 条一字未变。

幂等：已经有 `"142"` ⇒ rc=0 空转。
"""
import io
import json
from collections import Counter
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = u'C:/Users/23002/Desktop/\u9879\u76ee\u6587\u4ef6\u5939/try - \u526f\u672c/ralsei_pet/assets/scenes/_worlds.json'
KEY = '142'
VAL = 'dark'

_n = {'p': 0, 'f': 0}


def ck(desc, cond, extra=u''):
    _n['p' if cond else 'f'] += 1
    print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', desc,
                       (u'    ' + extra) if extra else u''))
    return cond


raw = io.open(P, encoding='utf-8', newline='').read()
print(u'原文件 %d 字节 / CRLF %d / 尾换行=%r' % (len(raw), raw.count('\r\n'), raw[-2:]))

d = json.loads(raw)
# ★ 幂等闸必须**按章判**：`"142": "dark"` 这个字面量在别的章（ch2/ch4…）里本来就有，
#   对整份文件做子串判断会**假阳性**（第一版就是这么空转的，实测才发现）。
if d['rooms']['ch1'].get(KEY) == VAL:
    print(u'★ ch1 已有 `"142": "dark"` ⇒ 空转 rc=0')
    sys.exit(0)
ck(u'W0 ch1 里还没有 142', KEY not in d['rooms']['ch1'])
_before = dict(d['rooms']['ch1'])
ck(u'W1 森林族 79~100 全是 dark（补值的依据）',
   all(d['rooms']['ch1'].get(str(i)) == 'dark' for i in range(79, 101)))

# ---- 写法自证：现文件 == 标准 dump（否则不许整文件重写，只能行插）
def dump1(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False).replace('\n', '\r\n')


ck(u'W2 现文件 == `indent=1 + CRLF` 的标准 dump（尾换行另算）',
   dump1(d) == raw.rstrip('\r\n') or dump1(d) + '\r\n' == raw,
   u'尾换行=%r' % (raw[-2:],))
_tail_nl = raw.endswith('\r\n')

# ---- 行级插入：先定位 `"rooms": {` 段（★ 不能直接找 `"ch1": {`，那不是 `"areas"` 就是 `"rooms"`）
lines = raw.split('\r\n')
_rooms_at = None
for i, ln in enumerate(lines):
    if ln.strip() == '"rooms": {':
        _rooms_at = i
        break
ck(u'W3a 找到 `"rooms": {` 段', _rooms_at is not None, u'行=%r' % (_rooms_at,))
lo = None
for i in range((_rooms_at or 0) + 1, len(lines)):
    if lines[i].strip() == '"ch1": {':
        lo = i
        break
ck(u'W3b 在 rooms 段里找到 `"ch1": {`', lo is not None and lo > (_rooms_at or 0),
   u'行=%r' % (lo,))
hi = None
if lo is not None:
    for i in range(lo + 1, len(lines)):
        if lines[i].strip() in ('},', '}'):
            hi = i
            break
ck(u'W3c 找到 ch1 段的结尾', hi is not None, u'行=%r' % (hi,))
if _n['f']:
    print(u'\n★ 定位失败 ⇒ 中止，一个字节都不写。')
    sys.exit(3)
print(u'  ch1 rooms 段：第 %d 行 ~ 第 %d 行' % (lo + 1, hi + 1))
_pos = None
for i in range(lo + 1, hi):
    s = lines[i].strip()
    if not s.startswith('"') or '":' not in s:
        continue
    k = s.split('":')[0][1:]
    if k.isdigit() and k > KEY:
        _pos = i
        break
ck(u'W3d 找到了插入位置（ch1 段里第一个键 > 142 的行）', _pos is not None and _pos > lo,
   u'行=%r' % (_pos,))
if _n['f']:
    print(u'\n★ 定位失败 ⇒ 中止，一个字节都不写。')
    sys.exit(3)

_indent = lines[_pos][:len(lines[_pos]) - len(lines[_pos].lstrip())]
_newline = u'%s"%s": "%s",' % (_indent, KEY, VAL)
new_lines = lines[:_pos] + [_newline] + lines[_pos:]
new = u'\r\n'.join(new_lines)

# ---- 自证 1：写法没变
d2 = json.loads(new)
ck(u'W4 插完仍是 `indent=1 + CRLF` 的标准 dump（写法没被改）',
   (dump1(d2) + ('\r\n' if _tail_nl else u'')) == new)

# ---- 自证 2：只有那一行是新的，其余逐行原序保留
# ★ 不能用 set：`   "142": "dark",` 这种行在**别的章**里逐字相同 ⇒ set 差分恒空
#   （第一版就这么假红了两条）。用多重集合 + "按位删掉那一行后整串必须逐行相等"。
_old_c, _new_c = Counter(lines), Counter(new_lines)
_added = _new_c - _old_c
ck(u'W5 新增行恰好 1 行（多重集合）', sum(_added.values()) == 1, u'%r' % (dict(_added),))
_i = new_lines.index(_newline)
ck(u'W6 删掉新增那一行后，行序列与原来**逐行全等**（不是重排）',
   new_lines[:_i] + new_lines[_i + 1:] == lines, u'插在第 %d 行' % (_i + 1))
ck(u'W7 行数恰好 +1', len(new_lines) == len(lines) + 1,
   u'%d → %d' % (len(lines), len(new_lines)))

# ---- 自证 3：语义
ck(u'W8 `rooms["ch1"]["142"] == "dark"`', d2['rooms']['ch1'].get(KEY) == VAL)
ck(u'W9 其余 134 条一字未变（只多这一个键）',
   {k: v for k, v in d2['rooms']['ch1'].items() if k != KEY} == _before,
   u'条数 %d → %d' % (len(_before), len(d2['rooms']['ch1'])))

if _n['f']:
    print(u'\n★ 自证不过 ⇒ 不写盘。')
    sys.exit(3)

io.open(P, 'w', encoding='utf-8', newline='').write(new)
print(u'\n已写入（+1 行）。结论：%s（%d/%d）'
      % ('PASS' if not _n['f'] else 'FAIL', _n['p'], _n['p'] + _n['f']))
sys.exit(0 if not _n['f'] else 1)
