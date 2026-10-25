# -*- coding: utf-8 -*-
u"""第113轮h回归锁：**角色档位**（human / machine）不许静默失效。

用户口径（2026-10-25 逐字）
--------------------------
「事实上，他不是有字体吗，你直接用就好了，还有，**别只顾着三人啊**，这三人当示例
  然后再推进到其他人身上即可，对了，**像是 oneshot 里很多没被制御的机器人不必要要求活人感**」

三条合起来的意思：
  ① 「全大写」这类**视觉**特征交给渲染层，别逼模型输出英文（中文没有大小写）；
  ② 做法要**可批量**，不是逐角色手改；
  ③ 机器人类角色**不需要活人感** —— 但也不等于放开演极端。

本套件守什么
------------
A 段 **档位机制**：`SPEAK_RULES` 的尾巴就是 human 段，machine 段是它的**唯一替换**。
  凡是"两段独立维护"的写法都会漂 —— 所以 A2 断言 human 段是 `SPEAK_RULES` 的**真后缀**，
  A3 断言 human 档返回的是**同一个对象**（不是拼一份看起来一样的），
  A9 是破坏性负控制：把后缀拆掉，machine 档必须**退回 human**而不是产出半套规则。

B 段 **渲染层**：机器档的大写化必须落在"这一条 NPC 消息"上，不能用控件级
  `QFont.setCapitalization`（那会把历史区里别人说的话一起改掉）。
  B1/B3/B4 走 **AST**，不扫字符串 —— 注释里专门写了为什么不用 setCapitalization，
  纯文本扫会自指误报（第96b/97/98 轮同坑；本套件第一版就是这么红的）。

C 段 **覆盖句**：`caps` 登记的每个角色，prompt 里必须带 `CAPS_RULE`
  （"大写是显示效果，你一律说中文"）；**未登记的必须一字不加**（C2 负控制）。
  ★ 判据刻意**不**去人设里数「全部大写」出现了几次 —— 那些是**原作依据**，
    要求删掉才是错的（C3 反向守着）。这里守的是"冲突有没有被就地消解"。

零网络、零 Qt（`dialogue_ui` 只做 AST 解析，不 import）、零外部盘。
"""
import ast
import hashlib
import io
import json
import logging
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, HERE)

PET = os.path.join(ROOT, 'ralsei_pet')
NP = os.path.join(PET, 'modules', 'npc_persona.py')
DUI = os.path.join(PET, 'modules', 'dialogue_ui.py')
KINDS = os.path.join(PET, 'assets', 'npc', '_kinds.json')
IDX = os.path.join(PET, 'assets', 'npc', '_personas.json')
PDIR = os.path.join(PET, 'assets', 'npc', 'persona')
CHECKG = os.path.join(HERE, 'check113g.py')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_persona as NPmod   # noqa: E402  （零依赖：只用 stdlib）

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))
        _failed.append(desc)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def extreme_words():
    """从 `check113g.MUST/EXTREME` 用 AST 取极端词表（不 import，那个文件是模块级直接跑的）。"""
    tree = ast.parse(_read(CHECKG))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == 'EXTREME':
                return tuple(e.value for e in node.value.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return ()


def sha_calc(path):
    with io.open(path, 'rb') as f:
        raw = f.read()
    return {
        'chars': len(raw.decode('utf-8')),
        'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'sha256_lf': hashlib.sha256(
            raw.decode('utf-8').replace('\r\n', '\n').encode('utf-8')).hexdigest(),
    }


#: 索引一次读完，A/C 两段共用。★ 用 `_personas.json` 的 `file` 字段定位，
#: 不假设"文件名 == id + .txt" —— 那个假设今天成立，明天某人改个名就静默失效。
_BY_ID = {e.get('id'): e for e in
          (json.loads(_read(IDX)).get('personas') or []) if isinstance(e, dict)}


def persona_path(nid):
    e = _BY_ID.get(nid) or {}
    fn = os.path.basename(e.get('file') or '') or (nid + '.txt')
    return os.path.join(PDIR, fn)


# ---------------------------------------------------------------- A 档位机制
print('=' * 74)
print('A 档位机制（human 段是 SPEAK_RULES 的尾巴；machine 段是它的唯一替换）')
print('=' * 74)

kind_doc = None
try:
    kind_doc = json.loads(_read(KINDS))
except Exception as e:
    print('  (读 _kinds.json 失败：%r)' % (e,))

