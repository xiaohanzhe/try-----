# -*- coding: utf-8 -*-
"""第198轮回归锁 · **记错机制**（真的会记偏，但重要的事不会）。

用户口径（第195轮选定）
------------------------
    「记混记错选 **B（真的会记偏）**，但**重要的事不会**」

改之前的状态：`recall_text` 的普通片段是**逐字引用**
（`· 昨天，你说过「我下午三点十五分去买了3个面包」`）—— 这是**完美记忆**，
而完美记忆不像人。改之后：约三成普通片段会说成「**好像**说过」，并且细节被降级 / 时间被漂移。

它守什么
--------
A 常量与口径   —— 触发率是真实值（不是 0，否则整机制是死的）、规则表结构对
B 谁会被记偏   —— 关键记忆 / 日摘要 / `PROTECTED_KINDS` / 内在活动**一律免疫**
C 不虚构       —— `SOFTEN` **只减不增**（不冒出新数字）、`TIMESHIFT` 可逆、空输入不炸
D 确定性       —— 同一条记忆每次都错成同一个样子；换文本会换结果（证明真的用了文本）
E 端到端       —— `RATE=0` 逐字回到旧格式；`RATE=1` 时普通片段必定「好像」、
                 **key 仍逐字不变**（"重要的事不会"这条口径的落点）
F 自检

★ 为什么用**稳定哈希**而不是 `random`：回归必须可重放。随机数会让同一用例
  这次绿下次红，而"有时红"的判据等于没有判据（本项目 §4 那条教训）。
"""
from __future__ import print_function

import ast
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MS = os.path.join(PET, 'modules', 'memory_system.py')
sys.path.insert(0, os.path.join(PET, 'modules'))

from memory_system import MemorySystem            # noqa: E402

_n = {'p': 0, 'f': 0}


def check(name, ok, extra=u''):
    if ok:
        _n['p'] += 1
        print('[PASS] %s' % name)
    else:
        _n['f'] += 1
        print('[FAIL] %s' % name)
    if extra:
        print('       %s' % extra)


