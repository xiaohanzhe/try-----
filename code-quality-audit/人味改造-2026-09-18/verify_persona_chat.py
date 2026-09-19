# -*- coding: utf-8 -*-
"""第十八轮（并行线）验证：对话 AI「人味」改造 —— 角色设定外置 + 接线修对 + 输出护栏。

背景
----
诊断见项目根 `Ralsei对话人味诊断与训练方案_2026-09-18.md`，证据见
`code-quality-audit/人味诊断-2026-09-18/_evidence/`。一句话：
**「没活人味」的主因不是 3B 模型不行，是提示词与接线没接对。**

本轮改的东西，以及每条为什么必须被锁住（都踩过坑）
----------------------------------------------------
1) **角色设定外置成单一真源** `ralsei_pet/assets/ralsei_persona.md`。
   为什么不能只写在 Modelfile 里：实测 Ollama 用 `messages` 里的 system
   **整体替换** Modelfile 的 SYSTEM（不传 system 时 prompt_eval_count=1237，
   传了之后骤降到 41）→ 写在模型里的人设，真实应用里**一次都不会生效**。

2) **persona 文件本身不能写 markdown**。它是喂给模型的提示词，不是给人看的文档；
   里面出现 `**` / 行首 `#` 会直接被 3B 学去（实测输出过
   `**听到也让我心里暖暖的**`，而对话框是逐字打字机渲染，星号会原样显示）。

3) **用户消息保持纯原话**，【此刻】/话题锚/记忆召回一律挂 system 尾部。
   拼在用户消息前面时模型会当成"用户说的话"并复述成回答（E4-V0）。

4) **车轱辘话护栏**：判退只看"和自己最近说过的话重复"，**不看"像不像 persona 示范"**。
   这是被实测推翻过一次的设计：3B 对「我好喜欢你呀」这类高频问题会**稳定地**
   吐出示范句，若示范句一律判退，真机链路上是"判退→重采样→还是照抄→交回 None
   →观众看到内置规则台词"，比照抄本身更出戏。示范句本身是好台词，第一次说出来没问题；
   真正出戏的是同一句反复出现 —— 第二次再想抄，它就落在 recent 里了。
   **所以本套件有一条"防回退"断言：回复等于 persona 示范句、但 recent 为空时必须放行。**

5) **判退后重采样**（抬温 +「换一个说法」），而不是直接沉默。

分组
----
  A persona 文件契约（存在 / 章节 / 桌宠化口径 / 无 markdown / 示范成对）
  B main.py 接线（源码级 + 行为级）
  C 输出护栏行为（14 用例，合成 persona，与内容解耦）
  D 判退后重采样链路（FakeCli 行为级）
  E 关键词拦截收紧（软闲聊放行 / 硬指令仍子串）
  F 运行时配置与 Modelfile

本套件**不打网络、不调用 Ollama**（模型质量不进回归基线 —— 它天生不可复现）。
必须用 C:\\Python311\\python.exe 运行（PyQt5）。
"""
import io
import os
import sys
import threading
import time
import types
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
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
MAIN_PY = os.path.join(SRC, 'main.py')
DIALOGUE_PY = os.path.join(MODS, 'dialogue_ui.py')
CFG_MGR_PY = os.path.join(MODS, 'config_manager.py')
PERSONA_MD = os.path.join(PET, 'assets', 'ralsei_persona.md')
MODELFILE = os.path.join(PET, 'assets', 'ralsei.modelfile')
CFG_JSON = os.path.join(PET, 'config.json')

MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()
DIALOGUE_TEXT = io.open(DIALOGUE_PY, encoding='utf-8').read()

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def code_only_src(src):
    """剥掉注释/字符串后的 token 串联（空白抹平）。

    铁律（MEMORY「验证脚本教训」）：`"字面量" in 源码` 会被注释/文档串误命中，
    所以源码级断言一律走这里；且 tokenize **不产空白 token**，
    拼回必须用 ' '.join（''.join 会把 `import heapq` 粘成 `importheapq`）。
    """
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in _DROP:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


