# -*- coding: utf-8 -*-
"""第113轮j · 验证「空间认知」整条链路：`place_hint` 块 + ⓪ 分片的接线与顺序。

为什么还要这一层
---------------
`verify_place113j.py` / `survey_place113j.py` 只测 `_scene_place_label`（**名字**对了）。
但名字对 ≠ 提示块对：
  · `at_home` 判错 ⇒ 在自己家里还说「累了会想回去」，模型会回一句"我该回家了"；
  · 顺序反了 ⇒ 模型先读到"这里很安静"再读到"你在城堡镇"，会把地名当形容气氛的词；
  · 接线没接上 ⇒ 函数再好也永远不会被调用。
⇒ 本脚本测这三件事。

判据
----
  A `place_hint` 块行为（5 条，含**在家不许说想回去**这条真错误防线）
  B AST 接线：`_npc_life_blocks` 里**确实调**了 `place_hint`，且**排在** `scene_traits` 之前，
    且 `at_home=` 的实参是 `sid == home_id`（不是硬编码）
  C 符号存在：`_npc_scene_id` 方法、`npc_placement.home_of`、`npc_life` 五个公开名
  D **方法级端到端**：把产品里的 `_npc_life_blocks` **整段**抽出来挂桩跑，三种情形
"""
import ast
import io
import logging
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import npc_life as L                                        # noqa: E402

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def extract_method(src, name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn)), fn
    return None, None


# ---------------------------------------------------------------- A
def part_a():
    print('=== A `place_hint` 块行为 ===')
    r = {}

    h = L.place_hint()
    r['A1 全空 ⇒ 空串'] = (h == '')
    print('  A1 全空 → %r  %s' % (h, 'OK' if r['A1 全空 ⇒ 空串'] else '**FAIL**'))

    h = L.place_hint(here='城堡镇（第一章 · 黑暗世界）')
    r['A2 只有 here'] = ('【你现在在哪】' in h and '【你的归属地】' not in h)
    print('  A2 here only → %s  %s' % (r['A2 只有 here'], 'OK' if r['A2 只有 here'] else '**FAIL**'))

    h = L.place_hint(here='荒野', home='城堡镇', at_home=False)
    r['A3 不在家'] = ('想回去' in h and '就是这儿' not in h)
    print('  A3 不在家 → 含「想回去」=%s 含「就是这儿」=%s  %s'
          % ('想回去' in h, '就是这儿' in h, 'OK' if r['A3 不在家'] else '**FAIL**'))

    h = L.place_hint(here='城堡镇', home='城堡镇', at_home=True)
    # ★ 这条是**真错误防线**：在家还说"想回去"，模型会答"那我该回家了"
    r['A4 在家不许说想回去'] = ('就是这儿' in h and '想回去' not in h)
    print('  A4 在家 → 含「就是这儿」=%s 含「想回去」=%s（必须 False）  %s'
          % ('就是这儿' in h, '想回去' in h, 'OK' if r['A4 在家不许说想回去'] else '**FAIL**'))

    h = L.place_hint(here='甲地', home='乙地', near=['丙地', '丁地'])
    order = (h.find('【你现在在哪】') < h.find('【你的归属地】') < h.find('【你还记得这些地方】'))
    r['A5 三块顺序'] = order
    print('  A5 顺序 在哪<归属地<记得 → %s  %s' % (order, 'OK' if order else '**FAIL**'))

    h = L.place_hint(here='甲地', near=['', None, '丙地'])
    r['A6 near 空值被滤'] = ('、、' not in h and '、。' not in h and '丙地' in h)
    print('  A6 near 含空/None → %s（滤空后 %r）  %s'
          % (r['A6 near 空值被滤'], h.split('【你还记得这些地方】')[-1][:14],
             'OK' if r['A6 near 空值被滤'] else '**FAIL**'))
    return r