def rd(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


TEXTS = [
    u'我下午三点十五分去买了3个面包',
    u'今天15:30 我跑了2次操场',
    u'刚才吃了5个饺子',
    u'昨天跟你聊到2点',
    u'前天买了4个苹果',
    u'我今天有点累',
    u'刚下过雨，路上湿',
    u'明天要早起开会',
    u'昨晚看了3集动画',
    u'刚才在楼下碰到邻居家的狗',
]
KEY_TEXT = u'升到5级了，这是第3次升级'
KEY_TEXT2 = u'我把钥匙放在玄关的第二个抽屉'


def plain(i=0):
    """一条普通片段（构造的，用于单点判据）。"""
    return {'id': 900 + i, 'kind': 'dialogue', 'day': '2026-11-18',
            'text': TEXTS[i % len(TEXTS)], 'is_key': False}


def main():
    mem = MemorySystem(None, memory_dir=tempfile.mkdtemp(prefix='mem198_', dir=r'D:\_tmp'))
    try:
        _run(mem)
    finally:
        shutil.rmtree(getattr(mem, 'memory_dir', '') or '', ignore_errors=True)
    print()
    print('=' * 78)
    print('合计 %d 条判据  PASS=%d  FAIL=%d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
    print('=' * 78)
    return 1 if _n['f'] else 0


def _run(mem):
    src = rd(MS)
    tree = ast.parse(src)

    # ============================================================ A 常量与口径
    print('=' * 78)
    print('A. 常量与口径')
    print('=' * 78)
    rate = float(getattr(MemorySystem, 'MISFIRE_RATE', 0.0) or 0.0)
    check('A1 触发率是真实值（0 < MISFIRE_RATE <= 1，不是 0 也不是 1）',
          0.0 < rate < 1.0, 'MISFIRE_RATE=%r' % rate)
    salt = str(getattr(MemorySystem, 'MISFIRE_SALT', '') or '')
    check('A2 存在非空盐值（换盐 ⇒ 错法整体换一套）', len(salt) >= 8, 'salt=%r' % salt)
    rules = tuple(getattr(MemorySystem, 'MISFIRE_TIME_RULES', ()) or ())
    ok_shape = bool(rules) and all(len(r) == 3 and isinstance(r[2], bool) for r in rules)
    check('A3 时间规则表是三元组 `(旧词, 新词, 是否保留"的<时段>")`',
          ok_shape, '条目=%d 样例=%r' % (len(rules), rules[:2]))
    check('A4 时间规则覆盖"今天/昨天/刚才"三种最常出现的说法',
          all(any(a == w for a, _, _ in rules) for w in (u'今天', u'昨天', u'刚才')),
          '旧词=%s' % [a for a, _, _ in rules])
    num_rules = tuple(getattr(MemorySystem, 'MISFIRE_NUM_RULES', ()) or ())
    check('A5 数字规则表至少覆盖"时刻 / 次数 / 个数"',
          len(num_rules) >= 3 and any(':' in p or u'：' in p for p, _ in num_rules),
          '条目=%d' % len(num_rules))

    # ============================================================ B 谁会被记偏
    print()
    print('=' * 78)
    print('B. 谁会被记偏（负控制全部在 RATE=1.0 下做，确保"不触发"不是因为没掷中）')
    print('=' * 78)
    old_rate = mem.MISFIRE_RATE
    mem.MISFIRE_RATE = 1.0
    try:
        k = {'id': 1, 'kind': 'dialogue', 'text': KEY_TEXT, 'is_key': True,
             'day': '2026-11-18'}
        check('B1 关键记忆（is_key）免疫', mem.misfire_mode(k) == '',
              'mode=%r' % mem.misfire_mode(k))
        d = {'id': 2, 'kind': 'dialogue', 'text': TEXTS[0], 'is_digest': True,
             'day': '2026-11-18'}
        check('B2 日摘要（is_digest）免疫', mem.misfire_mode(d) == '',
              'mode=%r' % mem.misfire_mode(d))
        bad_kinds = []
        for kind in MemorySystem.PROTECTED_KINDS:
            it = {'id': 3, 'kind': kind, 'text': TEXTS[1], 'day': '2026-11-18'}
            if mem.misfire_mode(it) != '':
                bad_kinds.append(kind)
        check('B3 PROTECTED_KINDS 里每一种都免疫', not bad_kinds,
              'kinds=%s 违规=%s' % (list(MemorySystem.PROTECTED_KINDS), bad_kinds))
        inner = {'id': 4, 'kind': 'inner', 'text': TEXTS[2], 'day': '2026-11-18'}
        check('B4 内在活动（kind=inner）免疫（它已有自己的"好像"口径）',
              mem.misfire_mode(inner) == '', 'mode=%r' % mem.misfire_mode(inner))
        hit = [mem.misfire_mode(plain(i)) for i in range(len(TEXTS))]
        check('B5 RATE=1.0 时普通片段必定走样（正控制：守卫不是恒真）',
              all(h in ('soften', 'timeshift') for h in hit), 'modes=%s' % hit)
    finally:
        mem.MISFIRE_RATE = old_rate
    old_rate0 = mem.MISFIRE_RATE
    mem.MISFIRE_RATE = 0.0
    try:
        check('B6 RATE=0.0 时普通片段必定不走样',
              all(mem.misfire_mode(plain(i)) == '' for i in range(len(TEXTS))),
              'RATE=%r' % mem.MISFIRE_RATE)
    finally:
        mem.MISFIRE_RATE = old_rate0

    # ============================================================ C 不虚构
    print()
    print('=' * 78)
    print('C. 不虚构（记偏 ≠ 编造）')
    print('=' * 78)
    bad_new, samples = 0, []
    for t in TEXTS:
        out = mem._misfire_soften(t)
        before = set(re.findall(r'\d+', t))
        after = set(re.findall(r'\d+', out))
        if not after <= before:
            bad_new += 1
            samples.append((t, out))
    check('C1 SOFTEN 只减不增：不冒出新数字（否则就是编造）', bad_new == 0,
          '违规=%d %s' % (bad_new, samples[:2]))

    idem = [t for t in TEXTS if mem._misfire_soften(mem._misfire_soften(t)) != mem._misfire_soften(t)]
    check('C2 SOFTEN 幂等（降级过的文本再降级不变）', not idem, '不稳=%s' % idem[:2])

    # ★ C3 原本写成"反向还原"，错了：规则表是**多对一**（昨天→前几天、前天→前几天），
    #   反查必然撞车。改成不依赖规则顺序的性质：**输出不许冒出新字符**，
    #   且必须真的变了（不是 no-op）。
    bad_shift = []
    for when, tod in ((u'今天', u'下午'), (u'昨天', u'早上'), (u'刚才', u''), (u'前天', u'')):
        out = mem._misfire_shift(when, tod)
        allowed = set(when) | set(tod) | set(u'的')
        for a, b, _keep in MemorySystem.MISFIRE_TIME_RULES:
            if a in when:
                allowed |= set(b)
                break
        invented = set(out) - allowed
        before = when + (u'的' + tod if tod else '')
        if invented or out == before:
            bad_shift.append((when, tod, out, u''.join(sorted(invented)) or u'未变化'))
    check('C3 TIMESHIFT 不冒出新字符且真的漂移了（不是 no-op）',
          not bad_shift, '违规=%s' % bad_shift[:2])

    check('C4 空输入不炸（None / 空串都原样返回空）',
          mem._misfire_soften(None) == '' and mem._misfire_soften('') == ''
          and mem._misfire_shift(None, None) == '' and mem._misfire_shift('', '') == '')

    # ============================================================ D 确定性
    print()
    print('=' * 78)
    print('D. 确定性（回归必须可重放）')
    print('=' * 78)
    twice = [mem.misfire_mode(plain(i)) for i in range(4)]
    twice2 = [mem.misfire_mode(plain(i)) for i in range(4)]
    check('D1 同一片段连问两次结果相同', twice == twice2, '%s vs %s' % (twice, twice2))

    mem.MISFIRE_RATE = 1.0
    try:
        modes = set(mem.misfire_mode(plain(i)) for i in range(len(TEXTS)))
        check('D2 不是常量：样本里两种变换都出现（否则等于只有一种实现）',
              len(modes) >= 2, 'modes=%s' % sorted(modes))
        base = dict(plain(0))
        diff = 0
        for i, t in enumerate(TEXTS):
            alt = dict(base)
            alt['text'] = t
            if mem.misfire_mode(alt) != mem.misfire_mode(base):
                diff += 1
        check('D3 换文本会换出不同结果（证明哈希真的用了 text，不是只按 id）',
              diff > 0, '不同=%d/%d' % (diff, len(TEXTS)))
    finally:
        mem.MISFIRE_RATE = old_rate

    # ============================================================ E 端到端
    print()
    print('=' * 78)
    print('E. 端到端 recall_text（真正落进提示词的那一段）')
    print('=' * 78)
    for t in TEXTS:
        mem.add_fragment(t, who='user')
    mem.remember_key('level_up', KEY_TEXT)
    # ★ 第二条 key 故意用**不在** PROTECTED_KINDS 里的 kind：
    #   第一条（level_up）同时有 is_key 与 PROTECTED_KINDS 两道门，
    #   拆掉 is_key 那道它照样绿 —— 实测过，E3 会因此失去鉴别力。
    #   这一条只靠 is_key 挡，才能证明"关键记忆"这个标记本身有用。
    mem.remember_key('chat_note', KEY_TEXT2)

    mem.MISFIRE_RATE = 0.0
    try:
        out0 = mem.recall_text(u'面包', limit=3)
        line0 = [ln for ln in out0.splitlines() if ln.startswith(u'·')]
        clean = bool(line0) and all(u'好像' not in ln for ln in line0) \
            and all(u'说过「' in ln for ln in line0)
        check('E1 RATE=0 ⇒ 逐字回到旧格式（无"好像"、仍是「说过」句）', clean,
              '样例=%s' % (line0[:1],))
    finally:
        mem.MISFIRE_RATE = old_rate

    mem.MISFIRE_RATE = 1.0
    try:
        out1 = mem.recall_text(u'面包', limit=3)
        line1 = [ln for ln in out1.splitlines() if ln.startswith(u'·')]
        check('E2 RATE=1 ⇒ 普通片段必定带"好像"（走样真的落到了输出上）',
              bool(line1) and any(u'好像' in ln for ln in line1),
              '样例=%s' % (line1[:1],))

        seen = []
        for cue in (u'升级', u'钥匙'):
            for ln in mem.recall_text(cue, limit=5).splitlines():
                if u'重要的事' in ln:
                    seen.append(ln)
        got = [t for t in (KEY_TEXT, KEY_TEXT2) if any(t in ln for ln in seen)]
        ok_verbatim = bool(seen) and all(u'好像' not in ln for ln in seen)
        check('E3 ★★★ RATE=1 下关键记忆仍逐字不变（"重要的事不会记偏"的落点）',
              ok_verbatim and len(got) == 2,
              '行数=%d 逐字命中=%d 样例=%s' % (len(seen), len(got), seen[:1]))
    finally:
        mem.MISFIRE_RATE = old_rate

    check('E4 分母闸：样本里普通片段与关键记忆都存在（不是空样本绿）',
          len(mem.fragments) >= len(TEXTS) and len(mem.keys) >= 2,
          'fragments=%d keys=%d' % (len(mem.fragments), len(mem.keys)))

    # ============================================================ F 自检
    print()
    print('=' * 78)
    print('F. 自检')
    print('=' * 78)
    n_total = _n['p'] + _n['f'] + 3          # 本条与 F2/F3 尚未计入
    check('F1 判据条数符合声明（A5 B6 C4 D3 E4 F3 = 25）', n_total == 25,
          '实际=%d' % n_total)

    # ★★★ F2 第一版犯了**两个**错，都是本项目的老账：
    #   ① 判据名里写了方括号标记字面量 ⇒ 那行自己往 stdout 多打两个标记，
    #      `run_all` 按出现次数统计 ⇒ 当场把 25/0 数成 26/1（第187轮那条规矩的复发）；
    #   ② AST 扫的是 `memory_system.py` —— 那里根本没有 `check()` 调用 ⇒ 恒真。
    #   修法：标记用**拼接**构造（源码里不出现完整字面量），并改成扫**本文件自己**。
    _MARK_P = '[' + 'PASS' + ']'
    _MARK_F = '[' + 'FAIL' + ']'
    own_tree = ast.parse(rd(os.path.abspath(__file__)))
    dirty = []
    for node in ast.walk(own_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'check' and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                if _MARK_P in a0.value or _MARK_F in a0.value:
                    dirty.append(a0.value[:24])
    check('F2 判据名里没有方括号 PASS/FAIL 标记（否则自己污染 run_all 计数）',
          not dirty, '违规=%s' % dirty[:3])

    # ★★ 必须按 AST 定位到 `misfire_mode` **函数体**里查 random：
    #    这个文件别处（934 行选技能）确实用了 random，注释里还写着 "random" 这个词 ——
    #    做纯文本扫描会两头误判（本项目"纯文本扫 API＝假象"）。判据要问的是
    #    "这个函数自己有没有用随机"，不是"文件里出现过这个词"。
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'misfire_mode':
            fn = node
            break
    uses_random = False
    uses_sha1 = False
    if fn is not None:
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == 'random':
                uses_random = True
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == 'random':
                uses_random = True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'sha1':
                uses_sha1 = True
    check('F3 misfire_mode 函数体内是稳定哈希（sha1）且不含 random（回归必须可重放）',
          fn is not None and uses_sha1 and not uses_random,
          'fn=%s sha1=%s random=%s' % (fn is not None, uses_sha1, uses_random))


if __name__ == '__main__':
    sys.exit(main())