def code_no_comment(src):
    """**只剥注释**（字符串字面量保留）—— 要找"字符串 needle"时必须用这个。

    为什么必须有第二个工具：`code_only_src` 把 STRING 也丢了，于是
      断言 `'assistant'` 之类的字面量 needle 永远匹配不上（B3/B4/B6/B7 首跑全挂，
      正是 MEMORY 里已记过的坑：「找字符串字面量 needle 要用 code_no_comment()」）。
    """
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


CODE_MAIN = code_only_src(MAIN_TEXT)
CODE_DIALOGUE = code_only_src(DIALOGUE_TEXT)


def func_src(src, name, cls=None):
    """取某个函数/方法的源码正文（顺序断言必须限定在目标函数体内，
    用全文件 .index() 会命中别的函数 → 判反）。"""
    lines = src.splitlines()
    start = None
    indent = None
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


# ---------------------------------------------------------------- A
section('A. persona 文件契约（单一真源）')
ok('A1 persona 文件存在且非空', os.path.exists(PERSONA_MD) and os.path.getsize(PERSONA_MD) > 800,
   'size=%s' % (os.path.getsize(PERSONA_MD) if os.path.exists(PERSONA_MD) else None))

PERSONA = io.open(PERSONA_MD, encoding='utf-8').read() if os.path.exists(PERSONA_MD) else ''
for tag, label in (('我是谁', 'A2 有人格定义节'), ('我现在在哪', 'A3 有桌宠化定位节'),
                   ('我怎么说', 'A4 有说话方式节'), ('我的语气', 'A5 有情绪反应节'),
                   ('语气示范', 'A6 有语气示范节')):
    ok('%s（%s）' % (label, tag), tag in PERSONA)

ok('A7 桌宠化口径：明确"主人不是 Kris"',
   '不是 Kris' in PERSONA and 'Windows' in PERSONA)
ok('A8 含违禁套话清单', '我理解你的感受' in PERSONA and '作为一个语言模型' in PERSONA)
ok('A9 明确"不要照抄示范句"', '不要整句搬' in PERSONA)
ok('A10 明确"复读口头禅要换着说"', '你还好吗' in PERSONA)

_bad_md = [m for m in ('**', '\n#', '\n>') if m in PERSONA]
ok('A11 persona 里没有 markdown 标记（它是 prompt，不是文档）', not _bad_md,
   '发现=%r' % (_bad_md,))

_n_owner = len([1 for ln in PERSONA.splitlines() if ln.startswith('主人：')])
_n_me = len([1 for ln in PERSONA.splitlines() if ln.startswith('我：')])
# A12 原断言是"主人：/ 我： 各 3 组"（few-shot 成对示范）。
# 2026-09-19 实测推翻了这个设计：**成对示范里的整句会被 4B 逐字背出来** ——
# 「今天吃了火锅」「我好喜欢你呀」两个高频输入，新旧 persona 都稳定输出示范原句。
# 所以把"整句示范"换成"三条接法规则 + 按场合绑定的短碎片"，并保留一条
# "不要整句搬"的显式禁令（见 A9）。
# 断言随之改成"三条接法规则齐备"—— 这才是 now 真正承载行为锚的东西，
# 而且比数对数更有判别力（少一条就说明行为锚缺了一角）。
_RULES = ('主人说的是坏消息', '主人说的是好消息', '不知道自己该说什么的时候')
_missing = [r for r in _RULES if r not in PERSONA]
ok('A12 三条"碰到事该怎么接"规则齐备（坏消息 / 好消息 / 不知道说什么）',
   not _missing, '缺=%r' % (_missing,))
# 反向控制：确认旧断言依赖的成对示范**确实已经不在了**，
# 否则说明改动没生效、上面那条断言是在测一份还在用旧结构的文件。
ok('A12b 反向控制：成对示范（主人：/ 我：）已移除，不再逐字可搬',
   _n_owner == 0 and _n_me == 0, '主人=%d 我=%d' % (_n_owner, _n_me))

