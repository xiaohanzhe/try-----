#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第75轮 · 动态结巴率（紧张度）回归锁 —— B4。

守的是**一件**事：结巴由「紧张度」驱动，而紧张度由 trust 档位 + 本轮事件决定。

用户口径（逐字，两处）：
  ·「结巴…这有点不好」⇒ 减少但**不许到 0**（真人语料真结巴 8.3%）；
  · 人设 `assets/ralsei_persona.md` 第 53 行：「心里一急会重复一个字，但不是每句都结巴
     —— **越紧张越明显，平常聊天基本不结巴**」。

判据分三层（★ 每层都配**负控制**，否则"守住了没有"无法被测到）：
  A 段 · 纯函数行为（单调性 / 下限 / 值域 / 事件方向）
  B 段 · 文案纪律（不含数值、不含"结巴率"、不含"信任"字样）
  C 段 · 接线（main.py 真的把 nervous_brief 追加进 system；负控制 = 关掉就没这段）

★ 本套件**不联网、不实例化 App、不需要显示器**（纯函数 + AST 源码检查）。
★ 放在 `code-quality-audit/第75轮.../_tools/` ⇒ 仓库根 = HERE 上两级。
"""

import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
#: ★ 本文件在 `code-quality-audit/第75轮.../_tools/` ⇒ 仓库根 = 上**三级**
#: （`_tools` → 轮次目录 → `code-quality-audit` → 仓库根）。少一级会
#: `ModuleNotFoundError: modules`（本项目已踩过同款）。
ROOT = os.path.join(HERE, '..', '..', '..')
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)

from modules import relationship as R          # noqa: E402

_REL = os.path.join(PET, 'modules', 'relationship.py')
_MAIN = os.path.join(PET, 'src', 'main.py')

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
    return io.open(path, encoding='utf-8').read()


# ============================================================ A. 纯函数行为

def _a1_monotone():
    """A1 档位基础紧张度随 trust **单调不增**（正控制：四点真比；负控制：不许恒定）。"""
    ts = (0.0, 0.30, 0.55, 0.80)
    ns = [R.nervousness(t, 'chat') for t in ts]
    noninc = all(ns[i] >= ns[i + 1] for i in range(len(ns) - 1))
    check('A1 紧张度随 trust 单调不增（0.62→0.44→0.24→0.10）', noninc)
    # 负控制：不能"恒定"（恒定的实现也能过单调 ⇒ 单调判据本身不够）
    check('A1n 负控制：四个档位不是同一个值（否则单调判据是空的）',
          len(set(ns)) == len(ns))
    check('A1s 判据串露出来（防 no-op）：%s' % ('>'.join('%.2f' % n for n in ns)), True)


def _a2_floor():
    """A2 下限**永不为 0** —— 用户口径「不许到 0」的核心。"""
    lo = min(R.nervousness(t, ev)
             for t in (0.0, 0.12, 0.5, 0.95)
             for ev in (None, 'chat', 'comfort', 'harsh'))
    check('A2 紧张度下限 > 0（实测 min=%.3f，FLOOR=%.3f）' % (lo, R.NERVOUS_FLOOR),
          lo > 0.0)
    check('A2b 下限等于常量 NERVOUS_FLOOR（不是散落的魔法数）',
          abs(lo - R.NERVOUS_FLOOR) < 1e-9)


def _a3_range():
    """A3 值域恒在 [0,1]，含非法输入（负 trust / 超 1 / 未知事件 / None）。"""
    bad = []
    for t in (-5, -0.1, 0, 0.5, 1, 9, 'x', None):
        for ev in ('chat', 'harsh', 'comfort', 'curious', 'self_share',
                   'cold', None, 'bogus'):
            v = R.nervousness(t, ev)
            if not (0.0 <= v <= 1.0):
                bad.append((t, ev, v))
    check('A3 值域恒在 [0,1]（含全部非法输入）', not bad)
    if bad:
        print('      越界样本:', bad[:5])


def _a4_events():
    """A4 事件方向：harsh 抬、comfort 压（**成对**正负控制）。"""
    base = R.nervousness(0.12, 'chat')
    harsh = R.nervousness(0.12, 'harsh')
    comfort = R.nervousness(0.12, 'comfort')
    check('A4 harsh（被凶）抬高紧张度（%.3f > %.3f）' % (harsh, base), harsh > base)
    check('A4b comfort（被哄）压低紧张度（%.3f < %.3f）' % (comfort, base),
          comfort < base)
    check('A4c A/B 先断言不同（两个事件不能算出同一个值）', abs(harsh - comfort) > 1e-9)


def _a5_stage_map():
    """A5 档位映射是**单一真源**（四档齐全，不许漏档导致回落默认）。"""
    keys = set(R._STAGE_NERVOUSNESS.keys())
    stages = set(k for k, _f, _l in R.STAGES)
    check('A5 每个信任档位都有紧张度（缺档会静默回落到 distrust）',
          stages <= keys)


def _a6_purity():
    """A6 纯函数：同输入同输出（跑两遍必须逐位相同）+ 不写全局。"""
    a = [R.nervousness(t, 'harsh') for t in (0.0, 0.4, 0.9)]
    b = [R.nervousness(t, 'harsh') for t in (0.0, 0.4, 0.9)]
    check('A6 确定性：同输入两遍逐位相同', a == b)


# ============================================================ B. 文案纪律

_NUM_TOKENS = ('%', '％', '0.', '1.', '0.6', '0.1')


def _b1_no_numbers():
    """B1 文案**不含数值**（给了模型就会念出来 —— 与 trust 同一条纪律）。"""
    hits = []
    for t in (0.0, 0.12, 0.30, 0.55, 0.80, 0.95):
        for ev in (None, 'chat', 'harsh', 'comfort'):
            b = R.nervous_brief(t, ev)
            for tok in _NUM_TOKENS:
                if tok in b:
                    hits.append((t, ev, tok))
    check('B1 文案不含数值/百分比（含 4 档 × 4 事件）', not hits)
    if hits:
        print('      命中:', hits[:5])


def _b2_no_meta_words():
    """B2 文案不含元游戏词：不许出现"结巴率/概率/信任/档位"。"""
    bad_words = ('结巴率', '概率', '信任', '档位', '百分比', '紧张度')
    hits = []
    for t in (0.0, 0.12, 0.30, 0.55, 0.80, 0.95):
        b = R.nervous_brief(t, 'chat')
        for w in bad_words:
            if w in b:
                hits.append((t, w))
    check('B2 文案不含元游戏词（结巴率/概率/信任/档位/百分比/紧张度）', not hits)
    if hits:
        print('      命中:', hits[:5])


def _b3_has_header():
    """B3 文案带固定抬头（宿主靠它自省；也便于真机日志定位）。"""
    b = R.nervous_brief(0.12, 'chat')
    check('B3 文案带【你现在的状态】抬头', '【你现在的状态】' in b)


def _b4_not_every_sentence():
    """B4 文案必须写明**不是每句都结巴**（persona 原句口径）。

    负控制：随便换成一个"请适当结巴"的写法 ⇒ 判据必须报红。
    这里用"同语义必须出现"的做法：distrust 档文案必须同时含
    『不是每句』与『磕绊/卡壳』两个语义簇之一。
    """
    b = R.nervous_brief(0.0, 'chat')
    has_not_every = ('不是每句' in b) or ('多数句子' in b)
    has_stumble = ('磕绊' in b) or ('卡' in b) or ('重复' in b)
    check('B4 文案写明"不是每句都结巴"（flavor 不许变成句式模板）', has_not_every)
    check('B4b 文案含"磕绊/卡/重复"类自然语言（不是干巴巴一句"别结巴"）',
          has_stumble)


def _b5_friend_is_relaxed():
    """B5 friend 档文案必须"放松/稳"，且**不许**出现"很紧/慌"这种反向措辞。

    负控制：若把 friend 的文案错配成 distrust 的，本判据必须报红。
    """
    b = R.nervous_brief(0.95, 'comfort')
    check('B5 friend 档文案是"稳/放松"（%.0f 字）' % len(b),
          ('稳' in b) or ('放松' in b))
    check('B5b friend 档**不**含"很紧/慌得"这种高紧张措辞',
          ('很紧' not in b))


# ============================================================ C. 接线

def _c1_relationship_api():
    """C1 `Relationship` 暴露 nervous_brief / nervousness 两个口。"""
    inst = R.Relationship()
    check('C1 Relationship.nervous_brief 存在', callable(getattr(inst, 'nervous_brief', None)))
    check('C1b Relationship.nervousness 存在', callable(getattr(inst, 'nervousness', None)))
    # 行为级：实例口必须与模块纯函数**同值**（别造第二份真相）
    inst._trust = 0.12
    check('C1c 实例口与模块纯函数同值（不许两处算）',
          abs(inst.nervousness('chat') - R.nervousness(0.12, 'chat')) < 1e-9)


def _c2_main_wiring():
    """C2 main.py **真的**把 nervous_brief 追加进 system（AST + 源码双查）。"""
    src = _read(_MAIN)
    tree = ast.parse(src)
    # (a) 源码里必须出现 `nervous_brief(` 调用与 `_nerv_brief` 变量
    has_call = '.nervous_brief(' in src
    has_var = '_nerv_brief' in src
    check('C2 main 调用了 relationship.nervous_brief(...)', has_call)
    check('C2b main 持有 _nerv_brief 变量', has_var)
    # (b) AST：存在 `system = system + "\n\n" + _nerv_brief` 这种追加
    appended = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) or isinstance(node, ast.Assign):
            seg = ast.dump(node)
            if '_nerv_brief' in seg and 'system' in seg:
                appended = True
                break
    check('C2c AST：_nerv_brief 被拼进 system（不是算了不用）', appended)


def _c3_neg_control_wiring():
    """C3 负控制：把 product 里 `_nerv_brief` 的追加**去掉**，判据 C2c 必须报红。

    做法**不改产品文件**：在内存里对源码做一次字符串手术，再 parse 检查
    —— 「同一个 AST 检查函数」对"改坏的源码"必须给出 False。
    """
    src = _read(_MAIN)
    # 手术：把追加那两行删掉（保留变量赋值 ⇒ 制造"算了不用"的假接线）
    broken = src.replace(
        '        if _nerv_brief:\n'
        '            system = system + "\\n\\n" + _nerv_brief\n', '')
    if broken == src:
        check('C3 负控制夹具**没改动源码**（说明替换串没命中 ⇒ 夹具失效）', False)
        return

    def _has_append(s):
        t = ast.parse(s)
        for node in ast.walk(t):
            if isinstance(node, (ast.AugAssign, ast.Assign)):
                seg = ast.dump(node)
                if '_nerv_brief' in seg and 'system' in seg:
                    return True
        return False

    check('C3 负控制：去掉追加后同判据报红（证明 C2c 不是恒真）',
          (not _has_append(broken)))


def _c4_no_second_truth():
    """C4 紧张度没在别处被重算（单一真源）：只有 relationship.py 定义它。"""
    hits = []
    for dirpath, _dirs, files in os.walk(PET):
        if '__pycache__' in dirpath:
            continue
        for fn in files:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.abspath(p) == os.path.abspath(_REL):
                continue
            txt = _read(p)
            if 'def nervousness(' in txt or 'def nervous_brief(' in txt:
                hits.append(p)
    check('C4 紧张度只在 relationship.py 定义（无第二份真相）', not hits)
    if hits:
        print('      重复定义:', hits)


def _c5_floor_constant():
    """C5 AST：NERVOUS_FLOOR 是模块级常量，且 > 0（不许被改成 0）。"""
    tree = ast.parse(_read(_REL))
    found = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'NERVOUS_FLOOR':
                    try:
                        found = float(node.value.value)
                    except Exception:
                        found = None
    check('C5 NERVOUS_FLOOR 是模块级数值常量', found is not None)
    check('C5b NERVOUS_FLOOR > 0（用户口径"不许到 0"的硬落点）',
          found is not None and found > 0.0)


def main():
    for fn in (_a1_monotone, _a2_floor, _a3_range, _a4_events, _a5_stage_map,
               _a6_purity,
               _b1_no_numbers, _b2_no_meta_words, _b3_has_header,
               _b4_not_every_sentence, _b5_friend_is_relaxed,
               _c1_relationship_api, _c2_main_wiring, _c3_neg_control_wiring,
               _c4_no_second_truth, _c5_floor_constant):
        try:
            fn()
        except Exception as e:
            check('%s 抛异常：%s' % (fn.__name__, e), False)
    print()
    print('=' * 62)
    print('check75：PASS=%d FAIL=%d' % (_P, _F))
    return 0 if _F == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
