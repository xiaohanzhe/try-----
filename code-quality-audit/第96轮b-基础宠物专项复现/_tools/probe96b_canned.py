# -*- coding: utf-8 -*-
u"""probe96b_canned.py —— 候选3 真机探针：
「宠物自主漫游靠近桌面图标时，会绕过 `speak_event` 直接弹出一句写死的罐头台词」

口径对照（用户 2026-09-19 定）：
  「所有对话全权交给 AI」⇒ `speak_event(pool=None)` **不给内置台词**，宁可沉默。
  而 `react_to_desktop_element`（main.py:9445-9447）**直调**
  `self.dialogue_ui.add_dialogue(...)` + `show_dialogue()` ⇒ 绕过了唯一入口。

本探针要拿到**用户视角可见**的证据：
  1. 起真宠（走产品启动序列，与 rec96 逐条一致）。
  2. 劫持 `dialogue_ui.add_dialogue`，记录**每一次**调用（谁发起、什么文本、来源方法）。
  3. 劫持 `speak_event`，记录它有没有被调用过。
  4. 强行驱动 `react_to_desktop_element`（构造一个假的"桌面元素"），
     看是否真能产出**不含 AI** 的台词，且**不经过** speak_event。
  5. 负控制：把同一段逻辑指向 `speak_event(pool=None)` ⇒ 必须**沉默**。

跑法：
  C:\\Python311\\python.exe <此文件>
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
EV = os.path.join(ROUND, '_evidence')
os.makedirs(EV, exist_ok=True)

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                             # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402
from PyQt5.QtCore import QTimer                              # noqa: E402

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()

print('[probe] shown pid=%d' % os.getpid())
sys.stdout.flush()

CALLS = []          # add_dialogue 调用记录
SPEAK = []          # speak_event 调用记录
UI = window.dialogue_ui

_orig_add = UI.add_dialogue
_orig_show = UI.show_dialogue


def add_wrap(*a, **kw):
    try:
        CALLS.append({'t': time.time(), 'args': repr(a)[:200],
                      'stack': ''.join(traceback.format_stack()[-4:-1])[:600]})
    except Exception:
        pass
    return _orig_add(*a, **kw)


def show_wrap(*a, **kw):
    try:
        CALLS.append({'t': time.time(), 'args': 'SHOW', 'stack': ''})
    except Exception:
        pass
    return _orig_show(*a, **kw)


UI.add_dialogue = add_wrap
UI.show_dialogue = show_wrap

_orig_speak = window.speak_event


def speak_wrap(kind, pool=None, face='happy', instant=False):
    SPEAK.append({'t': time.time(), 'kind': kind, 'pool': pool})
    return _orig_speak(kind, pool=pool, face=face, instant=instant)


window.speak_event = speak_wrap

RESULT = {}


def phase1():
    """A 段：真调 react_to_desktop_element，看是否产出罐头台词。"""
    print('\n[A] 真调 react_to_desktop_element（构造假元素）')
    n0 = len(CALLS)
    s0 = len(SPEAK)
    fake = {
        'path': 'C:\\Users\\Public\\Desktop\\示例文件.txt',
        'name': '示例文件.txt',
        'type': 'file',
        'size': 1024,
        'ext': '.txt',
    }
    try:
        window.react_to_desktop_element(fake)
        RESULT['call_ok'] = True
    except Exception as e:
        RESULT['call_ok'] = False
        RESULT['call_err'] = repr(e)
        print('  !! react_to_desktop_element 抛异常: %r' % (e,))
    RESULT['calls_delta'] = len(CALLS) - n0
    RESULT['speak_delta'] = len(SPEAK) - s0
    print('  add_dialogue 新增调用: %d' % RESULT['calls_delta'])
    print('  speak_event  新增调用: %d' % RESULT['speak_delta'])
    for c in CALLS[n0:n0 + 4]:
        print('    · args=%s' % c['args'])


def phase2():
    """B 段：负控制 —— 同一语义走 speak_event(pool=None) 必须沉默。"""
    print('\n[B] 负控制：speak_event(pool=None) 应当沉默（不给内置台词）')
    n0 = len(CALLS)
    try:
        r = window.speak_event('desktop_near', pool=None)
        RESULT['speak_none_ret'] = repr(r)
    except Exception as e:
        RESULT['speak_none_ret'] = 'ERR %r' % (e,)
    RESULT['speak_none_calls'] = len(CALLS) - n0
    print('  speak_event 返回: %s' % RESULT['speak_none_ret'])
    print('  add_dialogue 新增调用: %d（期望 0 = 沉默）' % RESULT['speak_none_calls'])


def phase3():
    """C 段：对照 —— speak_event 给了池子，必须有台词（证明入口本身可用）。"""
    print('\n[C] 正控制：speak_event(pool=[...]) 应当说出来')
    n0 = len(CALLS)
    try:
        r = window.speak_event('desktop_near', pool=['这是一句内置台词。'])
        RESULT['speak_pool_ret'] = repr(r)
    except Exception as e:
        RESULT['speak_pool_ret'] = 'ERR %r' % (e,)
    RESULT['speak_pool_calls'] = len(CALLS) - n0
    print('  speak_event 返回: %s' % RESULT['speak_pool_ret'])
    print('  add_dialogue 新增调用: %d（期望 ≥1）' % RESULT['speak_pool_calls'])


def finish():
    print('\n' + '=' * 74)
    print('# 汇总')
    print('=' * 74)
    for k, v in RESULT.items():
        print('  %s = %s' % (k, v))
    print('\n  add_dialogue 总调用 %d 次：' % len(CALLS))
    for c in CALLS[:8]:
        print('    %s' % c['args'])
    # 判决
    a = RESULT.get('calls_delta', 0)
    s = RESULT.get('speak_delta', 0)
    print('\n  【判决】A段（react_to_desktop_element）：')
    print('    · 绕过 speak_event 直写对话: %s' % ('是 ⚠️' if a > 0 else '否'))
    print('    · 未经过 speak_event: %s' % ('是 ⚠️（speak 增量 %d）' % s if s == 0 and a > 0 else '否'))
    print('  【判决】B段（负控制 pool=None）：沉默 = %s（期望 沉默）'
          % ('是 ✅' if RESULT.get('speak_none_calls') == 0 else '否 ❌'))
    print('  【判决】C段（正控制 pool=非空）：说了 = %s（期望 说了）'
          % ('是 ✅' if RESULT.get('speak_pool_calls', 0) > 0 else '否 ❌'))

    with io.open(os.path.join(EV, 'probe96b_canned.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write('# probe96b_canned 结果\n')
        for k, v in RESULT.items():
            f.write('%s = %s\n' % (k, v))
        f.write('\n# add_dialogue 调用明细（前 8 条）\n')
        for c in CALLS[:8]:
            f.write('t=%.2f args=%s\n' % (c['t'], c['args']))
            if c['stack']:
                f.write('  stack:\n%s\n' % c['stack'])

    QTimer.singleShot(200, app.quit)


QTimer.singleShot(3000, phase1)
QTimer.singleShot(6000, phase2)
QTimer.singleShot(8000, phase3)
QTimer.singleShot(11000, finish)

rc = app.exec_()
print('[probe] rc=%d' % rc)
