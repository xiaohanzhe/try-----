# -*- coding: utf-8 -*-
"""第十八轮（并行线二）· S7 事件台词分批接 AI —— 回归锁。

为什么 S7 值得单独锁
--------------------
改造前事件台词 100% 写死（全项目 191 处 `add_dialogue`，`main.py` 131 处），
连着摸三次都是「嘿嘿~ 好舒服呀！」—— 这是"没活人味"最直观的来源。
但"把事件台词交给模型"会踩三个坑，每一个都会让体验**倒退**：

1) **延迟**：报告 §5 明确写了"131 处一次性全交 AI = 每句话都卡 2 秒"。
   所以档位必须分：短促反应（甩飞「哇啊——！」/ 摔扁被戳 / 连点耳朵）保持罐头，
   且**未登记的事件一律保持改造前行为**（登记表是白名单，不是黑名单）。
2) **抢话 / 顶掉主人的回复**：事件请求和对话请求共用 `chat_with_ai`，
   而 `chat_with_ai` 会**覆盖写** `_ai_delta_sink`。主人那条回复正在流式时被事件请求
   插一脚 → 主人的文字**半路停住**。必须在 `_event_ai_ready` 里让路。
3) **一个事件两个气泡**：先兜底说了罐头，AI 的迟到回复又补一句 → 屏幕上两句连排。

分组
----
  A `modules/event_speech.py` 纯逻辑（档位 / 提示词 / 首句截断 / 罐头去重）
  B `main.py` 接线（唯一出口 / 让路 / 世代号 / 兜底 / 只发一个气泡）
  C 迁移完整性（batch 1 `main.py` 20 处 + batch 2 `energy_hunger.py` 2 处、
     物理状态机未动、kind 全部登记）
  D 行为级（真 `QApplication` + 桩宿主，含"AI 卡住"与"迟到回复"两条时序）
  E 配置（一键开关）

本套件**不打网络、不调用 Ollama**（真机数值另见 `_evidence/s7_*`）。
必须用 C:\\Python311\\python.exe 运行（PyQt5）。
"""
import io
import os
import re
import sys
import time
import tokenize
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
for _p in (SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


# ---------------------------------------------------------------- 源码工具
MAIN_TEXT = io.open(os.path.join(SRC, 'main.py'), encoding='utf-8').read()
DUI_TEXT = io.open(os.path.join(MODS, 'dialogue_ui.py'), encoding='utf-8').read()
ES_PY = os.path.join(MODS, 'event_speech.py')
ES_TEXT = io.open(ES_PY, encoding='utf-8').read()
CFG_MGR_PY = os.path.join(MODS, 'config_manager.py')

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def _strip(src, drop):
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in drop:
            continue
        out.append(tok.string)
    return re.sub(r'\s+', '', ' '.join(out))


def code_only_src(src):
    """剥注释+字符串（找语法结构用）。"""
    return _strip(src, _DROP)


def code_no_comment(src):
    """只剥注释（needle 里含字符串字面量时必须用这个 —— 见 MEMORY「验证脚本教训」）。"""
    return _strip(src, (tokenize.COMMENT,))


def func_src(src, name):
    """取函数正文（顺序/局部断言必须限定在目标函数体内，避免命中别的函数）。"""
    lines = src.splitlines()
    start = indent = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('def %s(' % name):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return ''
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= (indent or 0):
            break
        out.append(ln)
    return '\n'.join(out)


# ---------------------------------------------------------------- 导入
import event_speech as E                                        # noqa: E402
import main as M                                                # noqa: E402
R = M.RalseiPet

# ================================================================ A
section('A. modules/event_speech.py 纯逻辑')

ok('A1 未登记事件回落"罐头档"（登记表是白名单 —— 没迁移 = 行为不变）',
   E.tier_of('__没有这类事件__') == E.TIER_INSTANT)
ok('A2 已登记的社交事件是 AI 档', E.tier_of('poke_body') == E.TIER_AI
   and E.tier_of('pet_hair') == E.TIER_AI and E.tier_of('feed') == E.TIER_AI)
ok('A3 短促/状态机事件显式钉在罐头档（甩飞 / 摔扁被戳 / 连点耳朵）',
   E.tier_of('fling') == E.TIER_INSTANT
   and E.tier_of('splat_poked') == E.TIER_INSTANT
   and E.tier_of('ear_ruffle') == E.TIER_INSTANT)
_batch1 = ('poke_body', 'poke_shoulder', 'poke_default', 'pinch_ear', 'pull_arm',
           'press_body', 'pat_belly', 'pinch_face', 'pull_shoulder', 'double_hair',
           'double_belly', 'double_face', 'double_shoulder', 'double_other',
           'pet_hair', 'pet_ear', 'pet_face', 'pet_body', 'pet_arm',
           'pet_shoulder', 'pet_other', 'feed', 'pet_menu')
_missing = [k for k in _batch1 if k not in E.EVENT_TIERS]
ok('A4 第一批 23 个事件全部登记（漏登记 = 静默退回罐头，白改）',
   not _missing, '未登记: %s' % _missing)
_undirected = [k for k in E.EVENT_TIERS if k not in E.EVENT_DIRECTIVES]
ok('A5 每个登记事件都有提示词文案（否则 build_prompt 退化成通用旁白）',
   not _undirected, '缺文案: %s' % _undirected)
_p = E.build_prompt('poke_ear' if 'poke_ear' in E.EVENT_DIRECTIVES else 'poke_body')
ok('A6 build_prompt 含事件旁白 + 长度约束', ('（' in _p) and (str(E.EVENT_MAX_CHARS) in _p), _p)
ok('A7 build_prompt **不含示例台词**（3B 会把示例当模板照抄 —— 第十八轮的主因）',
   ('例如' not in _p) and ('比如' not in _p) and ('「' not in _p) and ('示例' not in _p), _p)
ok('A8 build_prompt 对未知事件也给出可用旁白（不返回空）',
   bool(E.build_prompt('__未知__', '主人摸了摸你的头。')))

_fs_cases = [
    ('哎呀！别捏我的耳朵！好痒呀！', '哎呀！别捏我的耳朵！好痒呀！'),   # 首句 3 字 <6 → 整句保留
    ('嗯？发生了什么吗？', '嗯？发生了什么吗？'),                       # 实测：切成「嗯？」等于没说
    ('谢谢你，小豆。让我靠你一会儿。', '谢谢你，小豆。'),               # 首句 7 字 ≥6 → 取第一句
    ('嘿嘿~ 好舒服呀！谢谢你主人！', '嘿嘿~ 好舒服呀！'),
    ('诶？！听到这话我都有点不好意思起来了。感觉就像在阳光下晒着一样舒服呢。',
     '诶？！听到这话我都有点不好意思起来了。'),
    ('「嘿嘿~」', '嘿嘿~'),
    ('', ''),
    ('。。。', ''),
]
_fs_bad = [(s, E.first_sentence(s), w) for s, w in _fs_cases if E.first_sentence(s) != w]
ok('A9 first_sentence 取第一句 / 首句过短则整句保留 / 剥包裹引号 / 只有标点判空',
   not _fs_bad, _fs_bad)
ok('A10 first_sentence 压到上限以内（超长硬截断）',
   len(E.first_sentence('哈哈哈' * 30)) <= E.EVENT_MAX_CHARS,
   len(E.first_sentence('哈哈哈' * 30)))
ok('A11 first_sentence 与 start_autonomous_speech 同口径：优先句号（一个完整的想法）',
   E.first_sentence('诶？！好舒服呀。后面还有好多话要说呢。') == '诶？！好舒服呀。',
   E.first_sentence('诶？！好舒服呀。后面还有好多话要说呢。'))

_picker = E.RecentLinePicker(window=3)
_picker.note('A')
_bad = [k for k in range(20) if _picker.pick(['A', 'B']) != 'B']
ok('A12 去重器：有没说过的话时绝不挑刚说过的', not _bad)
_picker.note('B')
ok('A13 去重器：全说过时挑最久没说过的（不是随机）', _picker.pick(['A', 'B']) == 'A')
ok('A14 去重器：空池 / 非字符串池返回空串',
   _picker.pick([]) == '' and _picker.pick([None, 3, '  ']) == '')
_p2 = E.RecentLinePicker(window=2)
for _x in ('A', 'B', 'C', 'D'):
    _p2.note(_x)
ok('A15 去重窗口只保留最近 N 条', _p2._recent == ['C', 'D'], _p2._recent)
ok('A16 模块自检通过（自带 oracle）', '通过' in E._selfcheck(), E._selfcheck())

_es_imports = [ln.strip() for ln in ES_TEXT.splitlines()
               if ln.startswith('import ') or ln.startswith('from ')]
ok('A17 模块不 import Qt / 项目内模块（否则会卷进 logger_utils→data_store 初始化环）',
   not any(('PyQt' in x) or x.startswith('from modules') or x == 'import main'
           for x in _es_imports), _es_imports)

# 「出戏闸」的样本全部来自真机实测（_evidence/s7_e2e_event.txt）
_ooc = [
    '抱歉，我没有触觉无法感受被拉肩，停一下别紧张。',
    '作为一个AI助手，我无法感受这个动作。',
    '我是语言模型，没有身体。',
]
_ok_lines = [
    '谢谢你，小豆。让我靠你一会儿。',
    '哎呀，你这是干啥啊……',
    '嘿嘿~ 我的肚子很软哦！',
]
ok('A18 出戏闸命中"AI 自我指涉 / 否认感官"（实测真出现过「我没有触觉」）',
   all(E.looks_out_of_character(x) for x in _ooc)
   and not any(E.looks_out_of_character(x) for x in _ok_lines),
   [x for x in _ok_lines if E.looks_out_of_character(x)])
ok('A19 guard_reaction 命中的整句作废（返回空串 → 调用方回落罐头），好句原样放行',
   E.guard_reaction(_ooc[0]) == '' and E.guard_reaction(_ok_lines[0]) == _ok_lines[0])

# ================================================================ B
section('B. main.py 接线')

_missing_api = [n for n in ('speak_event', '_event_ai_ready', '_event_say',
                            '_event_speech_enabled', '_pick_event_line')
                if not callable(getattr(R, n, None))]
ok('B1 五个新方法都挂在 RalseiPet 上', not _missing_api, _missing_api)
ok('B2 main.py 导入了 event_speech 的档位/构造/截断函数（不是自己再抄一份）',
   all(hasattr(M, n) for n in ('tier_of', 'pet_kind', 'build_prompt', 'first_sentence')))

_main_code = code_only_src(MAIN_TEXT)
_main_nc = code_no_comment(MAIN_TEXT)
ok('B3 __init__ 里初始化了去重器/世代号/上次时刻（全文件 needle：'
   '不同类的 `__init__` 只有 7 行，用 func_src 会取错）',
   '_event_line_picker=RecentLinePicker()' in _main_code
   and 'self._event_speak_gen=0' in _main_code
   and 'self._event_speak_last=None' in _main_code)

_say = code_only_src(func_src(MAIN_TEXT, '_event_say'))
ok('B4 _event_say 是"add_dialogue + show_dialogue"成对（顺序正确）',
   _say.index('dui.add_dialogue(') < _say.index('dui.show_dialogue()'),
   _say[:120])
ok('B5 _event_say 是唯一显示出口：main.py 里所有 speak_event 调用都不再直接 add_dialogue',
   'add_dialogue(' not in code_only_src(func_src(MAIN_TEXT, 'speak_event')))

_ready_nc = code_no_comment(func_src(MAIN_TEXT, '_event_ai_ready'))
_ready = code_only_src(func_src(MAIN_TEXT, '_event_ai_ready'))
ok('B6 主人正在打字 → 不走 AI（不抢话）', 'dui._is_user_inputting()' in _ready)
ok('B7 对话正在流式 → 不走 AI（否则会顶掉主人的流式接收端，回复半路停住）',
   "getattr(dui,'_streaming',False)" in _ready_nc)
ok('B8 主人那条请求还在路上 → 不走 AI（用 dialogue_ui 自己的 _ai_inflight）',
   "getattr(dui,'_ai_inflight',False)" in _ready_nc)
ok('B8b **不许**用 `_ai_delta_sink` 当门（S8 设计上收尾不清空它 → 用它做门 = '
   '开过一次流式之后事件永远走罐头，D22 钉这条）',
   '_ai_delta_sink' not in _ready_nc)
ok('B9 等着主人的回复（前台是占位）→ 不走 AI',
   "AI_THINKING_PLACEHOLDER" in _ready_nc)
ok('B10 频率闸用 EVENT_SPEAK_MIN_INTERVAL（连戳不连发请求）',
   'EVENT_SPEAK_MIN_INTERVAL' in _ready_nc)
ok('B11 instant=True 直接短路成罐头（不看配置、不碰 AI）',
   'instant' in _ready and 'notself._event_speech_enabled()' in _ready)
ok('B12 档位判定走 tier_of（未知事件回落罐头）', 'tier_of(kind)!=TIER_AI' in _ready)

_se = code_no_comment(func_src(MAIN_TEXT, 'speak_event'))
_se_struct = code_only_src(func_src(MAIN_TEXT, 'speak_event'))
ok('B13 罐头档立刻说罐头并返回（不发起 AI 请求）',
   'ifnotself._event_ai_ready(kind,instant):' in _se_struct
   and '_note(canned)' in _se_struct and 'returncanned' in _se_struct)
ok('B14 世代号：事件请求 +1 且迟到回调按世代丢弃',
   "self._event_speak_gen=getattr(self,'_event_speak_gen',0)+1" in _se
   and "gen!=getattr(self,'_event_speak_gen',0)" in _se)
ok('B15 一次事件只给一个气泡（state[said] 守卫）',
   "state['said']" in _se and "ifstate['said']or" in _se, _se[:0])
# 注：这条**必须**用 code_no_comment（`'said'` 是字符串字面量，code_only_src 会把它剥掉
# → `ifstate[,]or` → 永远搜不到。含引号的 needle 走 code_no_comment，本项目已第 5 次踩。）
ok('B16 首字兜底：QTimer 到 EVENT_SPEAK_FIRST_TOKEN_MS 且只在"没出字"时说罐头',
   'QTimer.singleShot(int(self.EVENT_SPEAK_FIRST_TOKEN_MS)' in _se_struct
   and "if(state['streaming']orstate['said'])" in _se)
ok('B16b 兜底时限只覆盖**首字**，且落在实测区间内（整句 1.13~1.65s；首字 0.79~0.90s）',
   500 <= R.EVENT_SPEAK_FIRST_TOKEN_MS <= 1500,
   'EVENT_SPEAK_FIRST_TOKEN_MS=%r（实测首字中位 0.81s / 最慢 0.90s；'
   '<500ms 会让大多数事件落回罐头，>1500ms 就不再是"即时反应"）'
   % R.EVENT_SPEAK_FIRST_TOKEN_MS)
ok('B17 AI 回复先过 first_sentence 再显示（长度/句数口径只有一份）',
   'first_sentence(reply,self.EVENT_SPEAK_MAX_CHARS)' in _se_struct)
ok('B17b 再出戏闸（3B 实测会吐「我没有触觉无法感受…」这种自毁角色的句子）',
   'guard_reaction(' in _se_struct)
ok('B18 事件请求是**流式**（传 on_delta），否则主人要干等 1.4s 才见到反应',
   'chat_with_ai(build_prompt(kind),_on_reply,_on_delta,lean=True)' in _se_struct)
ok('B18b 分片走 dialogue_ui.stream_delta，且按世代号丢弃旧事件的分片',
   'dui.stream_delta(chunk)' in _se_struct
   and "ifgen!=getattr(self,'_event_speak_gen',0)" in _se)
ok('B18c 护栏判退（chunk is None）→ 擦掉半句，不把罐头接在半句后面',
   "dui.stream_delta(None)" in _se_struct)
ok('B18d 流式打过的句子走"定格"（_streamed=True），不从头重打一遍',
   'self._event_say(text,face,streamed=state[streaming])' in _se_struct
   or "_streamed=bool(streamed)" in code_no_comment(func_src(MAIN_TEXT, '_event_say')))
ok('B18e 事件先行"开口"（show_dialogue），避免把字打进看不见的框',
   'dui.show_dialogue()' in _se_struct)
ok('B18e2 等待首字期间显示「……」（_ai_thinking_on），框子不空着',
   'dui._ai_thinking_on()' in _se_struct)
ok('B18e3 dialogue_ui.add_dialogue 必须继续丢弃思考占位（否则「……」会被并入历史）'
   ' —— 这是 B18e2 的**前置依赖**，跨模块锁',
   'ifself.typing_text==self.AI_THINKING_PLACEHOLDER:'
   in code_no_comment(func_src(DUI_TEXT, 'add_dialogue')))
ok('B18f 上一个事件还在等 AI 时不叠加第二个请求（_event_speaking）',
   "getattr(self,'_event_speaking',False)" in _ready_nc
   and 'self._event_speaking=True' in _se_struct)
ok('B18g 迟到分片必须被"已经说过话"挡住（否则会把 UI 钉在流式态 → 永久挡死后续事件）',
   "ifstate['said']:return" in _se, _se[:0])
ok('B19 罐头也进去重窗口（否则最常走的"AI 不可用"路径永远学不到自己说过什么）',
   'self._event_line_picker.note(text)' in _se)
ok('B20 显示长度上限与模块共用同一份（不写第二份 24）',
   R.EVENT_SPEAK_MAX_CHARS == E.EVENT_MAX_CHARS)
ok('B21 事件提示词走 build_prompt（不在 main 里手拼文案）',
   'chat_with_ai(build_prompt(kind)' in _se_struct)

# —— B22 组：lean 请求（S7 的命门，见 §11.11）——
# 为什么必须锁：事件请求的 system 只要**每轮都变**（【此刻】/话题锚/记忆召回），
# Ollama 的 KV 前缀缓存就失效 → 首字从 0.63s 涨到 1.82s，history 再 +0.52s
# → 2.5~3.0s，**必超** 1200ms 兜底 → 本批 20 处迁移在生产里全部退化成罐头。
# 实测：_evidence/probe_prefix_cache.txt。
_cw = code_no_comment(func_src(MAIN_TEXT, 'chat_with_ai'))
ok('B22 事件请求必须带 lean=True（不带 = 生产里事件 AI 全灭，静默）',
   'lean=True' in _se_struct)
ok('B22b chat_with_ai 的 lean 分支必须跳过"每轮都在变"的三处：此刻 / 话题锚 / 记忆召回',
   '_ctx=""ifleanelseself._build_ai_context()' in _cw
   and 'if_focusandnotlean:' in _cw
   and 'if_recallandnotlean:' in _cw,
   _cw[:0])
ok('B22c lean 分支还必须跳过对话历史（history 每轮都变，同样打掉前缀缓存）',
   'ifnotlean:' in _cw, _cw[:0])
ok('B22d recall_text 在 lean 下**不被调用**（它会跑记忆图检索，比其它几项都贵）',
   'ifnotleanand_msisnotNone' in _cw, _cw[:0])
ok('B22e lean 是**默认 False**（对话路径不传就保持原行为：带话题锚与记忆召回）',
   'defchat_with_ai(self,text,on_reply,on_delta=None,lean=False):' in _cw, _cw[:0])
_dui_c = code_no_comment(DUI_TEXT)
# 判据只用"**带右括号的整调用**"这一个 needle：调用参数一旦多出 `lean=True`，
# 这个串就不再匹配 —— 比另写一条 `'lean=' not in …` 更准。
# （第一版就是另写了一条 `'lean' not in`，被 dialogue_ui 里的 `clean = …`
#   顶成了 `clean=…` 里的子串 → 假 FAIL。老教训第 7 次：needle 别挑会被别的词包住的串。）
ok('B22f 对话路径（dialogue_ui → parent.chat_with_ai）确实**不传** lean',
   'chat_with_ai(user_input,_on_ai_reply,_on_ai_delta)' in _dui_c,
   'call=%s' % ('chat_with_ai(user_input,_on_ai_reply,_on_ai_delta)' in _dui_c))

# ================================================================ C
section('C. 迁移完整性')

_calls = re.findall(r'speak_event\(\s*"([a-z_]+)"', code_no_comment(MAIN_TEXT))
# 抚摸那处的事件名由 pet_kind(部位) 动态给出（无字面量）→ 字面量 19 + 动态 1 = 20
ok('C1 迁移点计数 = 20（字面量 %d + pet_kind 动态 1）' % len(_calls),
   code_no_comment(MAIN_TEXT).count('self.speak_event(') == 20 and len(_calls) == 19,
   '字面量 %d 处：%s' % (len(_calls), sorted(_calls)))
_unknown = sorted(set(k for k in _calls if k not in E.EVENT_TIERS))
ok('C2 每个迁移点的事件名都在 EVENT_TIERS 里登记（防手抄错名字 → 静默退回罐头）',
   not _unknown, '未登记: %s' % _unknown)
ok('C3 抚摸用 pet_kind(部位) 动态取事件名（6 个部位 + 兜底都在表里）',
   code_no_comment(MAIN_TEXT).count('speak_event(pet_kind(pet_part)') == 1)

_mouse_rel = code_only_src(func_src(MAIN_TEXT, 'mouseReleaseEvent'))
ok('C4 mouseReleaseEvent 里不再有裸事件台词（长按 6 处 + 甩飞 1 处全迁走）',
   'add_dialogue(' not in _mouse_rel, _mouse_rel.count('add_dialogue('))
ok('C5 甩飞那句仍然是 instant 罐头（要求 0 延迟）',
   '"fling",["哇啊——！"]' in code_no_comment(func_src(MAIN_TEXT, 'mouseReleaseEvent'))
   or 'instant=True' in code_no_comment(func_src(MAIN_TEXT, 'mouseReleaseEvent')))
_dbl = code_only_src(func_src(MAIN_TEXT, 'mouseDoubleClickEvent'))
ok('C6 mouseDoubleClickEvent 里不再有裸事件台词', 'add_dialogue(' not in _dbl)
_press = code_only_src(func_src(MAIN_TEXT, 'mousePressEvent'))
ok('C7 mousePressEvent 只剩非-Ralsei 台词（三个交互点已迁；无残留裸台词）',
   'add_dialogue(' not in _press, _press.count('add_dialogue('))
ok('C8 物理状态机未动：坠落/摔扁仍是罐头（有意保留，不是漏迁）',
   'add_dialogue(' in code_only_src(func_src(MAIN_TEXT, 'start_fall'))
   and 'add_dialogue(' in code_only_src(func_src(MAIN_TEXT, 'trigger_splat')))
ok('C9 菜单抚摸/喂食已迁走', 'add_dialogue(' not in code_only_src(func_src(MAIN_TEXT, 'pet_ralsei'))
   and 'add_dialogue(' not in code_only_src(func_src(MAIN_TEXT, 'feed_ralsei')))

# —— C10~C12：S7 batch 2（迁移点在 modules/energy_hunger.py，**不在** main.py，
#    所以 C1 的 main.py 计数不变仍为 20；这里单独锁这一批） ——
ENERGY_TEXT = io.open(os.path.join(MODS, 'energy_hunger.py'), encoding='utf-8').read()
_rest_c = code_no_comment(func_src(ENERGY_TEXT, 'rest'))
_eat_c = code_no_comment(func_src(ENERGY_TEXT, 'eat'))
ok('C10 batch 2 迁移完整性：rest()/eat() 的"开始"台词已走事件唯一出口'
   '（不再有裸 add_dialogue；函数里只剩"拒绝原因"那一处直接显示，2 处降到 1 处）',
   ('add_dialogue("ralsei","我要休息一下啦' not in _rest_c)
   and ('add_dialogue("ralsei","哇！有好吃的！我开动啦！' not in _eat_c)
   and ('speak_event("rest_start"' in _rest_c)
   and ('speak_event("eat_start"' in _eat_c)
   and (_rest_c.count('add_dialogue(') == 1)
   and (_eat_c.count('add_dialogue(') == 1),
   ('rest.add_dialogue=%d' % _rest_c.count('add_dialogue('),
    'eat.add_dialogue=%d' % _eat_c.count('add_dialogue('),
    'rest_start' in _rest_c, 'eat_start' in _eat_c))
ok('C11 batch 2 的事件名已登记为 AI 档（只在一侧写 = 静默退回罐头）',
   E.tier_of('rest_start') == E.TIER_AI and E.tier_of('eat_start') == E.TIER_AI
   and 'rest_start' in E.EVENT_DIRECTIVES and 'eat_start' in E.EVENT_DIRECTIVES)
ok('C12 **拒绝原因说明仍保持罐头**（"为什么没反应"的唯一提示，交模型会丢信息）',
   '我现在精神得很，一点都不累哦！' in _rest_c
   and '我已经吃得饱饱的啦' in _eat_c)

# ================================================================ D
section('D. 行为级（真 QApplication + 桩宿主）')

from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer                               # noqa: E402
_app = QApplication.instance() or QApplication([])


def pump(ms=150):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        _app.processEvents()
        time.sleep(0.004)


class _Dui(object):
    AI_THINKING_PLACEHOLDER = '……'

    def __init__(self):
        self.said = []          # (speaker, msg, face, streamed)
        self.deltas = []        # 收到的流式分片（含 None = 擦除）
        self.shown = 0
        self.typing_text = ''
        self._streaming = False
        self._inputting = False
        self._ai_inflight = False

    def add_dialogue(self, speaker, msg, face='normal', _streamed=False):
        # 复刻真 dialogue_ui：思考占位只是"等待"提示，绝不能被当成一条正式消息
        # （`add_dialogue` 里那段 `if self.typing_text == AI_THINKING_PLACEHOLDER`）
        if self.typing_text == self.AI_THINKING_PLACEHOLDER:
            self.typing_text = ''
        self.said.append((speaker, msg, face, bool(_streamed)))
        # 复刻真 dialogue_ui：落定一条消息会把流式状态收掉
        # （`_finalize_stream` / `stop_typing` 都会清 `_streaming`）
        self._streaming = False

    def show_dialogue(self, *a, **k):
        self.shown += 1

    def _ai_thinking_on(self):
        # 复刻真 dialogue_ui 的可观测效果：进"等待首字"态 + 前台写「……」
        self.thinking = getattr(self, 'thinking', 0) + 1
        self.typing_text = self.AI_THINKING_PLACEHOLDER

    def _is_user_inputting(self):
        return self._inputting

    def stream_delta(self, chunk):
        self.deltas.append(chunk)
        self._streaming = chunk is not None


def make_host(api_enabled=True, cfg=None, auto=True, reply_value=None, delay_ms=0,
              min_interval=None, deadline=90, deltas=None, delta_delay=0):
    h = types.SimpleNamespace()
    h.api_enabled = api_enabled
    h.api_config = {} if cfg is None else cfg
    h.dialogue_ui = _Dui()
    h.last_interaction_time = 0
    h._event_line_picker = E.RecentLinePicker()
    h._event_speak_gen = 0
    h._event_speak_last = None
    h._event_speaking = False
    h._ai_delta_sink = None
    h.chat_calls = []
    h.EVENT_SPEAK_FIRST_TOKEN_MS = deadline
    h.EVENT_SPEAK_MAX_CHARS = R.EVENT_SPEAK_MAX_CHARS
    h.EVENT_SPEAK_MIN_INTERVAL = (R.EVENT_SPEAK_MIN_INTERVAL
                                  if min_interval is None else min_interval)

    def chat_with_ai(text, on_reply, on_delta=None, lean=False):
        h.chat_calls.append({'text': text, 'on_reply': on_reply, 'on_delta': on_delta,
                             'lean': lean})
        # 复刻真 chat_with_ai 的**关键副作用**：覆盖写 `_ai_delta_sink` 且**收尾不清空**
        # （S8 故意如此）—— D22 就是钉"事件门禁不许依赖它"的。
        h._ai_delta_sink = on_delta
        for i, d in enumerate(deltas or []):
            if on_delta is not None:
                QTimer.singleShot(delta_delay + i * 5, lambda _d=d: on_delta(_d))
        if auto:
            QTimer.singleShot(delta_delay + 5 * len(deltas or []) + delay_ms,
                              lambda: on_reply(reply_value))

    h.chat_with_ai = chat_with_ai
    for name in ('speak_event', '_event_ai_ready', '_event_say',
                 '_event_speech_enabled', '_pick_event_line'):
        setattr(h, name, types.MethodType(getattr(R, name), h))
    return h


def last_msg(h):
    return h.dialogue_ui.said[-1][1] if h.dialogue_ui.said else None


def last_streamed(h):
    return h.dialogue_ui.said[-1][3] if h.dialogue_ui.said else None


POOL = ['罐头台词']

# D1 AI 档：不立刻说话，等 AI 那句（流式：分片先到）
h = make_host(auto=True, reply_value='诶？你戳我做什么呀！', deltas=['诶？', '你戳我做什么呀！'])
h.speak_event('poke_body', POOL, 'curious')
ok('D1 AI 档：请求已发出、框子先开、且**没有**立刻说罐头',
   len(h.chat_calls) == 1 and h.dialogue_ui.shown == 1 and not h.dialogue_ui.said,
   (h.dialogue_ui.shown, h.dialogue_ui.said))
ok('D1b 事件请求带上了 on_delta（流式）', callable(h.chat_calls[0]['on_delta']))
ok('D1d 事件请求带上了 lean=True（否则 system 每轮都变 → 前缀缓存失效 → 必超时限）',
   h.chat_calls[0]['lean'] is True, h.chat_calls[0])
ok('D1c 等待首字期间框子是「……」态（不是空白），且占位没被当成一条消息',
   h.dialogue_ui.thinking == 1
   and h.dialogue_ui.typing_text == h.dialogue_ui.AI_THINKING_PLACEHOLDER
   and not h.dialogue_ui.said,
   (getattr(h.dialogue_ui, 'thinking', None), h.dialogue_ui.typing_text,
    h.dialogue_ui.said))
pump(250)
ok('D2 AI 回复到达后说 AI 那句（罐头让位）', last_msg(h) == '诶？你戳我做什么呀！', h.dialogue_ui.said)
ok('D2b 分片确实进了 dialogue_ui.stream_delta',
   h.dialogue_ui.deltas[:2] == ['诶？', '你戳我做什么呀！'], h.dialogue_ui.deltas)
ok('D2c 流式打过的句子走"定格"（streamed=True），不从头重打一遍',
   last_streamed(h) is True, h.dialogue_ui.said)
ok('D3 AI 档仍然把提示词交给 build_prompt（含事件旁白）',
   '戳' in h.chat_calls[0]['text'] and str(E.EVENT_MAX_CHARS) in h.chat_calls[0]['text'])

# D4 首字都没到 → 兜底罐头
h = make_host(auto=False)
h.speak_event('poke_body', POOL, 'curious')
ok('D4 AI 未响应时：当场不说话（还在等首字）', not h.dialogue_ui.said)
pump(250)
ok('D5 首字超时 → 说罐头（主人不会"戳了没反应"）',
   last_msg(h) == '罐头台词', h.dialogue_ui.said)

# D5b 首字到了就不再说罐头（即使超过首字时限）
h = make_host(auto=False, deltas=['诶？'], deadline=60)
h.speak_event('poke_body', POOL, 'curious')
pump(250)
ok('D5b 首字已到 → 兜底定时器**不**再插一句罐头（一次事件一个气泡）',
   not h.dialogue_ui.said and h.dialogue_ui.deltas == ['诶？'], h.dialogue_ui.said)

# D5c AI 沉默（None）→ 立刻罐头
h = make_host(auto=True, reply_value=None, deadline=5000, deltas=['说了一半', None])
h.speak_event('poke_body', POOL, 'curious')
pump(150)
ok('D5c AI 沉默/被判退（None）→ 立刻用罐头顶上，不干等兜底',
   last_msg(h) == '罐头台词', h.dialogue_ui.said)
ok('D5c2 擦除分片（None）被透传到 stream_delta', None in h.dialogue_ui.deltas,
   h.dialogue_ui.deltas)

# D5d 出戏句 → 作废 + 罐头
h = make_host(auto=True, reply_value='抱歉，我没有触觉无法感受被拉肩。',
              deltas=['抱歉，我没有触觉'], deadline=5000)
h.speak_event('poke_body', POOL, 'curious')
pump(150)
ok('D5d 出戏句（"我没有触觉"）被作废，回落罐头（宁可重复也不能自毁角色）',
   last_msg(h) == '罐头台词', h.dialogue_ui.said)

# D6 一个事件只给一个气泡
h = make_host(auto=False)
h.speak_event('poke_body', POOL, 'curious')
pump(250)
n_after_fallback = len(h.dialogue_ui.said)
h.chat_calls[0]['on_reply']('这句来晚了！')
pump(60)
ok('D6 兜底说过之后，AI 的迟到回复**不再补第二个气泡**',
   len(h.dialogue_ui.said) == n_after_fallback == 1, h.dialogue_ui.said)

# D6b/D6c 兜底之后迟到的**分片**也必须被丢弃 —— 真机 e2e 抓到的真 bug。
# 时序：首字 > 兜底时限 → 先说了罐头 → 几百毫秒后模型的字才到。
# 当时 `_on_delta` 只查世代号、不查 `state['said']`，于是：
#   ① 罐头的字已经打完，又被 AI 的半句顶掉（屏幕上说了两句不一样的话）；
#   ② `stream_delta` 把 dialogue_ui 切进流式态（`_streaming=True`），
#      而这次事件之后再没人清它（`_on_reply` 因 `state['said']` 提前返回）
#      → `_event_ai_ready` 的 `_streaming` 检查此后永远为真
#      → **之后所有事件永久退回罐头**（静默、无日志）。
# 这是 D22 那类"永久挡死"的第二个入口，所以单独锁两条。
h = make_host(auto=False, min_interval=0.0, deadline=60)
h.speak_event('poke_body', POOL, 'curious')
_d_late = h.chat_calls[0]['on_delta']
pump(180)                                   # 兜底已说话（罐头落定，_streaming 归 False）
_n_before = len(h.dialogue_ui.said)
_d_late('迟到的分片')
pump(40)
ok('D6b 兜底之后迟到的分片被丢弃（不画进框、不让 UI 进流式态）',
   h.dialogue_ui.deltas == [] and h.dialogue_ui._streaming is False
   and len(h.dialogue_ui.said) == _n_before,
   (h.dialogue_ui.deltas, h.dialogue_ui._streaming, h.dialogue_ui.said))
h.speak_event('poke_default', POOL, 'happy')
ok('D6c 兜底 + 迟到分片之后，下一个事件**仍然**走 AI（不许永久挡死）',
   len(h.chat_calls) == 2, 'chat_calls=%d _streaming=%r'
   % (len(h.chat_calls), h.dialogue_ui._streaming))

# D7/D8 世代号：事件 1 首字超时兜底（门禁复位）→ 事件 2 起来 → 事件 1 的迟到回调必须被丢弃
h = make_host(auto=False, min_interval=0.0, deadline=60)
h.speak_event('poke_body', POOL, 'curious')
cb1, d1 = h.chat_calls[0]['on_reply'], h.chat_calls[0]['on_delta']
pump(180)
ok('D7 事件 1 首字超时 → 兜底罐头 + 门禁复位（否则后续事件全被挡）',
   last_msg(h) == '罐头台词' and h._event_speaking is False,
   (h.dialogue_ui.said, h._event_speaking))
h.dialogue_ui.said = []
h.dialogue_ui.deltas = []
h.dialogue_ui._streaming = False
h.speak_event('poke_default', POOL, 'happy')
cb2 = h.chat_calls[1]['on_reply']
cb1('旧事件的话')
d1('旧分片')
pump(40)
ok('D8 旧事件的迟到回复/分片按世代丢弃（不往对话框里塞过期内容）',
   last_msg(h) is None and not h.dialogue_ui.deltas, (h.dialogue_ui.said, h.dialogue_ui.deltas))
cb2('新事件的话')
pump(40)
ok('D8b 最新事件的回复正常显示', last_msg(h) == '新事件的话')

# D9 长回复被压成一句
h = make_host(auto=True, reply_value='诶？！听到这话我都有点不好意思起来了。感觉就像在阳光下晒着一样舒服呢。好开心。')
h.speak_event('poke_body', POOL, 'curious')
pump(250)
ok('D9 AI 长回复压成第一句且不超上限',
   last_msg(h) == '诶？！听到这话我都有点不好意思起来了。'
   and len(last_msg(h)) <= R.EVENT_SPEAK_MAX_CHARS, last_msg(h))

# D11 罐头路径（AI 关闭 / 关档 / instant / 未登记 / 让路）
def canned_case(desc, expect_canned, **kw):
    hh = make_host(**kw.get('host', {}))
    if 'tweak' in kw:
        kw['tweak'](hh)
    hh.speak_event(kw.get('kind', 'poke_body'), POOL, 'happy',
                   instant=kw.get('instant', False))
    pump(80)
    sid = [c['text'] for c in hh.chat_calls]
    if expect_canned:
        return (last_msg(hh) == '罐头台词' and not hh.chat_calls), (desc, hh.dialogue_ui.said, sid)
    return (bool(hh.chat_calls)), (desc, hh.dialogue_ui.said, sid)


ok_c, det_c = canned_case('AI 总开关关闭', True, host={'api_enabled': False})
ok('D11 api.enabled=False → 立刻罐头且**不发请求**', ok_c, det_c)
ok_c, det_c = canned_case('S7 开关关闭', True, host={'cfg': {'event_speech': False}})
ok('D12 api.event_speech=False → 立刻罐头（一键退回改造前行为）', ok_c, det_c)
ok_c, det_c = canned_case('instant=True', True, instant=True)
ok('D13 instant=True → 立刻罐头（短促反应不交给模型）', ok_c, det_c)
ok_c, det_c = canned_case('未登记事件', True, kind='signature_unknown_event')
ok('D14 未登记事件 → 立刻罐头（白名单语义）', ok_c, det_c)


def _typing(x):
    x.dialogue_ui._inputting = True


ok_c, det_c = canned_case('主人在打字', True, tweak=_typing)
ok('D15 主人正在输入 → 立刻罐头（不抢话）', ok_c, det_c)


def _streaming(x):
    x.dialogue_ui._streaming = True


ok_c, det_c = canned_case('对话正在流式', True, tweak=_streaming)
ok('D16 对话正在流式 → 立刻罐头（别插进主人那条正在打的字里）', ok_c, det_c)


def _inflight(x):
    x.dialogue_ui._ai_inflight = True


ok_c, det_c = canned_case('主人的请求在路上', True, tweak=_inflight)
ok('D17 主人的对话请求还在等回复（_ai_inflight）→ 立刻罐头', ok_c, det_c)


def _event_busy(x):
    x._event_speaking = True


ok_c, det_c = canned_case('上一个事件还在等', True, tweak=_event_busy)
ok('D17b 上一个事件还在等 AI → 不叠加第二个请求（_event_speaking）', ok_c, det_c)

# D18 频率闸
h = make_host(auto=False)
h.speak_event('poke_body', POOL)
h.speak_event('poke_body', POOL)
pump(20)
ok('D18 频率闸：2 秒内的第二次事件不发请求（连戳不产生请求风暴）',
   len(h.chat_calls) == 1 and len(h.dialogue_ui.said) == 1, (len(h.chat_calls), h.dialogue_ui.said))

# D19 罐头也进去重窗口：连戳 3 次不会连着同一句
h = make_host(api_enabled=False)
for _ in range(3):
    h.speak_event('poke_body', ['甲', '乙'])
got = [m for _s, m, _f, _st in h.dialogue_ui.said]
ok('D19 罐头连续 3 次不说重样（改造前 random.choice 三选一很容易撞）',
   len(set(got)) >= 2, got)
ok('D20 去重窗口记下了刚说过的罐头', len(h._event_line_picker._recent) == 3,
   h._event_line_picker._recent)

# D21 ★回归 ★：一次事件走完后，**下一次事件仍然要走 AI**
#   缺陷原型：门禁曾用 `_ai_delta_sink is not None` 判"对话在流式"，而 S8 设计上
#   **收尾不清空** sink → 开过一次流式之后，所有事件永远走罐头（AI 档形同虚设，
#   而且是静默的）。这条测试把 sink 留在非空状态，专钉这个。
h = make_host(auto=True, reply_value='第一次的话', deltas=['第一次的话'], min_interval=0.0)
h.speak_event('poke_body', POOL)
pump(200)
ok('D21 事件 1 走完（sink 仍非空，模拟 S8 收尾不清空）', len(h.chat_calls) == 1
   and h._ai_delta_sink is not None and last_msg(h) == '第一次的话',
   (h.chat_calls and h._ai_delta_sink, h.dialogue_ui.said))
h._event_speak_last = None
h.dialogue_ui.said = []
h.dialogue_ui.deltas = []
h.dialogue_ui._streaming = False
h.speak_event('poke_default', POOL)
pump(200)
ok('D22 事件 2 **仍然**走 AI（不许被残留的 _ai_delta_sink 永久挡住）',
   len(h.chat_calls) == 2 and last_msg(h) == '第一次的话', h.dialogue_ui.said)
ok('D22b 事件 2 结束后 _event_speaking 复位（不留下永久门禁）',
   h._event_speaking is False, h._event_speaking)

# D23 罐头与 AI 混用时，去重窗口两边都记
h = make_host(auto=True, reply_value='AI 说的一句', deltas=['AI 说的一句'], min_interval=0.0)
h.speak_event('poke_body', ['罐头甲'])
pump(200)
h.api_enabled = False
h.speak_event('poke_body', ['罐头甲'])
pump(50)
ok('D23 去重窗口同时收下 AI 台词与罐头（跨模式去重）',
   h._event_line_picker._recent == ['AI 说的一句', '罐头甲'],
   h._event_line_picker._recent)
ok('D23b 只能选一句时，罐头不会被 AI 刚说的那句挡住（池小也不至于"没反应"）',
   last_msg(h) == '罐头甲', h.dialogue_ui.said)

# D24/D25 batch 2：energy_hunger 的 rest_start / eat_start 走的是同一条出口，
# 但它们是**别的模块**调进来的（`self.parent.speak_event(...)`），单独证明一次。
_REST_POOL = ['我要休息一下啦... 呼...']
h = make_host(auto=True, reply_value='嗯……那我就眯一小会儿啦。')
h.speak_event('rest_start', _REST_POOL, 'normal')
ok('D24 rest_start 在 AI 可用时走 AI（发请求、先开框、不发罐头）',
   len(h.chat_calls) == 1 and h.dialogue_ui.shown == 1 and not h.dialogue_ui.said,
   (h.chat_calls, h.dialogue_ui.shown, h.dialogue_ui.said))
ok('D24b rest_start 的请求文案是「主人让你去休息」的旁白（不是罐头原句）',
   ('休息' in h.chat_calls[0]['text']) and (_REST_POOL[0] not in h.chat_calls[0]['text']),
   h.chat_calls[0]['text'])
pump(200)
ok('D24c rest_start 的 AI 回复到达后显示出来', last_msg(h) == '嗯……那我就眯一小会儿啦。',
   h.dialogue_ui.said)

h = make_host(api_enabled=False)
_out = h.speak_event('eat_start', ['哇！有好吃的！我开动啦！'], 'happy')
ok('D25 AI 关闭 → eat_start 立刻说罐头原句，且**不发请求**'
   '（守既有契约：AI 关闭不得改口、不得静默）',
   _out == '哇！有好吃的！我开动啦！' and len(h.chat_calls) == 0
   and last_msg(h) == '哇！有好吃的！我开动啦！',
   (h.chat_calls, h.dialogue_ui.said))

# E
section('E. 配置')
_sysmod = __import__('config_manager')
_dft = _sysmod.ConfigManager._default_config()
ok('E1 config_manager 默认值含 api.event_speech=True',
   _dft.get('api', {}).get('event_speech') is True, _dft.get('api'))
import json as _json
_cfgj = _json.load(io.open(os.path.join(PET, 'config.json'), encoding='utf-8'))
ok('E2 仓库 config.json 含 event_speech=true',
   _cfgj.get('api', {}).get('event_speech') is True, _cfgj.get('api'))
h = make_host(cfg={})
ok('E3 _event_speech_enabled 缺省开启（老配置没这个键也走 AI）', h._event_speech_enabled() is True)
h = make_host(cfg={'event_speech': False})
ok('E4 显式 false 生效', h._event_speech_enabled() is False)
h = make_host(api_enabled=False, cfg={})
ok('E5 api.enabled=False 时 S7 一定关（不会绕过总开关）', h._event_speech_enabled() is False)

# ================================================================ F
section('F. lean 请求的真实形态（真 chat_with_ai + 假 api_client，离线）')
# 为什么要真跑 chat_with_ai 而不是只查源码：B22 组是"源码里写了 lean"，
# 万一哪天有人把上下文又拼回去（比如在 lean 分支外 append），源码锁看不出行为差异。
# 这里把**真正发给模型的 system / history**抓下来，断言"一个会变的东西都没有"。
#
# 这是本项目第 6 次踩"桩要跟着主程序调用面走"（见 §11.6 的教训）：
# chat_with_ai 从 3 参变 4 参，D 组的桩当场就会 TypeError → 已被 D1d 接住。
_MARK_CTX = '【此刻】现在是凌晨（F 组桩）'
_MARK_FOCUS = '【我们正在聊】F 组话题锚，这一段每轮都会变'
_MARK_RECALL = '【零星想起】F 组记忆召回，这一段每轮都会变'


class _FakeSignal(object):
    """够用的 Qt 信号替身：emit 就直接同步调用回调（F 组只关心参数）。"""

    def __init__(self, fn):
        self._fn = fn

    def emit(self, *a):
        return self._fn(*a)


def make_lean_host():
    fh = types.SimpleNamespace()
    fh.api_enabled = True
    fh._persona_cache = None
    fh._ai_delta_gen = 0
    fh._ai_delta_sink = None
    fh._api_delta = _FakeSignal(lambda gen, piece: None)   # 分片内容不在本组关注点
    fh.calls = []
    fh.history_reads = []
    fh.recall_reads = []

    class _Dui(object):
        def get_ai_history(self, limit=6):
            fh.history_reads.append(limit)
            return [('user', '历史甲'), ('assistant', '历史乙')]

        def get_focus_brief(self):
            return _MARK_FOCUS

    d = _Dui()
    fh.dialogue_ui = d
    fh.dialogue_ui.get_ai_history = d.get_ai_history

    class _Mem(object):
        def recall_text(self, text, limit=3):
            fh.recall_reads.append(text)
            return _MARK_RECALL

        def get_user_preference(self, k, d=None):
            return d

        def get_user_preferences_summary(self):
            return []

    fh.memory_system = _Mem()

    class _Cli(object):
        enabled = True

        def chat_stream(self, prompt, system_prompt=None, on_delta=None, **kw):
            fh.calls.append({'prompt': prompt, 'system': system_prompt,
                             'history': list(kw.get('history') or []),
                             'on_delta': on_delta})
            if callable(on_delta):
                on_delta('嗯')
            return '嗯。'

    fh.api_client = _Cli()
    fh._ai_stream_enabled = lambda: True
    fh._ai_chat_options = lambda: {'temperature': 0.85, 'max_tokens': 256}
    # _clean_ai_reply 不在本组关注点（它有独立套件），直接放行，避免牵扯别的依赖
    fh._clean_ai_reply = lambda reply, recent=None: reply
    fh._build_ai_context = lambda: _MARK_CTX       # 用桩顶掉真实现（真实现会读天气/情绪）
    for name in ('chat_with_ai', '_build_persona_prompt'):
        setattr(fh, name, types.MethodType(getattr(R, name), fh))
    return fh


def run_chat(lean):
    fh = make_lean_host()
    done = []
    fh._api_result = _FakeSignal(lambda reply, cb: (done.append(reply), cb(reply)))
    fh.chat_with_ai('（主人用手指戳了戳你的身体。）', lambda r: None, lambda c: None,
                    lean=lean)
    t0 = time.time()
    while not done and time.time() - t0 < 5:
        pump(30)                                   # 等后台线程回来
    return fh


_fh_lean = run_chat(True)
_fh_full = run_chat(False)

ok('F1 lean 请求真的发出去了（抓到了 system / history）',
   len(_fh_lean.calls) == 1 and len(_fh_full.calls) == 1,
   (len(_fh_lean.calls), len(_fh_full.calls)))
_lean_sys = (_fh_lean.calls[0]['system'] or '') if _fh_lean.calls else ''
_full_sys = (_fh_full.calls[0]['system'] or '') if _fh_full.calls else ''

ok('F2 lean 的 system **不含**【此刻】/话题锚/记忆召回（一个会变的都没有）',
   _MARK_CTX not in _lean_sys and _MARK_FOCUS not in _lean_sys
   and _MARK_RECALL not in _lean_sys,
   _lean_sys[-160:])
ok('F2b 对照组（不传 lean）三样都在 —— 证明 F2 不是"因为压根没拼"',
   _MARK_CTX in _full_sys and _MARK_FOCUS in _full_sys and _MARK_RECALL in _full_sys,
   _full_sys[-160:])
ok('F3 lean 的 system 确实是 persona（不是空串兜底），且比完整版短',
   'Ralsei' in _lean_sys and 0 < len(_lean_sys) < len(_full_sys),
   (len(_lean_sys), len(_full_sys)))
ok('F4 lean 不发对话历史（history == []）',
   _fh_lean.calls[0]['history'] == [], _fh_lean.calls[0]['history'])
ok('F4b 对照组照旧带历史',
   _fh_full.calls[0]['history'] == [('user', '历史甲'), ('assistant', '历史乙')],
   _fh_full.calls[0]['history'])
ok('F4c lean 下**根本不去读**历史（get_ai_history 零调用）',
   _fh_lean.history_reads == [], _fh_lean.history_reads)
ok('F5 lean 下**根本不调** recall_text（记忆图检索比其它几项都贵）',
   _fh_lean.recall_reads == [] and len(_fh_full.recall_reads) == 1,
   (_fh_lean.recall_reads, _fh_full.recall_reads))
ok('F6 lean 仍然是**流式**（on_delta 有效），否则首字收益白拿',
   callable(_fh_lean.calls[0]['on_delta']))

print('')
print('PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - %s' % f)
sys.exit(1 if FAIL else 0)
