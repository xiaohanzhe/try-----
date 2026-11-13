# -*- coding: utf-8 -*-
u"""第183轮 · 删掉 ch2 `priority=7122` 那条确定性边（`traffic_3 → dw_city_man`）的回归锁。

## 为什么要删

原作 `obj_doorw_musfade.Alarm_2`（第181轮反编译取证）：

    if (global.flag[917] == 0 && scr_sideb_get_phase() == 0)
        room_goto(room_dw_city_dog_traffic);
    else {
        var man_room = scr_sideb_get_phase() == 0 && global.flag[917] < 2
                       && global.flag[918] == 0 && ceil(random(50)) == 50;
        if (man_room) room_goto(room_dw_city_man);
        else          room_goto(room_dw_city_moss);
    }

`man` 是 **1/50 的概率分支**，`moss` 才是 else。第169轮把同一扇门的三个互斥分支
（`dog_traffic` / `man` / `moss`）都物化成了**无条件边**，于是账本里多了一条
"确定性地去 man"——它既不是原作，又会让人误以为这条路一定走得通。

第182轮已把概率机制接上（`_hidden_rooms[1]`，`enabled: true`，p = 0.02），本轮让位。

## 为什么是"删"而不是"改指 moss"

`7123` 本来就指向 `dw_city_moss`。把 `7122` 也改指 moss 只会造出**两条一模一样的
moss 边**——重复边是本项目明令不加的（第170轮）。

## 为什么删它**不改变任何运行行为**（本轮最强的一条，B3/B4 成对钉）

`7121`（`dog_traffic`）的 `when_*` 与 `7122` **完全相同**、priority 更小
⇒ `match()` 只会返回 7121。所以：

  · B3：把留档加回表里再 `match()`，结果与不加班**完全一致** ⇒ 零行为差异；
  · B4：把 7121 也抠掉后 `match()` 必须返回 7122 ⇒ 说明 7122 本来是**能被选中**的，
        只是被 7121 挡住了。**没有 B4，B3 可能只是"7122 本来就是垃圾"** 的同义反复。

## ★ 本轮**没有**修的东西（如实记录，见报告 §遗留）

`7123 → dw_city_moss` 仍然被 `7121` 无条件遮挡 ⇒ 表里**表达不出**"先 dog_traffic、
后 moss"这种门控（`match()` 没有 `gate` 概念，`fallback` 只有全局一份）。
所以 `dw_city_moss` 目前不可达。这不是本轮造成的，也不在本轮范围内。

## 判据分段

- A 数据（7） · B 行为（6） · C 登记说明（3） · D 账本（4） · E 自检（5）

★ 环境变量口子（只给 `mutate183.py` 用，判据本身一行不改）：
  `CQ_ROUTES_183` / `CQ_MODS_183` / `CQ_EVID_183` / `CQ_CHECK181_183` / `CQ_APPLY183_183`
  ⚠️ `CQ_ROUTES_183` 指到的文件**必须**叫 `_routes.json` —— 产品侧
  `load_routes(os.path.dirname(...))` 是按目录拼文件名的（B1/B2 走的是产品真身）。
"""
import ast
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
MODS = os.environ.get('CQ_MODS_183') or os.path.join(PET, 'modules')
ROUTES = os.environ.get('CQ_ROUTES_183') or os.path.join(SCENES, '_routes.json')
EVID = os.environ.get('CQ_EVID_183') or os.path.join(ROUND, '_evidence', 'removed183.json')
CHECK181 = (os.environ.get('CQ_CHECK181_183')
            or os.path.join(REPO, 'code-quality-audit', u'第181轮-补门型', '_tools',
                            'check181.py'))
APPLY183 = os.environ.get('CQ_APPLY183_183') or os.path.join(HERE, 'apply183.py')

PRIORITY = 7122
FROM_SCENE = u'ch2.cyber_city.dw_city_traffic_3'
TO_SCENE = u'ch2.cyber_city.dw_city_man'

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


