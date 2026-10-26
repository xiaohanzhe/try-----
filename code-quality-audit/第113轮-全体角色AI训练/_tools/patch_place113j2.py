# -*- coding: utf-8 -*-
"""第113轮j · 修 `_scene_place_label` 的一个真错误：**把内部 id 当名字泄给模型**。

实测（改完第一版之后立刻发现的）：

    uty 章的场景在 `_index.json` 里 `name` 字段存的是**内部 id 本身**
    （`rm_steamworks_29`、`rm_intro`），而不是作品里的名字。
    第一版照抄 ⇒ 输出「【你现在在哪】全部房间 · rm_steamworks_29（黄魂）」——
    正是我在注释里写着"不能给模型看 rm_ 前缀"的那个东西。

两条修法（都是**结构化判据**，不靠"看起来像"）：
  ① `name == sid 的末段` 且 `name.islower()` ⇒ 认定"这个名字其实就是 id"，当无名处理。
     ★ 为什么加 `islower()`：OneShot 的原名是 `Blue` / `FINALE`（有大写），是**真名字**，
       不能一起判掉；内部 id 全是小写+下划线。
  ② 区名是容器名（「全部房间」/ `unzoned`）⇒ 不显示，因为对模型没有信息量。

顺带修：`章名 == 位置名`（desktop 的「桌面（桌面）」）时不加括注。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

FILLER_ANCHOR = "PLACE_SEP = ' · '"
FILLER_NEW = """PLACE_SEP = ' · '

#: 这些**区名**对模型没有信息量（它们是我们的容器，不是作品里的地方）⇒ 不显示。
#: ★ 为什么用白名单式的"已知填充名"而不是"短于 2 字就不要"：
#:   「桌面」只有 2 个字但是真地名，按长度判会把它误删。
PLACE_FILLER = frozenset(('全部房间', 'unzoned', '未分区', 'unknown', '未知'))
"""

OLD_LABEL = '''        sid = str(sid or '').strip()
        if not sid:
            return ''
        info = self._scene_label_map().get(sid)
        if info:
            ch_name, area_name, name = info
            if area_name and name and area_name != name:
                label = area_name + npc_life_mod.PLACE_SEP + name
            else:
                label = name or area_name
            if ch_name and label:
                return '%s（%s）' % (label, ch_name)
            if label or ch_name:
                return label or ch_name
        return npc_life_mod.room_word(sid) or ''
'''

NEW_LABEL = '''        sid = str(sid or '').strip()
        if not sid:
            return ''
        tail = sid.rsplit('.', 1)[-1]
        info = self._scene_label_map().get(sid) or ('', '', '')
        ch_name, area_name, name = info
        # ① 名字其实就是内部 id（全小写且等于末段）⇒ 当无名
        #    ★ `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是真名字，有大写；
        #      黄魂/UT 的 `rm_steamworks_29`/`room_start` 全是小写 —— 两类必须分开。
        if name and name == tail and name.islower():
            name = ''
        # ② 容器名（「全部房间」）不是地方名
        if area_name in npc_life_mod.PLACE_FILLER:
            area_name = ''
        if area_name and name and area_name != name:
            label = area_name + npc_life_mod.PLACE_SEP + name
        else:
            label = name or area_name
        # ③ 连区名都没有 ⇒ 用原作房间 id 的可读形（`rm_steamworks_29` → `steamworks 29`）
        if not label:
            label = npc_life_mod.room_word(sid)
        # ④ 章名与位置同名时不加括注（`桌面（桌面）` 像结巴）
        if ch_name and label and ch_name != label:
            return '%s（%s）' % (label, ch_name)
        return label or ch_name
'''


def main():
    life = io.open(LIFE, encoding='utf-8', newline='').read()
    if 'PLACE_FILLER' not in life:
        if life.count(FILLER_ANCHOR) != 1:
            print('ABORT: npc_life 锚 %d 次' % life.count(FILLER_ANCHOR))
            return 3
        # ★ 必须先把 LF 转 CRLF 再插：npc_life.py 是**全 CRLF** 文件，
        #   直接插 LF 会让 CRLF 数对不上（第一版就是这么被自己的断言拦下的）。
        filler = FILLER_NEW.replace('\n', '\r\n').rstrip('\r\n')
        life2 = life.replace(FILLER_ANCHOR, filler, 1)
        assert life2.count('\r\n') == life.count('\r\n') + filler.count('\r\n'), 'CRLF 数对不上'
        io.open(LIFE, 'wb').write(life2.encode('utf-8'))
        print('npc_life: 加 PLACE_FILLER ✓')
    else:
        print('npc_life: PLACE_FILLER 已存在，跳过')

    t = io.open(MAIN, encoding='utf-8', newline='').read()
    old_crlf = OLD_LABEL.replace('\n', '\r\n')
    new_crlf = NEW_LABEL.replace('\n', '\r\n')
    if t.count(old_crlf) != 1:
        print('ABORT: main.py 旧方法体 %d 次（可能已改过）' % t.count(old_crlf))
        return 3
    t2 = t.replace(old_crlf, new_crlf, 1)
    got = t2.count('\r\n') - t.count('\r\n')
    need = new_crlf.count('\r\n') - old_crlf.count('\r\n')
    if got != need:
        print('ABORT: CRLF 增量 %d ≠ %d' % (got, need))
        return 3
    io.open(MAIN, 'wb').write(t2.encode('utf-8'))
    back = io.open(MAIN, encoding='utf-8', newline='').read()
    print('main: 替换方法体 ✓ | 写回一致 = %s | 行数 %d → %d'
          % (back == t2, len(t.splitlines()), len(back.splitlines())))
    return 0 if back == t2 else 3


if __name__ == '__main__':
    sys.exit(main())
