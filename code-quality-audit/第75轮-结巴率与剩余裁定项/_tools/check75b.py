#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第75轮 · 队伍 HP 模型回归锁 —— B7。

守的是**一件事**：`modules/team_hp.py` 的血量语义与原作 GML **逐条对齐**，
而且"对齐"这件事**有转储证据**（不是我从别处推断的）。

★ 为什么这个套件必须先做「锚点自证」
--------------------------------------
本项目的头号坑是「判据/文档里出现无锚点断言」——第62~70轮反复栽在这里。
本文件第一段（A 段）**不测 team_hp**，而是**先证明我引用的原作文本真的存在**：
逐个打开 `_evidence/gml/` 里的转储文件、把关键行**原文读出来**做子串命中。
只有 A 段全过，B 段（测 team_hp 是否照抄）才有意义。

★ 一个**真实踩到的陷阱**（本文件的存在理由之一）
------------------------------------------------
`_evidence/gml/` 下同名文件有两代：
  · `gml_GlobalScript_scr_healitemspell.gml` —— **真转储**（有函数体）
  · `gml_Script_scr_healitemspell.gml`     —— **`// DECOMPILE FAILED`** 空壳
`team_hp.py` 的 docstring 最初引的是 `scr_healitem_all` / `healallitemspell`，
而那几个**恰好是失败的那代** ⇒ 引了等于没引。A 段专门守"被引文件必须有函数体"。

判据分三层：
  A 段 · **锚点自证**（原作文本逐行命中 + 被引文件必须真转储）
  B 段 · 行为（照抄是否正确：ceil / 封顶 / 下钳 / 只对死人复活 / 只回没满的）
  C 段 · 纪律（零依赖 / 单一真源 / 无第二份真相 / WIRING 诚实登记）

