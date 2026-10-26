# -*- coding: utf-8 -*-
"""第113轮j · 第二轮修 `_scene_place_label`：**推导名**与**容器名**两处真错误。

第一轮验证跑出三条不合格（`verify_place113j.py` 的 A/C 段），逐条查了索引原文：

  ① `ch2.ralsei_room.dw_ralsei_castle_front`
     索引里 `name = '拉尔赛的城堡·castle_front'` **且 `name_derived: true`**
     —— 这个名字是**我们推导出来的**（区名 + 房间 id 末段），不是原作名。
     ⇒ 输出成了「拉尔赛的城堡 · 拉尔赛的城堡·castle_front」：重复一遍还带 id。
     修法：`name_derived` 为真 ⇒ 当**无名**处理，走 `room_word(name_raw)`。

  ② `oneshot.mainline.FINALE`
     **区名本身就带分隔符**（`'主线 · 家/塔/终局'`），再拼场景名就成了三段。
     修法：区名里已有 `PLACE_SEP` ⇒ 不再拼名字。

  ③ `desktop` 的 scene key 是 `'desktop'`（不是 `desktop.desktop.desktop`）
     —— 这条是**我的测试用例写错了**，产品没错。用例已改。

附带：`room_word()` 现在也剥 `room_` 前缀（`room_dw_ralsei_castle_front`
→ `dw ralsei castle front`），否则黄魂/UT 的兜底会带一串 `room_`。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

# ---------------- npc_life: room_word 剥离 room_ 前缀 ----------------
OLD_RW = """    s = s.rsplit('.', 1)[-1]
    if s.startswith('rm_'):
        s = s[len('rm_'):]
"""
NEW_RW = """    s = s.rsplit('.', 1)[-1]
    # `rm_` = 黄魂/UT 的房间前缀；`room_` = Deltarune 的（`room_dw_ralsei_castle_front`）
    for _p in ('rm_', 'room_'):
        if s.startswith(_p):
            s = s[len(_p):]
            break
"""

# ---------------- main: _scene_label_map 改存 5 元组 ----------------
OLD_MAP = """                    for scid, sc in ((ar or {}).get('scenes') or {}).items():
                        m[str(scid)] = (ch_name, area_name,
                                        str((sc or {}).get('name') or ''))
"""
NEW_MAP = """                    for scid, sc in ((ar or {}).get('scenes') or {}).items():
                        sc = sc or {}
                        # ★ 存 5 元组：多带 `name_derived` 与 `name_raw`。
                        #   `name_derived=True` 的名字是我们**推导出来的**
                        #   （区名 + 房间 id 末段），拿它当原作名会既重复又带 id。
                        m[str(scid)] = (ch_name, area_name,
                                        str(sc.get('name') or ''),
                                        bool(sc.get('name_derived')),
                                        str(sc.get('name_raw') or ''))
"""

OLD_LABEL_HEAD = """        tail = sid.rsplit('.', 1)[-1]
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
"""

NEW_LABEL_HEAD = """        tail = sid.rsplit('.', 1)[-1]
        info = self._scene_label_map().get(sid) or ('', '', '', False, '')
        ch_name, area_name, name, derived, raw = info
        # ① `name_derived=True` ⇒ 这个名字是我们**推的**（区名 + id 末段），当无名
        if derived:
            name = ''
        # ② 名字其实就是内部 id（全小写且等于末段）⇒ 当无名
        #    ★ `islower()` 是关键：OneShot 的 `Blue`/`FINALE` 是真名字，有大写；
        #      黄魂/UT 的 `rm_steamworks_29`/`room_start` 全是小写 —— 两类必须分开。
        elif name and name == tail and name.islower():
            name = ''
        # ③ 容器名（「全部房间」）不是地方名
        if area_name in npc_life_mod.PLACE_FILLER:
            area_name = ''
        # ④ 区名里**已经带分隔符**（`主线 · 家/塔/终局`）⇒ 不再拼名字，否则三段
        if npc_life_mod.PLACE_SEP in area_name:
            label = area_name
        elif area_name and name and area_name != name:
            label = area_name + npc_life_mod.PLACE_SEP + name
        else:
            label = name or area_name
        # ⑤ 兜底：原作房间名（`rm_steamworks_29` → `steamworks 29`）
        if not label:
            label = npc_life_mod.room_word(raw) or npc_life_mod.room_word(sid)
"""


def patch(path, pairs):
    t = io.open(path, encoding='utf-8', newline='').read()
    for old, new in pairs:
        o = old.replace('\n', '\r\n')
        n = new.replace('\n', '\r\n')
        if t.count(o) != 1:
            print('ABORT: %s 锚 %d 次 —— %r' % (os.path.basename(path), t.count(o), old[:40]))
            return None
        t2 = t.replace(o, n, 1)
        if t2.count('\r\n') - t.count('\r\n') != n.count('\r\n') - o.count('\r\n'):
            print('ABORT: CRLF 数对不上（%s）' % os.path.basename(path))
            return None
        t = t2
    io.open(path, 'wb').write(t.encode('utf-8'))
    back = io.open(path, encoding='utf-8', newline='').read()
    print('%s ✓ 写回一致=%s 行数=%d' % (os.path.basename(path), back == t, len(back.splitlines())))
    return back == t


def main():
    if not patch(LIFE, [(OLD_RW, NEW_RW)]):
        return 3
    if not patch(MAIN, [(OLD_MAP, NEW_MAP), (OLD_LABEL_HEAD, NEW_LABEL_HEAD)]):
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