# ---------------------------------------------------------------- B
def part_b(src):
    print()
    print('=== B AST 接线（`_npc_life_blocks` 里真的接了，且顺序对）===')
    r = {}
    _code, fn = extract_method(src, '_npc_life_blocks')
    if fn is None:
        print('  找不到 _npc_life_blocks')
        return {'B0 方法存在': False}

    calls = {}
    at_home_arg = None
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute):
            # npc_life_mod.place_hint(...) / self.npc_placement.home_of(...)
            base = f.value
            bname = base.id if isinstance(base, ast.Name) else (
                base.attr if isinstance(base, ast.Attribute) else '')
            calls.setdefault('%s.%s' % (bname, f.attr), n.lineno)
            if f.attr == 'place_hint':
                for kw in n.keywords:
                    if kw.arg == 'at_home':
                        at_home_arg = ast.dump(kw.value)

    has_ph = 'npc_life_mod.place_hint' in calls
    has_tr = 'npc_life_mod.scene_traits' in calls
    r['B1 调了 place_hint'] = has_ph
    print('  B1 调 place_hint → %s  %s' % (has_ph, 'OK' if has_ph else '**FAIL**'))

    r['B2 排在 scene_traits 之前'] = bool(has_ph and has_tr and calls['npc_life_mod.place_hint']
                                          < calls['npc_life_mod.scene_traits'])
    print('  B2 顺序 place_hint(%s) < scene_traits(%s) → %s  %s'
          % (calls.get('npc_life_mod.place_hint'), calls.get('npc_life_mod.scene_traits'),
             r['B2 排在 scene_traits 之前'], 'OK' if r['B2 排在 scene_traits 之前'] else '**FAIL**'))

    r['B3 走 home_of 出口'] = 'npc_placement.home_of' in calls
    print('  B3 用 npc_placement.home_of → %s  %s'
          % (r['B3 走 home_of 出口'], 'OK' if r['B3 走 home_of 出口'] else '**FAIL**'))

    # B4：at_home 必须是 `sid == home_id` 这种**比较**，不能硬编码 True/False
    r['B4 at_home 是比较式'] = bool(at_home_arg and 'Compare' in at_home_arg)
    print('  B4 at_home 是 Compare 节点 → %s  %s'
          % (r['B4 at_home 是比较式'], 'OK' if r['B4 at_home 是比较式'] else '**FAIL（可能硬编码）**'))
    return r


# ---------------------------------------------------------------- C
def part_c(src):
    print()
    print('=== C 符号存在 ===')
    r = {}

    tree = ast.parse(src)
    methods = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef):
                    methods.add(fn.name)
    r['C1 _npc_scene_id'] = '_npc_scene_id' in methods
    r['C2 _npc_scene_text'] = '_npc_scene_text' in methods
    print('  C1 _npc_scene_id=%s  C2 _npc_scene_text=%s  %s'
          % (r['C1 _npc_scene_id'], r['C2 _npc_scene_text'],
             'OK' if all(r.values()) else '**FAIL**'))

    # ★ C3 第一版写的是 `callable(getattr(npc_placement, 'home_of'))` —— **判据错了**：
    #   `home_of` 是 `PlacementBook` 的**实例方法**，不是模块级函数。
    #   产品调的是 `self.npc_placement.home_of(npc_id)`，而 `self.npc_placement`
    #   来自 `npc_placement_mod.load_placement(root)` ⇒ 类型是 `PlacementBook`。
    #   ⇒ 改成在**类**上找，并用 AST 确认签名只吃一个参数（多一个就会 TypeError）。
    sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
    import npc_placement as P
    book = getattr(P, 'PlacementBook', None)
    has_home_of = callable(getattr(book, 'home_of', None))
    r['C3 PlacementBook.home_of'] = has_home_of
    print('  C3 PlacementBook.home_of 可调用 → %s  %s'
          % (has_home_of, 'OK' if has_home_of else '**FAIL**'))

    # C5：签名必须只吃一个位置参数 —— 多一个就 `TypeError`（而它被 try 吞掉，
    #     表现为"空间认知永远只剩【你现在在哪】"，静默降级）
    sig_ok = False
    if has_home_of:
        import inspect
        try:
            params = [p for p in inspect.signature(book.home_of).parameters.values()
                      if p.name != 'self']
            pos = [p for p in params if p.kind in (p.POSITIONAL_ONLY,
                                                   p.POSITIONAL_OR_KEYWORD)]
            req = [p for p in pos if p.default is p.empty]
            sig_ok = (len(req) == 1)
            print('  C5 home_of 签名 必填位置参数=%d（应 1）  %s'
                  % (len(req), 'OK' if sig_ok else '**FAIL**'))
        except (ValueError, TypeError) as e:
            print('  C5 读签名失败: %s  **FAIL**' % e)
    r['C5 home_of 单参'] = sig_ok

    names = ('place_hint', 'room_word', 'place_container', 'PLACE_SEP', 'PLACE_JOIN_ALT')
    miss = [n for n in names if not hasattr(L, n)]
    r['C4 npc_life 公开名齐全'] = not miss
    print('  C4 npc_life 缺 %r → %s' % (miss, 'OK' if not miss else '**FAIL**'))
    return r