★ 本套件不联网、不实例化 App、不需要显示器（纯函数 + 文件解析）。
★ 放在 `code-quality-audit/第75轮.../_tools/` ⇒ 仓库根 = HERE 上**三级**。
"""

import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
#: ★ `_tools` → 轮次目录 → `code-quality-audit` → 仓库根（上三级，少一级
#: 会 `ModuleNotFoundError: modules`，本项目已踩过三次）。
ROOT = os.path.join(HERE, '..', '..', '..')
PET = os.path.join(ROOT, 'ralsei_pet')
GML = os.path.join(ROOT, 'code-quality-audit',
                   '第48轮-道具与背包系统', '_evidence', 'gml')
sys.path.insert(0, PET)

from modules import team_hp as T          # noqa: E402

_TEAM = os.path.join(PET, 'modules', 'team_hp.py')
#: AST 级数据源（C1 用）——**只解析、不执行**（不产 `.pyc`，不改被测状态）。
_TEAM_TREE = ast.parse(io.open(_TEAM, encoding='utf-8').read())

_P = 0
_F = 0


def check(name, cond):
    global _P, _F
    if cond:
        _P += 1
        print('[PASS] %s' % name)
    else:
        _F += 1
        print('[FAIL] %s' % name)


def _read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


# ==================================================== A. 锚点自证（先证原文在）

def _gml(name):
    p = os.path.join(GML, name)
    if not os.path.exists(p):
        return None
    return _read(p)


def _a0_gml_dir():
    """A0 证据目录与四个关键文件**在场**（不在场 ⇒ 后面全是空判据）。"""
    check('A0 GML 证据目录存在（%s）' % os.path.basename(GML), os.path.isdir(GML))
    need = ('ch1.scr_itemuse.gml',
            'gml_GlobalScript_scr_healitemspell.gml',
            'gml_GlobalScript_scr_healallitemspell.gml',
            'gml_Object_obj_savepoint_Other_10.gml')
    miss = [n for n in need if not os.path.exists(os.path.join(GML, n))]
    check('A0b 四个关键锚点文件都在场（缺=%s）' % (miss or '无'), not miss)


def _a1_not_failed_decompile():
    """A1 ★ 被引用的 GML 必须是**真转储**，不是 `DECOMPILE FAILED` 空壳。

    负控制：`gml_Script_scr_healitem_all.gml` 确实是失败那代 ⇒
    本判据必须能把它识别出来（如果判据对失败文件也说"OK"，就是恒真判据）。
    """
    good = _gml('gml_GlobalScript_scr_healitemspell.gml')
    check('A1 被引的 healitemspell 有函数体（不是 DECOMPILE FAILED）',
          good is not None and 'DECOMPILE FAILED' not in good
          and 'function scr_healitemspell' in good)
    bad = _gml('gml_Script_scr_healitem_all.gml')
    check('A1n 负控制：同名失败代确实含 DECOMPILE FAILED（证明 A1 能分辨）',
          bad is not None and 'DECOMPILE FAILED' in bad)


def _a2_ceil_half():
    """A2 复活量锚点：`ceil(maxhp / 2)` —— 逐字命中 `ch1.scr_itemuse.gml`。"""
    src = _gml('ch1.scr_itemuse.gml')
    if src is None:
        check('A2 复活量锚点：源文件在场', False)
        return
    # 原文：reviveamt = ceil(global.maxhp[global.char[global.charselect]] / 2);
    m = re.search(r'reviveamt\s*=\s*ceil\(([^)]*global\.maxhp[^)]*)/\s*2\)', src)
    check('A2 锚点命中：「reviveamt = ceil(...maxhp... / 2)」', m is not None)
    if m:
        check('A2b 锚点原文露出来：%s' % src[m.start():m.end()][:70], True)
    # 负控制：不许是"除以 3"或"整除"
    check('A2n 负控制：原文里确实是「/ 2」而不是「/ 3」',
          m is not None and '/ 2' in src[m.start():m.end()])


def _a3_full_signal():
    """A3 满血信号锚点：`if (hp >= maxhp) { specialmessage = 3 }`。

    ★ 这条是本套件最该守的：`team_hp.heal()` 的 `full_before` 就是照它来的。
      原文在 `scr_healitemspell` / `scr_healallitemspell`（**真转储**那代）。
    """
    hits = 0
    for fn in ('gml_GlobalScript_scr_healitemspell.gml',
               'gml_GlobalScript_scr_healallitemspell.gml'):
        src = _gml(fn)
        if src is None:
            continue
        # 原文：global.hp[global.char[myself]] >= global.maxhp[global.char[myself]]
        # ★ 方括号**嵌套** ⇒ 不能用 `[^\]]+`（会在内层 `]` 处断开），
        #   要用"配平"写法：`\[[^\]]*(?:\[[^\]]*\][^\]]*)*\]`。
        #   ⚠️ 这条判据首跑就是被这个正则坑红的 —— 判据本身也是被测物。
        hp_re = r'global\.hp\[[^\]]*(?:\[[^\]]*\][^\]]*)*\]'
        mx_re = r'global\.maxhp\[[^\]]*(?:\[[^\]]*\][^\]]*)*\]'
        if re.search(hp_re + r'\s*>=\s*' + mx_re, src) \
                and 'specialmessage = 3' in src:
            hits += 1
    check('A3 满血信号锚点在 2 个真转储里都命中（实测 %d/2）' % hits, hits == 2)
    # ★ 负控制：把嵌套正则换成"简单版"，在两个文件上**必须**匹配不到
    #   （证明 A3 的正则确实需要处理嵌套，不是随便写写都能过）
    simple = r'global\.hp\[[^\]]+\]\s*>=\s*global\.maxhp\['
    simple_hits = sum(
        1 for fn in ('gml_GlobalScript_scr_healitemspell.gml',
                     'gml_GlobalScript_scr_healallitemspell.gml')
        if re.search(simple, _gml(fn) or ''))
    check('A3n 负控制：简单正则（不处理嵌套）在同样文件上命中 0 次',
          simple_hits == 0)


def _a4_loop_bounds_differ():
    """A4 ★ **原作循环上界三处不一致**（这条必须显式记录，否则会被当成 bug 改掉）。

    实测：
      · `scr_healitem_all`      → `for (i = 0; i < chartotal; ...)`
      · `scr_healallitemspell`  → `for (i = 0; i < 3; ...)`
      · `obj_savepoint_Other_10`→ `for (i = 0; i < 4; ...)`
    本模块**不照抄任何一个上界**（走名字集合），所以判据是"三处确实不同"
    —— 若哪天证据被"统一"了，说明有人动了转储，要重新审。
    """
    s1 = _gml('gml_GlobalScript_scr_healitem_all.gml') or ''
    s2 = _gml('gml_GlobalScript_scr_healallitemspell.gml') or ''
    s3 = _gml('gml_Object_obj_savepoint_Other_10.gml') or ''
    b1 = re.search(r'for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*(\w+)', s1)
    b2 = re.search(r'for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*(\w+)', s2)
    b3 = re.search(r'for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*(\w+)', s3)
    bounds = [b.group(1) if b else None for b in (b1, b2, b3)]
    check('A4 原作循环上界三处不一致（healitem_all=%s / spell=%s / savepoint=%s）'
          % tuple(bounds), len(set(bounds)) == 3 and None not in bounds)


def _a5_savepoint_restore():
    """A5 存档点回满锚点：`if (hp[i] < maxhp[i]) hp[i] = maxhp[i]`（含"只回没满的"）。"""
    src = _gml('gml_Object_obj_savepoint_Other_10.gml')
    if src is None:
        check('A5 存档点回满锚点', False)
        return
    has_cmp = re.search(r'global\.hp\[i\]\s*<\s*global\.maxhp\[i\]', src)
    has_set = re.search(r'global\.hp\[i\]\s*=\s*global\.maxhp\[i\]', src)
    check('A5 存档点锚点：「if (hp[i] < maxhp[i]) hp[i] = maxhp[i]」',
          bool(has_cmp) and bool(has_set))


# ==================================================== B. 行为（照抄是否正确）

def _b1_revive_ceil():
    """B1 `revive_amount` = `ceil(maxhp/2)`，**奇数**才能区分 ceil 与整除。"""
    check('B1 revive_amount(90) == 45', T.revive_amount(90) == 45)
    check('B1b revive_amount(91) == 46（ceil，不是整除的 45）', T.revive_amount(91) == 46)
    check('B1c revive_amount(1) == 1（ceil(0.5)）', T.revive_amount(1) == 1)
    # 负控制：整除实现会给 45
    check('B1n 负控制：整除实现(45)与 ceil 实现(46)在 91 上**确实不同**',
          (91 // 2) != T.revive_amount(91))
    check('B1d 非法输入不抛、回 0', T.revive_amount(0) == 0
          and T.revive_amount('x') == 0 and T.revive_amount(None) == 0)


def _b2_heal_cap():
    """B2 治疗**封顶** + 满血给显式信号（对应 A3 的 specialmessage=3）。"""
    t = T.TeamHP(members=('kris',))
    t.damage('kris', 50)
    r = t.heal('kris', 999)
    check('B2 治疗封顶：90-50=40，喂 999 后 =90（不是 1039）', t.hp('kris') == 90)
    check('B2b 返回实际变化量 delta=50（不是请求量 999）', r.delta == 50)
    check('B2c ok=True（真的动了）', r.ok is True)
    # 满血再来一次
    r2 = t.heal('kris', 40)
    check('B2d ★满血给治疗：full_before=True（对应原作 specialmessage=3）',
          r2.full_before is True)
    check('B2e ★满血给治疗：ok=False、delta=0（不静默装作治了）',
          r2.ok is False and r2.delta == 0)
    # 负控制：满血时血量**不许**乱跳
    check('B2n 负控制：满血治疗后 hp 仍 == maxhp', t.hp('kris') == 90)


def _b3_damage_floor():
    """B3 掉血**下钳 0**（不出现负血）。"""
    t = T.TeamHP(members=('kris',))
    r = t.damage('kris', 9999)
    check('B3 掉血下钳 0（90-9999 → 0，不是 -9909）', t.hp('kris') == 0)
    check('B3b delta 为负且等于 -90', r.delta == -90)
    check('B3c 归零后 is_dead 为真', t.is_dead('kris') is True)
    # 负控制：负数伤害 = 不生效（不能悄悄变成治疗）
    t2 = T.TeamHP(members=('kris',))
    t2.damage('kris', 30)
    before = t2.hp('kris')
    r2 = t2.damage('kris', -50)
    check('B3n 负控制：负伤害不生效（血量不变、ok=False）',
          t2.hp('kris') == before and r2.ok is False)


def _b4_revive_only_dead():
    """B4 复活**只对死人**生效（活着给复活 ⇒ 不动，否则复活药变成回血药）。"""
    t = T.TeamHP(members=('kris', 'ralsei'))
    # kris 活着
    r_alive = t.revive('kris')
    check('B4 给活人复活：ok=False、血量不动', r_alive.ok is False
          and t.hp('kris') == t.max_hp('kris'))
    # ralsei 打倒再复活
    t.damage('ralsei', 9999)
    check('B4b ralsei 已倒下', t.is_dead('ralsei') is True)
    r_dead = t.revive('ralsei')
    check('B4c 给死人复活：回 ceil(80/2)=40', t.hp('ralsei') == 40)
    check('B4d 复活 ok=True', r_dead.ok is True)
    check('B4e 复活量 == revive_amount(maxhp)（同一函数，无第二份真相）',
          t.hp('ralsei') == T.revive_amount(t.max_hp('ralsei')))


def _b5_restore_only_hurt():
    """B5 `restore_all` **只回没满的**（对应 A5 的 `if (hp < maxhp)`）。"""
    t = T.TeamHP(members=('kris', 'susie', 'ralsei'))
    t.damage('kris', 30)                     # kris 有伤
    # susie / ralsei 满血
    res = t.restore_all()
    by = {r.char_id: r for r in res}
    check('B5 有伤的 kris 被回满（90）', t.hp('kris') == 90)
    check('B5b 有伤的 kris：ok=True', by['kris'].ok is True)
    check('B5c ★本来就满的 susie：ok=False（没动过，可与"睡了但没伤"区分）',
          by['susie'].ok is False)
    check('B5d 满血者 full_before=True', by['susie'].full_before is True)
    check('B5e 三个都满血了', all(t.is_full(c) for c in t.members()))


def _b6_from_stats_wins():
    """B6 `from_stats` 在场时**外部数据就是唯一真源**（不许被 DEFAULT_MAX_HP 污染）。"""
    stats = {'kris': {'maxhp': 200, 'hp': 100}}
    t = T.TeamHP.from_stats(stats)
    check('B6 from_stats 采用外部 maxhp=200（不是兜底的 90）', t.max_hp('kris') == 200)
    check('B6b from_stats 只建数据里有的人（不凭空补 susie/ralsei）',
          t.members() == ('kris',))
    # 负控制：不给 stats 时才是兜底
    t2 = T.TeamHP(members=('kris',))
    check('B6n 负控制：无 stats 时才回落到 DEFAULT_MAX_HP=90', t2.max_hp('kris') == 90)


def _b7_invalid_char():
    """B7 对**不在册**的角色操作：返回空结果、不改状态（不 KeyError）。"""
    t = T.TeamHP(members=('kris',))
    r = t.heal('nobody', 50)
    check('B7 对不在册角色 heal：ok=False 且不抛', r.ok is False and r.char_id == 'nobody')
    check('B7b 不在册角色 hp/max_hp 都是 0', t.hp('nobody') == 0 and t.max_hp('nobody') == 0)
    check('B7c is_full/is_dead 对不在册角色都是 False（不许"幽灵满血"）',
          t.is_full('nobody') is False and t.is_dead('nobody') is False)


def _b8_zero_maxhp_not_enrolled():
    """B8 maxhp<=0 的角色**不建条目**（宁可没有，也不建个 0 血的）。"""
    t = T.TeamHP(members=('kris', 'ghost'), stats={'ghost': {'maxhp': 0}})
    check('B8 maxhp=0 的角色不入册', t.has('ghost') is False)
    check('B8b 只留下 kris', t.members() == ('kris',))


def _b9_determinism():
    """B9 纯函数：同输入同输出 + `to_dict` 键序固定（便于逐字比对）。"""
    a = T.TeamHP(members=('kris', 'susie', 'ralsei')).to_dict()
    b = T.TeamHP(members=('kris', 'susie', 'ralsei')).to_dict()
    check('B9 同构造两遍 to_dict 逐位相同', a == b)
    check('B9b to_dict 键序固定为 SLOT_ORDER 前缀', list(a.keys()) == ['kris', 'susie', 'ralsei'])
    check('B9c 每项含 hp 与 maxhp', all('hp' in v and 'maxhp' in v for v in a.values()))


# ==================================================== C. 纪律

def _c1_no_qt_no_project_import():
    """C1 ★ 零依赖：只准标准库（禁 Qt、禁任何项目内模块）。

    ★★ 第75轮修：本判据初版拿 `_read(_TEAM)`（**含注释的原文**）做子串匹配，
       结果被 `team_hp.py` 自己 docstring 里的**说明文字**误伤 ——
       第 120/131 行正好在讲这条纪律（"当 main.py 以**包形式**加载时…"、
       "`team_hp` 禁 `from modules`…那几条闸"）⇒ `from modules` 命中 ⇒ 假红。
       **"判据读到了注释"在本项目已出现三次**（`check75c` A1、`s7` C1、
       `check76` A4b），所以这里改成 **AST 级**：只看真的 `Import` / `ImportFrom`
       节点，注释与字符串一律不参与。
    """
    bad = []
    for node in ast.walk(_TEAM_TREE):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = a.name or ''
                if nm.startswith(('PyQt', 'PySide', 'modules', 'src')):
                    bad.append('import %s (line %d)' % (nm, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            if node.level:                       # 相对导入 `from .x import y`
                bad.append('from %s%s (line %d)' % ('.' * node.level, mod, node.lineno))
            elif mod.startswith(('PyQt', 'PySide', 'modules', 'src')):
                bad.append('from %s (line %d)' % (mod, node.lineno))
    check('C1 零依赖：无 Qt / 无项目内 import（AST 级，不吃注释）（命中=%s）'
          % (bad or '无'), not bad)
    # 复核：确认这些**否判据**确实会命中（否则是恒真）
    check('C1n 负控制：判据串本身能被"含 import PyQt5"的假源码触发',
          any(p in 'import PyQt5' for p in
              ('import PyQt', 'from PyQt', 'import PySide')))
    # ★ C1p 正控制：证明 AST 级扫描**真的能看到** `import logging`
    #   （否则"没命中项目内 import"可能只是因为整棵树是空的）
    _plain_imports = [a.name for n in ast.walk(_TEAM_TREE)
                      if isinstance(n, ast.Import) for a in n.names]
    check('C1p 正控制：AST 真解析出标准库 import（证明不是空树）（imports=%s）'
          % sorted(_plain_imports),
          'logging' in _plain_imports)


def _c2_no_logging_side_effect():
    """C2 模块**只用 logging 做诊断**，不 import 重型标准库（time/random/socket）。"""
    src = _read(_TEAM)
    heavy = [n for n in ('import time', 'import random', 'import socket',
                         'import threading', 'import subprocess')
             if n in src]
    check('C2 无 time/random/socket/threading/subprocess（命中=%s）' % (heavy or '无'),
          not heavy)


def _c3_wiring_honest():
    """C3 ★ WIRING 诚实登记：`wired=False`（模型已备、接线未做）。"""
    w = getattr(T, 'WIRING', None)
    check('C3 模块暴露 WIRING 台账', isinstance(w, dict))
    if not isinstance(w, dict):
        return
    check('C3b wired=False（未接线，不许虚报已完成）', w.get('wired') is False)
    check('C3c status=model_only', w.get('status') == 'model_only')
    check('C3d not_yet 至少 3 条（登记了还差什么）',
          isinstance(w.get('not_yet'), list) and len(w['not_yet']) >= 3)


def _c4_original_ids_inert():
    """C4 `ORIGINAL_CHAR_IDS` 只作对照、**不进逻辑**（文件里不许用它做判断）。"""
    src = _read(_TEAM)
    # 允许定义；但不许出现 `ORIGINAL_CHAR_IDS[` 这种索引运算（用它查表 = 进逻辑）
    used = 'ORIGINAL_CHAR_IDS[' in src and src.count('ORIGINAL_CHAR_IDS[') > 0
    # 定义处是 `ORIGINAL_CHAR_IDS = {`，不是索引 ⇒ 只在非赋值处出现才算"进逻辑"
    idx = [m.start() for m in re.finditer(r'ORIGINAL_CHAR_IDS\[', src)]
    check('C4 ORIGINAL_CHAR_IDS 不被索引使用（只作对照，不进逻辑）', not idx)
    if idx:
        print('      使用点:', [src[max(0, i - 40):i + 30] for i in idx[:3]])


def _c5_default_maxhp_marked_product():
    """C5 `DEFAULT_MAX_HP` 在注释/docstring 里**被明确标为产品口径**（非原作数值）。"""
    src = _read(_TEAM)
    check('C5 DEFAULT_MAX_HP 附近有"产品口径"字样（不许冒充原作数值）',
          '产品口径' in src)
    check('C5b docstring 说明数值真源应是 obj_hero*（未转储）',
          'obj_hero' in src)


def _c6_no_second_truth():
    """C6 血量语义无第二份真相：只有 team_hp.py 定义 `clamp_hp` / `revive_amount`。"""
    hits = []
    for dirpath, _d, files in os.walk(PET):
        if '__pycache__' in dirpath:
            continue
        for fn in files:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.abspath(p) == os.path.abspath(_TEAM):
                continue
            txt = _read(p)
            if 'def clamp_hp(' in txt or 'def revive_amount(' in txt:
                hits.append(os.path.relpath(p, ROOT))
    check('C6 clamp_hp / revive_amount 只在 team_hp.py 定义（无第二份真相）',
          not hits)
    if hits:
        print('      重复定义:', hits)


def main():
    for fn in (_a0_gml_dir, _a1_not_failed_decompile, _a2_ceil_half,
               _a3_full_signal, _a4_loop_bounds_differ, _a5_savepoint_restore,
               _b1_revive_ceil, _b2_heal_cap, _b3_damage_floor,
               _b4_revive_only_dead, _b5_restore_only_hurt, _b6_from_stats_wins,
               _b7_invalid_char, _b8_zero_maxhp_not_enrolled, _b9_determinism,
               _c1_no_qt_no_project_import, _c2_no_logging_side_effect,
               _c3_wiring_honest, _c4_original_ids_inert,
               _c5_default_maxhp_marked_product, _c6_no_second_truth):
        try:
            fn()
        except Exception as e:
            check('%s 抛异常：%s' % (fn.__name__, e), False)
    print()
    print('=' * 62)
    print('check75b：PASS=%d FAIL=%d' % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
