# -*- coding: utf-8 -*-
"""第140轮核心文件复检：改过 `main.py` / `npc_persona.py` 之后，逐项打 PASS/FAIL 并落盘。

为什么要有这个脚本：`check140` 守的是"新行为对不对"，本脚本守的是
**"改完这一轮，项目还是原来那个项目"** —— 语法、结构、编码、恒真判据、
逐令牌回验、以及"改动面没有外溢"。

★ 纪律（第139轮定的）：
  · 语法检查用 `ast.parse`，**不用 `py_compile`** —— 后者会产 `.pyc`，
    复检不许改变被测状态（`.pyc` 会让工作区变脏、还会撞"无 .pyc 被跟踪"这类判据）。
  · 逐令牌回验用**宽式匹配**（§ 可选），别重复踩"判据太窄 ⇒ 误报"。
  · 本文件自己也要过一遍恒真判据检查（H 段）。

★ 唯一对外写入：`_evidence/recheck140.json`（复检结论留痕）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
NP_PY = os.path.join(PET, 'modules', 'npc_persona.py')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
CD_PY = os.path.join(PET, 'modules', 'companion_dialog.py')
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
CARD_JSON = os.path.join(PET, 'assets', 'npc', '_training', 'cards', 'ralsei.json')
EV = os.path.join(ROUND, '_evidence')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


MAIN = _read(MAIN_PY)
NP = _read(NP_PY)
ES = _read(ES_PY)
CD = _read(CD_PY)
PERSONA_TXT = _read(PERSONA)
CARD = _json(CARD_JSON)

# =============================================== A 语法
head(u'A. 语法：四个被改过的文件都还能 parse（用 ast，不产 .pyc）')

for _nm, _src in ((u'main.py', MAIN), (u'npc_persona.py', NP),
                  (u'event_speech.py', ES), (u'companion_dialog.py', CD)):
    _ok = True
    _err = ''
    try:
        ast.parse(_src)
    except SyntaxError as e:
        _ok = False
        _err = u'%s (line %s)' % (e.msg, e.lineno)
    check(u'A %s 可解析' % _nm, _ok, _err)

# =============================================== B 结构
head(u'B. 结构：main.py 没被整体重排；新增函数各就各位')

_lines = MAIN.count(u'\n') + (0 if MAIN.endswith(u'\n') else 1)
_crlf = MAIN.count(u'\r\n')
_bare_lf = MAIN.count(u'\n') - _crlf
check(u'B1 main.py 行尾仍是**全 CRLF**（Edit 没把文件打散成混行）',
      _bare_lf == 0 and MAIN.count(u'\r') == _crlf,
      u'行=%d CRLF=%d 裸LF=%d' % (_lines, _crlf, _bare_lf))
check(u'B2 main.py 顶层类 `RalseiPet` 还在、`_clean_ai_reply` 仍是它的方法',
      u'class RalseiPet' in MAIN and u'    def _clean_ai_reply(self, reply, recent=None, speaker=None):' in MAIN)
check(u'B3 加载层两个函数都在（`training_length_policy` / `reply_length_limits`）',
      u'def training_length_policy(npc_id, assets_dir=None):' in NP
      and u'def reply_length_limits(npc_id, hard):' in NP)
check(u'B4 缓存是**独立一份**（不与 `_PATCH_CACHE` 混用）',
      u'_POLICY_CACHE = {}' in NP and u'_PATCH_CACHE = {}' in NP
      and u'_POLICY_CACHE[key]' in NP)

# =============================================== C 本轮改动本身
head(u'C. 本轮改动本身：卡片驱动字数、只许收紧、句数不执行')

check(u'C1 卡片仍是 (200, 3)（本轮**没有**改数据，只改执行）',
      (CARD.get('length_policy') or {}).get('max_chars') == 200
      and (CARD.get('length_policy') or {}).get('max_sentences') == 3)
check(u'C2 `_clean_ai_reply` 第 3 步从 `npc_persona_mod.reply_length_limits` 取阈值',
      u'npc_persona_mod.reply_length_limits(' in MAIN)
check(u'C3 只许收紧：`reply_length_limits` 里是 `min(...)` 不是 `max(...)`',
      u'return min(int(got[0]), cap), int(got[1])' in NP
      and u'return max(int(got[0]), cap), int(got[1])' not in NP)
check(u'C4 句数额度在 `_clean_ai_reply` 里**只赋值不使用**（`_max_sent`）',
      u'max_chars, _max_sent = npc_persona_mod.reply_length_limits(' in MAIN)
check(u'C5 两个调用点都把 `speaker` 传下去了（chat_with_ai 主路 + 重采样路）',
      MAIN.count(u'speaker=speaker') >= 2, u'处数=%d' % MAIN.count(u'speaker=speaker'))
check(u'C6 长度结算**不在 self 上**（桩只绑 `_clean_ai_reply`，挂 self 会被 except 吞掉）',
      u'self._reply_length_policy' not in MAIN)
check(u'C7 `type(chars) is int` 写法在位（`isinstance` 会把 `true` 当成 1）',
      u'if type(chars) is int and type(sents) is int' in NP)

# =============================================== D 编码
head(u'D. 编码：无 BOM、无替换符（U+FFFD）')

for _nm, _src in ((u'main.py', MAIN), (u'npc_persona.py', NP),
                  (u'event_speech.py', ES), (u'companion_dialog.py', CD),
                  (u'ralsei_persona.md', PERSONA_TXT)):
    check(u'D %s 无 BOM、无 U+FFFD' % _nm,
          not _src.startswith(u'\ufeff') and u'\ufffd' not in _src)

# =============================================== E 恒真判据复查
head(u'E. 恒真判据复查：`check(desc, True)` 与 `ok(True, ...)` 两套 harness 都要查')

_PAIR = [(u'check140.py', os.path.join(HERE, 'check140.py')),
         (u'mutate140.py', os.path.join(HERE, 'mutate140.py'))]
for _nm, _p in _PAIR:
    _src = _read(_p)
    _t = ast.parse(_src)
    _trivial = []
    for _nd in ast.walk(_t):
        if not isinstance(_nd, ast.Call):
            continue
        _fn = _nd.func
        _name = _fn.id if isinstance(_fn, ast.Name) else ''
        # `check(desc, cond, ...)` 的判定位是第 2 实参；`ok(cond, msg)` 是第 1 个
        _idx = 1 if _name == 'check' else (0 if _name == 'ok' else None)
        if _idx is None or len(_nd.args) <= _idx:
            continue
        _a = _nd.args[_idx]
        if isinstance(_a, ast.Constant) and _a.value is True:
            _trivial.append(_a.lineno)
    check(u'E %s 无恒真判据（判定位是常量 True）' % _nm, not _trivial,
          u'行=%r' % (_trivial,))

check(u'E3 本文件也没有恒真判据',
      not [1 for _nd in ast.walk(ast.parse(_read(os.path.abspath(__file__))))
           if isinstance(_nd, ast.Call) and isinstance(_nd.func, ast.Name)
           and _nd.func.id == 'check' and len(_nd.args) > 1
           and isinstance(_nd.args[1], ast.Constant) and _nd.args[1].value is True])

# =============================================== F 逐令牌回验
head(u'F. 逐令牌回验：本轮改/新增/没动的关键令牌，逐个回原文件 `in` 一次')

TOKENS = [
    (u'npc_persona.py', NP, u'training_length_policy'),
    (u'npc_persona.py', NP, u'reply_length_limits'),
    (u'npc_persona.py', NP, u'max_sentences'),
    (u'npc_persona.py', NP, u'_POLICY_CACHE'),
    (u'main.py', MAIN, u'reply_length_limits'),
    (u'main.py', MAIN, u'_max_sent'),
    (u'main.py', MAIN, u'speaker=speaker'),
    (u'main.py', MAIN, u'AI_REPLY_MAX_CHARS = 220'),
    (u'companion_dialog.py', CD, u'MAX_TEXT_CHARS = 220'),
    (u'event_speech.py', ES, u'EVENT_MAX_CHARS = 24'),
    (u'event_speech.py', ES, u'AUTO_SPEAK_MAX_CHARS = 40'),
    (u'ralsei_persona.md', PERSONA_TXT, u'一次只说 1~3 句'),
    (u'ralsei_persona.md', PERSONA_TXT, u'别拿它当句号'),
]
_bad = [t for _f, _s, t in TOKENS if t not in _s]
check(u'F1 %d 个令牌逐个都在（缺一个就说明改动没落到该落的地方）' % len(TOKENS),
      not _bad, u'缺=%r' % (_bad,))

check(u'F2 人设第 57 行那句「别拿它当句号」仍在 —— 它是本轮切句口径的唯一依据',
      u'别拿它当句号' in PERSONA_TXT)

# =============================================== G 改动面
head(u'G. 改动面：只动了该动的，产品常量一个没被偷改')

check(u'G1 `AI_REPLY_MAX_CHARS` 仍是 220（兜底不动，收紧交给卡片）',
      u'    AI_REPLY_MAX_CHARS = 220' in MAIN)
check(u'G2 事件台词 24 / 主动开口 40 未动',
      u'EVENT_MAX_CHARS = 24' in ES and u'AUTO_SPEAK_MAX_CHARS = 40' in ES)
check(u'G3 `companion_dialog.MAX_TEXT_CHARS` 仍是 220（与兜底同值的约定没破）',
      u'MAX_TEXT_CHARS = 220' in CD)
check(u'G4 本轮没有新增模块（`round5_smoke` 的模块数、`scene_p0 A6` 白名单都不用动）',
      not os.path.exists(os.path.join(PET, 'modules', 'reply_length.py'))
      and not os.path.exists(os.path.join(PET, 'modules', 'length_policy.py')))
check(u'G5 `event_speech.py` 里那句过期注释（`AI_REPLY_MAX_CHARS=80`）已清',
      u'AI_REPLY_MAX_CHARS=80' not in ES)

# =============================================== H 自检
head(u'H. 自检：本文件不许写产品文件；输出可留痕')

_SELF = _read(os.path.abspath(__file__))
_tree = ast.parse(_SELF)
_writes = []
for _nd in ast.walk(_tree):
    if not isinstance(_nd, ast.Call):
        continue
    _fn = _nd.func
    # `open(...)` 与 `io.open(...)` 两种写法都要认 —— 本文件用的是后者，
    # 只认 `ast.Name` 会得到"零处写入"，然后 H1 因为 `len([])==1` 不成立而报红
    # （看起来像产品被写了，其实是我漏认了一种写法）。
    _is_open = ((isinstance(_fn, ast.Name) and _fn.id == 'open')
                or (isinstance(_fn, ast.Attribute) and _fn.attr == 'open'))
    if not _is_open:
        continue
    _mode = _nd.args[1] if len(_nd.args) > 1 else None
    if isinstance(_mode, ast.Constant) and isinstance(_mode.value, str) and 'w' in _mode.value:
        _writes.append(ast.get_source_segment(_SELF, _nd.args[0]) or '')
# ★ 第一版写的是"零处写文件"，结果它把自己落盘 `_evidence/recheck140.json` 判红了
#   —— 判据太严也是误报。真正要守的是：**写的目标不许是产品目录**。
check(u'H1 本文件只写 `_evidence/` 一处，产品文件零写入（AST 取实参源码判目标）',
      len(_writes) == 1 and all(u'EV' in _w for _w in _writes),
      u'写入目标=%r' % (_writes,))

if not os.path.isdir(EV):
    os.makedirs(EV)
_out = {'pass': _n['p'], 'fail': _n['f'],
        'main_lines': _lines, 'main_crlf': _crlf, 'main_bare_lf': _bare_lf,
        'card_policy': CARD.get('length_policy'),
        'failed': _failed}
with io.open(os.path.join(EV, 'recheck140.json'), 'w', encoding='utf-8', newline='') as _f:
    _f.write(json.dumps(_out, ensure_ascii=False, indent=1))

check(u'H2 复检结论已落盘（`_evidence/recheck140.json`）',
      os.path.exists(os.path.join(EV, 'recheck140.json')))

print(u'')
print(u'=' * 78)
print(u'recheck140_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - ' + _d)
sys.exit(1 if _n['f'] else 0)
