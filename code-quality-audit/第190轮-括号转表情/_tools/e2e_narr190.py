# -*- coding: utf-8 -*-
u"""第190轮续 · 旁白分流的**真机离屏**验证。

真 `QApplication` + 真 `DialogueUI` + 真 `SpriteLoader`（**不桩任何产品代码**），
把窗口 `grab()` 成 png，肉眼可查。

★ 为什么必须真跑：`check190 G` 段用的是**假 self**（只测分流逻辑本身），
  证明不了"旁白真的进了 `_history_html`、真的画在屏幕上、真的有头像"。
★ 跑法：`QT_QPA_PLATFORM=offscreen`，不弹窗、不抢焦点（桌宠是透明置顶窗，
  真机起会盖在用户桌面上）。
"""
import io
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
sys.path.insert(0, MODS)

from PyQt5.QtWidgets import QApplication, QWidget   # noqa: E402

import sprite_loader as SL                          # noqa: E402
import event_speech as E                            # noqa: E402
import dialogue_ui as D                             # noqa: E402

OUT = os.path.join('D:\\', '_tmp190', 'preview')
os.makedirs(OUT, exist_ok=True)


class Host(QWidget):
    """最小宿主：只提供 `DialogueUI` 真正会用到的东西。

    ★ 三个 pending 方法与 `main.RalseiPet` **逐字同语义**（取出即清、两边互清）——
      这里不 import `main`：那会构造整套真机（宠物、场景、AI、托盘），
      几十秒起步，而且和"测一段显示逻辑"没有关系。
    """

    def __init__(self):
        super().__init__()
        self.sprite_loader = SL.SpriteLoader()
        self.emotion_system = None
        self._pending_paren_acts = []
        self._pending_face_emotion = None
        # ★★ 第190轮续二：宿主侧的"表情配动画"钩子。真机上由
        #   `main.RalseiPet.play_expression_anim` 实现（会真正调 play_animation_once），
        #   这里只记录**调用序列**，用来证明"贴脸时确实通知了宿主"。
        self.expr_anim_calls = []

    def play_expression_anim(self, emotion, char_id=None):
        self.expr_anim_calls.append((emotion, char_id))
        return True

    def peek_pending_paren_acts(self):
        return list(self._pending_paren_acts)

    def pop_pending_paren_acts(self):
        v = list(self._pending_paren_acts)
        self._pending_paren_acts = []
        self._pending_face_emotion = None
        return v

    def pop_pending_face_emotion(self):
        v = self._pending_face_emotion
        self._pending_face_emotion = None
        self._pending_paren_acts = []
        return v


#: (台词, 角色 id, 显示名, 期望表情键, 期望旁白片段)
#:   期望值都是**按真实 manifest 算出来的**，不是猜的：
#:     · mooch 的表情只有 `crying/happy/nervous/normal/smile/smirk/smug/surprised`
#:       ⇒ `sad` / `tired` 一张都没有，只能退底图 ⇒ 按用户口径 **走旁白**
#:     · chujin 有 `big_sad`（在 `sad` 的别名链里）⇒ `（苦笑）` 换得出表情
#:   ★ 同一句台词、两只角色、两种结果 —— 这就是"没表情就用旁白"最直观的证明。
CASES = [
    (u'（笑）你好呀，我在呢。', u'hy_mooch', u'Mooch',
     'smile', []),
    (u'（苦笑）算了，没什么。', u'hy_mooch', u'Mooch',
     None, [u'苦笑']),
    (u'（苦笑）算了，没什么。', u'hy_chujin_ketsukane', u'中仁',
     'sad', []),
    (u'（叹气）今天真是累。', u'hy_mooch', u'Mooch',
     None, [u'叹气']),
    (u'（点头）我记住了。', u'hy_chujin_ketsukane', u'中仁',
     'neutral', []),
    (u'（笑）（叹气）你先坐。', u'hy_mooch', u'Mooch',
     'smile', [u'叹气']),
]


