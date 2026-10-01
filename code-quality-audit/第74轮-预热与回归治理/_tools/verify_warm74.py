# -*- coding: utf-8 -*-
"""第74轮 · 常驻锁：NPC 预热（主角团优先）不许静默漂移。

为什么值得常驻
--------------
B8 给启动流程加了一条**会真的发 HTTP 请求**的后台队列。三件事都可能被无声改坏：

  ① **顺序**：用户口径是「**先预热主角团**」＋「没有什么常聊这类的，尽量全预热」。
     顺序一旦退回"随便排"，主角团就不再是第一批 —— 而这条是用户亲口要的；
  ② **让路**：预热跑在后台，用户一开口就必须停手。若判据被换成拿 `_ai_delta_sink`
     当门（本项目钉过的坑：它收尾**刻意不清空** ⇒ 拿它当门会永久为真），
     让路会**静默失效**，用户的请求永远排在预热后面；
  ③ **接点**：`_prewarm_npc_caches` 有没有被 `_prewarm_ai_cache` 真调用 ——
     「函数写对了 != 产品用上了」是本项目最贵的坑（第 3 次踩）。

设计纪律（沿用 check71~73）
--------------------------
① **零网络 / 零模型 / 零外部盘** ⇒ 可进 G2（C 段喂假 client，不碰 Ollama）。
② **正/负控制成对**：每条"优先"都配一条"不优先"，每个内核都配"改坏了必须报红"。
③ **不自比**：A8 的真源是 `_placement.json`（数据面），不是本文件自己写的名单。
④ 判据名里不许自带 `[PASS]` / `[FAIL]` / `[OK]` 字样（会污染 run_all 的计数）。
"""
from __future__ import print_function

import ast
import copy
import io
import json
import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODULES = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
NPCDIR = os.path.join(PET, 'assets', 'npc')
MAIN = os.path.join(SRC, 'main.py')
CONFIG = os.path.join(PET, 'config.json')
PLACEMENT = os.path.join(NPCDIR, '_placement.json')

FAILS = []
NCHECK = 0