# ---------------------------------------------------------------- B
section('B. main.py 接线（源码级 + 行为级）')

_f_chat = func_src(MAIN_TEXT, 'chat_with_ai')
_CHAT2 = code_no_comment(_f_chat)     # 保留字符串字面量（见 code_no_comment 注释）
ok('B1 chat_with_ai 里用户消息保持纯原话（user_msg = text）',
   'user_msg=text' in code_only_src(_f_chat))
ok('B2 chat_with_ai 的 system 来自 _build_persona_prompt()',
   'system=self._build_persona_prompt()' in _CHAT2)
ok('B3 【此刻】挂 system 尾部（不再是 user 消息前缀）',
   # S7 之后 `_build_ai_context()` 被包进 lean 分支（事件请求不发上下文，
   # 否则 system 每轮都变 → Ollama KV 前缀缓存失效 → 首字 0.63s→1.82s）。
   # 这里只要求"**非 lean** 时仍然调用它"，尾部拼接的断言不变。
   'ifleanelseself._build_ai_context()' in _CHAT2
   and 'system=system+"\\n\\n"+_ctx' in _CHAT2,
   _CHAT2[:0])
ok('B4 抽取 recent（role==assistant 的历史回复）传给护栏',
   "recent=[cfor_r,cinhistoryif_r=='assistant']" in _CHAT2)
# B5 在 S8（流式）那一轮被**加强**过：原来是数 `cli.chat(` 出现 2 次，
# 但引入流式后两次请求被收进同一个助手 `_ask()`（它负责"能流式就流式"），
# 计数法失效。改成直接断言"两次请求都存在、且都走同一个助手" ——
# 比计数更贴近意图（重采样**也**必须带上流式回调，不能绕过）。
ok('B5 判退后有重采样分支，且两次请求共用同一助手（保证重采样也走流式）',
   'reply=_ask(system,opts)' in _CHAT2
   and 'reply2=_ask(system+"\\n\\n"+RalseiPet._RETRY_NUDGE,retry_opts)' in _CHAT2
   and 'def_ask(sys_prompt,ask_opts)' in _CHAT2,
   'reply=%s reply2=%s helper=%s' % (
       'reply=_ask(system,opts)' in _CHAT2,
       'reply2=_ask(system+"\\n\\n"+RalseiPet._RETRY_NUDGE,retry_opts)' in _CHAT2,
       'def_ask(sys_prompt,ask_opts)' in _CHAT2))
ok('B6 重采样温度高于首次',
   "retry_opts['temperature']=min(1.0,float(opts.get('temperature',0.85))+0.1)" in _CHAT2)
ok('B7 _build_ai_context 返回以【此刻】开头',
   'return"【此刻】"+' in code_no_comment(func_src(MAIN_TEXT, '_build_ai_context')))

import main as M                                                    # noqa: E402
R = M.RalseiPet


def make_stub(**extra):
    s = types.SimpleNamespace()
    s.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    for name in ('_build_persona_prompt', '_clean_ai_reply', '_is_repeat_of_recent',
                 '_ai_chat_options'):
        setattr(s, name, types.MethodType(getattr(R, name), s))
    s.api_config = {}
    for k, v in extra.items():
        setattr(s, k, v)
    return s


stub = make_stub()
ok('B8 _build_persona_prompt 读到的就是 persona 文件全文',
   stub._build_persona_prompt().strip() == PERSONA.strip())

stub_cfg = make_stub(api_config={'options': {'temperature': 0.91, 'max_tokens': 128}})
_opts = stub_cfg._ai_chat_options()
ok('B9 _ai_chat_options 透传 config 的采样参数',
   _opts.get('temperature') == 0.91 and _opts.get('max_tokens') == 128, _opts)
