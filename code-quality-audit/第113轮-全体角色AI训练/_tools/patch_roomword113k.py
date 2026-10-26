# -*- coding: utf-8 -*-
"""第113轮k · 补丁 7：`room_word` 必须剥 **两层** 前缀（`room_dw_*` / `lw_*`）。

问题（第113轮k 调研时实测）
--------------------------
     dw_garden_video       -> 'dw garden video'      ← `dw` 是内部标记，泄给模型
     lw_icee_pizza         -> 'lw icee pizza'
     room_dw_ralsei_castle_front -> ?                ← 剥了 room_ 还留着 dw_

`dw_` = dark world、`lw_` = light world，都是**我们的命名**，不是作品里的词。
第113轮j 的 `room_word` 只剥 `rm_` / `room_`，漏了这两个，而且是**一层**：

    room_dw_xxx  →  剥 room_  →  dw_xxx   ← 还带内部标记

⇒ 改成**循环剥**，直到没有已知前缀。这样 `room_dw_*` 一次到位。

为什么不让调用方拼前缀列表：`room_word` 是"id → 能读的词"的**唯一出口**
（`_scene_place_label` 的兜底、`check113j` 的泄漏判据都走它）。多一处拼装就多一处分叉。

守门与 patch4~6 一致：全 CRLF / 锚唯一 / 回读比对 / CRLF 增量。幂等：见到 `_PREFIXES` 即跳过。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)
    assert rd(p) == t, '写回与内存不一致：%s' % p


OLD = (
    "    s = s.rsplit('.', 1)[-1]\r\n"
    "    # `rm_` = 黄魂/UT 的房间前缀；`room_` = Deltarune 的（`room_dw_ralsei_castle_front`）\r\n"
    "    for _p in ('rm_', 'room_'):\r\n"
    "        if s.startswith(_p):\r\n"
    "            s = s[len(_p):]\r\n"
    "            break\r\n"
)

NEW = (
    "    s = s.rsplit('.', 1)[-1]\r\n"
    "    # ★★ 前缀必须**循环剥**，而且已知前缀是这几个：\r\n"
    "    #   `rm_`   = 黄魂 / UT 的房间\r\n"
    "    #   `room_` = Deltarune 的房间（但它常常**套着**下一层：`room_dw_…`）\r\n"
    "    #   `dw_`   = 暗世界（dark world）· `lw_` = 光世界（light world）\r\n"
    "    # 第113轮j 只剥一层、漏了 dw_/lw_ ⇒ 模型会读到 `dw garden video`。\r\n"
    "    # 这些**全是我们的命名**，不是作品里的词，露出来等于把内部结构塞给模型。\r\n"
    "    # 循环最多剥 4 层（前缀表长度），防止某个畸形名字把循环拖成死循环。\r\n"
    "    _PREFIXES = ('rm_', 'room_', 'dw_', 'lw_')\r\n"
    "    for _ in range(len(_PREFIXES)):\r\n"
    "        for _p in _PREFIXES:\r\n"
    "            if s.startswith(_p):\r\n"
    "                s = s[len(_p):]\r\n"
    "                break\r\n"
    "        else:\r\n"
    "            break\r\n"
)


def main():
    t = rd(LIFE)
    lines = len(t.splitlines())
    gap = lines - t.count('\r\n')
    assert gap in (0, 1), 'npc_life.py 不是全 CRLF：lines=%d gap=%d' % (lines, gap)

    if '_PREFIXES' in t:
        print('npc_life.py 已是循环剥前缀，跳过')
        return 0

    n = t.count(OLD)
    assert n == 1, 'npc_life.py 锚命中 %d 次（需 1）' % n
    c0 = t.count('\r\n')
    t2 = t.replace(OLD, NEW, 1)
    assert t2 != t, '替换无变化'
    assert '_PREFIXES' in t2, '没写进前缀表'
    got = t2.count('\r\n') - c0
    need = NEW.count('\r\n') - OLD.count('\r\n')
    assert got == need, 'CRLF 增量 %d（应 %d）' % (got, need)
    gap2 = len(t2.splitlines()) - t2.count('\r\n')
    assert gap2 in (0, 1), '写回后不是全 CRLF：gap=%d' % gap2

    wr(LIFE, t2)
    print('npc_life.py OK 行数=%d CRLF增量=%d' % (len(t2.splitlines()), got))
    print('EXIT=0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