def main():
    app = QApplication.instance() or QApplication([])
    host = Host()
    try:
        ui = D.DialogueUI(host)
    except Exception as e:  # noqa: BLE001
        print(u'[!] DialogueUI 构造失败：%s' % e)
        import traceback
        traceback.print_exc()
        return 2

    bad = []
    for line, cid, label, want_face, want_narr in CASES:
        acts = []
        clean = E.strip_action_parentheticals(line, sink=acts)
        host._pending_paren_acts = list(acts)
        host._pending_face_emotion = E.acts_to_emotion(acts)
        # 预先算一遍"产品会怎么分"，便于对账
        face_key, narr = D.DialogueUI.split_acts(
            _RealSelf(ui), cid, acts)
        before = ui._history_html
        try:
            ui.add_npc_line(label, clean, char_id=cid)
        except Exception as e:  # noqa: BLE001
            bad.append((line, u'add_npc_line 抛异常: %s' % e))
            continue
        # ★★ 第190轮续：`add_npc_line` 现在会**清空历史区**（一个框只装当前这一条），
        #   所以不能再按"追加了多少字节"切片 —— 直接看**当前**整段 HTML。
        added = ui._history_html
        has_narr_div = u'font-style:italic' in added
        has_bullet_in_narr = False
        # 旁白行本身不许带 `▸`
        for seg in added.split(u'<div'):
            if u'font-style:italic' in seg and u'\u25b8' in seg:
                has_bullet_in_narr = True
        ok_face = (face_key == want_face)
        ok_narr = (narr == want_narr)
        ok_render = (has_narr_div == bool(want_narr)) and not has_bullet_in_narr
        if not (ok_face and ok_narr and ok_render):
            bad.append((line, u'face=%r(want %r) narr=%r(want %r) 渲染=%s'
                        % (face_key, want_face, narr, want_narr, has_narr_div)))
        print(u'  %-24s acts=%-16r face=%-9r narr=%r 旁白行=%s'
              % (line, acts, face_key, narr, has_narr_div))

    # ★★ 场景交互类（用户：`像是和场景互动比如推开门这类的也不用，
    #   那些是场景能表达出来的`）⇒ 括号**删掉**，但**不许**出旁白、
    #   也**不许**留在台词里（否则屏幕上还是"（推开门）有人吗？"）。
    acts = []
    clean = E.strip_action_parentheticals(u'（推开门）有人吗？', sink=acts)
    host._pending_paren_acts = list(acts)
    host._pending_face_emotion = E.act_to_emotion(acts)
    ui.add_npc_line(u'Mooch', clean, char_id=u'hy_mooch')
    html = ui._history_html
    ok_scene = (u'推开门' not in html) and (u'font-style:italic' not in html)
    if not ok_scene:
        bad.append((u'（推开门）', u'场景类既不该留文字、也不该出旁白'))
    print(u'  （推开门）场景类 -> 文字消失=%s 无旁白=%s'
          % (u'推开门' not in html, u'font-style:italic' not in html))

    # ★★ 一次一条（用户：`别一个对话框装n多条信息`）：连说两句，框里只剩最后一句。
    ui.add_npc_line(u'Mooch', u'第一句', char_id=u'hy_mooch')
    ui.add_npc_line(u'Mooch', u'第二句', char_id=u'hy_mooch')
    html = ui._history_html
    ok_one = ((u'第一句' not in html) and (u'第二句' in html)
              and html.count(u'\u25b8') <= 2)
    if not ok_one:
        bad.append((u'一次一条', u'历史区仍在堆：%r' % html[:200]))
    print(u'  连说两句 -> 只剩最后一句=%s 框内台词行数=%d'
          % (u'第一句' not in html, html.count(u'\u25b8')))

    # 截图定格在"一句台词 + 一条旁白"（**单个框、单条消息**，最能代表本轮效果）
    _a = []
    _c = E.strip_action_parentheticals(u'（叹气）今天真是累。', sink=_a)
    host._pending_paren_acts = list(_a)
    host._pending_face_emotion = E.act_to_emotion(_a)
    ui.add_npc_line(u'Mooch', _c, char_id=u'hy_mooch')

    # ★★ 表情配动画（用户：`角色做出表情的时候原作有些时候也会配合一些
    #   外部动画来加强表示`）：贴脸时必须**通知宿主**，并带上是谁的脸 ——
    #   宿主靠 `char_id` 区分"宠物本体该演"还是"NPC 说话不演"。
    host.expr_anim_calls = []
    ui.set_face('happy')
    ui.set_face('happy', char_id=u'hy_mooch')
    ok_expr = (host.expr_anim_calls
               == [('happy', None), ('happy', u'hy_mooch')])
    if not ok_expr:
        bad.append((u'表情动画钩子', u'调用序列 %r' % (host.expr_anim_calls,)))
    print(u'  表情->动画钩子 -> 调用序列=%r  %s'
          % (host.expr_anim_calls, u'OK' if ok_expr else u'✘'))

    # ★ 动画名必须真存在（写错时 play_animation_once 只静默返回 False）
    import json as _json
    _ap = os.path.join(REPO, 'ralsei_pet', 'assets', 'animations.json')
    with open(_ap, 'r', encoding='utf-8') as _f:
        _groups = set((_json.load(_f).get('groups') or {}).keys())
    _need = set(D.DialogueUI.EXPRESSION_ANIM.values()) | {u'look_up'}
    _miss = sorted(_need - _groups)
    if _miss:
        bad.append((u'动画名', u'这些不在 animations.json 里：%r' % (_miss,)))
    print(u'  动画名核对 -> 用到 %r 缺失 %r' % (sorted(_need), _miss))

    ui.show()
    app.processEvents()
    app.processEvents()
    pm = ui.grab()
    dst = os.path.join(OUT, 'narration190.png')
    ok = pm.save(dst)
    print(u'')
    print(u'[图] %s  %dx%d  saved=%s' % (dst, pm.width(), pm.height(), ok))
    print(u'[结论] %s' % (u'全部符合预期' if not bad else u'不符 %r' % (bad,)))
    return 0 if not bad else 1


class _RealSelf(object):
    """把真 `DialogueUI` 的 `face_has_real` 借给 `split_acts`（不改产品代码）。"""

    def __init__(self, ui):
        self._ui = ui

    def face_has_real(self, char_id, face_type):
        return self._ui.face_has_real(char_id, face_type)


if __name__ == '__main__':
    sys.exit(main())