_stub_empty = make_stub()
ok('B10 _ai_chat_options 缺省回落 0.7 / 256',
   _stub_empty._ai_chat_options() == {'temperature': 0.7, 'max_tokens': 256},
   _stub_empty._ai_chat_options())

# `_build_persona_prompt` 必须能在测试桩上跑（不依赖任何 self. 实例属性）——
# 曾经因为 except 分支引用 self.PERSONA_REL_PATH 而在桩上二次抛 AttributeError，
# 被上层宽 except 吞掉 → 表现为"AI 永远沉默"。
ok('B11 _build_persona_prompt 只用类属性（桩对象上可跑）',
   'self.PERSONA_REL_PATH' not in code_only_src(func_src(MAIN_TEXT, '_build_persona_prompt'))
   and 'RalseiPet.PERSONA_REL_PATH'
   in code_only_src(func_src(MAIN_TEXT, '_build_persona_prompt')))
ok('B12 自主开口与交互对话共用同一套护栏（_on_reply 里也过 _clean_ai_reply）',
   'text=self._clean_ai_reply(reply_text)or""'
   in code_no_comment(func_src(MAIN_TEXT, 'start_autonomous_speech')))
ok('B13 _on_reply 对护栏本身做了防御（护栏抛异常不得吞掉"已发起"）',
   'try:text=self._clean_ai_reply(reply_text)or""'
   in code_no_comment(func_src(MAIN_TEXT, 'start_autonomous_speech')))

# ---------------------------------------------------------------- C
section('C. 输出护栏行为（合成 persona，机制与内容解耦）')
SYNTH = ('## 示范\n'
         '主人：我好喜欢你呀\n'
         '我：诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。\n')
D = '诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。'   # 与合成示范逐字相同
MIRROR = '诪、诪！你突然说这个干嘛啦……我、我其实也挺喜欢你的。'        # 改两处，ratio 仅 0.74

s2 = make_stub()
s2._build_persona_prompt = lambda: SYNTH
RECENT = ['被骂了啊……是因为什么事呢？我听着都替你委屈。']

CASES = [
    ('C1 markdown 强调标记剥除', '**听到也让我心里暖暖的**。别太累了。',
     lambda g: g == '听到也让我心里暖暖的。别太累了。'),
    ('C2 行首井号/引用符剥除', '# 早点休息\n> 别熬夜', lambda g: '#' not in g and '>' not in g),
    ('C3 数字列表前缀剥除', '1. 早点休息', lambda g: g == '早点休息'),
    ('C4 小数不误伤（1.5 倍）', '今天效率是 1.5 倍呢。', lambda g: g == '今天效率是 1.5 倍呢。'),
    ('C5 自问自答续写只截前半句', '被骂了……我先陪着你。\n主人：老板说我业绩下滑了',
     lambda g: g == '被骂了……我先陪着你。'),
    ('C6 整条都是续写 → None', '主人：你怎么不说话\n你：我在想事情。', lambda g: g is None),
    ('C7 与 persona 示范逐字相同 + recent 为空 → **必须放行**（防回退）',
     D, lambda g: g == D),
    ('C8 与 persona 示范高度雷同 + recent 为空 → **必须放行**（防回退）',
     MIRROR, lambda g: g == MIRROR),
    ('C9 与 persona 示范逐字相同 + recent 已含它 → None',
     D, lambda g: g is None),
    ('C10 与 recent 高度雷同（后半段原样搬）→ None',
     '被骂了啊……是因为什么事呢？我听着都替你委屈。先坐下歇会儿吧。', lambda g: g is None),
    ('C11 纯标点（只回一个句号）→ None', '。', lambda g: g is None),
    ('C12 包裹引号剥除', '“今天辛苦了，早点休息哦。”', lambda g: g == '今天辛苦了，早点休息哦。'),
    ('C13 与示范/recent 都不重合的正常回复 → 原样通过',
     '今天风挺大的，出门记得加件外套。', lambda g: g == '今天风挺大的，出门记得加件外套。'),
    ('C14 空串 → None', '', lambda g: g is None),
    ('C15 None → None', None, lambda g: g is None),
    ('C16 非字符串 → 转字符串', 12345, lambda g: g == '12345'),
]
for name, inp, pred in CASES:
    recent = [D] if name.startswith('C9') else RECENT
    if name.startswith('C7') or name.startswith('C8'):
        recent = []
    got = s2._clean_ai_reply(inp, recent=recent)
    ok(name, bool(pred(got)), 'got=%r' % (got,))