def _sig(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  A 数据：表与留档
# ---------------------------------------------------------------------------
ROUTEDATA = jload(ROUTES)
ROUTES_L = ROUTEDATA.get('routes') or []
EVIDENCE = jload(EVID) if os.path.isfile(EVID) else {}
KEEP = EVIDENCE.get('routes') or []
META = EVIDENCE.get('meta') or {}

_hit = [r for r in ROUTES_L if isinstance(r, dict) and r.get('priority') == PRIORITY]
check(u'A1 表里已经查不到 `priority=7122`（删干净了）',
      _hit == [], u'命中 %d 条 %r' % (len(_hit), [r.get('to') for r in _hit]))

#: ★★★ 第185轮引账：本周目删边后是 2830，但第185轮加了 2 条森林手工边
#:   （`area5 --X--> forest_starwalker` priority 9001、
#:    `room_man --X--> forest_bake_sale` priority 9002，见 `第185轮-森林1of50隐藏房`）
#:   ⇒ 现在是 2832。
#:   ★ 留档里的 `total_before/after`（2831/2830）是**第183轮当天的历史事实**，
#:     一个字都不许改 —— 改了等于篡改留档。所以只让"现数"减去本条新增账。
_ADDED_185 = 2
#: ★ 第186轮引账：ch1 五间「进得去出不来」接了 11 条出口边（priority 9100~9110）。
#:   ★ 同样不把 2830 改掉 —— 那是"第183轮当天的路由数"的历史事实。
_ADDED_186 = 11
check(u'A2 路由总数 == 2830 + %d（第185轮账）+ %d（第186轮账）= %d，且与留档 `meta.total_after` 对得上'
      % (_ADDED_185, _ADDED_186, 2830 + _ADDED_185 + _ADDED_186),
      len(ROUTES_L) == 2830 + _ADDED_185 + _ADDED_186
      and META.get('total_after') == 2830
      and META.get('total_before') == 2831,
      u'实测 %d；留档 before=%r after=%r'
      % (len(ROUTES_L), META.get('total_before'), META.get('total_after')))

check(u'A3 留档文件存在、是对象、`routes` 恰好 1 条，且那条就是 7122',
      isinstance(EVIDENCE, dict)
      and len(KEEP) == 1
      and isinstance(KEEP[0], dict)
      and KEEP[0].get('priority') == PRIORITY,
      u'留档 %d 条；priority=%r'
      % (len(KEEP), [k.get('priority') for k in KEEP if isinstance(k, dict)]))

_k0 = KEEP[0] if (KEEP and isinstance(KEEP[0], dict)) else {}
check(u'A4 留档那条字段完整（`to`/`when_scene`/`when_door`/`_original` 都在，能原样加回去）',
      all(k in _k0 for k in ('to', 'when_scene', 'when_door', 'priority', '_original')),
      u'缺 %r' % [k for k in ('to', 'when_scene', 'when_door', 'priority', '_original')
                  if k not in _k0])

_org = _k0.get('_original') or {}
check(u'A5 留档的确实是"那条"：源 = traffic_3、目标 = dw_city_man、批次 = 169',
      _k0.get('when_scene') == FROM_SCENE
      and _k0.get('to') == TO_SCENE
      and _org.get('src_room_name') == u'room_dw_city_traffic_3'
      and _org.get('dst_room_name') == u'room_dw_city_man'
      and _org.get('batch') == 169,
      u'when_scene=%r to=%r src=%r dst=%r batch=%r'
      % (_k0.get('when_scene'), _k0.get('to'), _org.get('src_room_name'),
         _org.get('dst_room_name'), _org.get('batch')))

_by_prio = {}
for _r in ROUTES_L:
    if isinstance(_r, dict):
        _by_prio.setdefault(_r.get('priority'), []).append(_r)
check(u'A6 ★ 同源的另两条**没被误伤**：7121 仍 → dog_traffic、7123 仍 → moss',
      len(_by_prio.get(7121) or []) == 1
      and _by_prio[7121][0].get('to') == u'ch2.cyber_city.dw_city_dog_traffic'
      and len(_by_prio.get(7123) or []) == 1
      and _by_prio[7123][0].get('to') == u'ch2.cyber_city.dw_city_moss',
      u'7121=%r 7123=%r'
      % ([r.get('to') for r in _by_prio.get(7121) or []],
         [r.get('to') for r in _by_prio.get(7123) or []]))

_SAME = [r for r in ROUTES_L
         if isinstance(r, dict) and r.get('when_scene') == FROM_SCENE
         and r.get('when_door') == u'W']
_SAME_TO = [r.get('to') for r in _SAME]
check(u'A7 同一扇门（traffic_3 / W）现在恰好 2 条出边，且目标互不相同（没造出重复边）',
      len(_SAME) == 2 and len(set(_SAME_TO)) == 2,
      u'%d 条 → %r' % (len(_SAME), _SAME_TO))

# ---------------------------------------------------------------------------
#  B 行为：真调产品函数（`scene_routing.match` / `pick_hidden`）
# ---------------------------------------------------------------------------
sys.path.insert(0, MODS)
sys.path.insert(0, os.path.join(PET, 'modules'))
import scene_routing as SR                                     # noqa: E402

TABLE = SR.load_routes(os.path.dirname(ROUTES))
check(u'B1 产品侧 `load_routes()` 读得动（`ok` 为真），且条数与 A2 一致',
      isinstance(TABLE, dict) and TABLE.get('ok') is True
      and len(TABLE.get('routes') or []) == len(ROUTES_L),
      u'ok=%r n=%r' % (TABLE.get('ok'), len(TABLE.get('routes') or [])))

_CTX = {'scene_id': FROM_SCENE, 'door': u'W'}
_res_now = SR.match(TABLE, _CTX)
_NOW = (None if _res_now is None else (_res_now.get('priority'), _res_now.get('to')))
check(u'B2 ★ `match(traffic_3, 门W)` 仍返回 7121 → dog_traffic（删边前后应当一模一样）',
      _NOW == (7121, u'ch2.cyber_city.dw_city_dog_traffic'), u'实测 %r' % (_NOW,))

# ★ 把留档加回去，重跑同一个 match —— 结果必须一字不差
TABLE_OLD = {'ok': True,
             'routes': list(TABLE.get('routes') or []) + list(KEEP),
             'fallback': TABLE.get('fallback')}
_res_old = SR.match(TABLE_OLD, _CTX)
_OLD = (None if _res_old is None else (_res_old.get('priority'), _res_old.get('to')))
check(u'B3 ★★ 删边零行为差异：把留档加回表里再 match，结果与不加班**完全相同**',
      _OLD == _NOW, u'加回=%r 现在=%r' % (_OLD, _NOW))

# ★ 负控制：把 7121 也抠掉，7122 必须上位 —— 否则 B3 只是"7122 本来就是垃圾"的同义反复
TABLE_NO1 = {'ok': True,
             'routes': [r for r in (TABLE.get('routes') or [])
                        if r.get('priority') != 7121] + list(KEEP),
             'fallback': TABLE.get('fallback')}
_res_no1 = SR.match(TABLE_NO1, _CTX)
_NO1 = (None if _res_no1 is None else (_res_no1.get('priority'), _res_no1.get('to')))
check(u'B4 ★★ 负控制：抠掉 7121 后 match 必须返回 7122（证明 7122 真被遮住、不是死条目）',
      _NO1 == (PRIORITY, TO_SCENE), u'实测 %r' % (_NO1,))

check(u'B5 同一语境现在**选不到** man 了（确定性边确实没了）',
      _res_now is not None and _res_now.get('to') != TO_SCENE,
      u'to=%r' % (None if _res_now is None else _res_now.get('to')))

_HID = ROUTEDATA.get('_hidden_rooms') or []
#: ★ 第185轮：`pick_hidden` 新增 `door=`，且 ch2 那条补了 `when_door: "W"`
#:   （原作那扇门是 `obj_doorw_musfade`）。缺门不掷是**新语义**，所以这里必须
#:   显式说明走的是 W 门 —— 否则本判据会因 fail-closed 恒假（假红）。
_DOOR_W = 'W'
_divert = SR.pick_hidden(_HID, FROM_SCENE, seen=(), roll=lambda: 0.0, door=_DOOR_W)
check(u'B6 ★ 删边后概率机制接手：`pick_hidden(traffic_3, roll=0.0, door="W")` 仍命中 man',
      isinstance(_divert, dict) and _divert.get('scene') == TO_SCENE,
      u'实测 %r' % (None if _divert is None else _divert.get('scene')))

# ---------------------------------------------------------------------------
#  C 隐藏房登记（说明要跟着改，否则下一个人看到的还是假话）
# ---------------------------------------------------------------------------
_ch2 = [h for h in _HID if isinstance(h, dict) and h.get('from_scene') == FROM_SCENE]
check(u'C1 ch2 那条登记仍完好：4 条里启用 1 条、p=0.02、指向 dw_city_man',
      len(_HID) == 4 and len(_ch2) == 1
      and _ch2[0].get('enabled') is True
      and _ch2[0].get('probability') == 0.02
      and _ch2[0].get('scene') == TO_SCENE,
      u'登记 %d 条；ch2 命中 %d 条' % (len(_HID), len(_ch2)))

_note = (_ch2[0].get('note') if _ch2 else u'') or u''
check(u'C2 ★ 登记说明已更新：不再写"尚未删除"，并点明是第183轮删的',
      (u'尚未删除' not in _note) and (u'第183轮' in _note)
      and (u'已删' in _note),
      u'含"尚未删除"=%s 含"第183轮"=%s'
      % (u'尚未删除' in _note, u'第183轮' in _note))

check(u'C3 说明里仍保留关键口径（1/50 表达式 + 永久锁文件名），不是空口"已删除"',
      u'ceil(random(50)) == 50' in _note
      and u'hidden_rooms_seen.json' in _note,
      u'含表达式=%s 含锁文件=%s'
      % (u'ceil(random(50)) == 50' in _note, u'hidden_rooms_seen.json' in _note))

# ---------------------------------------------------------------------------
#  D 账本：与第181轮那道"只增不减"闸对上
# ---------------------------------------------------------------------------
_T181 = ast.parse(rd(CHECK181))
_LEDGER = None
for _node in ast.walk(_T181):
    if isinstance(_node, ast.Assign) and any(
            getattr(_t, 'id', None) == 'POST_181_REMOVED' for _t in _node.targets):
        try:
            _LEDGER = ast.literal_eval(_node.value)
        except Exception:                                      # noqa: BLE001
            _LEDGER = None
_led_prio = set()
if isinstance(_LEDGER, dict):
    for _k, _v in _LEDGER.items():
        if isinstance(_v, (list, tuple)) and _v and isinstance(_v[0], (list, tuple)):
            _led_prio.update(_v[0])
_ev_prio = set(k.get('priority') for k in KEEP if isinstance(k, dict))
check(u'D1 ★ 第181轮账本里记的删除 == 本轮留档里的 priority（跨轮对得上，不是各说各话）',
      _led_prio == _ev_prio and _ev_prio == {PRIORITY},
      u'账本 %r；留档 %r' % (sorted(_led_prio), sorted(_ev_prio)))


def _label0(node):
    u"""取 `check(...)` 第一个参数的**字面量前缀**（可能是 `'x' % (...)` 的 BinOp）。"""
    while isinstance(node, ast.BinOp):
        node = node.left
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return u''


_A1_CMP = None
for _node in ast.walk(_T181):
    if not (isinstance(_node, ast.Call) and getattr(_node.func, 'id', None) == 'check'):
        continue
    if not _node.args or not _label0(_node.args[0]).startswith(u'A1 '):
        continue
    if len(_node.args) >= 2 and isinstance(_node.args[1], ast.Compare):
        _A1_CMP = type(_node.args[1].comparators[0]).__name__
check(u'D2 ★ 第181轮 A1 已"引账不调数"：右边是 `_BASE_TOTAL - _N_REMOVED`（BinOp），不再是裸数字',
      _A1_CMP is not None and _A1_CMP not in (u'Constant', u'Num', u'Str'),
      u'右操作数类型 %r' % (_A1_CMP,))

_restore = list(ROUTES_L) + list(KEEP)
_restore_hit = [r for r in _restore if isinstance(r, dict) and r.get('priority') == PRIORITY]
check(u'D3 留档可整段还原：内存里拼回去 = 2831 + %d（第185轮账）+ %d（第186轮账）= %d 条，'
      u'且 7122 仍唯一（还原不会造重复）'
      % (_ADDED_185, _ADDED_186, 2831 + _ADDED_185 + _ADDED_186),
      len(_restore) == 2831 + _ADDED_185 + _ADDED_186 and len(_restore_hit) == 1,
      u'%d 条；7122 命中 %d' % (len(_restore), len(_restore_hit)))

_apply_src = rd(APPLY183) if os.path.isfile(APPLY183) else u''
check(u'D4 施工脚本仍幂等且守格式：无 `assert`（第180轮教训），且用 `dump_routes` 走无损往返',
      bool(_apply_src) and not re.search(r'^\s*assert\s', _apply_src, re.M)
      and u'def dump_routes' in _apply_src,
      u'存在=%r 有 dump_routes=%r' % (bool(_apply_src), u'def dump_routes' in _apply_src))

# ---------------------------------------------------------------------------
#  E 自检
# ---------------------------------------------------------------------------
_raw = io.open(os.path.abspath(__file__), 'rb').read()
check(u'E1 本文件无 BOM 且 UTF-8 可解', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'E2 本文件无 U+FFFD', _raw.decode('utf-8').count(u'\ufffd') == 0)

_T = ast.parse(_raw.decode('utf-8'))
_CONST_TRUE = [n.lineno for n in ast.walk(_T)
               if isinstance(n, ast.Call) and len(n.args) >= 2
               and getattr(n.func, 'id', None) == 'check'
               and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'E3 本文件里没有"常量 True"判据（恒真比不写还危险）', _CONST_TRUE == [],
      u'行号 %r' % _CONST_TRUE)

_TEXT = _raw.decode('utf-8')
_EXT = re.findall(r'[D-E]:[\\/]{1,2}[A-Za-z_\u4e00-\u9fff][^\'"\s]{2,}', _TEXT)
check(u'E4 不依赖外部盘/临时区（源码里没有真实盘符路径）', _EXT == [], u'命中 %r' % _EXT)

_bad_imp = [n.lineno for n in ast.walk(_T)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            and any(x in ast.dump(n) for x in ('main', 'socket', 'requests',
                                               'urllib', 'http', 'Qt'))]
check(u'E5 不 import 真机/网络/Qt（`main`/`socket`/`requests`/`urllib`/`http`/`Qt` 全不碰）',
      _bad_imp == [], u'行号 %r' % _bad_imp)

check(u'E6 判据条数不随环境变（本文件恒发 26 条断言，含本条自身）',
      _n['p'] + _n['f'] + 1 == 26, u'当前 %d' % (_n['p'] + _n['f'] + 1))

# ---------------------------------------------------------------------------
print('')
print('=' * 74)
print(u'合计 %d 条判据  PASS=%d  FAIL=%d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _bad:
    print(u'FAIL 明细：')
    for d in _bad:
        print(u'  - ' + d)
print('=' * 74)
print(u'[NOTE] 现状（本轮不修）：7123 → dw_city_moss 仍被 7121 无条件遮挡 ⇒ ')
print(u'       `dw_city_moss` 目前不可达；表里表达不出"先 dog_traffic 后 moss"的门控。')
sys.exit(0 if _n['f'] == 0 else 1)
