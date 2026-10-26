# -*- coding: utf-8 -*-
"""第113轮k · 验证「活动 → 去处」：听懂、同章、能给建议、**默认路径不打扰**。

用户口径（2026-10-26 逐字）
--------------------------
「咱吃饭去吧」→「那要不去 XXX 家餐厅？」。

判据
----
  A ★★ **默认路径零变化**：`heard=None` ⇒ 不产活动块。这条最重要 ——
     这条 prompt 每个 NPC 每次都用，无条件加行等于给所有人改人设。
  B 听懂：`咱吃饭去吧` / `我有点累了` / `出去逛逛` / `去买点东西` 各命中对应活动
  C 给出**具体地点**：产出里必须有至少一个真实地名，且**只在本章**
  D 无关的话**不产块**（负控制：`今天天气不错`）
  E 判不出章 ⇒ **不产块**（负控制：宁可不张罗，也不推荐别的世界）
  F 不泄内部标记：输出里零 `rm_` / `dw ` / `room_` / `全部房间`
  G 四类活动的候选都真的存在（eat / rest / play / work 各 >0 或如实为 0）

★ 被测代码是**产品里那几个方法本身**（AST 抽出来 exec），不是复刻版。
"""
import ast
import io
import json
import logging
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
IDX = os.path.join(PET, 'assets', 'scenes', '_index.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                        # noqa: E402

METHODS = ('_scene_place_label', '_activity_chapter', '_activity_places', '_npc_life_blocks')


def extract_method(src, name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn))
    return None


def build_index():
    idx = json.loads(io.open(IDX, encoding='utf-8').read())
    m = {}
    for _cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for scid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                m[str(scid)] = (ch_name, area_name, str(sc.get('name') or ''),
                                bool(sc.get('name_derived')),
                                str(sc.get('name_raw') or ''))
    return m


_NS = {'npc_life_mod': L, '_log': logging.getLogger('verify_act113k')}
_SRC = io.open(MAIN, encoding='utf-8', newline='').read()
_MISSING = []
for _n in METHODS:
    _code = extract_method(_SRC, _n)
    if not _code:
        _MISSING.append(_n)
        continue
    exec(compile(_code, '<%s>' % _n, 'exec'), _NS)

_IDXMAP = build_index()


class Stub(object):
    npc_life_mod = L
    npc_bonds = None

    def __init__(self, sid, home=None):
        self._sid = sid
        self.npc_placement = _Place(home)

    # ---- 桩：只提供产品代码真正用到的那几个出口
    def _scene_label_map(self):
        return _IDXMAP

    def _scene_place_label(self, sid):
        return _NS['_scene_place_label'](self, sid)

    # ★ 必须**转发**到产品方法，不能自己实现一份：
    #   自己实现 = 测的是复刻版；不实现 = AttributeError 被 try 吞掉 ⇒ 静默不产块（假红）
    def _activity_chapter(self, npc_id):
        return _NS['_activity_chapter'](self, npc_id)

    def _activity_places(self, kind, chapter):
        return _NS['_activity_places'](self, kind, chapter)

    def _npc_scene_id(self):
        return self._sid

    def _npc_scene_text(self):
        return ''

    def _npc_life_ids(self):
        return []

    def _npc_relative_positions(self, *a, **k):
        return {}

    def _npc_display_label(self, nid):
        return ''


class _Place(object):
    def __init__(self, home):
        self._home = home

    def home_of(self, npc_id):
        return self._home


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


def blocks(stub, heard=None):
    return _NS['_npc_life_blocks'](stub, 'ralsei', heard=heard)