LONG_IN = '唔……' + '这是一段很长的独白，用来测试超长截断。' * 12
LONG_OUT = stub._clean_ai_reply(LONG_IN)
ok('C17 超长截断：真实长度 ≤ 上限且以句末标点收尾',
   bool(LONG_OUT) and len(LONG_OUT) <= R.AI_REPLY_MAX_CHARS and LONG_OUT[-1] in '。！？!?',
   'in=%d out=%s last=%r' % (len(LONG_IN), len(LONG_OUT or ''), (LONG_OUT or '')[-1:]))

# —— C18/C19：句中「括号动作旁白」（2026-09-19 新增的 0b 步）——
# 样本来自探针归档的真实输出（_evidence/paren_gate_2026-09-19.txt，可复算）。
_PAREN_IN = '诶、诶？晚安啊……你也是呀。（轻轻敲了下键盘）睡吧，梦里有星星的。'
_PAREN_OUT = stub._clean_ai_reply(_PAREN_IN)
ok('C18 括号动作旁白只删那一段（不是整句作废）',
   _PAREN_OUT == '诶、诶？晚安啊……你也是呀。睡吧，梦里有星星的。',
   'got=%r' % (_PAREN_OUT,))
ok('C18b 星号版的动作旁白同样删掉（实测真出现过 `*轻轻敲了敲键盘*`）',
   stub._clean_ai_reply('诶……不说话也行啊。我在呢。*轻轻敲了敲键盘* 要不要先喝点水？')
   == '诶……不说话也行啊。我在呢。要不要先喝点水？',
   repr(stub._clean_ai_reply('诶……不说话也行啊。我在呢。*轻轻敲了敲键盘* 要不要先喝点水？')))
ok('C18c 整句只有一个括号动作 → 判无效（走重采样，与其它判退同路）',
   stub._clean_ai_reply('（歪着头）') is None, repr(stub._clean_ai_reply('（歪着头）')))
# 负控制：Ralsei 用括号讲心里话是他的正常表达手段（原作 853 条里 35 条含括号、26 条以括号开头），
# 必须原样放行 —— 否则"补一个洞"变成"砍掉他的特征"。
_INNER = '（其实我有点怕）'
ok('C19 负控制：括号讲心里话**原样放行**（对话链路不做"句首括号=旁白"的整句作废）',
   stub._clean_ai_reply(_INNER) == _INNER
   and stub._clean_ai_reply('其实……（我想想该怎么说）') == '其实……（我想想该怎么说）',
   repr((stub._clean_ai_reply(_INNER), stub._clean_ai_reply('其实……（我想想该怎么说）'))))

# ---------------------------------------------------------------- D
section('D. 判退后重采样（行为级，FakeCli）')


class FakeCli:
    enabled = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, prompt, system_prompt=None, **kw):
        self.seen.append({'temp': kw.get('temperature'),
                          'tail': (system_prompt or '')[-24:]})
        return self.replies.pop(0) if self.replies else None


class FakeSig:
    def __init__(self):
        self.vals = []
        self.ev = threading.Event()

    def emit(self, val, cb):
        self.vals.append(val)
        self.ev.set()