check('A1 _kinds.json 在位、可解析、每条都有 why（可审计，不是拍脑袋）',
      isinstance(kind_doc, dict) and isinstance(kind_doc.get('kinds'), dict)
      and all(isinstance(v, str) and v for v in (kind_doc.get('why') or {}).values())
      and set(kind_doc.get('kinds') or {}) <= set(kind_doc.get('why') or {}),
      'kinds=%d why=%d' % (len((kind_doc or {}).get('kinds') or {}),
                           len((kind_doc or {}).get('why') or {}))
      if isinstance(kind_doc, dict) else '')

check('A1b 缺省档位必须是 human（缺省成 machine 会把所有人变成机器人）',
      (kind_doc or {}).get('default') == 'human',
      'default=%r' % ((kind_doc or {}).get('default'),))

# ★★ 这条是本套件的核心：human 段必须是 SPEAK_RULES 的**真后缀**。
#   否则 speak_rules_for() 的 replace 不命中 ⇒ machine 档静默退回 human，
#   而且**没有任何报错** —— 用户只会觉得"机器人怎么还是那个语气"。
check('A2 PERSONA_TONE_HUMAN 是 SPEAK_RULES 的真后缀（防"改了规则忘了同步"）',
      bool(NPmod.PERSONA_TONE_HUMAN)
      and NPmod.SPEAK_RULES.endswith(NPmod.PERSONA_TONE_HUMAN),
      'suffix_len=%d rules_len=%d' % (len(NPmod.PERSONA_TONE_HUMAN),
                                      len(NPmod.SPEAK_RULES)))

check('A3 human 档返回**同一个对象**（不是拼一份"看起来一样"的）',
      NPmod.speak_rules_for('human', 'mike') is NPmod.SPEAK_RULES)

m_ids = sorted((kind_doc or {}).get('kinds') or {})
m_rules = [NPmod.speak_rules_for(None, i) for i in m_ids]
check('A4 machine 档：含机段、**不含**人段（逐个登记角色验）',
      bool(m_ids) and all(NPmod.PERSONA_TONE_MACHINE in r
                          and NPmod.PERSONA_TONE_HUMAN not in r for r in m_rules),
      '登记 %d 个：%s' % (len(m_ids), ','.join(m_ids[:6])))

check('A5 未知 / 空 / 非字符串 npc_id 一律回 human（保守，不误判）',
      all(NPmod.kind_of(x) == 'human' for x in (None, '', 'zzz_not_exist', 123))
      and NPmod.kind_of('mike') == 'human',
      'mike=%s' % NPmod.kind_of('mike'))

_EXTREME = extreme_words()
_bad_m = [w for w in _EXTREME if w in NPmod.PERSONA_TONE_MACHINE]
check('A6 机段里**不含任何极端词**（同 113g 的写法红线：描述违规形态＝给模板）',
      bool(_EXTREME) and not _bad_m,
      '极端词表 %d 个；命中 %r' % (len(_EXTREME), _bad_m))

# 结构性断言：两档 prompt 的差异**只在 tone 段**（长度差恰好等于两段长度差）
_p_h = NPmod.build_system_prompt('X', '人设正文', npc_id='mike', kind='human')
_p_m = NPmod.build_system_prompt('X', '人设正文', npc_id='mike', kind='machine')
check('A7 两档 prompt 只差 tone 段（长度差 == 两段长度差，别处一字不动）',
      len(_p_h) - len(_p_m) == len(NPmod.PERSONA_TONE_HUMAN) - len(NPmod.PERSONA_TONE_MACHINE),
      'human=%d machine=%d' % (len(_p_h), len(_p_m)))

check('A8 负控制：被制御的机器人 `os_silver` 必须仍是 human'
      '（人设原文：造它就是为"像人一样思考、有情感"）',
      NPmod.kind_of('os_silver') == 'human',
      'os_silver=%s' % NPmod.kind_of('os_silver'))

