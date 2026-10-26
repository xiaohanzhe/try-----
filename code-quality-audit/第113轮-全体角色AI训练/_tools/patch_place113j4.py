# -*- coding: utf-8 -*-
"""第113轮j · 补丁 4：`区名自带 ` · `` 时**换分隔符**，而不是**丢掉末级地名**。

为什么
------
j3 的修法是「区名含 ` · ` ⇒ 不拼名字」，结果：

    oneshot.mainline.FINALE → '主线 · 家/塔/终局'

重复确实没了，但真正的末级地名 `FINALE`（终局场景）也被吞了。
**修一条、丢一条**，对模型的损害比原来更大 —— 它不知道这是终局。
⇒ 改成：区名已含中点时，用 ` — ` 接末级名。

    oneshot.mainline.FINALE → '主线 · 家/塔/终局 — FINALE（OneShot · 世界机器版）'

守门
----
① 两文件都必须**全 CRLF**（`lines - crlf_count in (0, 1)`，末行有无换行的两种都放行）；
② 锚必须 `assert` 命中且**唯一**（`count == 1`）—— `replace(x, y, 1)` 静默改错位置
   在本项目已经栽过，宁可报红；
③ 写回后**回读比对**，且 CRLF 增量 == 预期。
幂等：`PLACE_JOIN_ALT` 已存在 ⇒ 跳过该文件。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)
    got = rd(p)
    assert got == t, '写回与内存不一致：%s' % p


def eol_guard(t, tag):
    lines = len(t.splitlines())
    crlf = t.count('\r\n')
    gap = lines - crlf
    assert gap in (0, 1), '%s 不是全 CRLF：lines=%d crlf=%d gap=%d' % (tag, lines, crlf, gap)
    return crlf


# ---------------------------------------------------------------- npc_life.py
LIFE_OLD = (
    "#: 场景标签的层级分隔符：`区 · 场景名`。\r\n"
    "PLACE_SEP = ' · '\r\n"
)

LIFE_NEW = (
    "#: 场景标签的层级分隔符：`区 · 场景名`。\r\n"
    "PLACE_SEP = ' · '\r\n"
    "\r\n"
    "#: 区名**自己就带** `PLACE_SEP` 时用的替代连接符（第113轮j）。\r\n"
    "#: ★ 为什么需要它：OneShot 的区名是 `主线 · 家/塔/终局`，已经占用了中点。\r\n"
    "#:   再拼场景名就有两种坏结果 —— 要么三段（`主线 · 家/塔/终局 · FINALE`，\r\n"
    "#:   读者分不清哪层是哪层），要么干脆不拼、把末级地名丢掉（`FINALE` 没了，\r\n"
    "#:   模型就不知道这是终局场景）。换一个分隔符两头都能保住。\r\n"
    "PLACE_JOIN_ALT = ' — '\r\n"
)

# ---------------------------------------------------------------- main.py
MAIN_OLD = (
    "        # ④ 区名里**已经带分隔符**（`主线 · 家/塔/终局`）⇒ 不再拼名字，否则三段\r\n"
    "        if npc_life_mod.PLACE_SEP in area_name:\r\n"
    "            label = area_name\r\n"
    "        elif area_name and name and area_name != name:\r\n"
    "            label = area_name + npc_life_mod.PLACE_SEP + name\r\n"
    "        else:\r\n"
    "            label = name or area_name\r\n"
)

MAIN_NEW = (
    "        # ④ 区名**自己带**分隔符（`主线 · 家/塔/终局`）⇒ 换一个分隔符接末级名。\r\n"
    "        #    ★ 早先这里是「直接不拼名字」，结果 `oneshot.mainline.FINALE` 输出成\r\n"
    "        #      「主线 · 家/塔/终局」：重复没了，但真正的末级地名 `FINALE` 也没了 ——\r\n"
    "        #      修一条丢一条，模型反而更不知道自己在哪个场景。\r\n"
    "        if area_name and name and area_name != name:\r\n"
    "            sep = (npc_life_mod.PLACE_JOIN_ALT\r\n"
    "                   if npc_life_mod.PLACE_SEP in area_name\r\n"
    "                   else npc_life_mod.PLACE_SEP)\r\n"
    "            label = area_name + sep + name\r\n"
    "        else:\r\n"
    "            label = name or area_name\r\n"
)


def patch_life():
    t = rd(LIFE)
    eol_guard(t, 'npc_life.py(pre)')
    if 'PLACE_JOIN_ALT' in t:
        print('npc_life.py 已有 PLACE_JOIN_ALT，跳过')
        return len(t.splitlines())
    assert t.count(LIFE_OLD) == 1, 'npc_life.py 锚命中 %d 次（需 1）' % t.count(LIFE_OLD)
    crlf0 = t.count('\r\n')
    t2 = t.replace(LIFE_OLD, LIFE_NEW, 1)
    assert t2 != t, 'npc_life.py 替换无变化'
    assert 'PLACE_JOIN_ALT = \' — \'' in t2, 'npc_life.py 没写进常量'
    need = LIFE_NEW.count('\r\n') - LIFE_OLD.count('\r\n')
    got = t2.count('\r\n') - crlf0
    assert got == need, 'npc_life.py CRLF 增量 %d（应 %d）' % (got, need)
    eol_guard(t2, 'npc_life.py(post)')
    wr(LIFE, t2)
    print('npc_life.py OK 行数=%d CRLF增量=%d' % (len(t2.splitlines()), got))
    return len(t2.splitlines())


def patch_main():
    t = rd(MAIN)
    eol_guard(t, 'main.py(pre)')
    if 'PLACE_JOIN_ALT' in t:
        print('main.py 已有 PLACE_JOIN_ALT，跳过')
        return len(t.splitlines())
    assert t.count(MAIN_OLD) == 1, 'main.py 锚命中 %d 次（需 1）' % t.count(MAIN_OLD)
    crlf0 = t.count('\r\n')
    t2 = t.replace(MAIN_OLD, MAIN_NEW, 1)
    assert t2 != t, 'main.py 替换无变化'
    assert 'npc_life_mod.PLACE_JOIN_ALT' in t2, 'main.py 没用上新常量'
    need = MAIN_NEW.count('\r\n') - MAIN_OLD.count('\r\n')
    got = t2.count('\r\n') - crlf0
    assert got == need, 'main.py CRLF 增量 %d（应 %d）' % (got, need)
    eol_guard(t2, 'main.py(post)')
    wr(MAIN, t2)
    print('main.py OK 行数=%d CRLF增量=%d' % (len(t2.splitlines()), got))
    return len(t2.splitlines())


if __name__ == '__main__':
    patch_life()
    patch_main()
    print('EXIT=0')
    sys.exit(0)
