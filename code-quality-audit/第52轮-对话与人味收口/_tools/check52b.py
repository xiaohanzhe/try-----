# -*- coding: utf-8 -*-
"""第52轮 · 「内置对话清理」+「捉迷藏双闸」验证

用户口径逐字（本套件守的就是这两句）：
  「还有把他内置的对话去掉！！！！并且去掉那个与文件夹交互的功能吧，感觉过于鸡肋了，
    还有，他捉迷藏只是用户提出来才能玩而且必须是在桌面上。」

划的那条线（**重要**，决定了哪些迁、哪些不迁）
------------------------------------------------
  · **纯情绪 / 零信息量**的台词（"我好累"、"谢谢你陪我玩"）⇒ **删掉**，改走
    `speak_event(kind, pool=None)` —— 即 `event_speech.py` docstring 写明的
    "全权交给 AI"口径：**不给内置台词**，AI 不可用就安静。
  · **带数值 / 带名字 / 规则提示**的功能播报（"你 3 - 2 我"、"解锁了'满分达人'"、
    "请输入石头、剪刀或布"）⇒ **不迁**：交模型必然丢信息。
    这条线不是本轮的发明 —— `verify_s7_event_speech` 的 **C12** 早就锁着它
    （"拒绝原因说明仍保持罐头"）。

判据纪律
--------
· 全部用 **AST**（取函数体的字面量表），**不用** `'字面量' in 源码` ——
  第52轮真踩过：那种写法会匹配到我自己新写的注释/docstring，报假 FAIL。
· 正 / 负控制成对：迁走的东西要"真的不在了"，**有意保留**的东西要"真的还在"
  （否则"删干净了"和"手滑删多了"两种错都看不见）。
· D 段行为级用桩宿主调**真控制器**，断言 `game_state` 没被污染。

不联网、不调 Ollama、不实例化主程序、不需要显示器（D 段纯 Python 桩）。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
for _p in (SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


def _read(p):
    with open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def _tree(p, tag):
    try:
        return ast.parse(_read(p)), ""
    except SyntaxError as e:
        return None, "%s SyntaxError: %s (line %s)" % (tag, e.msg, e.lineno)


def _func(tree, name):
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _str_literals(node):
    """节点子树里所有字符串字面量的集合（AST，不受注释/docstring 干扰……但 docstring
    也是 `ast.Constant`！所以调用方要把函数 docstring 单独排除，见 `_func_strings`）。"""
    out = set()
    if node is None:
        return out
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _func_strings(node):
    """函数体里真正会被执行的字符串字面量（**排除 docstring**）。"""
    out = set()
    if node is None:
        return out
    doc = ast.get_docstring(node, clean=False)
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if doc is not None and n.value == doc:
                continue          # 跳过函数自己的 docstring
            out.add(n.value)
    return out


def _calls_named(node, attr):
    """节点子树里 `xxx.<attr>(...)` 的调用参数列表。"""
    res = []
    if node is None:
        return res
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == attr:
            res.append(n)
    return res


# ============================================================ A. energy_hunger
EH_PATH = os.path.join(MODS, 'energy_hunger.py')
EH, _eh_err = _tree(EH_PATH, 'energy_hunger')
check("A0 energy_hunger.py 可编译", EH is not None and not _eh_err, _eh_err)

_csc = _func(EH, 'check_status_changes')
_check_strs = _func_strings(_csc)

_GONE_PURE = [
    "呜... 我真的好累好累... 几乎走不动了...",
    "我有点累了... 能不能休息一下？",
    "肚子好饿好饿... 我快饿死了...",
    "嗯... 我有点饿了... 有没有什么吃的？",
    "好吃！我已经吃饱了！谢谢你的食物！",
    "哇！我感觉好多了！谢谢你让我休息！",
]
_still = [s for s in _GONE_PURE if s in _check_strs]
check("A1 ★6 句纯情绪（累/饿/吃饱/休息好）已从 check_status_changes 里删干净",
      not _still, "残留=%r" % (_still,))

# 反控制：**有意保留**的拒绝说明必须还在（这才是"干净的删"，不是"手滑全删"）
_rest = _func(EH, 'rest')
_eat = _func(EH, 'eat')
_rest_s, _eat_s = _func_strings(_rest), _func_strings(_eat)
_keep_ok = (any('我现在精神得很' in s for s in _rest_s)
            and any('我已经吃得饱饱的啦' in s for s in _eat_s))
check("A2 反控制：rest()/eat() 的**拒绝说明**仍在（功能反馈，删了主人就不知道为什么没反应）",
      _keep_ok, "rest 有=%s eat 有=%s"
      % (any('我现在精神得很' in s for s in _rest_s),
         any('我已经吃得饱饱的啦' in s for s in _eat_s)))

# 新通道：_speak() 必须真的用 pool=None（说不了就安静），而不是换了个地方仍塞罐头
_spk = _func(EH, '_speak')
_spk_args = _calls_named(_spk, 'speak_event')
_plain_none = False
for c in _spk_args:
    if len(c.args) >= 2 and isinstance(c.args[1], ast.Constant) and c.args[1].value is None:
        _plain_none = True
check("A3 `_speak()` 走 `speak_event(kind, None, face)`（pool=None = 不给内置台词）",
      bool(_spk_args) and _plain_none,
      "speak_event 调用 %d 处 / 第二参数为 None = %s" % (len(_spk_args), _plain_none))

# 迁移点必须都被调用到（防"写了 _speak 但没人用"）
_csc_src = ast.unparse(_csc) if _csc is not None else ''
_speak_calls = _csc_src.count('self._speak(')
check("A4 check_status_changes 里 6 处纯情绪播报全改走 `self._speak(...)`",
      _speak_calls == 6, "self._speak( 出现 %d 次" % _speak_calls)

# 反控制：没迁的地方不许被顺手改掉（C10 的口径：rest/eat 各只剩"拒绝原因"那一处 add_dialogue）
_rest_dial, _eat_dial = _calls_named(_rest, 'add_dialogue'), _calls_named(_eat, 'add_dialogue')
check("A5 反控制：rest()/eat() 各自**仍恰好 1 处** add_dialogue（= 只剩拒绝原因）",
      len(_rest_dial) == 1 and len(_eat_dial) == 1,
      "rest=%d eat=%d" % (len(_rest_dial), len(_eat_dial)))

# ---- 档位/提示词登记（一侧不写 = 静默退回罐头，C2/C11 的老坑）
import event_speech as E                                            # noqa: E402

_NEW_KINDS = ["energy_critical", "energy_low", "hunger_critical", "hunger_low",
              "ate_enough", "rested_well", "hide_seek_not_desktop", "game_thanks"]
_unregistered = [k for k in _NEW_KINDS if k not in E.EVENT_TIERS]
_undirected = [k for k in _NEW_KINDS if k not in E.EVENT_DIRECTIVES]
_not_ai = [k for k in _NEW_KINDS if E.tier_of(k) != E.TIER_AI]
check("A6 8 个新事件名全部登记进 EVENT_TIERS 且是 AI 档", not _unregistered and not _not_ai,
      "未登记=%r 非AI档=%r" % (_unregistered, _not_ai))
check("A7 8 个新事件名全部有 EVENT_DIRECTIVES 旁白", not _undirected, "缺旁白=%r" % (_undirected,))
check("A8 旁白是「（…）」形式的动作描述，不是台词示范（写示范=复读机成因）",
      all(str(E.EVENT_DIRECTIVES[k]).startswith('（')
          and str(E.EVENT_DIRECTIVES[k]).endswith('）') for k in _NEW_KINDS))

# ======================================================= B. games_controller
GC_PATH = os.path.join(MODS, 'games_controller.py')
GC, _gc_err = _tree(GC_PATH, 'games_controller')
check("B0 games_controller.py 可编译", GC is not None and not _gc_err, _gc_err)
_gc_all = _func_strings(GC)   # 整个模块（无 docstring 误伤：模块级 docstring 不在函数里）
check("B1 内置台词「谢谢你陪我玩！」已从 games_controller 删除",
      not any('谢谢你陪我玩' in s for s in _gc_all),
      "残留=%r" % ([s for s in _gc_all if '谢谢你陪我玩' in s][:3],))

_gc_thanks = []
for n in ast.walk(GC) if GC is not None else []:
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
            and n.func.attr == 'speak_event':
        if n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'game_thanks':
            _gc_thanks.append(n)
_plain = any(len(c.args) >= 2 and isinstance(c.args[1], ast.Constant)
             and c.args[1].value is None for c in _gc_thanks)
check("B2 改成 `speak_event(\"game_thanks\", None, ...)`（2 处终局都要）",
      len(_gc_thanks) == 2 and _plain, "找到 %d 处 / pool=None=%s" % (len(_gc_thanks), _plain))

# 反控制：带数值的结算与统计**必须还在**（别把信息一起删了）
_has_final = any('最终比分' in s for s in _gc_all)
_has_stats = any('游戏统计' in s for s in _gc_all)
check("B3 反控制：带数值的「最终比分」「游戏统计」仍在（有意保留的功能播报）",
      _has_final and _has_stats, "比分=%s 统计=%s" % (_has_final, _has_stats))

# ================================================ C. play_game 不再随机抽躲猫猫
MAIN_PATH = os.path.join(SRC, 'main.py')
MAIN, _m_err = _tree(MAIN_PATH, 'main')
check("C0 main.py 可编译", MAIN is not None and not _m_err, _m_err)
_pg = _func(MAIN, 'play_game')
_games_list = None
if _pg is not None:
    for n in ast.walk(_pg):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'games' for t in n.targets):
            if isinstance(n.value, ast.List):
                try:
                    _games_list = [e.value for e in n.value.elts]
                except Exception:
                    _games_list = None
check("C1 ★`play_game` 的随机名单不再含 `hide_and_seek`（用户没提就不许玩）",
      isinstance(_games_list, list) and 'hide_and_seek' not in _games_list,
      "名单=%r" % (_games_list,))
check("C2 反控制：其余 5 个小游戏仍在名单里（不是把整段删了）",
      isinstance(_games_list, list)
      and set(_games_list) == {"dance", "sing", "chase_cursor",
                               "rock_paper_scissors", "guess_number"},
      "名单=%r" % (_games_list,))
_pg_src = ast.unparse(_pg) if _pg is not None else ''
check("C3 原 `elif game == \"hide_and_seek\":` 死分支已删除（不留永远走不到的代码）",
      'hide_and_seek' not in _pg_src, "仍在=%s" % ('hide_and_seek' in _pg_src))

# ============================================ D. 躲猫猫「必须在桌面」闸（行为级）
HC, _hc_err = _tree(os.path.join(MODS, 'hide_controller.py'), 'hide_controller')
check("D0 hide_controller.py 可编译", HC is not None and not _hc_err, _hc_err)
_start = _func(HC, 'start_hide_and_seek_game')
_strs = _func_strings(_start)
_src = ast.unparse(_start) if _start is not None else ''
check("D1 源码级：入口先查 `current_scene`，非桌面用 `hide_seek_not_desktop` 说明并 return False",
      ('current_scene' in _src) and ('hide_seek_not_desktop' in _src)
      and ('returnFalse' in _src.replace(' ', '') or 'return False' in _src),
      "current_scene=%s kind=%s" % ('current_scene' in _src, 'hide_seek_not_desktop' in _src))

# ---- 行为级：桩宿主 + **真控制器**
from hide_controller import HideAndSeekController                    # noqa: E402


class _GatePassed(Exception):
    """走到闸门**之后**才可能抛的东西 —— 用它反证'闸放行了'。"""


class _StubAgent(object):
    def __init__(self):
        self.suspended = 0

    def suspend(self):
        self.suspended += 1


def _make_host(scene):
    calls = []

    class Host(object):
        # 用类属性给出 host 身上的方法（`__getattr__` 第二条白名单要能查到）
        def speak_event(self, kind, pool=None, face="happy", instant=False):
            calls.append({'kind': kind, 'pool': pool, 'face': face})
            return ""

        def _current_screen_rect(self):
            raise _GatePassed('已越过桌面闸')

    h = Host()
    # 实例字典里的状态（`__getattr__` 第一条白名单）
    h.game_state = {'is_playing': False, 'game_type': None}
    h.current_scene = scene
    h._hide_stage = None
    h.autonomous_agent = _StubAgent()
    return h, calls


# —— 负控制：不在桌面 ⇒ 拒绝、状态零污染、有说明 ——
_h1, _c1 = _make_host('ch1.room_town_north')
_ctrl1 = HideAndSeekController(_h1)
_r1 = _ctrl1.start_hide_and_seek_game()
check("D2 非桌面（ch1.room_town_north）⇒ 返回 False", _r1 is False, "返回 %r" % (_r1,))
check("D3 ★状态零污染：`game_state['is_playing']` 仍为 False、`_hide_stage` 仍为 None",
      _h1.game_state['is_playing'] is False and _h1._hide_stage is None,
      "is_playing=%r hide_stage=%r" % (_h1.game_state['is_playing'], _h1._hide_stage))
check("D4 拒绝时给出了说明（kind=hide_seek_not_desktop 且**带罐头兜底**）",
      len(_c1) == 1 and _c1[0]['kind'] == 'hide_seek_not_desktop'
      and bool(_c1[0]['pool']),
      "calls=%r" % (_c1,))
check("D5 拒绝路径**没有**去暂停自主代理（闸在最前面）",
      _h1.autonomous_agent.suspended == 0,
      "suspend 次数=%d" % _h1.autonomous_agent.suspended)

# —— 正控制：就在桌面 ⇒ 必须放行（用一个"越过闸才会抛"的哨兵证明） ——
_h2, _c2 = _make_host('desktop')
_ctrl2 = HideAndSeekController(_h2)
_passed = False
try:
    _ctrl2.start_hide_and_seek_game()
except _GatePassed:
    _passed = True
except Exception as _e:
    _passed = False
    _unexpected = repr(_e)
else:
    _unexpected = ''
check("D6 正控制：在桌面（desktop）时闸**放行**（越过后才会碰到真屏幕计算）",
      _passed and _h2.autonomous_agent.suspended == 1,
      "放行=%s suspend=%d %s" % (_passed, _h2.autonomous_agent.suspended,
                                 _unexpected if not _passed else ''))

# 恒真判据自查：桩宿主真的被控制器用到了（否则上面全是空跑）
check("D7 判据自证：桩宿主的 speak_event 真的被控制器调到（不是空跑）",
      len(_c1) == 1 and len(_c2) == 0, "非桌面 calls=%d 桌面 calls=%d" % (len(_c1), len(_c2)))

# ------------------------------------------------------------------ summary
_n_pass = sum(1 for ok, _n, _d in RESULTS if ok)
_n_fail = len(RESULTS) - _n_pass
print("-" * 68)
print("合计：PASS=%d FAIL=%d" % (_n_pass, _n_fail))
for ok, _n, _d in RESULTS:
    if not ok:
        print("  FAIL: %s  %s" % (_n, _d))
print("=== 结论 = %s ===" % ("PASS" if _n_fail == 0 else "FAIL"))
sys.exit(0 if _n_fail == 0 else 1)