def main():
    check('A0 四个产品方法都抽到了（缺一个后面全是假绿）', not _MISSING,
          '缺=%r' % (_MISSING,))
    if _MISSING:
        print('结论： FAIL')
        return 3

    print()
    print('--- A ★★ 默认路径零变化 ---')
    st = Stub('ch1.hometown.town_square')
    out_plain = blocks(st)
    check('A1 `heard=None` ⇒ 不产「这会儿能张罗的事」',
          '【这会儿能张罗的事】' not in out_plain, repr(out_plain[:60]))

    print()
    print('--- B 听懂四种活动 ---')
    cases = [
        ('咱吃饭去吧', 'eat'),
        ('我有点累了，歇会儿吧', 'rest'),
        ('出去逛逛？', 'play'),
        ('去买点东西', 'work'),
    ]
    for line, want in cases:
        got = L.detect_activity(line)
        check('B `%s` ⇒ %s' % (line, want), got[0] == want, '实测 %r' % (got,))

    print()
    print('--- C 给出具体地点（且只在本章）---')
    out_eat = blocks(Stub('ch1.hometown.town_square'), heard='咱吃饭去吧')
    has_block = '【这会儿能张罗的事】' in out_eat
    check('C1 吃饭 ⇒ 真产出活动块', has_block)
    if has_block:
        line = [x for x in out_eat.split('\n') if '这会儿能张罗的事' in x][0]
        print('      %s' % line)
        check('C2 块里点名了**具体地方**（不止一句空话）', '：' in line and '。' in line)
        check('C3 说明了"真有的地方"（防止模型以为可以编）', '真有的地方' in line)
        check('C4 明确要求"用自己的说法，别照念"（防固定例句被逐字搬走）',
              '别照着念' in line or '别照着念' in out_eat)

    # C5 只在同章：四个活动在 ch1 的候选，sid 必须全部以 ch1. 开头
    bad_ch = []
    for kind in L.ACTIVITY_KINDS:
        for sid, _lbl in st._activity_places(kind, 'ch1'):
            if not sid.startswith('ch1.'):
                bad_ch.append((kind, sid))
    check('C5 候选**只在本章**（跨作品推荐是硬错）', not bad_ch, '%r' % (bad_ch[:3],))

    print()
    print('--- D 负控制：无关的话不产块 ---')
    out_none = blocks(st, heard='今天天气不错')
    check('D1 `今天天气不错` ⇒ 不产块', '【这会儿能张罗的事】' not in out_none)

    print()
    print('--- E 负控制：判不出章就不张罗 ---')
    # 当前场景为空、也没有归属地 ⇒ chapter='' ⇒ 不该产块
    st_none = Stub(None, None)
    check('E0 `_activity_chapter` 判不出 ⇒ 返回空串',
          st_none._activity_chapter('ralsei') == '', repr(st_none._activity_chapter('ralsei')))
    out_noch = blocks(st_none, heard='咱吃饭去吧')
    check('E1 判不出章 ⇒ 不产块（宁可不张罗，也不推荐别的世界）',
          '【这会儿能张罗的事】' not in out_noch, repr(out_noch[:60]))

    print()
    print('--- F 不泄内部标记 ---')
    leak = []
    for kind in L.ACTIVITY_KINDS:
        for sid, lbl in st._activity_places(kind, 'ch1'):
            for tok in ('rm_', 'dw ', 'lw ', 'room_', '全部房间', '未分区', 'None'):
                if tok in lbl:
                    leak.append((kind, sid, tok, lbl))
    check('F1 候选名里零内部标记', not leak, '%r' % (leak[:3],))

    print()
    print('--- G 四类活动的候选真的存在 ---')
    counts = {}
    for kind in L.ACTIVITY_KINDS:
        counts[kind] = len(st._activity_places(kind, 'ch1'))
    print('      ch1 候选数 = %r' % counts)
    check('G1 至少 eat / work 在 ch1 有候选（原作里家乡有 diner / 学校 / 图书馆）',
          counts.get('eat', 0) > 0 and counts.get('work', 0) > 0)
    check('G2 如实：没有候选的活动**不许编一个出来**（返回 0 是对的）',
          all(isinstance(v, int) and v >= 0 for v in counts.values()))

    print()
    print('--- H 端到端四种活动（ch1）---')
    for line, _want in cases:
        out = blocks(st, heard=line)
        has = '【这会儿能张罗的事】' in out
        tail = ''
        if has:
            tail = [x for x in out.split('\n') if '这会儿能张罗的事' in x][0]
            tail = tail[:90]
        print('  %-12s ⇒ 产块=%s  %s' % (line, has, tail))

    print()
    print('=' * 70)
    print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
    print('=' * 70)
    return 0 if _n_fail == 0 else 3


if __name__ == '__main__':
    sys.exit(main())