def check(name, cond, extra=''):
    global NCHECK
    NCHECK += 1
    for tok in ('[PASS]', '[FAIL]', '[OK]'):
        if tok in name:
            FAILS.append('判据名字面量污染: %s' % name)
    line = ('[PASS] %s %s' % (name, extra)) if cond else ('[FAIL] %s %s' % (name, extra))
    print(line)
    if not cond:
        FAILS.append(name)


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def source_of(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


for _p in (MODULES, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as M                                              # noqa: E402

_MAIN_SRC = source_of(MAIN)
_TREE = ast.parse(_MAIN_SRC)


def _func_node(name):
    for node in ast.walk(_TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _func_src(name):
    """取某个**函数/方法**的原文片段（含 docstring 与嵌套定义）。取不到 ⇒ 空串。"""
    node = _func_node(name)
    return (ast.get_source_segment(_MAIN_SRC, node) or '') if node is not None else ''


def _code_only_src(name):
    """★ 取"**剥掉 docstring** 的代码体"（用 AST 反解析）。

    为什么必须剥：本段有**负控制**（"这段代码里没有 X"），而 docstring 里**故意**
    会写「绝不用 X」这类防坑说明 —— 拿原文比对就会把说明当成事实（本项目已踩多次：
    check55 / check67 都栽在"docstring 提到了"上）。`ast.unparse` 顺带去掉注释。
    """
    node = _func_node(name)
    if node is None:
        return ''
    node = copy.deepcopy(node)
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) \
            and isinstance(getattr(body[0], 'value', None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    node.body = body or [ast.Pass()]
    try:
        return ast.unparse(node)
    except Exception:
        return ''


# 数据面真源：主角团成员（A8 拿它当锚点，不让本文件自说自话）
_PL = read_json(PLACEMENT)
_PARTY = []
for _g in (_PL.get('groups') or []):
    if _g.get('id') == 'party':
        _PARTY = list(_g.get('members') or [])
        break

print('=' * 68)
print('第七十四轮 · NPC 预热（主角团优先）自检')
print('数据面：主角团 = %s' % (_PARTY,))
print('=' * 68)

# ==================================================================== A
print('')
print('=== A. 纯函数 prewarm_order（三档排序）===')

order = M.prewarm_order

_sort_t = ['kris', 'susie', 'ralsei']
_r1 = order(['zed', 'susie', 'kris', 'ralsei', 'aaa'], team=_sort_t, here=[])
check('A1 主角团排最前，且**保持队伍给定顺序**（kris→susie→ralsei）',
      _r1[:3] == _sort_t, _r1)

_r2 = order(['zed', 'susie', 'kris', 'ralsei', 'aaa'], team=[], here=[])
check('A2 负控制：主角团名单为空时，他们**不再**被优先（落到其余档，按 id 排序）',
      _r2[:3] == ['aaa', 'kris', 'ralsei'], _r2)

_r3 = order(['a', 'b', 'c'], team=[], here=['c'])
check('A3 当前场景在场的优先于其余（非主角团场景）',
      _r3 == ['c', 'a', 'b'], _r3)

_r4 = order(['a', 'b', 'kris'], team=['kris'], here=['b'])
check('A4 主角团 > 同场（同场里的非团成员排在其后）',
      _r4 == ['kris', 'b', 'a'], _r4)

_r5 = order(['a', 'b', 'c', 'd'], team=['b'], here=['d'])
check('A5 「尽量全」：输出集合 == 输入集合（一个都不丢）',
      sorted(_r5) == ['a', 'b', 'c', 'd'], _r5)

_r6a = order(['m', 'n', 'o'], team=['o'], here=['n'])
_r6b = order(['o', 'm', 'n'], team=['o'], here=['n'])
check('A6 确定性且与输入顺序无关（打乱输入 → 结果一致）',
      _r6a == _r6b == ['o', 'n', 'm'], '%s / %s' % (_r6a, _r6b))

_r7 = order(['a', None, 3, '', 'b'])
check('A7 坏输入不抛：非字符串/空串一律过滤掉',
      _r7 == ['a', 'b'] and order(None) == [], _r7)

check('A8 ★ 数据面锚点：`_placement.json` 的 party 成员 == 本套件用作真值的名单',
      _PARTY == ['kris', 'susie', 'ralsei'], _PARTY)

# ==================================================================== B
print('')
print('=== B. 接点（源码级 / AST）===')

_top_defs = set()
for _n in _TREE.body:
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _top_defs.add(_n.name)
check('B1 `prewarm_order` 是**模块级**函数（不在类里 —— 纯函数才好单测）',
      'prewarm_order' in _top_defs)

# ★ 判据一律看**剥掉 docstring 后的代码体**（`_code_only_src`）：
#   `_prewarm_should_yield` 的 docstring 里**故意**写着"绝不用 `_ai_delta_sink`"——
#   那是防坑知识，不能因为判据拿原文比对就把它判成"用了"（本项目已踩多次）。
_warm_code = _code_only_src('_prewarm_ai_cache')
check('B2 ★ 接点：`_prewarm_ai_cache` 真调用 `_prewarm_npc_caches`（不是写完就算）',
      '_prewarm_npc_caches(' in _warm_code)

_npc_code = _code_only_src('_prewarm_npc_caches')
check('B3 `_prewarm_npc_caches` 真调用 `prewarm_order`（排序不另写一份）',
      'prewarm_order(' in _npc_code)

_yield_code = _code_only_src('_prewarm_should_yield')
check('B4 ★ 让路判据**不含** `_ai_delta_sink`（负控制：拿它当门会永久为真，D22 的坑）',
      '_ai_delta_sink' not in _yield_code
      and '_ai_inflight' in _yield_code,
      '代码体含 `_ai_inflight`=%s / 含 `_ai_delta_sink`=%s'
      % ('_ai_inflight' in _yield_code, '_ai_delta_sink' in _yield_code))

_cfg = read_json(CONFIG).get('startup') or {}
check('B5 配置项在位且默认关：`startup.prewarm_npc`=false / `prewarm_scope`=all',
      _cfg.get('prewarm_npc') is False and _cfg.get('prewarm_scope') == 'all',
      'prewarm_npc=%r scope=%r' % (_cfg.get('prewarm_npc'), _cfg.get('prewarm_scope')))

check('B6 预发热请求只取 1 个 token（目的是 prefill，不是要内容）',
      'max_tokens=1' in _npc_code)

# ==================================================================== C
print('')
print('=== C. 行为级（喂假 client，不碰 Ollama）===')


class _FakeCli(object):
    """假 Ollama client：记下每次调用 + 记并发峰值 + 可在第 N 次后"让用户开始说话"。"""

    def __init__(self, dui=None, yield_after=None):
        self.calls = []
        self.live = 0
        self.max_live = 0
        self.dui = dui
        self.yield_after = yield_after

    def chat(self, text, system_prompt=None, temperature=None,
             max_tokens=None, timeout=None):
        self.live += 1
        self.max_live = max(self.max_live, self.live)
        self.calls.append({'text': text, 'system': system_prompt,
                           'max_tokens': max_tokens, 'timeout': timeout})
        if self.dui is not None and self.yield_after \
                and len(self.calls) >= self.yield_after:
            self.dui._ai_inflight = True      # 模拟"用户开口了"
        self.live -= 1
        return 'ok'


class _FakeBook(object):
    def __init__(self, team):
        self._team = list(team)

    def rig(self, group_id='party', anchor=None):
        if group_id == 'party' and self._team:
            return types.SimpleNamespace(members=list(self._team))
        return None


def _mk_app(personas, systems, here=(), team=()):
    """造一个"只有预热需要的那几个面"的假 App，方法全部绑生产代码真身。"""
    s = types.SimpleNamespace()
    s.npc_personas = dict(personas)
    s.npc_bodies = dict((h, object()) for h in here)
    dui = types.SimpleNamespace(_ai_inflight=False, _streaming=False)
    s.dialogue_ui = dui
    s._event_speaking = False
    s.npc_placement = _FakeBook(team)
    s._ai_chat_options = lambda: {'temperature': 0.7}
    s.npc_system_prompt = lambda nid: systems.get(nid, '')
    for name in ('_prewarm_npc_caches', '_prewarm_should_yield',
                 '_prewarm_team_ids', 'npc_persona_of', '_npc_life_ids'):
        setattr(s, name, types.MethodType(getattr(M.RalseiPet, name), s))
    return s, dui


# C1 一次一个、system 走唯一出口、只要 1 token
_app, _dui = _mk_app({'a': 'PA', 'b': 'PB'}, {'a': 'SA', 'b': 'SB'})
_cli = _FakeCli()
_n = _app._prewarm_npc_caches(_cli, 10, 'all')
check('C1 每个已装人设的 NPC 各发**恰一次**，system 取自 `npc_system_prompt`，max_tokens=1',
      _n == 2 and len(_cli.calls) == 2
      and sorted(c['system'] for c in _cli.calls) == ['SA', 'SB']
      and all(c['max_tokens'] == 1 for c in _cli.calls),
      'n=%s calls=%d' % (_n, len(_cli.calls)))

check('C2 串行：并发峰值 == 1（纯 CPU 单实例，并发只是排队）',
      _cli.max_live == 1, 'max_live=%d' % _cli.max_live)

# C3 让路（正控制：不是 0 个，而是"发够了就停"）
_app3, _dui3 = _mk_app({'a': 'PA', 'b': 'PB', 'c': 'PC'}, {'a': 'SA', 'b': 'SB', 'c': 'SC'})
_cli3 = _FakeCli(dui=_dui3, yield_after=1)
_n3 = _app3._prewarm_npc_caches(_cli3, 10, 'all')
check('C3 ★ 让路：用户一开口就不再发新的（发了 1 个就停，且确实发过 1 个）',
      _n3 == 1 and len(_cli3.calls) == 1, 'n=%s calls=%d' % (_n3, len(_cli3.calls)))

# C4 没装人设的不预热
_app4, _dui4 = _mk_app({'a': 'PA', 'b': '', 'c': 'PC'}, {'a': 'SA', 'c': 'SC'})
_cli4 = _FakeCli()
_n4 = _app4._prewarm_npc_caches(_cli4, 10, 'all')
check('C4 没装人设的不预热（不许借别人的设定开口），且不计入成功数',
      _n4 == 2 and sorted(c['system'] for c in _cli4.calls) == ['SA', 'SC'],
      'n=%s' % _n4)

# C5 scope=same_scene：只发同场的（正/负控制成对）
_app5, _dui5 = _mk_app({'a': 'PA', 'b': 'PB', 'c': 'PC'},
                       {'a': 'SA', 'b': 'SB', 'c': 'SC'}, here=['b'])
_cli5 = _FakeCli()
_n5 = _app5._prewarm_npc_caches(_cli5, 10, 'same_scene')
check('C5 scope=same_scene 只发当前场景在场的；负控制：不在场的一个都不发',
      _n5 == 1 and [c['system'] for c in _cli5.calls] == ['SB'],
      'n=%s %s' % (_n5, [c['system'] for c in _cli5.calls]))

# C6 主角团在真实桩上真被排到最前（把 A1 从纯函数推到"真被用上"）
_app6, _dui6 = _mk_app({'zed': 'PZ', 'susie': 'PS', 'kris': 'PK', 'ralsei': 'PR'},
                       {'zed': 'SZ', 'susie': 'SS', 'kris': 'SK', 'ralsei': 'SR'},
                       team=['kris', 'susie', 'ralsei'])
_cli6 = _FakeCli()
_app6._prewarm_npc_caches(_cli6, 10, 'all')
check('C6 ★ 主角团在**真桩**上排最前且按队伍序（kris → susie → ralsei）',
      [c['system'] for c in _cli6.calls][:3] == ['SK', 'SS', 'SR'],
      [c['system'] for c in _cli6.calls])

# ==================================================================== 汇总
print('')
print('=' * 68)
print('第七十四轮自检：%d PASS / %d FAIL' % (NCHECK - len(FAILS), len(FAILS)))
for _f in FAILS:
    print('  FAIL: %s' % _f)
print('=' * 68)
sys.exit(1 if FAILS else 0)
