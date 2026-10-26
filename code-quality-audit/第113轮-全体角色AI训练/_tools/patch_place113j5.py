# -*- coding: utf-8 -*-
"""第113轮j · 补丁 5：全量普查（2166 个场景）暴露的两条真错误。

① **容器名漏判 26 条**
   `PLACE_FILLER` 用 `in frozenset` 精确匹配，但索引里实际写作
   `未分区（废弃/调试/演示）` —— 带括注后缀 ⇒ 匹配不上 ⇒ 模型会看到
   「未分区（废弃/调试/演示） · Bedroom」，等于把我们的目录结构泄给它。
   ⇒ 新增 `place_container()`：**去掉括注取主干**再比。

② **场景名自带区名前缀**（`纸牌城堡` + `纸牌城堡·一层`）
   拼出来是「纸牌城堡 · 纸牌城堡·一层」，重复。
   ⇒ 场景名以区名开头时剥掉重复前缀。
   ★ 守门：剥完必须**非空**，且剥之前必须是**完整前缀**（`startswith`），
     不是模糊包含 —— 否则 `原野上` 被 `原野` 剥成 `上`，地名被截断。

守门与 patch4 一致（全 CRLF / 锚唯一 / 回读比对 / CRLF 增量）。幂等：见到 `place_container` 即跳过。
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
    assert rd(p) == t, '写回与内存不一致：%s' % p


def eol_guard(t, tag):
    lines = len(t.splitlines())
    gap = lines - t.count('\r\n')
    assert gap in (0, 1), '%s 不是全 CRLF：lines=%d gap=%d' % (tag, lines, gap)


def swap(t, old, new, tag, must=None):
    """锚唯一 → 替换 → 断言变化 → 断言 CRLF 增量 → 断言必含。返回新文本。"""
    assert t.count(old) == 1, '%s 锚命中 %d 次（需 1）' % (tag, t.count(old))
    c0 = t.count('\r\n')
    t2 = t.replace(old, new, 1)
    assert t2 != t, '%s 替换无变化' % tag
    if must:
        assert must in t2, '%s 没写进 %r' % (tag, must)
    need = new.count('\r\n') - old.count('\r\n')
    got = t2.count('\r\n') - c0
    assert got == need, '%s CRLF 增量 %d（应 %d）' % (tag, got, need)
    eol_guard(t2, tag + '(post)')
    return t2


# ---------------------------------------------------------------- npc_life.py
# 在 PLACE_FILLER 定义之后追加 place_container()。锚取 "PLACE_FILLER = frozenset(...)" 整行 + 其后空行。
LIFE_ANCHOR = (
    "PLACE_FILLER = frozenset(('全部房间', 'unzoned', '未分区', 'unknown', '未知'))\r\n"
    "\r\n"
)

LIFE_ADD = (
    "PLACE_FILLER = frozenset(('全部房间', 'unzoned', '未分区', 'unknown', '未知'))\r\n"
    "\r\n"
    "\r\n"
    "def place_container(area_name):\r\n"
    "    \"\"\"这个**区名**是不是我们自己的容器？⇒ True 表示「不是作品里的地方」。\r\n"
    "\r\n"
    "    ★ 为什么不能只做 `area_name in PLACE_FILLER`：索引里同一类容器有两种写法，\r\n"
    "      带括注的那种（`未分区（废弃/调试/演示）`）精确匹配不上。第113轮j 全量普查\r\n"
    "      因此漏判 **26 条**，模型会在 prompt 里读到「未分区（废弃/调试/演示） · Bedroom」\r\n"
    "      —— 它看到的是我们的目录结构，不是作品里的地名。\r\n"
    "    ★ 只剥**一层**括注取主干：多剥会把 `城堡镇（废墟）` 也误判成容器。\r\n"
    "    \"\"\"\r\n"
    "    s = str(area_name or '').strip()\r\n"
    "    if not s:\r\n"
    "        return False\r\n"
    "    if s in PLACE_FILLER:\r\n"
    "        return True\r\n"
    "    core = s.split('（', 1)[0].split('(', 1)[0].strip()\r\n"
    "    return bool(core) and core in PLACE_FILLER\r\n"
)

# ---------------------------------------------------------------- main.py
MAIN_OLD = (
    "        # ② 名字其实就是内部 id（全小写且等于末段）⇒ 当无名\r\n"
    "        #    ★ `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是真名字，有大写；\r\n"
    "        #      黄魂/UT 的 `rm_steamworks_29`/`room_start` 全是小写 —— 两类必须分开。\r\n"
    "        elif name and name == tail and name.islower():\r\n"
    "            name = ''\r\n"
    "        # ③ 容器名（「全部房间」）不是地方名\r\n"
    "        if area_name in npc_life_mod.PLACE_FILLER:\r\n"
    "            area_name = ''\r\n"
)

MAIN_NEW = (
    "        # ② 名字其实就是内部 id（全小写且等于末段）⇒ 当无名\r\n"
    "        #    ★ `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是真名字，有大写；\r\n"
    "        #      黄魂/UT 的 `rm_steamworks_29`/`room_start` 全是小写 —— 两类必须分开。\r\n"
    "        elif name and name == tail and name.islower():\r\n"
    "            name = ''\r\n"
    "        # ③ 容器名（「全部房间」「未分区（废弃/调试/演示）」）不是地方名\r\n"
    "        #    ★ 必须走 `place_container()`：索引里带括注的写法精确匹配不上，\r\n"
    "        #      第113轮j 全量普查因此漏判 26 条。\r\n"
    "        if npc_life_mod.place_container(area_name):\r\n"
    "            area_name = ''\r\n"
    "        # ③b 场景名**自己已经带着区名**（`纸牌城堡` + `纸牌城堡·一层`）⇒ 剥掉重复前缀。\r\n"
    "        #    ★ 只认**完整前缀**（`startswith`）且剥完必须非空：\r\n"
    "        #      模糊包含会把 `原野上` 用区名 `原野` 剥成 `上` —— 地名被截断比重复更糟。\r\n"
    "        if area_name and name and name != area_name and name.startswith(area_name):\r\n"
    "            _rest = name[len(area_name):].lstrip(' ·-—_')\r\n"
    "            if _rest:\r\n"
    "                name = _rest\r\n"
)


def patch_life():
    t = rd(LIFE)
    eol_guard(t, 'npc_life.py(pre)')
    if 'def place_container' in t:
        print('npc_life.py 已有 place_container，跳过')
        return
    t2 = swap(t, LIFE_ANCHOR, LIFE_ADD, 'npc_life.py', must='def place_container')
    wr(LIFE, t2)
    print('npc_life.py OK 行数=%d' % len(t2.splitlines()))


def patch_main():
    t = rd(MAIN)
    eol_guard(t, 'main.py(pre)')
    if 'place_container' in t:
        print('main.py 已用 place_container，跳过')
        return
    t2 = swap(t, MAIN_OLD, MAIN_NEW, 'main.py', must='npc_life_mod.place_container')
    wr(MAIN, t2)
    print('main.py OK 行数=%d' % len(t2.splitlines()))


if __name__ == '__main__':
    patch_life()
    patch_main()
    print('EXIT=0')
    sys.exit(0)
