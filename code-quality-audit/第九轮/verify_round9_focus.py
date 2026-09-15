# -*- coding: utf-8 -*-
"""第九轮验证：对话注意力 / 对话框自动隐藏 / 自主开口不打断聊天。

四组断言：
  A. conversation_focus 纯逻辑（话题归属、悬置问题、冷场归档、brief 出口、快照容错）
  B. dialogue_ui 行为（has_active_conversation / _auto_hide_blocked / _mouse_on_input /
     _schedule_auto_hide / _try_auto_hide / _note_focus），用 SimpleNamespace 桩 + 真实方法绑定
  C. 源码级契约（main / ai_driver / dialogue_ui 的关键接线），用 tokenize 剥注释与字符串
  D. 回归护栏（阈值常量、鼠标压下不得改 _last_activity）

必须用 C:\\Python311\\python.exe 运行（PyQt5）。
"""
import ast
import io
import os
import sys
import time
import tokenize
import types
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
for p in (MODS, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

import conversation_focus as CF  # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name + ('' if cond else '   <<< ' + str(detail)))


# --------------------------------------------------------------------- helpers
def read(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


def code_only(src):
    """剥掉注释与字符串字面量（防止"已删的字面量"被误判为还在）。"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                out.append('\n')
            else:
                out.append(tok.string)
    except Exception:
        return src
    return ''.join(out)


def func_src(src, name):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ''
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ''
    return ''


def method(cls, name):
    fn = getattr(cls, name, None)
    if fn is None:
        raise AssertionError('method not found: %s' % name)
    return fn


# ===================================================================== A. focus
def test_focus():
    print('\n[A] conversation_focus 纯逻辑')
    kws = CF.extract_keywords('我们聊聊今天的天气怎么样')
    ok('A1 关键词：抽到"天气"、剔除虚词', ('天气' in kws) and ('我们' not in kws) and ('怎么样' not in kws), kws)
    ok('A2 空串 → 空关键词', CF.extract_keywords('') == [], None)

    f = CF.ConversationFocus()
    r1 = f.note_user('今天想聊聊塞尔达这游戏的剧情')
    lab1 = f.current_label()
    ok('A3 首句 → new 并建题', r1 == 'new' and lab1 != '', (r1, lab1))

    r2 = f.note_user('塞尔达这游戏的剧情我觉得挺有意思')
    ok('A4 同题继续 → continue', r2 == 'continue' and f.current_label() == lab1, (r2, f.current_label()))

    r3 = f.note_user('对了 C++ 模板元编程的编译期计算怎么优化')
    ok('A5 用户换题 → switch 且标签变化', r3 == 'switch' and f.current_label() != lab1, (r3, f.current_label()))

    f2 = CF.ConversationFocus()
    f2.note_user('我们在说这个游戏的剧情')
    lab2 = f2.current_label()
    r4 = f2.note_user('继续')
    ok('A6 接力标记"继续" → continue（不换题）', r4 == 'continue' and f2.current_label() == lab2, (r4, f2.current_label()))

    f3 = CF.ConversationFocus()
    f3.note_user('聊游戏')
    lab3 = f3.current_label()
    f3.note_assistant('那你想聊聊完全不同的量子物理吗？')
    ok('A7 助手说话不得改话题（换题权只在用户）', f3.current_label() == lab3, f3.current_label())

    f4 = CF.ConversationFocus()
    f4.note_user('聊游戏')
    f4.note_assistant('你最喜欢哪个角色呢？')
    ok('A8 助手抛问 → 登记 pending', f4.pending_question() is not None, f4.pending_question())
    f4.clear_pending()
    ok('A9 clear_pending 后无 pending', f4.pending_question() is None, None)

    f5 = CF.ConversationFocus()
    f5.note_user('聊游戏', )
    f5.topic.last_at = time.time() - (CF.ConversationFocus.IDLE_ARCHIVE_SECONDS + 60)
    r5 = f5.note_user('我们聊聊量子物理吧')
    ok('A10 冷场超时 → 归档并重开', r5 == 'new' and len(f5.history) >= 1, (r5, len(f5.history)))

    f6 = CF.ConversationFocus()
    f6.note_user('聊游戏')
    f6.note_assistant('要不要试试这个？')
    f6.topic.pending = [(f6.topic.pending[-1][0], time.time() - (CF.ConversationFocus.PENDING_TTL + 60))]
    ok('A11 pending 超时后不再追问', f6.pending_question() is None, None)

    ok('A12 无话题时 brief 为空串', CF.ConversationFocus().brief() == '', None)

    f7 = CF.ConversationFocus()
    f7.note_user('今天想聊聊塞尔达这游戏的剧情')
    b = f7.brief()
    ok('A13 brief 含焦点标识与"继续本话题"指令',
       ('注意力焦点' in b) and ('继续这个话题' in b) and ('塞尔达' in b), b[:120])
    f7.note_assistant('你最喜欢哪个角色呢？')
    b2 = f7.brief()
    ok('A14 brief 含"未回应"提醒', '还没有回应' in b2, b2[:160])
    f7.topic.turns = CF.ConversationFocus.MAX_TURNS_BEFORE_REFRESH
    ok('A15 聊太久 → brief 提示收一收', '收一收' in f7.brief(), None)

    f8 = CF.ConversationFocus()
    f8.note_user('今天想聊聊塞尔达这游戏的剧情')
    f8.note_assistant('你最喜欢哪个角色呢？')
    snap = f8.snapshot()
    f9 = CF.ConversationFocus()
    f9.restore(snap)
    ok('A16 snapshot/restore 往返一致',
       f9.current_label() == f8.current_label()
       and f9.topic.turns == f8.topic.turns
       and set(f9.topic.keywords) == set(f8.topic.keywords), (f9.current_label(), f9.topic.turns))
    f10 = CF.ConversationFocus()
    for junk in (None, 123, 'x', {'topic': 'bad'}, {'topic': {'keywords': 'no'}}):
        f10.restore(junk)
        f10.note_user('随便说点什么')   # 坏数据后仍可用
    ok('A17 坏快照不致崩且仍可用', True, None)

    # 标签质量 & 滑窗碎片（第九轮修：原来 label 取 keywords[0] 会得到"今天"）
    f11 = CF.ConversationFocus()
    f11.note_user('今天想聊聊塞尔达这游戏的剧情')
    ok('A18 话题标签取具体词而非时间词', f11.current_label() == '塞尔达', f11.current_label())
    k2 = CF.extract_keywords('今天想聊聊塞尔达这游戏的剧情')
    ok('A19 滑窗碎片被剪掉（无"达这游"/"聊天的"）',
       ('达这游' not in k2) and ('聊天的' not in k2) and ('塞尔达' in k2), k2)
    k3 = CF.extract_keywords('我们聊聊今天的天气怎么样')
    ok('A20 虚词开头的话题仍能抽到（"天气"）', '天气' in k3 and '今天' not in k3, k3)


# ================================================================ B. dialogue_ui
def test_dialogue_ui():
    print('\n[B] dialogue_ui 行为（桩 + 真实方法绑定）')
    import dialogue_ui as DU

    D = DU.DialogueUI

    def stub(**kw):
        s = SimpleNamespace()
        s._ai_inflight = False
        s.is_typing = False
        s._last_activity = time.time()
        s.ACTIVE_CONVERSATION_SECONDS = D.ACTIVE_CONVERSATION_SECONDS
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def bind(s, name, cls=D):
        setattr(s, name, types.MethodType(method(cls, name), s))
        return s

    # has_active_conversation
    s = bind(stub(_last_activity=time.time()), 'has_active_conversation')
    s._is_user_inputting = lambda: False
    ok('B1 刚聊过 → 正在聊天', s.has_active_conversation() is True, None)
    s2 = bind(stub(_last_activity=time.time() - 1000), 'has_active_conversation')
    s2._is_user_inputting = lambda: False
    ok('B2 很久没动静 → 非聊天中', s2.has_active_conversation() is False, None)
    s3 = bind(stub(_last_activity=time.time() - 1000, _ai_inflight=True), 'has_active_conversation')
    s3._is_user_inputting = lambda: False
    ok('B3 模型思考中 → 算聊天中', s3.has_active_conversation() is True, None)
    s4 = bind(stub(_last_activity=time.time() - 1000, is_typing=True), 'has_active_conversation')
    s4._is_user_inputting = lambda: False
    ok('B4 正在打字 → 算聊天中', s4.has_active_conversation() is True, None)
    s5 = bind(stub(_last_activity=time.time() - 1000), 'has_active_conversation')
    s5._is_user_inputting = lambda: True
    ok('B5 用户正在输入 → 算聊天中', s5.has_active_conversation() is True, None)
    s6 = bind(stub(_last_activity=time.time() - 200), 'has_active_conversation')
    s6._is_user_inputting = lambda: False
    ok('B6 窗口可覆盖（window=300 → True）', s6.has_active_conversation(300.0) is True, None)

    # _mouse_on_input：用假输入栏 + 注入坐标
    from PyQt5.QtCore import QRect, QPoint

    class FakeBar(object):
        def __init__(self, rect, origin):
            self._r, self._o = rect, origin
        def isVisible(self):
            return True
        def rect(self):
            return self._r
        def mapFromGlobal(self, gp):
            return QPoint(gp.x() - self._o.x(), gp.y() - self._o.y())

    def mk_mouse(bar):
        s = SimpleNamespace(_input_bar=bar)
        return bind(s, '_mouse_on_input')

    bar = FakeBar(QRect(0, 0, 200, 40), QPoint(1000, 700))
    m = mk_mouse(bar)
    ok('B7 鼠标在输入栏内 → True', m._mouse_on_input(QPoint(1100, 720)) is True, None)
    ok('B8 鼠标在输入栏外 → False', m._mouse_on_input(QPoint(50, 50)) is False, None)
    m2 = mk_mouse(None)
    ok('B9 无输入栏 → False（不崩）', m2._mouse_on_input(QPoint(1100, 720)) is False, None)

    # _auto_hide_blocked
    def mk_blocked(mouse_hit, inputting, inflight):
        s = SimpleNamespace(_ai_inflight=inflight)
        bind(s, '_is_user_inputting')
        s._is_user_inputting = (lambda: inputting)
        bind(s, '_mouse_on_input')
        s._mouse_on_input = (lambda global_pos=None: mouse_hit)
        bind(s, '_auto_hide_blocked')
        return s

    ok('B10 无动静 → 不拦（可以隐藏）', mk_blocked(False, False, False)._auto_hide_blocked() is False, None)
    ok('B11 鼠标压输入栏 → 拦', mk_blocked(True, False, False)._auto_hide_blocked() is True, None)
    ok('B12 正在输入 → 拦', mk_blocked(False, True, False)._auto_hide_blocked() is True, None)
    ok('B13 模型思考中 → 拦', mk_blocked(False, False, True)._auto_hide_blocked() is True, None)

    # _schedule_auto_hide（带参、用 AUTO_HIDE_MS）
    class FakeTimer(object):
        def __init__(self):
            self.calls = []
        def start(self, ms):
            self.calls.append(ms)
        def stop(self):
            self.calls.append(-1)

    s = SimpleNamespace(_auto_hide_timer=FakeTimer(), AUTO_HIDE_MS=D.AUTO_HIDE_MS)
    bind(s, '_schedule_auto_hide')
    s._schedule_auto_hide()
    s._schedule_auto_hide('x')      # textChanged 会带一个 str
    ok('B14 _schedule_auto_hide 接受 str 参数且用 20000ms',
       s._auto_hide_timer.calls == [20000, 20000], s._auto_hide_timer.calls)

    # _try_auto_hide 两种分支
    hidden = {'n': 0}
    s = SimpleNamespace(_auto_hide_timer=FakeTimer(), AUTO_HIDE_RECHECK_MS=D.AUTO_HIDE_RECHECK_MS)
    bind(s, '_auto_hide_blocked')
    s._auto_hide_blocked = (lambda: True)
    bind(s, 'hide_dialogue')
    s.hide_dialogue = (lambda: hidden.__setitem__('n', hidden['n'] + 1))
    bind(s, '_try_auto_hide')
    s._try_auto_hide()
    ok('B15 被拦 → 1s 后复查且不隐藏',
       s._auto_hide_timer.calls == [D.AUTO_HIDE_RECHECK_MS] and hidden['n'] == 0,
       (s._auto_hide_timer.calls, hidden['n']))

    s2 = SimpleNamespace(_auto_hide_timer=FakeTimer(), AUTO_HIDE_RECHECK_MS=D.AUTO_HIDE_RECHECK_MS)
    bind(s2, '_auto_hide_blocked')
    s2._auto_hide_blocked = (lambda: False)
    bind(s2, 'hide_dialogue')
    s2.hide_dialogue = (lambda: hidden.__setitem__('n', hidden['n'] + 1))
    bind(s2, '_try_auto_hide')
    s2._try_auto_hide()
    ok('B16 无动静 → 执行隐藏', hidden['n'] == 1, hidden['n'])

    # _note_focus
    class FakeFocus(object):
        def __init__(self):
            self.assistant, self.user, self.cleared = [], [], 0
        def note_assistant(self, t):
            self.assistant.append(t)
        def note_user(self, t):
            self.user.append(t)
        def clear_pending(self):
            self.cleared += 1

    ff = FakeFocus()
    s = SimpleNamespace(focus=ff, _last_activity=0.0)
    bind(s, '_note_focus')
    s._note_focus('user', '你好')
    ok('B17 _note_focus 用户轮：刷新活动时间 + 清 pending + 喂 note_user',
       s._last_activity > 0 and ff.cleared == 1 and ff.user == ['你好'] and ff.assistant == [],
       (s._last_activity, ff.cleared, ff.user))
    s._note_focus('ralsei', '嗯嗯')
    ok('B18 _note_focus 助手轮：只喂 note_assistant',
       ff.assistant == ['嗯嗯'] and ff.user == ['你好'] and ff.cleared == 1, (ff.assistant, ff.cleared))

    s2 = SimpleNamespace(focus=None, _last_activity=0.0)
    bind(s2, '_note_focus')
    s2._note_focus('user', 'x')
    ok('B19 focus 为 None 时不崩（仍刷时间戳）', s2._last_activity > 0, None)

    # get_focus_brief
    s = SimpleNamespace(focus=CF.ConversationFocus())
    bind(s, 'get_focus_brief')
    ok('B20 无话题 → 空串', s.get_focus_brief() == '', None)
    s.focus.note_user('聊塞尔达剧情')
    ok('B21 有话题 → 返回 brief 文本', '注意力焦点' in s.get_focus_brief(), s.get_focus_brief()[:80])
    s3 = SimpleNamespace(focus=object())
    bind(s3, 'get_focus_brief')
    ok('B22 focus 异常 → 空串（不抛）', s3.get_focus_brief() == '', None)

    ok('B23 AUTO_HIDE_MS == 20000', D.AUTO_HIDE_MS == 20000, D.AUTO_HIDE_MS)
    ok('B24 ACTIVE_CONVERSATION_SECONDS == 150', D.ACTIVE_CONVERSATION_SECONDS == 150.0,
       D.ACTIVE_CONVERSATION_SECONDS)


# ================================================================= C. 源码契约
def test_source():
    print('\n[C] 源码级契约（tokenize 剥注释/字符串）')
    main_src = read(os.path.join(SRC, 'main.py'))
    du_src = read(os.path.join(MODS, 'dialogue_ui.py'))
    drv_src = read(os.path.join(MODS, 'ai_driver.py'))

    a = code_only(func_src(main_src, '_autonomous_speech_allowed'))
    ok('C1 自主开口闸门含"正在聊天则不插话"', 'has_active_conversation' in a, a[:200])

    c = code_only(func_src(main_src, 'chat_with_ai'))
    ok('C2 chat_with_ai 把焦点简报拼进系统提示',
       'get_focus_brief' in c and 'system' in c, None)

    d = code_only(func_src(drv_src, '_say'))
    ok('C3 ai_driver._say 在聊天中跳过插话', 'has_active_conversation' in d, d[:200])

    p = code_only(func_src(drv_src, '_build_prompt'))
    ok('C4 ai_driver._build_prompt 带上焦点简报', 'get_focus_brief' in p, None)

    ok('C5 dialogue_ui 挂上 textChanged → _schedule_auto_hide',
       '_schedule_auto_hide' in code_only(func_src(du_src, '_init_state')), None)
    ok('C6 打字完成重起倒计时', '_schedule_auto_hide' in code_only(func_src(du_src, '_type_next_char')), None)
    ok('C7 show_dialogue 重起倒计时', '_schedule_auto_hide' in code_only(func_src(du_src, 'show_dialogue')), None)

    mp = code_only(func_src(du_src, 'mousePressEvent'))
    ok('C8 鼠标按下只重置倒计时、不改 _last_activity',
       ('_schedule_auto_hide' in mp) and ('_last_activity' not in mp), mp[:200])

    nb = code_only(func_src(du_src, '_note_focus'))
    ok('C9 _note_focus 区分说话人并刷时间戳',
       ('note_assistant' in nb) and ('note_user' in nb) and ('_last_activity' in nb), None)

    ok('C10 add_dialogue 调用了 _note_focus',
       '_note_focus' in code_only(func_src(du_src, 'add_dialogue')), None)


if __name__ == '__main__':
    print('python =', sys.executable)
    test_focus()
    test_dialogue_ui()
    test_source()
    print('\n' + '=' * 60)
    print('PASS = %d   FAIL = %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：')
        for n in FAIL:
            print('  - ' + n)
    sys.exit(1 if FAIL else 0)