FRESH = '诶？！你、你别突然说这个啦……我耳朵都要热起来了。'
s3 = make_stub(api_config={'options': {'temperature': 0.85, 'max_tokens': 256}})
s3.api_enabled = True
s3.api_client = FakeCli([D, FRESH])
s3._api_result = FakeSig()
# 触发条件必须是"和 recent 重合"（本轮的定案）——所以历史里得先有一句几乎一样的台词。
# 曾经这里挂的是 get_ai_history=lambda: []，配旧版"照抄 persona 也算判退"的实现能过；
# 改成 recent-only 之后为空历史 = 不判退 = 不重试，D1~D4 全挂（首跑实测）。
s3.dialogue_ui = types.SimpleNamespace(
    get_ai_history=lambda limit=0: [('assistant', D)],
    get_focus_brief=lambda: '')
s3._build_ai_context = lambda: ''
s3.memory_system = None
s3._build_persona_prompt = lambda: SYNTH
R.chat_with_ai(s3, '我好喜欢你呀', lambda r: None)
s3._api_result.ev.wait(10)
ok('D1 首次判退后确实重采样（cli.chat 调用 2 次）',
   len(s3.api_client.seen) == 2, 'calls=%d' % len(s3.api_client.seen))
ok('D2 重采样温度抬高（0.85 → 0.95）',
   len(s3.api_client.seen) == 2
   and abs(s3.api_client.seen[0]['temp'] - 0.85) < 1e-6
   and abs(s3.api_client.seen[1]['temp'] - 0.95) < 1e-6,
   [c['temp'] for c in s3.api_client.seen])
ok('D3 重采样带「换一个说法」提示',
   len(s3.api_client.seen) == 2
   and '不要沿用你想到的第一句' in s3.api_client.seen[1]['tail'],
   [c['tail'] for c in s3.api_client.seen])
ok('D4 最终交给 UI 的是重采样结果，不是被丢弃的那句',
   s3._api_result.vals == [FRESH], s3._api_result.vals)

s4 = make_stub(api_config={'options': {'temperature': 0.85, 'max_tokens': 256}})
s4.api_enabled = True
s4.api_client = FakeCli(['   '])
s4._api_result = FakeSig()
s4.dialogue_ui = types.SimpleNamespace(get_ai_history=lambda limit=0: [],
                                       get_focus_brief=lambda: '')
s4._build_ai_context = lambda: ''
s4.memory_system = None
R.chat_with_ai(s4, '在吗', lambda r: None)
s4._api_result.ev.wait(10)
ok('D5 模型主动沉默（空回复）不触发重试',
   len(s4.api_client.seen) == 1, 'calls=%d' % len(s4.api_client.seen))

# ---------------------------------------------------------------- E
section('E. 关键词拦截收紧（软闲聊放行 / 硬指令仍子串）')
from modules.dialogue_ui import DialogueUI as DUI                    # noqa: E402

KW_CASES = [
    ('天气', '天气', True), ('天气', '查看天气', True),
    ('天气', '今天天气真好', False), ('天气', '我这边天气怎么样', False),
    ('哭', '我快哭了', False), ('哭', '别哭', True),
    ('游戏', '我做的游戏上线了', False), ('游戏', '游戏', True),
    ('状态', '我状态不太好', False), ('精力', '没什么精力', False),
    ('饿了吗', '你饿了吗', True), ('唱歌', '你唱歌真好听', False),
    ('石头剪刀布', '陪我玩石头剪刀布吧', True), ('睡觉', '你去睡觉吧', True),
]
kw_bad = []
for kw, raw, want in KW_CASES:
    got = (kw in raw) if kw in DUI._HARD_CMDS else DUI._is_command_phrase(raw, kw)
    if got != want:
        kw_bad.append((kw, raw, got, want))
ok('E1 14 条关键词用例全部符合预期', not kw_bad, kw_bad)
ok('E2 硬指令集合非空且与"动作控制流"同名',
   isinstance(DUI._HARD_CMDS, frozenset) and '睡觉' in DUI._HARD_CMDS
   and '石头剪刀布' in DUI._HARD_CMDS)
ok('E3 软关键词的命中判定要求"去掉关键词后剩字 ≤ allowance"',
   'CMD_EXTRA_ALLOWANCE' in DIALOGUE_TEXT and '_is_command_phrase' in DIALOGUE_TEXT)

