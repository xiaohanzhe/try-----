# -*- coding: utf-8 -*-
"""第113轮m：地名标签收尾（`Bedroom` 复合词 + 位置块大小写统一）。

两处改动，都是"读一眼就能看出不对"的残留：

① `npc_life.trim_core_at_type`：`Bed_room` 被截成 `Bed`（一张床）。
   根因：`room_word('Bed_room')` ⇒ `bed room`，`place_matches` 命中的是 `bed`
   且在**首位** ⇒ 截到第一个词就停了。而 `bedroom` 本身就是类型词，
   应该把 `bed` + `room` 先合成 `bedroom` 再判。

② `main._scene_place_label`：位置块仍是 `town square`（原始小写），
   活动块却是 `Town Square`。同一份 prompt 里两种写法，模型会挑一个照抄。
   ⇒ 拼章名**之前**过一遍 `speakable_en`（对中文无副作用，且幂等）。

★ 两个文件都是全 CRLF。用 `newline=''` 读写 + **CRLF 锚点**替换，
  改不动就 assert 失败（`.replace()` 没命中必须报错，不能静默当成功）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def crlf(s):
    return s.replace('\n', '\r\n')


def patch(path, pairs):
    raw = io.open(path, 'r', encoding='utf-8', newline='').read()
    for i, (old, new) in enumerate(pairs, 1):
        o, n = crlf(old), crlf(new)
        if o not in raw:
            print('[中止] %s 第 %d 段锚点没命中' % (os.path.basename(path), i))
            print('       期望片段：%r' % o[:80])
            return False
        if raw.count(o) != 1:
            print('[中止] %s 第 %d 段锚点命中 %d 次（要求恰好 1 次）'
                  % (os.path.basename(path), i, raw.count(o)))
            return False
        raw = raw.replace(o, n)
    io.open(path, 'w', encoding='utf-8', newline='').write(raw)
    print('[OK] %s（%d 段）' % (os.path.basename(path), len(pairs)))
    return True


LIFE_OLD_1 = '''def trim_core_at_type(core, hits):'''
LIFE_NEW_1 = '''#: 两个词**拼起来**才是类型词的复合词：`bed` + `room` ⇒ `bedroom`。
#: ★ 为什么需要（实测）：OneShot 的 `Bed_room` 经 `room_word` 变成 `bed room`，
#:   `place_matches` 命中的是 `bed`（在**首位**）⇒ `trim_core_at_type` 在第一个词
#:   就截断，标签成了 `Barrens · Bed`（一张床）。而 `bedroom` 本身就是类型词。
#: ★ 只认**拼接结果真的在词表里**的：`coffee`+`shop` = `coffeeshop` 不在表里 ⇒
#:   **不合并**。宁可少合，也不要把两个词硬拼成一个不存在的新名字。
_TYPE_VOCAB = frozenset(
    list(PLACE_GLOSS.keys())
    + [w for _t in PLACE_WORDS.values() for w in _t.get('en', ())])


def _merge_type_compounds(toks):
    """相邻两个词拼起来是类型词 ⇒ 合成一个：`['bed','room']` ⇒ `['bedroom']`。"""
    out = []
    for t in toks:
        if out and (out[-1] + t).lower() in _TYPE_VOCAB:
            out[-1] = out[-1] + t
            continue
        out.append(t)
    return out


def trim_core_at_type(core, hits):'''

LIFE_OLD_2 = '''    toks = str(core or '').split()
    if len(toks) < 2:
        return ' '.join(toks)'''
LIFE_NEW_2 = '''    # ★ 先合复合词再判：`bed room` ⇒ `bedroom`（否则会在 `bed` 处截断成「床」）。
    toks = _merge_type_compounds(str(core or '').split())
    if len(toks) < 2:
        return ' '.join(toks)'''

MAIN_OLD = '''        # ⑤ 兜底：原作房间名（`rm_steamworks_29` → `steamworks 29`）
        if not label:
            label = npc_life_mod.room_word(raw) or npc_life_mod.room_word(sid)'''
MAIN_NEW = '''        # ⑤ 兜底：原作房间名（`rm_steamworks_29` → `steamworks 29`）
        if not label:
            label = npc_life_mod.room_word(raw) or npc_life_mod.room_word(sid)
        # ⑥ 英文整形：`town square` ⇒ `Town Square`。
        #    ★ 为什么必须做：活动块早就走 `speakable_en`（`Town Square`），位置块却是
        #      原始小写 `town square` —— 同一份 prompt 两种写法，模型会挑一个照抄。
        #      ★ 放在**拼章名之前**：章名括注是中文（`（第一章 · 黑暗世界）`），
        #      分开做能保证"地名部分"逐字可测。
        #    ★ 幂等：活动候选那一支（`with_chapter=False`）还会再过一次
        #      `place_label` → `speakable_en`；Title Case 幂等、`'s` 有守卫，两遍一样。
        #    ★ 对中文无副作用：`纸牌城堡 · 一层` 逐字不变（`·` 不是词）。
        if label:
            label = npc_life_mod.speakable_en(label, proper=self._place_proper())'''


def main():
    ok = patch(LIFE, [(LIFE_OLD_1, LIFE_NEW_1), (LIFE_OLD_2, LIFE_NEW_2)])
    if not ok:
        return 2
    ok = patch(MAIN, [(MAIN_OLD, MAIN_NEW)])
    if not ok:
        return 3
    # 语法自证：改了必须能编译（用 ast，不产 .pyc）
    import ast
    for p in (LIFE, MAIN):
        ast.parse(io.open(p, encoding='utf-8').read())
        print('[OK] ast.parse %s' % os.path.basename(p))
    return 0


if __name__ == '__main__':
    sys.exit(main())
