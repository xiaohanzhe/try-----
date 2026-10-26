# -*- coding: utf-8 -*-
"""第113轮k-g：翻译表不越权 + 调试区不当去处 + 去掉 id 单字母残留。

三个都是**全量人读**抓到的（6 个样本一条都看不出来）：

1. `Research Station（车站）` —— `station` 在 OneShot 的幽谷里是**研究站**，
   不是火车站。翻译表一旦猜错就是**编造**，比不给中文更糟 ⇒ `station` / `dock`
   两个词**退出** `PLACE_GLOSS`（保留英文原词，模型自己看得懂）。
2. `系统与演出 · shop（商店）` —— `ch5.system` 是 `plat_lab`（平台测试）/
   `rhythmgame_editor`（节奏游戏编辑器）/ `shop_ch5` 三个**调试房**。
   把它们当"去处"推荐，等于让 NPC 把人送进测试关。
3. `Citadel · c asgore kitchen（厨房）` —— `c_` / `a_` / `f_` / `w_` 是 Outertale
   把区名缩写进 id 的产物（`c_asgore_kitchen`）。单字母残留在 prompt 里
   像打错字 ⇒ `strip_room_index` 顺手丢掉**行首的单字母字母 token**。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
MAIN = os.path.join(PET, 'src', 'main.py')
NL = '\r\n'


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(t)


# ---------------------------------------------------------------- 1 · 翻译表
GLOSS_OLD = """    'clinic': '诊所', 'lab': '实验室', 'mine': '矿', 'station': '车站',
    'dock': '码头', 'bank': '银行',
}"""
GLOSS_NEW = """    'clinic': '诊所', 'lab': '实验室', 'mine': '矿', 'bank': '银行',
    # ★★ `station` / `dock` **故意不在这里**（第113轮k 全量人读）：
    #   OneShot 的 `Research Station` 是**研究站**不是火车站、UT 的
    #   `room_fire_dock` 到底是码头还是停靠点我判不准 —— 猜错就是**编造地名**，
    #   比留着英文更糟（模型自己看得懂 `Research Station`）。表格里**只放
    #   我确定**的翻译，宁缺毋滥。
}"""

# ---------------------------------------------------------------- 2 · 调试区
SKIP_ANCHOR = "def place_container(area_name):"
SKIP_ADD = '''#: 这些**区 id** 是我们自己的系统 / 演出 / 调试区，不是作品里的地方 ⇒
#:   **不给"去处"候选**（位置标签照旧显示，人在里面也要知道自己在哪）。
#: ★ 与 `PLACE_FILLER` 分工：那个按**区名**过滤（容器叫「全部房间」），
#:   这个按 **id** 过滤 —— `系统与演出` 读起来像真地名，按名字判会漏；
#:   而 id 是索引结构的一部分、不是文案，按 id 判不会误伤真地名。
#: ★ 实测：`ch5.system` = `plat_lab` / `rhythmgame_editor` / `shop_ch5` 三个**调试房**，
#:   不拦的话 NPC 会建议「那要不去系统与演出那家商店」—— 把人送进测试关。
PLACE_SKIP_AREA_IDS = frozenset(('system', 'unzoned', 'test', 'debug', 'tmp'))


'''

# ---------------------------------------------------------------- 3 · 单字母
STRIP_OLD = '''    toks = [t for t in str(core or '').split() if t]
    while toks and toks[-1].isdigit():
        toks.pop()
    return ' '.join(toks)'''
STRIP_NEW = '''    toks = [t for t in str(core or '').split() if t]
    # ★ 行首的**单字母**是区名缩写（Outertale 的 `c_asgore_kitchen` → `c`）：
    #   留在 prompt 里像打错字。只认行首、只认单个 ASCII 字母 ——
    #   `House 1 - stew` 的 `1`、`tundra inn 2f` 的 `2f` 都不受影响。
    while len(toks) > 1 and len(toks[0]) == 1 and toks[0].isalpha() \\
            and toks[0].isascii():
        toks.pop(0)
    while toks and toks[-1].isdigit():
        toks.pop()
    return ' '.join(toks)'''

STRIP_DOC_OLD = '''    ★ 只去**纯数字**：`tundra inn 2f` 的 `2f` 有意义（二层），不动它。
    """'''
STRIP_DOC_NEW = '''    ★ 只去**纯数字**：`tundra inn 2f` 的 `2f` 有意义（二层），不动它。
    ★ 另去**行首单字母**（`c asgore kitchen` → `asgore kitchen`）：那是 Outertale
      把区名缩写进 id 的产物，不是店名的一部分。第113轮k 全量人读抓到。
    """'''

# ---------------------------------------------------------------- 4 · 接线
WIRE_OLD = '''                parts = sid_s.split('.')
                area_id = parts[1] if len(parts) >= 3 else ''
                core = npc_life_mod.room_word(_raw)'''
WIRE_NEW = '''                parts = sid_s.split('.')
                area_id = parts[1] if len(parts) >= 3 else ''
                # ★ 系统/演出/调试区不是"去处"（位置标签里照旧显示，人得知道自己在哪）
                if area_id in npc_life_mod.PLACE_SKIP_AREA_IDS:
                    continue
                core = npc_life_mod.room_word(_raw)'''

DOC_OLD = '''          3. **只认强信号**（房间名 / 剥过前缀的原作名），**不用区名** ——
             否则「这个区叫希望之园」会被读成「每间房都是公园」。'''
DOC_NEW = '''          3. **只认强信号**（房间名 / 剥过前缀的原作名），**不用区名** ——
             否则「这个区叫希望之园」会被读成「每间房都是公园」。
          4. **系统/演出/调试区一律不算去处**（`PLACE_SKIP_AREA_IDS`）——
             `ch5.system` 是三个调试房，推荐它等于把人送进测试关。'''


def run():
    t = read(LIFE)
    n_ok = 0
    for old, new, tag in (
        (GLOSS_OLD, GLOSS_NEW, 'gloss 去掉 station/dock'),
        (STRIP_DOC_OLD, STRIP_DOC_NEW, 'strip_room_index 文档'),
        (STRIP_OLD, STRIP_NEW, 'strip_room_index 单字母'),
    ):
        old = old.replace('\n', NL)
        new = new.replace('\n', NL)
        if new in t:
            print('[SKIP] %s 已是新版' % tag)
            n_ok += 1
            continue
        if old not in t:
            print('[FAIL] %s 锚点没命中' % tag)
            return 1
        t = t.replace(old, new, 1)
        print('[ OK ] %s' % tag)
        n_ok += 1
    if 'PLACE_SKIP_AREA_IDS = frozenset' not in t:
        if SKIP_ANCHOR not in t:
            print('[FAIL] PLACE_SKIP_AREA_IDS 锚点没命中')
            return 1
        t = t.replace(SKIP_ANCHOR, SKIP_ADD.replace('\n', NL) + SKIP_ANCHOR, 1)
        print('[ OK ] 插入 PLACE_SKIP_AREA_IDS')
    else:
        print('[SKIP] 已有 PLACE_SKIP_AREA_IDS')
    write(LIFE, t)

    m = read(MAIN)
    for old, new, tag in (
        (DOC_OLD, DOC_NEW, 'main 文档串第 4 条'),
        (WIRE_OLD, WIRE_NEW, 'main 调试区接线'),
    ):
        old = old.replace('\n', NL)
        new = new.replace('\n', NL)
        if new in m:
            print('[SKIP] %s 已是新版' % tag)
            continue
        if old not in m:
            print('[FAIL] %s 锚点没命中' % tag)
            return 1
        m = m.replace(old, new, 1)
        print('[ OK ] %s' % tag)
    write(MAIN, m)

    import ast
    for p in (LIFE, MAIN):
        src = read(p)
        try:
            ast.parse(src)
            ok = 'PASS'
        except SyntaxError as e:
            ok = 'FAIL %s' % e
        n = src.count('\n')
        crlf = src.count('\r\n')
        print('%-12s 语法=%s 行=%d CRLF=%d gap=%d' % (
            os.path.basename(p), ok, n, crlf, n - crlf))
    return 0


if __name__ == '__main__':
    sys.exit(run())
