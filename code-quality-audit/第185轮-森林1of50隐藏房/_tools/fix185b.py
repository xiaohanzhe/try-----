# -*- coding: utf-8 -*-
u"""第185轮 · 施工修正：撤掉 `bake_sale` 的重复载体 + 把 index 的 `room_man` 条目改回同区惯例。

为什么要撤（★★★ 这是本轮第 2 个真缺陷，`rooms_round47 B1` / `scene_route_original E1c` /
`objects_round44` 三处红才暴露出来）
------------------------------------------------------------------------
`ch1.forest.forest_bake_sale`（原作 `room_forest_savepoint2`，rid 82）**早就有自己的独立
场景文件** `ch1.forest.forest_bake_sale.json`（3,022 字节，带 `bg` / `bgm` / `ambient`），
里面那 10 个物件与第115轮证据 **10/10 逐条一致**（src + pos 全同，连顺序都一样）。
我施工时误以为它"缺物件数据"，又往 `_zone.ch1.forest.json` 里塞了一份 ⇒
**同一间房有两个载体**：物件数被多算 10（4072 → 4086，而独立重算应是 4076），
`objects_round44 C2/C3` 就是这么红的。

为什么要改 index（同一批红里 `rooms_round47 B1` 指出的）
----------------------------------------------------------
1. 我给它写了 `"file": "ch1.forest.room_man.json"` —— **那个文件不存在**，
   而 `room_man` 的物件我已经放进 `_zone.ch1.forest.json` 了。同区惯例是：
   **进 zone 的场景，index 条目不写 `file`**（`forest_area5` / `forest_starwalker` 都没有）。
2. 少了 `name_raw` / `name_derived` / `bg` / `bg_source` 四个字段（同区每条都有）。
3. `name` 写成了 `森林·man`，而**派生名的 index 侧带区域前缀**（`forest_area5` →
   `猩红森林·area5`、`forest_starwalker` → `猩红森林·starwalker`）⇒ 改成 `猩红森林·man`，
   与 zone 侧、也与用户批准的名字一致。

做法：**字节级 + 三重自证**
1. 改前：`dump_zone(parse(orig)) == orig` 且 `dump2(parse(orig)) == orig`（格式无损，才敢重写）；
2. 改后：同样再证一遍（证明"只少了那两个东西"以外没别的变化）；
3. 终态对账：zone 里没有 `bake_sale`、index 里 `room_man` 六字段齐全且无 `file`、
   `solo + zone == index` 这条恒等式成立、`bake_sale` 的独立文件仍在且 10 个物件没动。

幂等：已经是终态 ⇒ rc=0 空转。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SC = u'C:/Users/23002/Desktop/\u9879\u76ee\u6587\u4ef6\u5939/try - \u526f\u672c/ralsei_pet/assets/scenes'
IDX_P = os.path.join(SC, '_index.json')
ZONE_P = os.path.join(SC, '_zone.ch1.forest.json')
BAKE_FILE = os.path.join(SC, 'ch1.forest.forest_bake_sale.json')

MAN = 'ch1.forest.room_man'
BAKE = 'ch1.forest.forest_bake_sale'

_n = {'p': 0, 'f': 0}


def ck(desc, cond, extra=u''):
    _n['p' if cond else 'f'] += 1
    print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', desc,
                       (u'    ' + extra) if extra else u''))
    return cond


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def dumps_inline(obj, indent=1, level=0):
    u"""复现 `_zone.*.json` 的写法：缩进 1、纯 int 列表内联、无尾换行。"""
    pad = ' ' * (indent * level)
    pad2 = ' ' * (indent * (level + 1))
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        return '{\n' + ',\n'.join(
            '%s%s: %s' % (pad2, json.dumps(k, ensure_ascii=False),
                          dumps_inline(v, indent, level + 1)) for k, v in obj.items()
        ) + '\n' + pad + '}'
    if isinstance(obj, list):
        if not obj:
            return '[]'
        if all(isinstance(x, int) and not isinstance(x, bool) for x in obj):
            return '[' + ', '.join(str(x) for x in obj) + ']'
        return '[\n' + ',\n'.join(pad2 + dumps_inline(v, indent, level + 1)
                                  for v in obj) + '\n' + pad + ']'
    return json.dumps(obj, ensure_ascii=False)


def dump_zone(obj):
    return dumps_inline(obj).replace('\n', '\r\n') + '\r\n'


def dump2(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False).replace('\n', '\r\n')


zone_raw, idx_raw = rd(ZONE_P), rd(IDX_P)
zone, idx = json.loads(zone_raw), json.loads(idx_raw)

# ---------------------------------------------------------------- 幂等闸
_fs = idx['chapters']['ch1']['areas']['forest']['scenes']
_already = (BAKE not in zone['scenes']
            and 'file' not in (_fs.get(MAN) or {})
            and (_fs.get(MAN) or {}).get('name') == u'猩红森林·man')
if _already:
    print(u'★ 已是终态（zone 无 bake_sale / index 无 file / name 带区域前缀）⇒ 空转 rc=0')
    sys.exit(0)

print('')
print('=' * 72)
print(u'F1 改前无损往返（证明可以整文件重写）')
print('=' * 72)
ck(u'F1.1 `_zone.ch1.forest.json` 往返一致', dump_zone(zone) == zone_raw)
ck(u'F1.2 `_index.json` 往返一致', dump2(idx) == idx_raw)
if _n['f']:
    print(u'\n★ 往返不符 ⇒ 禁止整文件重写。中止，一个字节都不写。')
    sys.exit(3)

# ---------------------------------------------------------------- zone：删 bake_sale
if BAKE in zone['scenes']:
    _nobj = len(zone['scenes'][BAKE].get('objects') or [])
    zone['scenes'].pop(BAKE)
    print(u'\n  已从 zone 撤掉 `%s`（撤掉 %d 个物件）' % (BAKE, _nobj))
else:
    print(u'\n  zone 里本来就没有 `%s`（无需撤）' % BAKE)

# ---------------------------------------------------------------- index：room_man 六字段
_new = {
    'name': u'猩红森林·man',
    'name_raw': 'room_man',
    'name_derived': True,
    'original_room_id': 142,
    'bg': None,
    'bg_source': 'none',
}
if _fs.get(MAN) == _new:
    print(u'  index 的 `%s` 已是终态' % MAN)
else:
    print(u'  index 的 `%s`：%r → %r' % (MAN, _fs.get(MAN), _new))
    _fs[MAN] = _new

_zone_new = dump_zone(zone)
_idx_new = dump2(idx)
ck(u'F2 改后 `_zone` 往返仍然一致（只是少了那一块）', dump_zone(json.loads(_zone_new)) == _zone_new)
ck(u'F3 改后 `_index` 往返仍然一致', dump2(json.loads(_idx_new)) == _idx_new)
if _n['f']:
    print(u'\n★ 改后往返不符 ⇒ 中止，一个字节都不写。')
    sys.exit(3)

wr(ZONE_P, _zone_new)
wr(IDX_P, _idx_new)

# ---------------------------------------------------------------- 终态对账
print('')
print('=' * 72)
print(u'F4 终态对账')
print('=' * 72)
z2 = json.loads(rd(ZONE_P))
i2 = json.loads(rd(IDX_P))
fs2 = i2['chapters']['ch1']['areas']['forest']['scenes']

ck(u'F4.1 zone 里**没有** `bake_sale`（不再是重复载体）', BAKE not in z2['scenes'])
ck(u'F4.2 zone 里仍有 `room_man`，4 个物件',
   len((z2['scenes'].get(MAN) or {}).get('objects') or []) == 4)
ck(u'F4.3 index 的 `room_man` 没有 `file` 键',
   'file' not in (fs2.get(MAN) or {}), u'%r' % (sorted((fs2.get(MAN) or {}).keys()),))
ck(u'F4.4 index 的 `room_man` 六字段齐全且值对',
   fs2.get(MAN) == _new, u'%r' % (fs2.get(MAN),))
ck(u'F4.5 `bake_sale` 的独立文件仍在，且 10 个物件一个没动',
   os.path.isfile(BAKE_FILE)
   and len((json.loads(rd(BAKE_FILE)).get('objects') or [])) == 10,
   u'存在=%s' % os.path.isfile(BAKE_FILE))

# ★★ 恒等式：独立文件数 + zone 场景数 == index 场景数（施工前是 88 + 2078 == 2166）
SCN = {}


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, dict):
                if 'original_room_id' in v:
                    SCN[k] = v
                _walk(v)


_walk(i2)
_solo = {k for k, v in SCN.items() if v.get('file')}
_zoneall = {}
for fn in sorted(os.listdir(SC)):
    if fn.startswith('_zone.') and fn.endswith('.json'):
        for k in (json.loads(rd(os.path.join(SC, fn))).get('scenes') or {}):
            _zoneall[k] = fn
ck(u'F4.6 ★ index 场景数 %d == 独立文件 %d + zone %d' % (len(SCN), len(_solo), len(_zoneall)),
   len(SCN) == len(_solo) + len(_zoneall),
   u'%d vs %d' % (len(SCN), len(_solo) + len(_zoneall)))
ck(u'F4.7 ★ 两种载体**不重叠**（同一场景不许既是独立文件又在 zone）',
   not (_solo & set(_zoneall)), u'重叠=%r' % (sorted(_solo & set(_zoneall))[:5],))
ck(u'F4.8 ★ 没有孤儿：zone 里每一间都在 index 里登记过',
   not (set(_zoneall) - set(SCN)), u'孤儿=%r' % (sorted(set(_zoneall) - set(SCN))[:5],))
ck(u'F4.9 没有空壳：index 里每一间都有载体（独立文件或 zone）',
   not (set(SCN) - _solo - set(_zoneall)),
   u'空壳=%r' % (sorted(set(SCN) - _solo - set(_zoneall))[:5],))

print('')
print(u'结论：%s（%d/%d）' % ('PASS' if not _n['f'] else 'FAIL',
                            _n['p'], _n['p'] + _n['f']))
sys.exit(0 if not _n['f'] else 1)
