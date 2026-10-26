# -*- coding: utf-8 -*-
"""第113轮j · 把「空间认知」接进 NPC 的 prompt（`main.py` 两处插入）。

为什么单独写成脚本而不是就地编辑：`main.py` 是 **16532 行、全 CRLF**，
用编辑器改一个字都会把整份文件的 EOL 换掉（第113轮i 已经踩过一次：
94 个 CRLF 被抹成 LF，而当时的 EOL 判据只判"有没有 CRLF"，照样绿）。
本脚本用 `keepends` 思路之外的最简做法：**整文件读 → 精确子串替换 → 断言 CRLF 增量
正好等于插入内容里的 CRLF 数 → 写回 → 回读比对**。

两处插入：
  ① 在 `_npc_life_blocks` 之前加两个方法：`_scene_label_map()` / `_scene_place_label()`；
  ② 在 `_npc_life_blocks` 的 `out = []` 之后、`try: scene_traits(...)` 之前，
     插入「⓪ 空间认知」分片。

幂等：已插过就跳过（用 `_scene_place_label` 是否已存在判断）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

METHODS = '''    def _scene_label_map(self):
        """懒加载 `assets/scenes/_index.json` → `{scene_id: (章名, 区名, 场景名)}`。

        ★ 读不到 ⇒ 空表（`{}`），**不是异常**：位置块会退回 `room_word()`，
          整条链路仍然可用 —— 这是本项目"读不到就返回空、不抛"的一贯做法。
        ★ 为什么缓存：索引里有 2166 个场景；NPC 一分钟可能开口好几次，
          每次都重读 400KB JSON 纯属浪费（`_scene_labels` 为 `None` 才算没读过）。
        """
        cached = getattr(self, '_scene_labels', None)
        if cached is not None:
            return cached
        m = {}
        try:
            path = os.path.join(project_root, 'assets', 'scenes', '_index.json')
            with open(path, 'r', encoding='utf-8') as fh:
                idx = json.load(fh)
            for _cid, ch in ((idx or {}).get('chapters') or {}).items():
                ch_name = str((ch or {}).get('name') or '')
                for _aid, ar in ((ch or {}).get('areas') or {}).items():
                    area_name = str((ar or {}).get('name') or '')
                    for scid, sc in ((ar or {}).get('scenes') or {}).items():
                        m[str(scid)] = (ch_name, area_name,
                                        str((sc or {}).get('name') or ''))
        except Exception as e:
            _log.debug('场景索引读取失败（位置块退回 room_word）: %s', e)
            m = {}
        self._scene_labels = m
        return m

    def _scene_place_label(self, sid):
        """场景 id → 可读标签 `区 · 场景名（章名）`；取不到 ⇒ `''`（**不猜**）。

        ★ 三级回落，每级**只从已有数据里取**：
          ① `_index.json` 的 `name`（Deltarune 有中文名、OneShot 是英文原题）；
          ② 没有名字 ⇒ `npc_life.room_word(sid)`（`rm_steamworks_29` → `steamworks 29`）；
          ③ 连 id 都没有 ⇒ `''`，调用方据此**不产块**（不写"你在某个地方"这种废话）。
        ★ 区名 == 场景名时只留一个：`城堡镇 · 城堡镇（第一章 · 黑暗世界）` 读起来像结巴。
        """
        sid = str(sid or '').strip()
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

BLOCK = '''        # ---- ⓪ 空间认知（★ 第113轮j）：他得先知道"自己在哪儿" ----
        #   ★ 为什么排在【你周围】之前：位置是**坐标事实**，"这地方什么样"是在它之上
        #     的描述。顺序反了，模型先读到"这里很安静"再读到"你在城堡镇"，
        #     就容易把地点当成形容气氛的词去发挥。
        #   ★ home 走 `npc_placement.home_of()`（登记 home > 回落 scene > None），
        #     与"回家 / 就寝"用的是**同一个出口** ⇒ 不会出现"它以为家在 A、
        #     roam 却把它送回 B"这种同一事实两处算的分叉。
        #   ★ 任何一步失败都只 `debug` 掉：位置块是增益，不该把整句 prompt 拖垮。
        try:
            sid = self._npc_scene_id()
            home_id = None
            try:
                if self.npc_placement is not None:
                    home_id = self.npc_placement.home_of(npc_id)
            except Exception as e:
                _log.debug('归属地解析失败（按无 home 处理）: %s', e)
            here_txt = self._scene_place_label(sid)
            home_txt = self._scene_place_label(home_id)
            if here_txt or home_txt:
                ph = npc_life_mod.place_hint(
                    here=here_txt, home=home_txt,
                    at_home=bool(sid and home_id and sid == home_id))
                if ph:
                    out.append(ph)
        except Exception as e:
            _log.debug('空间认知分片失败（已忽略）: %s', e)
'''

A_METHOD = '    def _npc_life_blocks(self, npc_id):'
A_OUT = '        out = []'
A_TRY = '        try:\r\n            traits = npc_life_mod.scene_traits(self._npc_scene_text())'


def main():
    t = io.open(MAIN, encoding='utf-8', newline='').read()
    if '_scene_place_label' in t:
        print('已插过（`_scene_place_label` 存在）⇒ 跳过')
        return 0
    # ★ 守门只要求"除最后一行外全是 CRLF"：文件末尾**没有**换行时，
    #   `splitlines()` 仍算它一行 ⇒ CRLF 数会比行数少 1。这不是问题。
    _gap = len(t.splitlines()) - t.count('\r\n')
    if _gap not in (0, 1):
        print('ABORT: main.py 不是全 CRLF（%d CRLF / %d 行，差 %d）—— 先查清再改'
              % (t.count('\r\n'), len(t.splitlines()), _gap))
        return 3

    if t.count(A_METHOD) != 1:
        print('ABORT: 方法锚 %d 次' % t.count(A_METHOD))
        return 3
    if t.count(A_TRY) != 1:
        print('ABORT: 注入锚 %d 次' % t.count(A_TRY))
        return 3

    methods_crlf = METHODS.replace('\n', '\r\n')
    t2 = t.replace(A_METHOD, methods_crlf + A_METHOD, 1)

    block_crlf = BLOCK.replace('\n', '\r\n')
    # 把 `out = []` + 紧随的 `try:` 拆成 `out = []` + BLOCK + `try:`
    t2 = t2.replace(A_TRY, block_crlf + A_TRY, 1)

    need = methods_crlf.count('\r\n') + block_crlf.count('\r\n')
    got = t2.count('\r\n') - t.count('\r\n')
    if got != need:
        print('ABORT: CRLF 增量 %d ≠ 预期 %d' % (got, need))
        return 3

    io.open(MAIN, 'wb').write(t2.encode('utf-8'))
    back = io.open(MAIN, encoding='utf-8', newline='').read()
    ok = (back == t2)
    print('写回一致 = %s | 行数 %d → %d | CRLF %d → %d'
          % (ok, len(t.splitlines()), len(back.splitlines()),
             t.count('\r\n'), back.count('\r\n')))
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