# ---------------------------------------------------------------- F
section('F. 运行时配置与 Modelfile')
import json                                                          # noqa: E402

_cfg = json.load(io.open(CFG_JSON, encoding='utf-8'))
_api = _cfg.get('api') or {}
# 断言写成"ralsei 系列 + 带版本号"而不是钉死某个版本：
# 底座会随换代而换（2026-09-19 :v2(3B) → :v3(4B)），钉死版本号等于每换一次就要改测试
# —— 与 s1_anim_miss / round5_smoke 的教训同源：**别在断言里写会随项目演进而变的常量**。
ok('F1 仓库默认配置指向 ralsei 系列模型（:vN，版本随底座换代而变）',
   str(_api.get('model', '')).startswith('ralsei:'), _api.get('model'))
ok('F2 仓库默认配置带 options（temperature/max_tokens）',
   isinstance(_api.get('options'), dict) and 'temperature' in _api['options']
   and 'max_tokens' in _api['options'], _api.get('options'))

_cm = io.open(CFG_MGR_PY, encoding='utf-8').read()
ok('F3 config_manager 默认值同步带 options（新装用户也是这套采样参数）',
   '"options"' in _cm and '"temperature": 0.85' in _cm and '"max_tokens": 256' in _cm)

_mf = io.open(MODELFILE, encoding='utf-8').read() if os.path.exists(MODELFILE) else ''
ok('F4 ralsei.modelfile 存在', bool(_mf))
ok('F5 Modelfile 写死 num_ctx 8192（/v1 端点会忽略该参数，只能靠 Modelfile）',
   'num_ctx 8192' in _mf, repr(_mf[:80]))
ok('F6 Modelfile 写死 repeat_penalty（同上）', 'repeat_penalty' in _mf)
# 原断言是 'FROM qwen2.5:3b'（钉死底座）。2026-09-19 底座换到 4B 后它会假红 ——
# 而 Modelfile 真正要守的不变量不是"用哪个底座"，而是 **FROM 指向 ralsei 系列底座**
# 且**采样参数烘在里面**（不然 App 只发 temperature/max_tokens，其余会被静默换掉）。
_mf_from = [ln.strip() for ln in _mf.splitlines() if ln.strip().startswith('FROM ')]
ok('F7 Modelfile 有且只有一条 FROM（底座换代只会改这一行，断言不钉死具体版本）',
   len(_mf_from) == 1 and len(_mf_from[0]) > len('FROM '), _mf_from)
ok('F8 保存配置时不会清空 options（api_config 字典带 options）',
   "'options':_cur_cfg.get('options'," in code_no_comment(MAIN_TEXT))

# ---------------------------------------------------------------- G
section('G. 载体层状态管理（_build_ai_context 的状态口径）')
# 「载体层状态」= 由 App（载体）持有、每轮拼进 system 尾部的"Ralsei 此刻状态"。
# 性格不只在人设文件里，也在状态里：累了会抱怨、被冷落会委屈、
# 站在窗口上和在桌面上说话不该一模一样。
# 这里锁两件事：① 状态确实进了提示词；② 缺子系统时必须静默降级（不能拖垮对话）。
#
# 视图选择：本组 needle 大多含**字符串字面量**（`getattr(self,'is_falling',...)`），
# 而 code_only_src 会把 STRING 也剥掉 → 一律走 code_no_comment（MEMORY 已记 5 次踩坑）。
# G0 就是这条工具语义的自检，免得视图一变形、下面所有断言一起失真。
_CTX_SRC = code_no_comment(func_src(MAIN_TEXT, '_build_ai_context'))
_CTX_CODE = code_only_src(func_src(MAIN_TEXT, '_build_ai_context'))

ok('G0 X0 自检：含引号的 needle 在 code_only_src 上必然落空、在 code_no_comment 上才搜得到',
   ('你站在桌面上' not in _CTX_CODE) and ('你站在桌面上' in _CTX_SRC))