# ★★ 两轴**正交**是本轮的关键结构。反例各占一边，缺一个就说明有人把两轴混成一条：
#   ot_papyrus 是骷髅（human）却全大写；os_kelvin 是机器（machine）却不大写。
#   用 kind 推 caps 或反之，这两条必有一条红。
check('A10 caps 与 kinds 正交（ot_papyrus=human 但大写；os_kelvin=machine 但不大写）',
      NPmod.kind_of('ot_papyrus') == 'human' and NPmod.caps_of('ot_papyrus')
      and NPmod.kind_of('os_kelvin') == 'machine' and not NPmod.caps_of('os_kelvin'),
      'papyrus=%s/%s kelvin=%s/%s' % (NPmod.kind_of('ot_papyrus'),
                                      NPmod.caps_of('ot_papyrus'),
                                      NPmod.kind_of('os_kelvin'),
                                      NPmod.caps_of('os_kelvin')))

_caps_ids = sorted(NPmod.load_caps())
check('A11 caps 表非空、且每个 id 都在索引里有人设文件'
      '（登记了不存在的 id ⇒ 永远静默不生效，还查不出来）',
      bool(_caps_ids) and all(i in _BY_ID and os.path.isfile(persona_path(i))
                              for i in _caps_ids),
      'caps=%d %s' % (len(_caps_ids), ','.join(_caps_ids)))


def _mutated_drift():
    """破坏性负控制：把后缀拆掉后，A2 用的判据必须重新为假，且 machine 档退回 human。

    ★ 这里会**故意**触发一条 `WARNING`（`speak_rules_for` 找不到后缀就告警，这是它的
      正确行为）。但那条日志会混进 stdout，让 G2 的输出比对在本套件上永远 DIFF。
      ⇒ 只在这一次调用期间全局压日志（`logging.disable`，测完恢复），
        不用 `getLogger(...).setLevel()`：logger 名字是 `_pet_logger_name()` 算出来的，
        硬编码名字又是个"改了就静默失效"的坑。
    """
    _old_disable = logging.root.manager.disable
    old_h = NPmod.PERSONA_TONE_HUMAN
    old_r = NPmod.SPEAK_RULES
    try:
        logging.disable(logging.CRITICAL)
        NPmod.PERSONA_TONE_HUMAN = '×这段后缀不存在×'
        drifted = not NPmod.SPEAK_RULES.endswith(NPmod.PERSONA_TONE_HUMAN)
        fell_back = NPmod.speak_rules_for(None, 'hy_axis') == NPmod.SPEAK_RULES
        return drifted and fell_back
    finally:
        NPmod.PERSONA_TONE_HUMAN = old_h
        NPmod.SPEAK_RULES = old_r
        logging.disable(_old_disable)


check('A9 破坏性负控制：拆掉后缀 ⇒ 后缀判据重新报假，且 machine 档**退回 human**'
      '（证明 A2/A3 不是恒真）',
      _mutated_drift())

# ---------------------------------------------------------------- B 渲染层
print()
print('=' * 74)
print('B 渲染层（caps 角色的大写化只作用于这一条 NPC 消息）')
print('=' * 74)

_dui_tree = ast.parse(_read(DUI))
_dui_src = _read(DUI)


def _find_fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


_add = _find_fn(_dui_tree, 'add_dialogue')
_guard = None
if _add is not None:
    for n in ast.walk(_add):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Call):
            f = n.test.func
            if isinstance(f, ast.Name) and f.id == '_caps_on':
                _guard = n
                break

_has_translate = False
if _guard is not None:
    for n in ast.walk(_guard):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'translate'):
            _has_translate = True

check('B1 `add_dialogue` 里有 `if _caps_on(speaker)` 分支，且大写化在分支**内**'
      '（AST 判，不扫字符串）',
      _guard is not None and _has_translate)

check('B2 大写化只做 ASCII 小写→大写（`str.maketrans` 两个参数各 26 个字母）',
      '_ASCII_UPPER = str.maketrans(' in _dui_src
      and _dui_src.count("'abcdefghijklmnopqrstuvwxyz'") >= 1
      and _dui_src.count("'ABCDEFGHIJKLMNOPQRSTUVWXYZ'") >= 1)


def _calls_set_capitalization(tree):
    """源码里有没有**真的调用** `setCapitalization`（AST，不管注释/字符串里提没提）。

    ★ 这条判据第一版写的是 `'setCapitalization' not in _dui_src` —— 而就在同一段代码
      上面的注释里，我为了说明"为什么不用它"写了这个方法名 ⇒ **判据被自己的解释文本
      打红**。纯文本扫"禁某 API"类判据已连踩六次（§108.6），这次改成 AST 结构化。
    """
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == 'setCapitalization':
                hits.append(getattr(n, 'lineno', -1))
    return hits


