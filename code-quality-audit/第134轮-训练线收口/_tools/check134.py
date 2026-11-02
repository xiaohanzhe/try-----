# -*- coding: utf-8 -*-
"""第134轮回归锁：**训练线**（113 轮那批 NPC 训练产物）到产品的整条链，不许"登记了没人读"。

## 为什么单开一轮

第113轮开始，训练线陆续落了四类产物：人设（76 份）、训练纠正 `patch`（59 人）、
关系卡 `relation`（58 人）、关系演化 `evolution`（44 人）。它们都由
`modules/npc_persona.py::build_system_prompt` 拼进 system prompt。

**问题是：这条接线没有任何判据守着。** 现有 `check113` 的 C2 只用一条**合成** patch
验证"传进去就会进 prompt"；如果哪天 `main.py` 的
`patch=npc_persona_mod.training_patch(npc_id)` 被顺手删掉，`check113` 照样全绿 ——
而这就是本项目反复踩的那一类坑（113r 的 `bonds.familiarity` 不存在、
120 轮的 `room.Backgrounds` 恒空、101 轮的"登记了没人读"）。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 数据面守恒：96 条目 / 76 人设 / 18 内置台词 / 1 沉默，四个数**从磁盘数出来**并与
  `_index.json.counts` 自己对账（口径写清楚，不靠印象）
B 端到端（**真跑** `build_system_prompt`）：59 / 58 / 44 三类卡逐字进 prompt；
  没有卡的角色**一个块标题都不许出现**（成对，防空集恒真）
C 接线（AST）：`main.npc_system_prompt` 真把三者作为关键字实参传下去，
  且值分别来自那三个函数；**破坏性负控制**：删掉 `patch=` 那一行后同一判据必须报缺
D 空人设短路：`persona=''` ⇒ 返回 `''`（这是 plain/沉默角色"拒绝对话"的依据）
E `Twinkly` 结案：把"为什么不接"的**数据事实**钉住（目标卡是两个人合一）
F 自检：无恒真判据 / 无 BOM / 零外部盘

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（一律调产品函数，
不复制模板字符串）；不把"训练有效果"写成判据（那是真机问题，见 §134 报告）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
ASSETS = os.path.join(PET, 'assets', 'npc')
EV = os.path.join(ROUND, '_evidence')
MAIN_PY = os.path.join(PET, 'src', 'main.py')

if PET not in sys.path:
    sys.path.insert(0, PET)
from modules import npc_persona as NP                             # noqa: E402

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _jload(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


REG = _jload(os.path.join(ASSETS, '_registry.json'))
IDX = _jload(os.path.join(ASSETS, '_training', '_index.json'))
SEEK = _jload(os.path.join(ASSETS, '_seek.json'))
NPCS = REG['npcs']
BY_ID = {n['id']: n for n in NPCS}
PATCH = IDX.get('patches') or {}
PERSONAS = NP.load_personas()          # 真源：产品自己的装载函数
TREE = ast.parse(_read(MAIN_PY))       # 接线判据要 AST，C/B 两段共用


def _func(tree, name):
    """按名字取顶层/类内函数（`ast.walk`，不看 `tree.body` —— 类方法会漏，§133 E3）。"""
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None

# =============================================== A 数据面
head(u'A. 数据面守恒（四个数从磁盘数出来，并与 _index.counts 对账）')

check(u'A1 registry 条目 96', len(NPCS) == 96, u'%d' % len(NPCS))
_main = [n for n in NPCS if n['tier'] == 'main']
_plain = [n for n in NPCS if n['tier'] == 'plain']
check(u'A2 档位 main 78 / plain 18',
      (len(_main), len(_plain)) == (78, 18),
      u'%d / %d' % (len(_main), len(_plain)))

# persona 字段三态：普通 NPC 走 persona/xx.txt；ralsei 走 ../ralsei_persona.md；其余 None
_tri = {'file': [], 'ralsei': [], 'none': []}
for n in NPCS:
    p = n.get('persona')
    if p is None:
        _tri['none'].append(n['id'])
    elif p.startswith('../'):
        _tri['ralsei'].append(n['id'])
    else:
        _tri['file'].append(n['id'])
check(u'A3 persona 三态：76 份文件 + 1 个主宠外链 + 19 个 None',
      (len(_tri['file']), len(_tri['ralsei']), len(_tri['none'])) == (76, 1, 19),
      u"%d / %d / %d" % (len(_tri['file']), len(_tri['ralsei']), len(_tri['none'])))
check(u'A3b 19 个 None = 18 plain + knight（knight 是"沉默"设计，notes 写明）',
      sorted(_tri['none']) == sorted([n['id'] for n in _plain] + ['knight'])
      and '沉默' in (BY_ID['knight'].get('notes') or ''),
      u'差集=%s' % (set(_tri['none']) ^ set([n['id'] for n in _plain] + ['knight'])))

_cdir = os.path.join(ASSETS, '_training', 'cards')
_cards = sorted(f[:-5] for f in os.listdir(_cdir) if f.endswith('.json'))
check(u'A4 训练卡 96 张，与 registry 的 id 一一对应（无多无少）',
      sorted(_cards) == sorted(BY_ID), u'%d 张' % len(_cards))

check(u'A5 `patch` 59 人，且全部是 main 档、都是非空字符串',
      len(PATCH) == 59
      and all(BY_ID.get(k, {}).get('tier') == 'main' for k in PATCH)
      and all(isinstance(v, str) and v.strip() for v in PATCH.values()),
      u'%d 人' % len(PATCH))

_cnt = IDX.get('counts') or {}
check(u'A6 `_index.counts` 与实测四个数一致（96 / 77 / 18 / 1）',
      (_cnt.get('total'), _cnt.get('persona'), _cnt.get('canned'), _cnt.get('gap'))
      == (96, 77, 18, 1),
      u'%s' % json.dumps(_cnt, ensure_ascii=False))
check(u'A6b counts.persona=77 = 76 份文件 + ralsei（两种口径各自自洽，别混算）',
      _cnt.get('persona') == len(_tri['file']) + len(_tri['ralsei']))
check(u'A7 gaps 列表恰为 [knight]，与 counts.gap 自洽',
      (IDX.get('gaps') or []) == ['knight'] and _cnt.get('gap') == 1)

check(u'A8 `_seek`：72 人有权重、24 条未解（记录分母，不判好坏）',
      len(SEEK.get('seek') or {}) == 72
      and len(SEEK.get('unresolved_names') or {}) == 24,
      u'%d / %d' % (len(SEEK.get('seek') or {}),
                    len(SEEK.get('unresolved_names') or {})))

# =============================================== B 端到端（真跑产品函数）
head(u'B. 端到端：三类卡真的逐字进了 system prompt（真跑 build_system_prompt）')

REL = {i: NP.relation_patch(i) for i in BY_ID}
EVO = {i: NP.evolution_patch(i) for i in BY_ID}
check(u'B0 三类卡覆盖数：patch 59 / relation 58 / evolution 44（分母非空）',
      (len(PATCH), sum(1 for v in REL.values() if v),
       sum(1 for v in EVO.values() if v)) == (59, 58, 44),
      u'%d / %d / %d' % (len(PATCH), sum(1 for v in REL.values() if v),
                        sum(1 for v in EVO.values() if v)))

# ---------------------------------------------------------------- 分母：谁真能进这条链
#
# ★★ `ralsei` 是「主宠外链」态，**本轮按产品事实登记为已知未接线**（不是夹具缺陷）。
#   数据侧：他有 patch（160 字）/ relation（84 字），evolution 为 0；
#   链侧：`load_personas()` 里没有他 —— 它读 `_personas.json`（76 份游戏 NPC 人设），
#         主宠的真源是 `assets/ralsei_persona.md`；
#   调用侧：`chat_with_ai` 把 `speaker == 'ralsei'` 直接判成老路径 ⇒
#         `npc_system_prompt()` **永不服务他**，`training_patch('ralsei')` 零读取。
#   ⇒ 下面每条"进 prompt"的分母一律取 `PERSONAS`（能进链的那 76 个），
#     ralsei 单独由 B1b（数据完好）/ B1c + B1c2（结构成因）/ D3（不在名单里）三条钉住。
#     谁哪天把他接上了，B1c 会红 ⇒ 逼人回来复审这几条，而不是悄悄多读一条。
#
# ★★★ 第137轮更新（缺口的**下半句**）：那个缺口已经接上了，但**不是**走 `build_system_prompt()` ——
#   而是 `main._with_ralsei_patch()`（对话 + 预热各一处，见 `check137`）。
#   所以本节下面几条**依然成立**（NPC 链的分母没变、ralsei 仍不在 `PATCH_IN`、
#   `npc_system_prompt()` 仍不服务他），但"`training_patch('ralsei')` 零读取"这句话
#   **已经过时**，别照着它再做一次"补接线"。
#   本判据的 B1c2 会因为源码里多出两个 `'ralsei'` 字面量而改变回显计数（17 → 19），
#   那是**计数回显**，不是行为变化；真正的接线由 `check137 D1/D2/D3` 守。
PATCH_IN = [nid for nid in PATCH if nid in PERSONAS]
REL_IN = dict((k, v) for k, v in REL.items() if k in PERSONAS and v)
EVO_IN = dict((k, v) for k, v in EVO.items() if k in PERSONAS and v)
_outer = [nid for nid in _tri['ralsei']]
check(u'B0b 进链分母：patch 58/59、relation 57/58、evolution 44/44 进链（差的都属主宠外链）',
      (len(PATCH_IN), len(REL_IN), len(EVO_IN)) == (58, 57, 44)
      and len(_outer) == 1 and _outer[0] not in PERSONAS
      and sorted(set(PATCH) - set(PATCH_IN)) == _outer
      and sorted(set(k for k, v in REL.items() if v) - set(REL_IN)) == _outer,
      u'%d / %d / %d，差=%r' % (len(PATCH_IN), len(REL_IN), len(EVO_IN),
                               set(PATCH) - set(PATCH_IN)))

_ok_p = 0
_bad = []
for nid in PATCH_IN:
    txt = PATCH[nid]
    pr = NP.build_system_prompt(BY_ID[nid].get('name') or nid, PERSONAS.get(nid, ''),
                                [], nid, '', patch=txt,
                                relation=REL.get(nid, ''), evolution=EVO.get(nid, ''))
    if pr and txt.strip() in pr:
        _ok_p += 1
    else:
        _bad.append(nid)
check(u'B1 进链的 %d 条 patch 全部逐字进 prompt' % len(PATCH_IN),
      _ok_p == len(PATCH_IN) and _ok_p > 0,
      u'%d/%d 缺=%s' % (_ok_p, len(PATCH_IN), _bad[:4]))

_bad_r = [nid for nid, txt in REL_IN.items()
          if (txt.strip() not in NP.build_system_prompt(
              BY_ID[nid].get('name') or nid, PERSONAS.get(nid, ''), [], nid, '',
              patch=PATCH.get(nid, ''), relation=txt, evolution=EVO.get(nid, '')))]
check(u'B2 进链的 %d 条 relation 全部逐字进 prompt' % len(REL_IN),
      not _bad_r and len(REL_IN) > 0, u'缺 %d 条' % len(_bad_r))

_bad_e = [nid for nid, txt in EVO_IN.items()
          if (txt.strip() not in NP.build_system_prompt(
              BY_ID[nid].get('name') or nid, PERSONAS.get(nid, ''), [], nid, '',
              patch=PATCH.get(nid, ''), relation=REL.get(nid, ''), evolution=txt))]
check(u'B3 进链的 %d 条 evolution 全部逐字进 prompt' % len(EVO_IN),
      not _bad_e and len(EVO_IN) > 0, u'缺 %d 条' % len(_bad_e))

# ---- ralsei 那条到底卡在哪：数据没问题，是调用方不服务他
_rp = _read(os.path.join(PET, 'assets', 'ralsei_persona.md'))
_rp_prompt = NP.build_system_prompt(BY_ID['ralsei'].get('name') or 'Ralsei', _rp,
                                    [], 'ralsei', '', patch=PATCH['ralsei'],
                                    relation=REL.get('ralsei', ''))
check(u'B1b ralsei 的卡本身没问题：拿他主宠人设去调，patch 逐字进 prompt（缺口在调用方）',
      bool(_rp_prompt) and PATCH['ralsei'].strip() in _rp_prompt,
      u'prompt %d 字' % len(_rp_prompt))


def _excludes_ralsei(fn):
    """函数体里是否把 `'ralsei'` 排出 NPC 路径。

    认三种等价写法（`!=` 两侧任一 / `not in (...)`）；写成"只认我脑子里那一种"
    正是本项目连续四轮踩的坑（§130~§133）。
    """
    if fn is None:
        return False
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Compare) and len(n.comparators) == 1):
            continue
        l, r, op = n.left, n.comparators[0], n.ops[0]
        lit_l = l.value if isinstance(l, ast.Constant) else None
        lit_r = r.value if isinstance(r, ast.Constant) else None
        if isinstance(op, (ast.NotEq, ast.IsNot)) and 'ralsei' in (lit_l, lit_r):
            return True
        if isinstance(op, ast.NotIn) and isinstance(r, ast.Tuple):
            if 'ralsei' in [e.value for e in r.elts if isinstance(e, ast.Constant)]:
                return True
    return False


_CA = _func(TREE, 'chat_with_ai')
check(u'B1c 结构成因：`chat_with_ai` 里确有"speaker == ralsei ⇒ 不走 NPC 路径"那一步',
      _excludes_ralsei(_CA), u'found=%s' % _excludes_ralsei(_CA))

# ★ 破坏性负控制：把 `'ralsei'` 换成别的字面量，B1c 必须报红（证明它有鉴别力）
_src_b = _read(MAIN_PY)
_n_mut = _src_b.count(u"'ralsei'")
_neg = None
if _n_mut:
    _mut_b = _src_b.replace(u"'ralsei'", u"'ralsei__x'")
    _t2 = ast.parse(_mut_b)
    _neg = _excludes_ralsei(_func(_t2, 'chat_with_ai'))
# ★★ 第138轮：extra **不再回显 `'ralsei'` 的出现次数**。
#   旧写法 `u'原文出现 %d 次' % _n_mut` 在**第137轮接上主宠 patch 时变红**
#   （17 → 19，因为新加的两个调用点各带一个字面量）—— 那是计数回显，不是行为变化。
#   `_n_mut > 0` 作为分母闸**留在条件里**，只是不打印具体数字。
check(u'B1c2 负控制：把 `\'ralsei\'` 全部改掉后 B1c 必须报红（用的是真实变异，不是空跑）',
      _n_mut > 0 and _neg is False, u'变异后 B1c=%r（必须 False）' % (_neg,))


# 成对负控制：**没有**卡的角色，块标题一个都不许出现（否则就是凭空造设定）
_NO_PATCH = [nid for nid in PERSONAS if nid not in PATCH]
_leak = [nid for nid in _NO_PATCH
         if u'【这个角色容易犯的毛病' in NP.build_system_prompt(
             BY_ID[nid].get('name') or nid, PERSONAS.get(nid, ''), [], nid, '')]
check(u'B4 无 patch 的 %d 个角色：prompt 里没有训练纠正块（负控制，分母非空）'
      % len(_NO_PATCH),
      bool(_NO_PATCH) and not _leak, u'漏进 %d 个：%s' % (len(_leak), _leak[:4]))
# ★ 分母必须是"有卡的那 57 个"（`REL_IN`），不能是 `REL` —— 后者是**全 96 个 id** 的字典，
#   `nid not in REL` 恒假 ⇒ `_other_leak` 恒空 ⇒ 这条判据就成了恒真摆设（自查时抓到，
#   与 §125 那类"看着在守其实没守"同型）。
_NO_REL = [nid for nid in PERSONAS if nid not in REL_IN]
_other_leak = [nid for nid in _NO_REL
               if u'【你和其他人的关系' in NP.build_system_prompt(
                   BY_ID[nid].get('name') or nid, PERSONAS.get(nid, ''), [], nid, '')]
check(u'B5 无 relation 的 %d 个角色：prompt 里没有关系块（同上，分母非空）'
      % len(_NO_REL),
      bool(_NO_REL) and not _other_leak, u'漏进 %d 个：%s' % (len(_other_leak), _other_leak[:4]))

# =============================================== C 接线（AST）
head(u'C. 接线：`main.npc_system_prompt` 真的把三者传下去了吗（AST + 破坏性负控制）')


def _build_call(fn):
    """在给定函数体里找 `build_system_prompt(...)` 的调用节点。"""
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else '')
            if nm == 'build_system_prompt':
                return n
    return None


def _kw_names(call):
    return [k.arg for k in (call.keywords or []) if k.arg]


def _kw_value_call(call, name):
    for k in (call.keywords or []):
        if k.arg == name and isinstance(k.value, ast.Call):
            f = k.value.func
            return f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else '')
    return None


_host = _func(TREE, 'npc_system_prompt')
check(u'C0 `main.npc_system_prompt` 真在', _host is not None)
_call = _build_call(_host) if _host is not None else None
check(u'C1 它内部真的调用了 build_system_prompt', _call is not None)

_kws = _kw_names(_call) if _call is not None else []
check(u'C2 三个关键字实参都在（patch / relation / evolution）',
      set(['patch', 'relation', 'evolution']) <= set(_kws), u'实际=%r' % (_kws,))
check(u'C2b 值分别来自 training_patch / relation_patch / evolution_patch',
      (_kw_value_call(_call, 'patch'),
       _kw_value_call(_call, 'relation'),
       _kw_value_call(_call, 'evolution')) ==
      ('training_patch', 'relation_patch', 'evolution_patch'),
      u'%s / %s / %s' % (_kw_value_call(_call, 'patch'),
                         _kw_value_call(_call, 'relation'),
                         _kw_value_call(_call, 'evolution')))

# ★ 破坏性负控制：把 `patch=...` 那一行删掉，同一条判据必须报缺
_src = _read(MAIN_PY)
_lines = _src.splitlines(True)
_dropped = [ln for ln in _lines if 'patch=npc_persona_mod.training_patch(' in ln]
check(u'C3 变异前：能定位到要删的那一行（否则负控制是空跑）', len(_dropped) == 1,
      u'%d 行' % len(_dropped))
if len(_dropped) == 1:
    _mut = ast.parse(''.join(ln for ln in _lines if ln is not _dropped[0]))
    _h2 = _func(_mut, 'npc_system_prompt')
    _c2 = _build_call(_h2) if _h2 is not None else None
    _kws2 = _kw_names(_c2) if _c2 is not None else []
    check(u'C3b 删掉 patch= 之后，C2 那条判据必须报缺（证明它不是恒真）',
          'patch' not in _kws2, u'变异后=%r' % (_kws2,))
else:
    check(u'C3b 删掉 patch= 之后，C2 那条判据必须报缺（证明它不是恒真）', False, u'无法变异')

# =============================================== D 空人设短路
head(u'D. 空人设 ⇒ 返回空串（plain/沉默角色"拒绝对话"的依据）')

_blank = NP.build_system_prompt('测试角色', '', [], 'asgore', '',
                               patch=PATCH.get('asgore', ''))
check(u'D1 persona 为空 ⇒ 返回 ""（连 patch 也不拼）', _blank == '', repr(_blank))
_pos = NP.build_system_prompt('测试角色', u'你是一个测试角色。', [], 'asgore', '',
                             patch=PATCH.get('asgore', ''))
check(u'D1n 正控制：同一调用给人设就非空且含 patch（证明 D1 不是"永远返回空"）',
      bool(_pos) and PATCH['asgore'].strip() in _pos)
check(u'D2 `load_personas()` 恰好 76 份，且不含 plain 18 与 knight',
      len(PERSONAS) == 76
      and not any(n['id'] in PERSONAS for n in _plain)
      and 'knight' not in PERSONAS,
      u'%d 份' % len(PERSONAS))
check(u'D3 反向自证：ralsei 也不在这份表里（他走主宠链，不该被当成普通 NPC）',
      'ralsei' not in PERSONAS)

# =============================================== E Twinkly 结案
head(u'E. `Twinkly` 为什么不接（把数据事实钉住，避免下一轮再翻案）')

_un = SEEK.get('unresolved_names') or {}
_tw = [(k, v) for k, v in _un.items() if any('twink' in str(x).lower() for x in v)]
check(u'E1 未解名单里 `Twinkly` 只出现 1 次（ot_asgore 提的）',
      len(_tw) == 1 and _tw[0][0] == 'ot_asgore', u'%r' % (_tw,))
_tgt = BY_ID.get('ot_asriel_twinkly') or {}
_name = _tgt.get('name') or ''
check(u'E2 目标卡是**两个人合一**（登记名同时含 Asriel 与 Twinkly）⇒ 接它等于把两人当一人',
      ('Asriel' in _name) and ('Twinkly' in _name), _name)
check(u'E3 而且它在 `seek` 里已经有 5 条出边（不是"没人用"的孤儿卡）',
      len((SEEK.get('seek') or {}).get('ot_asriel_twinkly') or {}) == 5,
      u'%d 条' % len((SEEK.get('seek') or {}).get('ot_asriel_twinkly') or {}))

# =============================================== F 自检
head(u'F. 本套件自检')

_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'F2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'F3 零外部盘（读的文件全在仓库内）',
      all(os.path.abspath(p).startswith(ROOT + os.sep)
          for p in (MAIN_PY, ASSETS, os.path.join(PET, 'assets', 'npc', '_seek.json'))),
      ROOT)

# =============================================== 落盘证据
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'registry': len(NPCS), 'main': len(_main), 'plain': len(_plain),
       'persona_files': len(_tri['file']), 'persona_none': len(_tri['none']),
       'cards': len(_cards), 'patch': len(PATCH),
       'relation': sum(1 for v in REL.values() if v),
       'evolution': sum(1 for v in EVO.values() if v),
       'seek': len(SEEK.get('seek') or {}),
       'unresolved': len(_un),
       'patch_in_prompt': _ok_p,
       'personas_loaded': len(PERSONAS)}
with io.open(os.path.join(EV, 'train134.json'), 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check134：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