# ---------------------------------------------------------------- D
class _Place(object):
    def __init__(self, home=None):
        self._home = home

    def home_of(self, npc_id):
        return self._home


class _Stub(object):
    """只提供 `_npc_life_blocks` 真正用到的那几个出口。"""

    npc_life_mod = L
    npc_bonds = None

    def __init__(self, sid, home_sid=None, label=None):
        self._sid = sid
        self.npc_placement = _Place(home_sid)
        self._label = label or (lambda s: '' if not s else 'LBL:%s' % s)

    def _npc_scene_id(self):
        return self._sid

    def _scene_place_label(self, sid):
        return self._label(sid)

    def _npc_scene_text(self):
        return ''

    def _npc_life_ids(self):
        return []

    def _npc_relative_positions(self, *a, **k):
        return {}

    def _npc_display_label(self, nid):
        return ''


def part_d(src):
    print()
    print('=== D 方法级端到端（抽产品里的 `_npc_life_blocks` 整段来跑）===')
    r = {}
    code, _fn = extract_method(src, '_npc_life_blocks')
    if not code:
        print('  抽取失败')
        return {'D0': False}
    ns = {'npc_life_mod': L, '_log': logging.getLogger('verify_j_b')}
    exec(compile(code, '<npc_life_blocks>', 'exec'), ns)
    blocks = ns['_npc_life_blocks']

    # D1 在家：sid == home
    out = blocks(_Stub('ch1.castle_town.castle_town', 'ch1.castle_town.castle_town'), 'ralsei')
    r['D1 在家'] = ('【你现在在哪】' in out and '就是这儿' in out and '想回去' not in out)
    print('  D1 在家 → %s  %s' % ('OK' if r['D1 在家'] else '**FAIL**', ''))
    print('     %r' % out[:110])

    # D2 不在家
    out = blocks(_Stub('uty.rooms.rm_steamworks_29', 'ch1.castle_town.castle_town'), 'ralsei')
    r['D2 不在家'] = ('【你的归属地】' in out and '想回去' in out)
    print('  D2 不在家 → %s' % ('OK' if r['D2 不在家'] else '**FAIL**'))
    print('     %r' % out[:110])

    # D3 无 home（跨作品角色常见：scene=null，只登记 home；这里两个都空）
    out = blocks(_Stub('desktop', None), 'ralsei')
    r['D3 无 home'] = ('【你现在在哪】' in out and '【你的归属地】' not in out)
    print('  D3 无 home → %s' % ('OK' if r['D3 无 home'] else '**FAIL**'))
    print('     %r' % out[:110])

    # D4 位置块必须排在其它块之前（这里只有位置块，验证它在最前面）
    out = blocks(_Stub('ch1.castle_town.castle_town', 'ch1.castle_town.castle_town'), 'ralsei')
    r['D4 位置块在首位'] = out.startswith('【你现在在哪】')
    print('  D4 位置块在最前 → %s' % ('OK' if r['D4 位置块在首位'] else '**FAIL**'))

    # D5 负控制：标签全空 ⇒ **不许**产出一句"你在某个地方"这种空话
    out = blocks(_Stub('', None), 'ralsei')
    r['D5 全空不产块'] = (out == '')
    print('  D5 全空 ⇒ 输出 %r  %s' % (out, 'OK' if r['D5 全空不产块'] else '**FAIL**'))
    return r


def main():
    src = io.open(MAIN, encoding='utf-8', newline='').read()
    a = part_a()
    b = part_b(src)
    c = part_c(src)
    d = part_d(src)
    allr = {}
    allr.update(a)
    allr.update(b)
    allr.update(c)
    allr.update(d)
    bad = [k for k, v in allr.items() if not v]
    print()
    print('判据 %d 条，失败 %d 条%s' % (len(allr), len(bad), ('：' + ', '.join(bad)) if bad else ''))
    print('结论：', 'ALL PASS' if not bad else 'FAIL')
    return 0 if not bad else 3


if __name__ == '__main__':
    sys.exit(main())
