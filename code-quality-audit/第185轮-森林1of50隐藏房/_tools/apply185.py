# -*- coding: utf-8 -*-
u"""第185轮 · 施工：把 ch1 森林那扇 1/50 神秘门（`room_man`）完整接上。

做什么（四件事，一件都不多）
--------------------------------
1. 登记场景 `ch1.forest.room_man`（原作房号 **142**，`obj_readable`×2 + `obj_doorX_musfade`
   + `obj_markerX` 共 4 个实例，全部来自第115轮普查 `raw/ch1/inst68.json`）。
2. ~~给**已登记但缺区域数据**的场景 `ch1.forest.forest_bake_sale` 补 10 个物件~~
   ★★★ **这条是第1版写错的，已撤销**（见 `fix185b.py`）：`bake_sale` **本来就有独立场景文件**
   `ch1.forest.forest_bake_sale.json`（带 `bg`/`bgm`/`ambient`），里面那 10 个物件与第115轮证据
   **10/10 逐条一致**。再往 zone 塞一份就是**重复载体** ⇒ 物件被数两遍（4086 而非 4076）、
   而且"谁生效"取决于加载顺序。现在 `BAKE_SCENE` 只用来**对账**，不写进 zone。
   落点照样是它 —— 它已经有载体，不需要新建。
3. `_routes.json` 加两条边（原作 `obj_doorX_musfade.Alarm_2` 的两个分支）：
   · `(forest_area5, X) → forest_starwalker`   —— `else` 那一支
   · `(room_man,    X) → forest_bake_sale`     —— `if (room == room_man)` 那一支
   **不改** `(forest_area5, A) → before_maze`：那条是**另一扇门**（`obj_doorA`，走下标位移
   机制），跟这扇 1/50 门无关（第185轮纠正）。
4. `_hidden_rooms[0]` 启用 + 限定门字母 `X`；`_hidden_rooms[1]`（ch2）补 `when_door: "W"`。

幂等（铁律：同一命令可能被跑两次）
--------------------------------
目标状态已存在 ⇒ 空转 `rc=0`；存在但内容不同 ⇒ **不覆盖**、`rc=2` 并逐条列出差异。

三条**能失败**的自证
--------------------
P1 改前三个文件都能**无损往返**（各自 EOL/缩进/尾换行都对得上）—— 否则禁止整文件重写。
P2 改后 routes 只多 2 条，**原有 2830 条逐条未变**（多重集合比对，不是"条数对得上"）。
P3 新增边/场景引用的每个 scene id 都存在；两间新场景引用的**每个贴图文件都真实存在**。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SC = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EVID = os.path.join(REPO, 'code-quality-audit', u'第115轮-跨作品物件普查',
                    '_evidence', 'raw', 'ch1', 'inst68.json')

RC = {'p': 0, 'f': 0}


def check(desc, cond, extra=u''):
    if cond:
        RC['p'] += 1
        print('[ OK ] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        RC['f'] += 1
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    return cond


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def dumps_inline(obj, indent=1, level=0):
    u"""缩进 1 的 JSON；**纯 int 列表内联**成 `[a, b]` —— 复现 `_zone.*.json` 的原写法。"""
    pad = ' ' * (indent * level)
    pad2 = ' ' * (indent * (level + 1))
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = ['%s%s: %s' % (pad2, json.dumps(k, ensure_ascii=False),
                               dumps_inline(v, indent, level + 1))
                 for k, v in obj.items()]
        return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
    if isinstance(obj, list):
        if not obj:
            return '[]'
        if all(isinstance(x, int) and not isinstance(x, bool) for x in obj):
            return '[' + ', '.join(str(x) for x in obj) + ']'
        items = [pad2 + dumps_inline(v, indent, level + 1) for v in obj]
        return '[\n' + ',\n'.join(items) + '\n' + pad + ']'
    return json.dumps(obj, ensure_ascii=False)


def dump2(obj):
    """`_index.json` / `_routes.json` 的写法：缩进 2 + CRLF + **无**尾换行。"""
    return json.dumps(obj, indent=2, ensure_ascii=False).replace('\n', '\r\n')


def dump_zone(obj):
    """`_zone.*.json` 的写法：缩进 1 + 内联 int 列表 + CRLF + **有**尾换行。"""
    return dumps_inline(obj).replace('\n', '\r\n') + '\r\n'


IDX_P = os.path.join(SC, '_index.json')
ZONE_P = os.path.join(SC, '_zone.ch1.forest.json')
RT_P = os.path.join(SC, '_routes.json')

# ----------------------------------------------------------------- 事实常量
MAN = 'ch1.forest.room_man'
BAKE = 'ch1.forest.forest_bake_sale'
AREA5 = 'ch1.forest.forest_area5'
STAR = 'ch1.forest.forest_starwalker'
OLD_ROUTE_N = 2830

#: 两条新边的 priority：**手工边**（原作 `Alarm_2` 分支，不走上标位移机制）。
#: ★★★ 取 9001/9002，**故意放在 `gen_routes44.py` 的生成区间之外**。
#: 第一版取的是 7900/7901，有两处错：
#:   ① `7901` 早被 `ch5.flower_castle.dw_fcastle_gloves_tower` 的 Any 门占着
#:      （第172轮按实例创建代码补的那条）⇒ 真撞号了；
#:   ② 7850~8262 整段是生成器用 `110 + scene_ord * BAND + k` 铺出来的，手工边塞在
#:      里面，**重跑生成器就会再撞一次，而且不报错**。
#: `fix_prio185.py` 负责把已经落错的值挪走（字节级 + 其余字节零改动自证），
#: `check185` 的 `A13` 钉死"全表唯一 + 高于生成器区间"。
PRIO_AREA5_X = 9001
PRIO_MAN_X = 9002

GML_AREA5 = (u'if (room == room_forest_area5)\r\n{\r\n    ch = ceil(random(50));\r\n'
             u'    if (ch == 50 && global.flag[910] == 0)\r\n    {\r\n'
             u'        room_goto(room_man);\r\n    }\r\n    else\r\n    {\r\n'
             u'        room_goto(room_forest_starwalker);\r\n    }\r\n}')
GML_MAN = u'if (room == room_man)\r\n{\r\n    room_goto(room_forest_savepoint2);\r\n}'
SRC_GML = 'gml_Object_obj_doorX_musfade_Alarm_2'

print('')
print('=' * 72)
print(u'P1 改前无损往返（三个文件各自 EOL/缩进/尾换行）')
print('=' * 72)
idx_raw, zone_raw, rt_raw = rd(IDX_P), rd(ZONE_P), rd(RT_P)
idx = json.loads(idx_raw)
zone = json.loads(zone_raw)
rt = json.loads(rt_raw)
ok = True
ok &= check(u'P1.1 `_index.json` 往返', dump2(idx) == idx_raw)
ok &= check(u'P1.2 `_routes.json` 往返', dump2(rt) == rt_raw)
ok &= check(u'P1.3 `_zone.ch1.forest.json` 往返（内联 int 列表）',
            dump_zone(zone) == zone_raw)
if not ok:
    print(u'\n★ 往返不符 ⇒ **禁止整文件重写**（会把几千个数组展开，等于顺手重排文件）。中止。')
    sys.exit(3)

# ----------------------------------------------------------------- 期望态
ev = json.loads(rd(EVID))
rooms = {r['name']: r for r in ev['rooms']}

_OBJ2SPR = {}


def _learn_sprite_map():
    for fn in sorted(os.listdir(SC)):
        if not (fn.startswith('_zone.') and fn.endswith('.json')):
            continue
        try:
            z = json.loads(rd(os.path.join(SC, fn)))
        except Exception:
            continue
        for sc in (z.get('scenes') or {}).values():
            for o in (sc.get('objects') or []):
                if o.get('src') and o.get('sprite'):
                    _OBJ2SPR.setdefault(o['src'], {}).setdefault(o['sprite'], 0)
                    _OBJ2SPR[o['src']][o['sprite']] += 1


def sprite_of(obj):
    u"""`obj` → 贴图路径。**取现有数据里出现最多的那个**（不猜命名规律），
    取不到 → `None`（调用方必须报错，不许编）。"""
    m = _OBJ2SPR.get(obj)
    if not m:
        return None
    return sorted(m.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def build_objects(room_name):
    r = rooms[room_name]
    out = []
    for i in r['insts']:
        sp = sprite_of(i['obj'])
        if sp is None:
            raise RuntimeError(u'推不出贴图：%s / %s（禁止猜）' % (room_name, i['obj']))
        out.append({'pos': [i['x'], i['y']], 'sprite': sp, 'src': i['obj'], 'depth': 0})
    return out


_learn_sprite_map()

MAN_SCENE = {
    'name': u'猩红森林·man',
    'name_raw': 'room_man',
    'name_derived': True,
    'original_room_id': 142,
    'bg': None,
    'bg_source': 'none',
    'objects': build_objects('room_man'),
}
BAKE_SCENE = {
    'name': u'猩红森林·savepoint2',
    'name_raw': 'room_forest_savepoint2',
    'name_derived': True,
    'original_room_id': 82,
    'bg': None,
    'bg_source': 'none',
    'objects': build_objects('room_forest_savepoint2'),
}
#: ★★★ 第185轮**施工修正**（见 `fix185b.py` 的 docstring）：
#: ① `BAKE_SCENE` 现在**只用来对账**，不再写进 zone —— `bake_sale` 早就有独立文件
#:    `ch1.forest.forest_bake_sale.json`（带 bg/bgm/ambient），再塞一份就是重复载体，
#:    物件会被数两遍（`objects_round44 C2/C3` 实测 +10 假增量）。
#: ② index 条目走同区惯例：**进 zone 的场景不写 `file`**（`forest_area5` 也没有），
#:    并且派生名的 index 侧要带区域前缀（`forest_starwalker` → `猩红森林·starwalker`）。
MAN_IDX = {
    'name': u'猩红森林·man',
    'name_raw': 'room_man',
    'name_derived': True,
    'original_room_id': 142,
    'bg': None,
    'bg_source': 'none',
}

NEW_ROUTES = [
    {
        'to': STAR,
        'priority': PRIO_AREA5_X,
        'reason': (u'原作 `obj_doorX_musfade.Alarm_2` 的 else 分支：站在 猩红森林·area5 '
                   u'推这扇门（X），1/50 触发隐藏房 `room_man`，否则落到 猩红森林·starwalker。'
                   u'★ 与 `(area5, A)` 无关 —— 那条是另一扇门（`obj_doorA`，走下标位移机制）。'),
        'when_scene': AREA5,
        'when_door': 'X',
        '_original': {
            'chapter': 'ch1',
            'object': 'obj_doorX_musfade',
            'event': 'Alarm_2',
            'door_letter': 'X',
            'src_room_name': 'room_forest_area5',
            'dst_room_name': 'room_forest_starwalker',
            'cond_man': 'ceil(random(50)) == 50 && global.flag[910] == 0',
            'code': GML_AREA5,
            'evidence': ('code-quality-audit/第109轮-场景过渡动画/_evidence/door_codes109b.json'
                         ' → gml_Object_obj_doorX_musfade_Alarm_2（len=1765）'),
        },
    },
    {
        'to': BAKE,
        'priority': PRIO_MAN_X,
        'reason': (u'原作 `obj_doorX_musfade.Alarm_2`：`if (room == room_man) room_goto('
                   u'room_forest_savepoint2)` —— 隐藏房的出口。`room_forest_savepoint2`(82) '
                   u'在本项目里就是 森林·义卖（`forest_bake_sale`）。'),
        'when_scene': MAN,
        'when_door': 'X',
        '_original': {
            'chapter': 'ch1',
            'object': 'obj_doorX_musfade',
            'event': 'Alarm_2',
            'door_letter': 'X',
            'src_room_name': 'room_man',
            'dst_room_name': 'room_forest_savepoint2',
            'code': GML_MAN,
            'evidence': ('code-quality-audit/第109轮-场景过渡动画/_evidence/door_codes109b.json'
                         ' → gml_Object_obj_doorX_musfade_Alarm_2（len=1765）'),
        },
    },
]

print('')
print('=' * 72)
print(u'幂等闸：目标状态是否已存在')
print('=' * 72)
_idx_sc = idx['chapters']['ch1']['areas']['forest']['scenes']
_zone_sc = zone['scenes']
_hid = rt['_hidden_rooms']
_routes = rt['routes']

have_man_idx = MAN in _idx_sc
have_man_zone = MAN in _zone_sc
#: ★ 终态是"bake_sale **不在** zone"（它有自己的独立文件）—— 第185轮施工修正。
have_bake_zone = BAKE in _zone_sc
have_r1 = any(r.get('when_scene') == AREA5 and r.get('when_door') == 'X'
              and r.get('to') == STAR for r in _routes)
have_r2 = any(r.get('when_scene') == MAN and r.get('when_door') == 'X'
              and r.get('to') == BAKE for r in _routes)
have_hid = bool(_hid) and _hid[0].get('scene') == MAN and _hid[0].get('enabled') is True

print(u'  index 有 room_man=%s | zone 有 room_man=%s | zone 有 bake_sale=%s（应 False）' %
      (have_man_idx, have_man_zone, have_bake_zone))
print(u'  边 area5-X=%s | 边 room_man-X=%s | 隐藏房已启用=%s' % (have_r1, have_r2, have_hid))

ALL_DONE = all((have_man_idx, have_man_zone, have_r1, have_r2, have_hid)) \
    and not have_bake_zone
if ALL_DONE:
    # 逐字段核验"已存在的那份 == 期望那份"，不同 ⇒ rc=2（不覆盖）
    _diffs = []
    if _idx_sc.get(MAN) != MAN_IDX:
        _diffs.append('index/room_man')
    if _zone_sc.get(MAN) != MAN_SCENE:
        _diffs.append('zone/room_man')
    if _zone_sc.get(BAKE) is not None:
        _diffs.append('zone/bake_sale 不该存在')
    if _hid[0].get('when_door') != 'X':
        _diffs.append('hidden[0].when_door')
    if len(_hid) > 1 and _hid[1].get('when_door') != 'W':
        _diffs.append('hidden[1].when_door')
    if _diffs:
        print(u'\n★ 目标状态已存在但与期望**不一致**（不覆盖）：%r' % (_diffs,))
        sys.exit(2)
    print(u'\n★ 空转：目标状态已完整存在且逐字段一致，不写任何文件（rc=0）')
    sys.exit(0)

if any((have_man_idx, have_man_zone, have_r1, have_r2, have_hid)) or have_bake_zone:
    print(u'\n★ **半成品状态**（部分已存在、部分没有）⇒ 拒绝施工，先人工看：')
    print(u'   index=%s zone_man=%s zone_bake=%s r1=%s r2=%s hid=%s'
          % (have_man_idx, have_man_zone, have_bake_zone, have_r1, have_r2, have_hid))
    sys.exit(2)

check(u'施工前 routes 条数 == 2830', len(_routes) == OLD_ROUTE_N, u'实测=%d' % len(_routes))
check(u'施工前 `_zone.ch1.forest.json` 有 27 个场景', len(_zone_sc) == 27, u'实测=%d' % len(_zone_sc))
check(u'施工前 `_hidden_rooms[0]` 是 ch1 那条且未启用',
      _hid and _hid[0].get('from_scene') == AREA5 and _hid[0].get('enabled') is False)

# ----------------------------------------------------------------- 施 工
print('')
print('=' * 72)
print(u'施工')
print('=' * 72)

# ① index：插到 forest.scenes 末尾之前（按 rid 升序插到合适位置）
_idx_sc[MAN] = MAN_IDX
_rid_order = sorted(_idx_sc.items(), key=lambda kv: kv[1].get('original_room_id') or 0)
idx['chapters']['ch1']['areas']['forest']['scenes'] = dict(_rid_order)
print(u'  index：+1 场景（%s）⇒ forest 场景数 %d' % (MAN, len(_idx_sc)))

# ② zone：只插 room_man（bake_sale 有自己的独立文件，**不插**），按 rid 保持升序
_zone_sc[MAN] = MAN_SCENE
_rorder = sorted(_zone_sc.items(), key=lambda kv: kv[1].get('original_room_id') or 0)
zone['scenes'] = dict(_rorder)
print(u'  zone ：+1 场景（room_man 4 物件）⇒ 场景数 %d'
      u'（bake_sale 不插：它有独立文件，插了就是重复载体）' % len(zone['scenes']))

# ③ routes：+2 边
_routes.extend([dict(x) for x in NEW_ROUTES])
print(u'  routes：+2 边（%d）⇒ 共 %d 条' % (PRIO_AREA5_X, len(_routes)))

# ④ hidden_rooms
_hid[0]['scene'] = MAN
_hid[0]['enabled'] = True
_hid[0]['when_door'] = 'X'
_hid[0]['status'] = 'enabled'
_hid[0]['scene_name'] = u'猩红森林·man（隐藏房）'
_hid[0]['note'] = (
    u'第185轮**已启用**：站在 `ch1.forest.forest_area5` 推 **X 门**（`obj_doorX_musfade`）时掷 '
    u'1/50（`ceil(random(50)) == 50`），命中且没发现过才改去本房；真站进来后写 '
    u'`data_store/hidden_rooms_seen.json` **永久锁定**（代理原作 `global.flag[910] == 0`）。'
    u'★ 只对 X 门生效：same 房间还有一扇 `obj_doorA`（字母 A），原作那扇门**不掷骰**。'
    u'★ 本房出口＝`(room_man, X) → ch1.forest.forest_bake_sale`（原作 '
    u'`room_goto(room_forest_savepoint2)`）。')
_hid[0]['evidence'] = (
    u'code-quality-audit/第185轮-森林1of50隐藏房/_evidence/room_man185.json ← '
    u'第109轮 door_codes109b.json → gml_Object_obj_doorX_musfade_Alarm_2（len=1765）；'
    u'第115轮 raw/ch1/inst68.json → room_man(idx=142, n=4) / room_forest_savepoint2(idx=82, n=10)')
if len(_hid) > 1:
    _hid[1]['when_door'] = 'W'
    _hid[1]['note'] = _hid[1].get('note', u'') + (
        u' ★ 第185轮补 `when_door: "W"`：原作那扇门是 `obj_doorw_musfade`（字母 W），'
        u'本房所在的 4 个出口里只有 W 门该掷骰 —— 之前"任意门都掷"是接线层的近似。')
print(u'  hidden：ch1 启用 + when_door=X；ch2 补 when_door=W')

wr(IDX_P, dump2(idx))
wr(ZONE_P, dump_zone(zone))
wr(RT_P, dump2(rt))
print(u'  三个文件已写')

# ----------------------------------------------------------------- 自 证
print('')
print('=' * 72)
print(u'P2 改后只多 2 条边，原有 2830 条**逐条**未变（多重集合）')
print('=' * 72)


def sig(r):
    u"""一条边的**规范化**签名：`sort_keys` 的 JSON 串。

    ★ 不能返回含 `None` 的元组再去 `sorted()` —— 元组比较会在 `str` vs `None` 上抛
      `TypeError`（第一版就是这么崩的）。串起来既可比又不受 dict 键序影响。
    """
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


rt2 = json.loads(rd(RT_P))
new_routes = rt2['routes']
check(u'P2.1 条数 == 2830 + 2', len(new_routes) == OLD_ROUTE_N + 2,
      u'实测=%d' % len(new_routes))
_old_sig = sorted(sig(x) for x in _routes[:OLD_ROUTE_N])
_new_sig = sorted(sig(x) for x in new_routes)
check(u'P2.2 原有 2830 条按多重集合**逐条仍在**',
      all(s in _new_sig for s in _old_sig) and len(_new_sig) == len(set(_new_sig)),
      u'老=%d 新=%d 去重新=%d' % (len(_old_sig), len(_new_sig), len(set(_new_sig))))
_extra = [s for s in _new_sig if s not in _old_sig]
check(u'P2.3 多出来的恰好是那 2 条', len(_extra) == 2,
      u'多出=%r' % ([e[:110] for e in _extra],))

print('')
print('=' * 72)
print(u'P3 引用完整性（scene id 都在、贴图文件都真实存在）')
print('=' * 72)
idx2 = json.loads(rd(IDX_P))
zone2 = json.loads(rd(ZONE_P))
_sc_all = set()
for ch in idx2['chapters'].values():
    for ar in ch['areas'].values():
        _sc_all |= set(ar['scenes'])
_miss_sc = sorted({AREA5, MAN, STAR, BAKE} - _sc_all)
check(u'P3.1 四条新引用（源×2/目标×2）都在 index 里', not _miss_sc,
      u'缺=%r' % (_miss_sc,))
_bad_sp = []
for o in zone2['scenes'][MAN]['objects']:
    if not os.path.isfile(os.path.join(SC, o['sprite'])):
        _bad_sp.append((MAN, o['sprite']))
for o in (json.loads(rd(os.path.join(SC, BAKE + '.json'))).get('objects') or []):
    if not os.path.isfile(os.path.join(SC, o['sprite'])):
        _bad_sp.append((BAKE, o['sprite']))
check(u'P3.2 room_man（zone）与 bake_sale（独立文件）的贴图**逐个**存在',
      not _bad_sp, u'缺=%r' % (_bad_sp,))
#: ★ 修正后 `bake_sale` **只验它自己的文件**，并额外钉"它不在 zone 里"（不许重复载体）。
_bf = json.loads(rd(os.path.join(SC, BAKE + '.json')))
check(u'P3.3 room_man 物件数 == 4；bake_sale 独立文件 10 个且**不在 zone**',
      len(zone2['scenes'][MAN]['objects']) == 4
      and len(_bf.get('objects') or []) == 10
      and BAKE not in zone2['scenes'],
      u'%d / %d / 在zone=%s' % (len(zone2['scenes'][MAN]['objects']),
                                len(_bf.get('objects') or []),
                                BAKE in zone2['scenes']))

print('')
print('=' * 72)
print(u'合计：OK=%d FAIL=%d' % (RC['p'], RC['f']))
print('=' * 72)
sys.exit(0 if RC['f'] == 0 else 1)