_cap_calls = _calls_set_capitalization(_dui_tree)
check('B3 负控制：**不许**真的调用控件级 `QFont.setCapitalization`'
      '（那会把历史区里别人说的话一起改掉）—— AST 判调用，不扫文本',
      not _cap_calls, '调用点行号=%r' % (_cap_calls,))

# ★ 破坏性自检：把同一套 AST 判据喂给一段**真的调用**的代码，必须报出来。
#   否则 `not _cap_calls` 恒真也看不出来（第85轮 `{}=={}` 的教训）。
_probe = ast.parse('def f(w):\n    w.setCapitalization(1)\n')
check('B3b 负控制的负控制：同一套 AST 判据对"真调用"必须报出 1 处'
      '（证明 B3 不是恒真）',
      len(_calls_set_capitalization(_probe)) == 1)

check('B4 `_caps_on` 失败时返回 False（json 读不到不能连渲染一起坏）',
      (function := _find_fn(_dui_tree, '_caps_on')) is not None
      and any(isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
              and n.value.value is False for n in ast.walk(function)))

# ---------------------------------------------------------------- C 覆盖句
print()
print('=' * 74)
print('C 覆盖句（caps 登记角色才注入；未登记的必须一字不加）')
print('=' * 74)

_targets = ['hy_guardener', 'hy_axis']      # 用户点名的两个示例
_no_caps = []


def _prompt_of(nid):
    """按该角色**自己的**档位与 caps 登记构造一条 prompt（只放最小人设正文）。"""
    return NPmod.build_system_prompt('X', '人设正文', npc_id=nid,
                                     kind=NPmod.kind_of(nid))


for nid in _caps_ids:
    if NPmod.CAPS_RULE not in _prompt_of(nid):
        _no_caps.append(nid)

check('C1 caps 登记的每个角色，prompt 里都带 `CAPS_RULE`'
      '（"大写是显示效果，你一律说中文" —— 冲突就地消解）',
      bool(_caps_ids) and not _no_caps,
      '缺覆盖=%r' % (_no_caps,))

# ★★ 负控制：没登记的角色**绝不能**收到这句。否则等于对所有人谎称"人设要求你全大写"，
#    而那句话会顺手把人往"机器人腔"推 —— 正是本轮要避免的反向副作用。
_leak = [nid for nid in ('mike', 'os_kelvin', 'rouxls', 'susie', 'zzz_不存在')
         if NPmod.CAPS_RULE in _prompt_of(nid)]
check('C2 负控制：caps **未**登记的角色 prompt 里没有 `CAPS_RULE`'
      '（漏进去＝凭空造设定）',
      not _leak, '误加=%r' % (_leak,))

check('C3 `CAPS_RULE` 自己不含极端词、且明确要求「中文」'
      '（覆盖句不能变成新的失真源：同 113g 的写法红线）',
      bool(NPmod.CAPS_RULE) and '中文' in NPmod.CAPS_RULE
      and not [w for w in _EXTREME if w in NPmod.CAPS_RULE],
      '命中极端词=%r' % ([w for w in _EXTREME if w in NPmod.CAPS_RULE],))

# ★ 反向：原作台词依据**不许**被删。上一条判据曾被写成"人设里不许再出现『全部大写』"，
#   那会逼着后续几轮去删人设里的原作依据（英文台词是语气凭据），方向是错的。
_keep = []
for nid in _targets:
    p = persona_path(nid)
    if os.path.isfile(p) and '经典台词' in _read(p):
        _keep.append(nid)

check('C4 负控制：「经典台词」仍在这两份示例人设里'
      '（只改"用哪种语言输出"，不许把原作台词依据删掉）',
      len(_keep) == len(_targets), '保留=%r' % (_keep,))

_sync_bad = []
for nid in sorted(set(_targets) | set(_caps_ids)):
    p = persona_path(nid)
    if not os.path.isfile(p):
        _sync_bad.append(nid + '(缺文件)')
        continue
    got = sha_calc(p)
    e = _BY_ID.get(nid) or {}
    if any(got[k] != e.get(k) for k in ('chars', 'bytes', 'sha256', 'sha256_lf')):
        _sync_bad.append(nid)

check('C5 索引 `_personas.json` 的 chars/bytes/sha256/sha256_lf 与磁盘同源（两层登记第一层）',
      not _sync_bad, '不同步：%r' % (_sync_bad,))

# ---------------------------------------------------------------- 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
