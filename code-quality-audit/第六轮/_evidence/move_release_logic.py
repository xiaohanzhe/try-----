# -*- coding: utf-8 -*-
"""第六轮 · 把"放手/甩飞判定"从 mouseMoveEvent 搬到 mouseReleaseEvent。

为什么这是"动作的触发逻辑完全不对"的主要根因：
  · 判定写在 mouseMoveEvent 的 `else`（左键已松开）分支里 —— 也就是说
    "松手"这件事只有**再动一次鼠标**才会被处理。
  · 后果一：甩出去后手一停（最常见的甩法），松开时没有后续 move 事件，
    甩飞永远不触发。
  · 后果二：松手后过一会儿随便挪一下鼠标，才用**过期采样**补触发一次甩飞 ——
    表现就是"过几秒突然自己飞出去/瞬移一下"。
搬到 mouseReleaseEvent（真正的松手事件）后，这两个毛病一起消失。

同时给"长按部位反应"加 `not is_falling` 守卫：被甩飞时不再顺带触发捏脸/拉手臂台词。
"""
import io
import os
import sys

TARGET = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', 'ralsei_pet', 'src', 'main.py'))

BLOCK_START = 4579          # "# 处理拖拽释放时的物理反馈效果"
BLOCK_END = 4687            # "delattr(self, '_last_drag_pos')"
INSERT_AFTER = 4827         # mouseReleaseEvent 里 "delattr(self, '_drag_speed')"
LONGPRESS_LINE = 4829       # "if hasattr(self, '_pet_detection_state') ..."


def main():
    with io.open(TARGET, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print('before lines =', len(lines))

    if '处理拖拽释放时的物理反馈效果' not in lines[BLOCK_START - 1]:
        print('ABORT: block start mismatch:', repr(lines[BLOCK_START - 1]))
        return 1
    if "delattr(self, '_last_drag_pos')" not in lines[BLOCK_END - 1]:
        print('ABORT: block end mismatch:', repr(lines[BLOCK_END - 1]))
        return 1
    if "delattr(self, '_drag_speed')" not in lines[INSERT_AFTER - 1]:
        print('ABORT: insert anchor mismatch:', repr(lines[INSERT_AFTER - 1]))
        return 1
    if '_pet_detection_state' not in lines[LONGPRESS_LINE - 1]:
        print('ABORT: longpress anchor mismatch:', repr(lines[LONGPRESS_LINE - 1]))
        return 1

    block = lines[BLOCK_START - 1:BLOCK_END]      # 含两端
    rest = lines[:BLOCK_START - 1] + lines[BLOCK_END:]
    # 行号平移：插入点在删除区间之后
    shift = (BLOCK_END - BLOCK_START + 1)
    insert_at = INSERT_AFTER - shift              # 0-based 索引：插在 anchor 行之后

    header = [
        u"            # ===== 松手判定（第六轮从 mouseMoveEvent 搬来）=====\n",
        u"            # 原来这段写在 mouseMoveEvent 的\"左键已松开\"分支里：只有再动一次\n",
        u"            # 鼠标才会被处理。甩出去后手一停就永远不触发；松手后随便挪一下\n",
        u"            # 鼠标又会用过期采样补触发 —— 表现就是\"过一会儿自己飞一下\"。\n",
        u"            # 松手就该在 mouseReleaseEvent 处理。\n",
    ]
    rest[insert_at:insert_at] = header + block

    # 长按部位反应加守卫（在插入之后重新定位）
    for i, ln in enumerate(rest):
        if ("if hasattr(self, '_pet_detection_state') and "
                "self._pet_detection_state['is_pressing']:") in ln:
            rest[i] = ln.replace(
                "self._pet_detection_state['is_pressing']:",
                "self._pet_detection_state['is_pressing'] and not getattr(self, 'is_falling', False):")
            print('guarded long-press at line', i + 1)
            break
    else:
        print('WARN: long-press guard anchor not found')

    print('after lines =', len(rest))
    with io.open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.writelines(rest)
    print('written:', TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())
