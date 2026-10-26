# -*- coding: utf-8 -*-
"""第113轮j · 补丁 6：混合大小写的内部 id（`rm_dalvExit`）泄给模型。

问题
----
② 原来只判 `name.islower()`，用来保护 `FINALE`/`Blue` 这类真名字（它们有大写）。
但黄魂有 4 个房间是**混合大小写**的内部 id：

    uty.rooms.rm_dalvExit             name = 'rm_dalvExit'
    uty.rooms.rm_dalvExit_genocide    name = 'rm_dalvExit_genocide'
    uty.rooms.rm_dalvExit_pacifist    name = 'rm_dalvExit_pacifist'
    uty.rooms.rm_dunes_19B            name = 'rm_dunes_19B'

`islower()` 为 False ⇒ 被当"真名字"保留 ⇒ 模型读到「rm_dalvExit（黄魂 · …）」。

修法（**结构化判据**，不看字面）
------------------------------
加一条：**`room_word(name)` 会改动它** ⇒ 它是 id 形态。
  `rm_dalvExit`  → `dalvExit`      改了 ⇒ 判为 id ⇒ 走 ⑤ 兜底
  `FINALE`       → `FINALE`        没改 ⇒ 真名字，保留
  `TESTROOM`     → `TESTROOM`      没改 ⇒ 保留

为什么不写成「`name.startswith('rm_')`」：那只是把上一版的字面判断换个字面，
再多一种前缀（`room_`、别的作品前缀）就又要改。`room_word` 本来就是
"把 id 变成能读的词"的唯一出口，用它的**行为差异**判，跟着它一起演进。

守门与 patch5 一致。幂等：见到 `name != npc_life_mod.room_word(name)` 即跳过。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


OLD = (
    "        # ② 名字其实就是内部 id（全小写且等于末段）⇒ 当无名\r\n"
    "        #    ★ `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是真名字，有大写；\r\n"
    "        #      黄魂/UT 的 `rm_steamworks_29`/`room_start` 全是小写 —— 两类必须分开。\r\n"
    "        elif name and name == tail and name.islower():\r\n"
    "            name = ''\r\n"
)

NEW = (
    "        # ② 名字其实就是内部 id ⇒ 当无名，交给 ⑤ 用 `room_word` 转成能读的词。\r\n"
    "        #    ★ 两条判据缺一不可：\r\n"
    "        #      a) 全小写且等于末段（`bullettest` / `room_start`）——\r\n"
    "        #         `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是大写真名字。\r\n"
    "        #      b) **`room_word()` 会改动它**（`rm_dalvExit` → `dalvExit`）——\r\n"
    "        #         黄魂那 4 个混合大小写的 id 靠 a 判不出来，全量普查才抓到。\r\n"
    "        #    ★ 为什么不写 `startswith('rm_')`：那是把字面判断换个字面，\r\n"
    "        #      再多一种前缀就又要改。`room_word` 是 id→可读词的唯一出口，\r\n"
    "        #      用它的**行为差异**判，它演进时这里自动跟着走。\r\n"
    "        elif (name and name == tail\r\n"
    "              and (name.islower() or name != npc_life_mod.room_word(name))):\r\n"
    "            name = ''\r\n"
)


def main():
    t = rd(MAIN)
    lines = len(t.splitlines())
    gap = lines - t.count('\r\n')
    assert gap in (0, 1), 'main.py 不是全 CRLF：lines=%d gap=%d' % (lines, gap)

    if 'name != npc_life_mod.room_word(name)' in t:
        print('main.py 已是新判据，跳过')
        return 0

    n = t.count(OLD)
    assert n == 1, 'main.py 锚命中 %d 次（需 1）' % n
    c0 = t.count('\r\n')
    t2 = t.replace(OLD, NEW, 1)
    assert t2 != t, '替换无变化'
    assert 'name != npc_life_mod.room_word(name)' in t2, '没写进新判据'
    got = t2.count('\r\n') - c0
    need = NEW.count('\r\n') - OLD.count('\r\n')
    assert got == need, 'CRLF 增量 %d（应 %d）' % (got, need)
    gap2 = len(t2.splitlines()) - t2.count('\r\n')
    assert gap2 in (0, 1), '写回后不是全 CRLF：gap=%d' % gap2

    io.open(MAIN, 'w', encoding='utf-8', newline='').write(t2)
    assert rd(MAIN) == t2, '写回与内存不一致'
    print('main.py OK 行数=%d CRLF增量=%d' % (len(t2.splitlines()), got))
    print('EXIT=0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