ok('G1 仍以【此刻】开头（S7 时代订下的格式，不许改）',
   'return"【此刻】"+' in _CTX_SRC)
ok('G2 精力/饥饿分档（不再只有"低"一档）',
   '_energy<20' in _CTX_CODE and '_energy<45' in _CTX_CODE
   and '_energy>85' in _CTX_CODE and '_hunger<20' in _CTX_CODE
   and '_hunger<45' in _CTX_CODE)
ok('G3 载体状态：在窗口上 / 在桌面上 / 走动 / 掉落 都会说出来',
   all(k in _CTX_SRC for k in ('你站在一个打开的窗口上', '你站在桌面上',
                               '你正在走动', '你正从高处往下掉')))
ok('G4 被冷落时长由载体时间戳派生（>30 分钟才提，不让模型猜）',
   '主人已经很久没跟你说话了' in _CTX_SRC and '_idle>1800' in _CTX_CODE)
ok('G5 尾部带"别逐条念"的用法约束（否则模型会把状态当清单念出来）',
   '别逐条念' in _CTX_SRC)
_F_CHAT_CODE = code_only_src(_f_chat)
ok('G6 chat_with_ai 是"主人开口时间戳"的唯一写点，且写在 api_enabled 判断之前（关 AI 也要记）',
   '_last_user_chat_ts=time.time()' in _F_CHAT_CODE
   and _F_CHAT_CODE.index('_last_user_chat_ts=time.time()')
   < _F_CHAT_CODE.index('ifnotself.api_enabled:'))


class _Sub:
    """只提供 _build_ai_context 需要的两个读口的极简桩。"""

    def __init__(self, e, h):
        self._e, self._h = e, h

    def get_energy(self):
        return self._e

    def get_hunger(self):
        return self._h


def make_ctx_stub(energy=50, hunger=50, window=None, fall=False, moving=False,
                  idle=None):
    """**故意不挂** weather_system / emotion_system / memory_system ——
    那三块本来就该走 except 静默降级，顺便当"缺子系统不崩"的常驻负控制。"""
    s = types.SimpleNamespace()
    s.energy_hunger = _Sub(energy, hunger)
    s.current_window = window
    s.window_level = 0
    s.is_falling = fall
    s.is_moving = moving
    if idle is not None:
        s._last_user_chat_ts = time.time() - idle
    return s


_c1 = R._build_ai_context(make_ctx_stub(energy=10, hunger=10))
ok('G7 行为级：低精力 + 低饥饿真的进了上下文',
   '累得快撑不住' in _c1 and '饿得厉害' in _c1, _c1[:90])
_c2 = R._build_ai_context(make_ctx_stub(energy=95, window={'hwnd': 1}, idle=3600))
ok('G8 行为级：精神好 + 站在窗口上 + 久未互动，三条都在',
   '精神很好' in _c2 and '窗口上' in _c2 and '很久没跟你说话' in _c2, _c2[:130])
_c3 = R._build_ai_context(make_ctx_stub(idle=5))
ok('G9 行为级："刚聊过"与"久未互动"互斥（不会同时出现）',
   '刚跟你说过话' in _c3 and '很久没跟你说话' not in _c3, _c3[:130])
_c4 = R._build_ai_context(make_ctx_stub(fall=True))
ok('G10 行为级：掉落时不再报"在走动"（同一份状态的优先级）',
   '往下掉' in _c4 and '正在走动' not in _c4, _c4[:130])
_c5 = R._build_ai_context(types.SimpleNamespace())
ok('G11 行为级：子系统与状态属性全缺也不抛（静默降级），仍是【此刻】串',
   isinstance(_c5, str) and _c5.startswith('【此刻】'), repr(_c5)[:90])

# ---------------------------------------------------------------- 汇总
print('')
print('=' * 60)
print('总计 %d 项，通过 %d，失败 %d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - ' + f)
sys.exit(1 if FAIL else 0)
