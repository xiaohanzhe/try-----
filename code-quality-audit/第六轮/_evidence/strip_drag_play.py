# -*- coding: utf-8 -*-
"""第六轮 · 重做"拖拽桌面元素玩耍"。

判断依据（用户："自己判断一下，人会不会那么做"）：
  人不会去搬动你桌上的东西；而原实现把 Ralsei **内部模型**里的图标坐标改成
  "被拖走"的样子，再让 Ralsei 每帧 self.move 追这个假坐标 ——
  真实桌面图标根本没动，用户看到的是"对着空气搬东西"，且追假坐标是瞬移来源。

改动：
  A) 删除 handle_dragging_play（含早已不可达的"拖动光标"分支）
  B) start_dragging_play 重写为诚实的"走过去看看某个图标"
  C) 删除 update_movement 里的 dragging_element 分派块（A/B 后已无对象）
"""
import io
import os
import sys

TARGET = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', 'ralsei_pet', 'src', 'main.py'))

NEW_START = u'''    def start_dragging_play(self):
        """"走过去看看某个桌面图标"——不再假装搬动用户的文件。

        第六轮（"人会不会那么做"）：原实现把 Ralsei 内部模型里的图标坐标改成
        "被拖走"的样子，再让 Ralsei 每帧 self.move 追这个假坐标；但真实桌面图标
        根本没动，用户看到的是"对着空气搬东西"，而且追假坐标是一条实打实的瞬移来源。
        现在改成诚实的行为：随便挑一个图标，用正常走路系统走过去，到了歪头看一眼。
        """
        import random
        elements = list(getattr(self.desktop_interaction, 'desktop_elements', None) or [])
        if not elements:
            return
        el = random.choice(elements)
        try:
            tx = int(el.get('x', self.x())) + 60   # 站在图标旁边，不压住它
            ty = int(el.get('y', self.y()))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return
        tx, ty = self._clamp_pos_to_desktop(tx, ty)
        self.target_pos = QPoint(tx, ty)
        self.is_moving = True
        self.current_activity = "looking_around"
        self._pending_look_at_element = True
        self.last_dragging_time = time.time()
'''

# 自底向上：(start, end, kind)
#  kind = 'del' 删除 / 'replace' 用 NEW_START 替换
OPS = [
    (2976, 3070, 'del'),        # handle_dragging_play + 尾随空行
    (2938, 2974, 'replace'),    # start_dragging_play
    (1427, 1435, 'del'),        # update_movement 里的 dragging_element 分派块
]


def main():
    with io.open(TARGET, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print('before lines =', len(lines))

    anchors = {
        2976: 'def handle_dragging_play',
        2938: 'def start_dragging_play',
        1427: '# 处理正在拖动的桌面元素',
    }
    for ln, expect in anchors.items():
        got = lines[ln - 1].strip()
        if expect not in got:
            print('ABORT: line %d expected %r, got %r' % (ln, expect, got))
            return 1

    for start, end, kind in OPS:   # 已按行号降序
        if kind == 'del':
            del lines[start - 1:end]
        else:
            lines[start - 1:end] = [NEW_START]

    print('after lines =', len(lines))
    with io.open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)
    print('written:', TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())
