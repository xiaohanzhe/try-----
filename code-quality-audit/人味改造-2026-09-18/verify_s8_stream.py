# -*- coding: utf-8 -*-
"""第十八轮（并行线）· S8 流式输出验证：api_client 流式接口 + main 接线 + 打字机增量显示。

为什么 S8 值得单独锁
--------------------
S8 的收益全在"**首字延迟**"：实测同一句 ralsei:v2 回复，非流式要等整句生成完
（热 0.9s / 冷 6.0s）才显示第一个字；流式 0.23s 就开始冒字 —— 而"盯着「……」空等
几秒"正是用户说的"假人感"来源之一。数值来自 `_evidence/s8_*_probe.txt`。

但 S8 也引入了三处**容易后期改坏**的耦合，必须锁住：

1) **基类必须给 chat_stream 一个具体默认实现**（回落 chat + 单次回调）。
   否则 `LocalAIStub` 与用户 `register_provider()` 注册的实现会被迫改造 ——
   App 一升级就崩在用户那边。这是"扩展点不能被新功能打破"。

2) **流式清洗必须是"前缀安全"的**。屏幕上显示的是"按规则清洗过的已收到部分"，
   收尾时 `_clean_ai_reply` 还要再洗一次。若两条规则漂移（各写一份正则），
   就会出现"字已经打出去了、最后又被改掉"的抖动。所以两者**共用**
   `_md_strip_re()` / `_role_marker_re()`。
   注意：`主人：` 跨分片到达时前缀假设必然被打破（前半段「主人」没带冒号，
   已经显示了）—— 这靠调用方的"不是前缀就整段替换"兜底，**不是**靠规则本身。

3) **流式与"护栏判退重采样"是冲突的**：判退发生在收完之后，可这时被判退的半句
   **已经在屏幕上了**。必须先在 UI 上擦掉（`on_delta(None)` → `_stream_reset`）
   再重采样，否则新句会接在旧句后面，像两句话黏在一起。
   另外 `_on_ai_reply` 在流式路径下**不能**调 `_ai_thinking_off`（它会清空
   typing_text → 已显示内容一闪而逝再从第 0 字重打）。

分组
----
  A api_client 流式契约（含 SSE 解析的行为级用例）
  B main.py 接线（信号 / 世代号 / 开关 / reset-重采样顺序）
  C 流式清洗的前缀安全性（含穷举单调性 + 跨分片标记）
  D dialogue_ui 打字机增量显示（行为级，桩对象）
  E 配置

本套件**不打网络、不调用 Ollama**（真机数值见 _evidence/，见开头说明）。
必须用 C:\\Python311\\python.exe 运行（PyQt5 + requests）。
"""
import io
import json
import os
import sys
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
MAIN_PY = os.path.join(SRC, 'main.py')
API_PY = os.path.join(MODS, 'api_client.py')
DIALOGUE_PY = os.path.join(MODS, 'dialogue_ui.py')
CFG_MGR_PY = os.path.join(MODS, 'config_manager.py')
CFG_JSON = os.path.join(PET, 'config.json')

MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()
API_TEXT = io.open(API_PY, encoding='utf-8').read()
DIALOGUE_TEXT = io.open(DIALOGUE_PY, encoding='utf-8').read()

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def _strip(src, drop):
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in drop:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


def code_only_src(src):
    """剥注释+字符串（找语法结构用）。"""
    return _strip(src, _DROP)


def code_no_comment(src):
    """只剥注释（找字符串字面量 needle 用 —— 见 MEMORY「验证脚本教训」）。"""
    return _strip(src, (tokenize.COMMENT,))


def func_src(src, name, cls=None):
    """取函数正文（顺序断言必须限定在目标函数体内，避免命中别的函数）。"""
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


# ---------------------------------------------------------------- 导入
import api_client as A                                          # noqa: E402
import main as M                                                # noqa: E402
import dialogue_ui as D                                         # noqa: E402
R = M.RalseiPet

# ---------------------------------------------------------------- A
section('A. api_client 流式契约')

BASE_TEXT = API_TEXT
_a_base_cs = code_no_comment(func_src(BASE_TEXT, 'chat_stream'))
ok('A1 基类给出具体（非抽象）的 chat_stream，老 provider 不会被新功能打破',
   hasattr(A.LocalAIBase, 'chat_stream')
   and not getattr(A.LocalAIBase.chat_stream, '__isabstractmethod__', False),
   'abstract=%s' % getattr(A.LocalAIBase.chat_stream, '__isabstractmethod__', None))
ok('A2 基类默认实现：回落 self.chat() 并把全文作为单分片回调',
   'text=self.chat(prompt,system_prompt=system_prompt,**kwargs)' in _a_base_cs
   and 'on_delta(text)' in _a_base_cs)

_HTTP_SEC = API_TEXT.split('class HTTPLocalAI')[1]
_http_cs = code_no_comment(func_src(_HTTP_SEC, 'chat_stream'))
ok('A3 HTTPLocalAI 覆盖 chat_stream 为真流式（stream=True + 逐行消费）',
   '_chat_payload(prompt,system_prompt,kwargs,True)' in _http_cs
   and '_consume_stream(resp,on_delta)' in _http_cs)
ok('A4 on_delta 为 None 时回落 chat()（不必走流式解析）',
   'ifon_deltaisNone:returnself.chat(prompt,system_prompt=system_prompt,**kwargs)'
   in _http_cs, _http_cs[:0])
ok('A5 流式**不重试**：重试会让同一句被说两遍，网络抖动交给上层重采样兜底',
   'retry' not in _http_cs.lower(),
   'HTTPLocalAI.chat_stream 里出现了 retry 分支')

_consume = code_no_comment(func_src(API_TEXT, '_consume_stream'))
ok('A6 _consume_stream 用 chunk_size=1（实测默认攒批 0.45s vs 0.23s）',
   'iter_lines(chunk_size=1)' in _consume)

ok('A7 chat 与 chat_stream 共用 _chat_payload（不重复编码 messages/参数）',
   'def_chat_payload' in code_only_src(API_TEXT)
   # 注意：必须限定在 HTTPLocalAI 段里找 chat —— 文件里第一个 `def chat(` 是
   # LocalAIBase 的抽象方法（函数体只有一个 `...`），用整文件会取错那个。
   and code_no_comment(func_src(_HTTP_SEC, 'chat')).count('_chat_payload(') == 1
   and _http_cs.count('_chat_payload(') == 1)
ok('A8 chat 与 chat_stream 共用 _chat_messages（钳位规则只有一份）',
   'def_chat_messages' in code_only_src(API_TEXT)
   and code_no_comment(func_src(API_TEXT, '_chat_payload')).count('_chat_messages(') == 1)

# ---- 行为级：SSE 解析 ----
class _Resp:
    """假的流式响应体（逐行给出，模拟 requests 的 iter_lines）。"""

    def __init__(self, lines):
        self._lines = lines
        self.closed = False
        self.chunk_size_seen = None

    def iter_lines(self, chunk_size=None):
        self.chunk_size_seen = chunk_size
        for ln in self._lines:
            yield ln.encode('utf-8')

    def close(self):
        self.closed = True


def sse(*pieces):
    out = []
    for i, p in enumerate(pieces):
        out.append('data: ' + json.dumps(
            {'choices': [{'index': 0, 'delta': {'content': p}}]}, ensure_ascii=False))
        out.append('')
    out.append('data: [DONE]')
    out.append('')
    return out


cli = A.HTTPLocalAI({'enabled': True, 'base_url': 'http://x', 'model': 'm'})
got = []
resp = _Resp(sse('你', '好', '呀'))
full = cli._consume_stream(resp, got.append)
ok('A9 [DONE] 正确终止；增量按序回调', full == '你好呀' and ''.join(got) == '你好呀',
   'full=%r got=%r' % (full, got))
ok('A10 传给 iter_lines 的 chunk_size 必须是 1（延迟关键）',
   resp.chunk_size_seen == 1, 'chunk_size=%r' % (resp.chunk_size_seen,))
ok('A11 消费完必须关闭响应（否则连接泄漏）', resp.closed)

# 畸形行必须跳过而不是中断 —— 一次解析失败不能把已收到的半句一起丢掉
bad = ['data: {"choices":[{"delta":{"content":"甲"}}]}', '',
       '这不是 SSE 行', '',
       'data: {坏 JSON', '',
       'data: {"choices":[]}', '',
       'data: {"choices":[{"delta":{}}]}', '',
       'data: {"choices":[{"delta":{"content":"乙"}}]}', '',
       'data: [DONE]', '']
got2 = []
full2 = cli._consume_stream(_Resp(bad), got2.append)
ok('A12 畸形行跳过而不中断（保住已收到内容）', full2 == '甲乙' and got2 == ['甲', '乙'],
   'full=%r got=%r' % (full2, got2))

# 回调抛异常不能中断接收（否则"用户关掉对话框"会连带丢掉整条回复）
got3 = []


def _boom(p):
    got3.append(p)
    raise RuntimeError('UI 已销毁')


full3 = cli._consume_stream(_Resp(sse('一', '二', '三')), _boom)
ok('A13 回调抛异常不中断接收（回复不会被 UI 异常连带丢掉）',
   full3 == '一二三' and len(got3) == 3, 'full=%r got=%r' % (full3, got3))

ok('A14 一个字都没收到 → 返回 None（与 chat 失败语义一致）',
   cli._consume_stream(_Resp(['data: [DONE]', '']), None) is None)

# payload 构造
p_stream = cli._chat_payload('hi', 'SYS', {'history': [('user', 'u1'),
                                                      ('assistant', 'a1')]}, True)
p_plain = cli._chat_payload('hi', 'SYS', {}, False)
ok('A15 payload.stream 随参数切换；messages 顺序 = system→history→user',
   p_stream['stream'] is True and p_plain['stream'] is False
   and [m['role'] for m in p_stream['messages']] == ['system', 'user', 'assistant', 'user'],
   [m['role'] for m in p_stream['messages']])
ok('A16 history 里的畸形条目仍被跳过（老防御不能因重构丢失）',
   [m['role'] for m in cli._chat_payload(
       'hi', None, {'history': ['bad', ('x', 'y'), ('user', '  '), ('user', 'ok')]},
       False)['messages']] == ['user', 'user'],
   [m['role'] for m in cli._chat_payload(
       'hi', None, {'history': ['bad', ('x', 'y'), ('user', '  '), ('user', 'ok')]},
       False)['messages']])

# ---------------------------------------------------------------- B
section('B. main.py 接线')

CHAT_SRC = func_src(MAIN_TEXT, 'chat_with_ai')
CHAT_NC = code_no_comment(CHAT_SRC)
CHAT_CO = code_only_src(CHAT_SRC)

ok('B1 chat_with_ai 签名接受 on_delta（S7 之后末尾多了 lean，见 S7 §11.11）',
   'defchat_with_ai(self,text,on_reply,on_delta=None,lean=False)' in CHAT_CO,
   CHAT_CO[:0])
ok('B2 新增跨线程分片信号 _api_delta（object, object）',
   '_api_delta=pyqtSignal(object,object)' in code_only_src(MAIN_TEXT))
# 不用 func_src(MAIN_TEXT,'__init__')：main.py 里第一个 `def __init__` 未必是
# RalseiPet 的（还有别的类）→ 会取到别的类而误判。改在整文件规范化源码里找，
# 下面两条 needle 都是唯一的，不会误命中。
_MAIN_CO = code_only_src(MAIN_TEXT)
ok('B3 __init__ 连接 _on_api_delta 并初始化世代号/接收方',
   'self._api_delta.connect(self._on_api_delta)' in _MAIN_CO
   and 'self._ai_delta_gen=0' in _MAIN_CO
   and 'self._ai_delta_sink=None' in _MAIN_CO)
ok('B4 worker 优先走 chat_stream（不再无条件 cli.chat）',
   'chat_stream' in CHAT_SRC and "_sfn=getattr(cli,'chat_stream',None)" in CHAT_NC)
ok('B5 流式回调经 _emit_delta 投递（工作线程不直接碰 UI）',
   "_api_delta.emit(_gen,piece)" in code_only_src(func_src(MAIN_TEXT, 'chat_with_ai'))
   or '_api_delta.emit(_gen,piece)' in CHAT_CO)
ok('B6 流式请求带上 on_delta=_emit_delta',
   'on_delta=_emit_delta' in CHAT_NC)
# 判退后必须"先擦屏幕再重采样"，否则新旧两句话会黏在一起
_i_reset = CHAT_CO.find('_emit_delta(None)')
_i_retry = CHAT_CO.find('reply2=_ask(')
ok('B7 判退重采样前先发 reset（先擦屏幕再重发）',
   _i_reset > 0 and _i_retry > 0 and _i_reset < _i_retry,
   'reset@%d retry@%d' % (_i_reset, _i_retry))

_delta_nc = code_no_comment(func_src(MAIN_TEXT, '_on_api_delta'))
_delta_co = code_only_src(func_src(MAIN_TEXT, '_on_api_delta'))
# B8 的 needle 里含字符串字面量 `'_ai_delta_gen'` → 必须用 code_no_comment
# （code_only_src 会把它丢掉，变成 getattr(self,,0)，断言恒假 —— 老坑）
ok('B8 _on_api_delta 做世代号校验（丢弃过期请求的迟到分片）',
   "ifgeneration!=getattr(self,'_ai_delta_gen',0):return" in _delta_nc,
   _delta_nc[:160])
# B9 反过来要用 code_only_src：docstring 里**提到**了 `_ai_delta_sink`
# （解释为什么故意不清理），只有剥掉字符串才能确认"代码里真的没有这次赋值"
ok('B9 _on_api_delta **故意不清理** sink（清理会误杀新请求的接收方）',
   '_ai_delta_sink=None' not in _delta_co,
   'sink 被清理了，会造成竞态')

# ---- 行为级：开关与世代号 ----
def mstub(**extra):
    s = types.SimpleNamespace()
    s._ai_delta_gen = 0
    s._ai_delta_sink = None
    for name in ('_ai_stream_enabled', '_on_api_delta'):
        setattr(s, name, types.MethodType(getattr(R, name), s))
    for k, v in extra.items():
        setattr(s, k, v)
    return s


ok('B10 _ai_stream_enabled 缺省开启', mstub(api_config={})._ai_stream_enabled() is True)
ok('B11 _ai_stream_enabled 读 config 的 api.stream（可一键关闭）',
   mstub(api_config={'stream': False})._ai_stream_enabled() is False
   and mstub(api_config={'stream': True})._ai_stream_enabled() is True)
ok('B12 配置异常（非 dict）不崩，回落开启',
   mstub(api_config=['坏'])._ai_stream_enabled() is True)

s = mstub()
collected = []
s._ai_delta_sink = collected.append
s._ai_delta_gen = 7
s._on_api_delta(7, '甲')
s._on_api_delta(6, '旧')      # 过期世代 → 必须丢弃
s._on_api_delta(7, None)      # reset 标记必须原样转发
ok('B13 世代号校验生效：过期分片丢弃、当前分片与 reset 都转发',
   collected == ['甲', None], 'collected=%r' % (collected,))
s._ai_delta_sink = None
s._on_api_delta(7, '甲')
ok('B14 没有接收方时分片静默丢弃（不抛异常）', collected == ['甲', None])

# ---------------------------------------------------------------- C
section('C. 流式清洗的前缀安全性')

_san = code_no_comment(func_src(MAIN_TEXT, '_sanitize_partial_reply'))
ok('C1 与收尾护栏共用 markdown 规则（不各写一份）',
   'RalseiPet._md_strip_re()' in code_no_comment(func_src(MAIN_TEXT, '_clean_ai_reply'))
   and '_md_strip_re().sub' in _san)
ok('C2 与收尾护栏共用角色标记规则',
   'RalseiPet._role_marker_re()' in code_no_comment(func_src(MAIN_TEXT, '_clean_ai_reply'))
   and '_role_marker_re().search' in _san)

stub = types.SimpleNamespace()
# `_sanitize_partial_reply` 是 staticmethod 且内部用 `RalseiPet.` 取规则 → 绑到桩上
# 也能正常工作（这正是它不写成 classmethod 的原因：桩上 `cls._MD_STRIP_RE` 取不到
# 会被宽 except 吞掉，表现为"流式屏幕上是未清洗的原文"——本套件首跑就是这么挂的）。
stub._sanitize_partial_reply = R._sanitize_partial_reply
stub._md_strip_re = R._md_strip_re
stub._role_marker_re = R._role_marker_re
stub._clean_ai_reply = types.MethodType(R._clean_ai_reply, stub)
stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
stub.api_config = {}

san = lambda t: R._sanitize_partial_reply(t)          # noqa: E731

ok('C3 剥 markdown 强调标记', san('**听到也让我心里暖暖的**。') == '听到也让我心里暖暖的。',
   san('**听到也让我心里暖暖的**。'))
ok('C4 小数不被误伤（1.5 倍）',
   san('今天效率是 1.5 倍呢。') == '今天效率是 1.5 倍呢。', san('今天效率是 1.5 倍呢。'))
ok('C5 截断自问自答续写',
   san('我先陪着你。\n主人：老板骂我了') == '我先陪着你。',
   san('我先陪着你。\n主人：老板骂我了'))
ok('C6 去包裹引号',
   san('“今天辛苦了。”') == '今天辛苦了。', san('“今天辛苦了。”'))
ok('C7 非字符串 → 空串（不抛）', san(None) == '' and san(123) == '')
ok('C8 空串 → 空串', san('') == '')

# —— 穷举前缀单调性（S8 的核心不变量）——
# 对**不含"行首列表标记"和"角色标记"**的文本：第 i 个字符的前缀清洗结果，
# 必须永远是"全文清洗结果"的前缀 —— 否则屏幕会出现"字打出去了又缩回去"。
MONO_TEXTS = [
    '别太自责了，偶尔一次也正常，休息一下放松心情吧。',
    '**加粗开头**然后正常文字，后面还有一个 `code` 片段。',
    '今天效率是 1.5 倍呢，明天争取 2.0 倍。',
    '“我把话说完。”他说完就笑了。',
    '# 标题\n> 引用\n- 列表项',
]
mono_bad = []
for T in MONO_TEXTS:
    want = san(T)
    for i in range(1, len(T) + 1):
        p = san(T[:i])
        if not want.startswith(p):
            mono_bad.append((T[:i], p, want))
ok('C9 穷举前缀单调：不含标记类文本，任何前缀的清洗结果都是全文结果的前缀',
   not mono_bad, '违例 %d 个，首个=%r' % (len(mono_bad), mono_bad[0] if mono_bad else None))

# —— 两个**已知非单调**边界 ——
# 成因：清洗规则要"看到后面的字符"才能判定，所以前半段必然已经显示出去。
# 调用方（dialogue_ui.stream_delta）发现"新结果不是已显示内容的前缀"就整段替换，
# 所以**最终态一定正确**；代价只是回复最开头那几个字符可能闪一下。
NON_MONO = [
    ('行首数字列表标记', '1. 第一条\n2. 第二条'),
    ('角色标记跨分片', '\n主人：你怎么不说话'),
]
nm_report = [(label, T, [i for i in range(1, len(T) + 1)
                         if not san(T).startswith(san(T[:i]))])
             for label, T in NON_MONO]


def _near_line_start(T, i):
    """违例位置是否落在"回复开头 3 字内"或"某个行首附近"。

    为什么违例只可能出现在这些位置：需要"看到后面的字符"才能判定的规则
    （`1. ` 要等点号后的空白、`主人：` 要等冒号），所以被延后剥掉的那 1~2 个字符
    必然紧跟在"回复开头"或"某个换行"之后。
    """
    return i <= 3 or '\n' in T[max(0, i - 4):i]


ok('C10 两个已知非单调边界：违例确实存在，但只出现在回复开头 / 行首附近',
   all(v and all(_near_line_start(T, i) for i in v) for _l, T, v in nm_report),
   nm_report)
ok('C10a 数字列表标记的最终态正确（`1. ` / `2. ` 都被剥掉）',
   san('1. 第一条\n2. 第二条') == '第一条\n第二条', san('1. 第一条\n2. 第二条'))

# 具体断言"前缀假设被打破"确实会发生 —— 证明调用方的整段替换兜底不是多余的
T = '\n主人：你怎么不说话'
early = san(T[:3])      # '\n主人' → 还没冒号 → 已经显示出去了
late = san(T)
ok('C10b 跨分片时前缀假设**确实**被打破（调用方兜底路径是必需的）',
   early == '主人' and late == '' and not late.startswith(early),
   'early=%r late=%r' % (early, late))
T2 = '1. 第一条'
ok('C10c 行首数字标记：`1` 已显示后，`1. ` 到齐会被剥掉 → 前缀假设被打破',
   san(T2[:1]) == '1' and san(T2[:3]) == ''
   and not san(T2).startswith(san(T2[:1])),
   '%r %r %r' % (san(T2[:1]), san(T2[:3]), san(T2)))

# 收尾护栏与流式清洗在"简单文本"上必须给出相同结果（规则漂移会让字被改掉）
mismatch = [T for T in MONO_TEXTS if san(T) != stub._clean_ai_reply(T, recent=[])]
ok('C11 简单文本上：流式清洗结果 == 收尾护栏结果（证明两条规则没漂移）',
   not mismatch, '不一致=%r' % (mismatch,))

# ---------------------------------------------------------------- D
section('D. dialogue_ui 打字机增量显示')

ok('D1 add_dialogue 支持 _streamed 参数',
   'def add_dialogue(self, speaker, message, face_type="normal", _streamed=False):'
   in DIALOGUE_TEXT)
_add = code_only_src(func_src(DIALOGUE_TEXT, 'add_dialogue'))
ok('D2 _streamed=True 走"定格"路径，不重打、不把本条当"上一条"提交',
   'if_streamed:self._finalize_stream(message)' in _add
   and 'else:self.stop_typing()' in _add)
# 注意：打字机/流式状态是在 `_init_state()`（376 行）里初始化的，**不在 `__init__`**
# —— `__init__` 只有 7 行，转发调用 `_build_ui()` / `_init_state()`。
# 这坑就是"用 func_src 找 __init__ 结果取到别的短方法"的实例。
ok('D3 _init_state 初始化流式状态',
   'self._streaming=False' in code_only_src(func_src(DIALOGUE_TEXT, '_init_state'))
   and 'self._stream_raw=' in code_only_src(func_src(DIALOGUE_TEXT, '_init_state')))
_tnc = code_no_comment(func_src(DIALOGUE_TEXT, '_type_next_char'))
ok('D4 流式期间打到队尾时**不停表、不排自动隐藏**（否则第一个分片后就收摊）',
   "ifgetattr(self,'_streaming',False):self._refresh_display()return" in _tnc.replace(' ', '')
   or 'ifgetattr(self,"_streaming",False):' in _tnc.replace("'", '"'))
_stop = code_no_comment(func_src(DIALOGUE_TEXT, 'stop_typing'))
ok('D5 stop_typing 无条件清 _streaming（用户打断后不能再追加）',
   '_streaming=False' in _stop and 'ifnotself.is_typing:return' in _stop.replace(' ', ''))
ok('D6 stream_delta(None) → _stream_reset；非空则 _stream_begin',
   'ifchunkisNone:self._stream_reset()return' in
   code_only_src(func_src(DIALOGUE_TEXT, 'stream_delta')).replace(
       'ifchunkisNone:', 'ifchunkisNone:'))
_reply = code_only_src(func_src(DIALOGUE_TEXT, '_on_ai_reply'))
# needle 必须带上中间的 `try:` —— code_only_src 会把缩进/换行全抹平，
# 写 `ifnotstreamed:self._ai_thinking_off()` 会匹配不上（中间隔着 try/except）。
ok('D7 流式路径下不调 _ai_thinking_off（调了会让已显示内容一闪而逝）',
   'ifnotstreamed:try:self._ai_thinking_off()' in _reply,
   _reply[:200])
ok('D8 流式且回复为空（判退）→ 先 _stream_reset 再回退规则台词',
   'ifstreamed:try:self._stream_reset()' in _reply)
ok('D9 排除了 thinking_off 与 add_dialogue 的顺序问题：'
   'add_dialogue 带 _streamed=streamed',
   '_streamed=streamed' in _reply)
_sm = code_only_src(func_src(DIALOGUE_TEXT, 'send_message'))
ok('D10 send_message 传入分片回调且做世代号校验',
   'self.parent.chat_with_ai(user_input,_on_ai_reply,_on_ai_delta)' in _sm
   and 'ifreq_seq!=getattr(self,' in _sm.replace(' ', ''))

# ---- 行为级：把真实方法绑到桩上，喂分片看打字机队列 ----
class _Timer:
    def __init__(self):
        self.active = False
        self.interval = None

    def isActive(self):
        return self.active

    def start(self, ms=None):
        self.active = True
        self.interval = ms

    def stop(self):
        self.active = False


def dui_stub():
    s = types.SimpleNamespace()
    s.AI_THINKING_PLACEHOLDER = D.DialogueUI.AI_THINKING_PLACEHOLDER
    s.parent = stub          # 提供 _sanitize_partial_reply
    s.typing_text = ''
    s.typing_index = 0
    s.is_typing = False
    s._streaming = False
    s._stream_raw = ''
    s.typing_timer = _Timer()
    s._auto_hide_timer = _Timer()
    s.rendered = []
    s.scheduled = []
    s.committed = []
    s.faces = []
    s._refresh_display = lambda: s.rendered.append(s.typing_text)
    s._schedule_auto_hide = lambda: s.scheduled.append(s.typing_text)
    s._commit_previous_ralsei_into_history = lambda: s.committed.append(s.typing_text)
    s.set_face = lambda f: s.faces.append(f)
    for name in ('stream_delta', '_sanitize_stream', '_stream_begin', '_stream_reset',
                 '_finalize_stream', 'stop_typing', '_type_next_char'):
        setattr(s, name, types.MethodType(getattr(D.DialogueUI, name), s))
    return s


# 逐块喂入：队列内容必须始终是"最终文本"的前缀（不能出现回缩）
FULL = '别太自责了，偶尔一次也正常，休息一下放松心情吧。'
s1 = dui_stub()
s1._ai_thinking_on = lambda: None
prefix_ok = True
for i in range(1, len(FULL) + 1):
    s1.stream_delta(FULL[i - 1:i])
    if not FULL.startswith(s1.typing_text):
        prefix_ok = False
        break
ok('D11 逐字喂入时，打字机队列始终是最终文本的前缀（无回缩抖动）',
   prefix_ok, '断了：queue=%r' % (s1.typing_text,))
ok('D12 首块到达即从"……"切走并拉起打字机',
   s1._streaming is True and s1.typing_timer.active
   and s1.typing_text == FULL, 'text=%r active=%s' % (s1.typing_text, s1.typing_timer.active))

# 打字机打完当前队列后，流式未结束 → 不许停表
s2 = dui_stub()
s2.typing_text = '好'
s2.typing_index = 1
s2.is_typing = True
s2._streaming = True
s2.typing_timer.start(35)
s2._type_next_char()
ok('D13 队尾 + 流式未完 → 不停表、不排自动隐藏（等下一块）',
   s2.is_typing is True and s2.typing_timer.active and not s2.scheduled,
   'typing=%s active=%s scheduled=%r' % (s2.is_typing, s2.typing_timer.active, s2.scheduled))

# reset：擦干净并回到等待态
s3 = dui_stub()
s3.stream_delta('我先陪着你')
s3.stream_delta(None)
ok('D14 reset 把已显示的半句擦掉并回到"……"等待态',
   s3.typing_text == s3.AI_THINKING_PLACEHOLDER and s3._streaming is False
   and not s3.typing_timer.active and s3.faces == ['thinking'],
   'text=%r streaming=%s faces=%r' % (s3.typing_text, s3._streaming, s3.faces))

# finalize：与已显示内容一致 → 不打断打字机
s4 = dui_stub()
s4.typing_text = FULL
s4.typing_index = 10
s4.is_typing = True
s4._streaming = True
s4.typing_timer.start(35)
s4._finalize_stream(FULL)
ok('D15 finalize 一致时不打断打字机（让它自然打完最后几个字）',
   s4.is_typing is True and s4.typing_timer.active and s4.typing_index == 10,
   'typing=%s idx=%d' % (s4.is_typing, s4.typing_index))

# finalize：不一致（护栏截断）→ 直接定格，避免"打完又改字"
s5 = dui_stub()
s5.typing_text = '很长的半句' * 5
s5.typing_index = len(s5.typing_text)
s5.is_typing = True
s5._streaming = True
s5.typing_timer.start(35)
s5._finalize_stream('短句。')
ok('D16 finalize 不一致（护栏截断）→ 定格为最终文本并收尾',
   s5.typing_text == '短句。' and s5.typing_index == len('短句。')
   and s5.is_typing is False and not s5.typing_timer.active and s5.scheduled,
   'text=%r' % (s5.typing_text,))

# 跨分片角色标记：中途会显示「主人」，冒号到了必须整段消失
s6 = dui_stub()
s6.stream_delta('我先陪着你。\n主')
mid = s6.typing_text
s6.stream_delta('人：老板骂我了')
ok('D17 跨分片角色标记：拿到冒号后整段替换，屏幕上不留「主人：」',
   '主' in mid and '主人' not in s6.typing_text and s6.typing_text == '我先陪着你。',
   'mid=%r end=%r' % (mid, s6.typing_text))

_s18 = dui_stub()
_s18.parent = types.SimpleNamespace()      # 故意换掉：这个 parent **没有**清洗函数
ok('D18 取不到 parent 的清洗函数时原样追加（绝不因取不到而丢字）',
   _s18._sanitize_stream('**原样**') == '**原样**',
   _s18._sanitize_stream('**原样**'))
ok('D19 能取到清洗函数时，流式内容是被清洗过的（屏幕上不闪 markdown）',
   dui_stub()._sanitize_stream('**听到也让我心里暖暖的**') == '听到也让我心里暖暖的',
   dui_stub()._sanitize_stream('**听到也让我心里暖暖的**'))

# ---------------------------------------------------------------- E
section('E. 配置')

_cfgmgr = io.open(CFG_MGR_PY, encoding='utf-8').read()
ok('E1 config_manager 默认配置带 api.stream=True',
   '"stream": True' in _cfgmgr, '未找到')
_cfg = json.loads(io.open(CFG_JSON, encoding='utf-8').read())
ok('E2 仓库 config.json 的 api.stream 为 true',
   _cfg['api'].get('stream') is True, _cfg['api'].get('stream'))
ok('E3 采样参数仍是 0.85 / 256（S8 不应改动它们）',
   _cfg['api']['options'] == {'temperature': 0.85, 'max_tokens': 256},
   _cfg['api']['options'])

# ---------------------------------------------------------------- F
section('F. Qt 跨线程投递（这一环没接上，流式就一个字都不会显示）')

# 为什么单列一组：A~D 组都只测到"函数级别"，而流式分片是
# **工作线程 emit → 主线程槽执行**。这条链路能不能真的走通，只有把 Qt 的
# 事件队列跑起来才验得到 —— 本项目最贵的坑就是"改了 A 却没接线到 B"（第 3 次了）。
_f_setup, _f_err = False, None
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QCoreApplication
    from PyQt5.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])

    def _mk_harness():
        """只保留"信号 + 槽 + 两个状态字段"的最小宿主。

        `_on_api_delta` 直接绑 RalseiPet 的真身（它只依赖 `_ai_delta_gen`
        与 `_ai_delta_sink` 两个属性），所以测的就是生产代码那个槽。
        """
        class _H(QObject):
            _api_delta = pyqtSignal(object, object)

            def __init__(self):
                super().__init__()
                self._ai_delta_gen = 0
                self._ai_delta_sink = None
                self._api_delta.connect(R._on_api_delta.__get__(self, _H))

        return _H()

    def _pump(n=60):
        """跨线程 queued connection：必须让主线程跑一会儿事件队列才会被处理。"""
        for _ in range(n):
            QCoreApplication.processEvents()

    h = _mk_harness()
    received = []
    h._ai_delta_sink = received.append
    h._ai_delta_gen = 5

    import threading

    def _emit_from_worker():
        for ch in '甲乙丙':
            h._api_delta.emit(5, ch)
        h._api_delta.emit(5, None)      # reset 标记
        h._api_delta.emit(4, '过期')     # 过期世代 → 必须被丢弃

    _t = threading.Thread(target=_emit_from_worker)
    _t.start()
    _t.join()
    _pump()

    h2 = _mk_harness()
    seq = []
    h2._ai_delta_sink = seq.append
    h2._ai_delta_gen = 9

    def _emit_retry():
        # 复刻"判退 → reset → 重采样"的发射顺序
        h2._api_delta.emit(9, '旧句')
        h2._api_delta.emit(9, None)
        h2._api_delta.emit(9, '新句')

    _t2 = threading.Thread(target=_emit_retry)
    _t2.start()
    _t2.join()
    _pump()
    _f_setup = True
except Exception as e:                       # pragma: no cover
    _f_err = e

ok('F1 工作线程 emit 的分片按序投递到主线程槽（含 reset，并丢弃过期世代）',
   _f_setup and received == ['甲', '乙', '丙', None],
   'setup=%s err=%r received=%r' % (_f_setup, _f_err, locals().get('received')))
ok('F2 reset 在队列里的顺序严格保持（旧句 → reset → 新句）'
   '—— 顺序错了重采样会把旧句粘在新句前面',
   _f_setup and seq == ['旧句', None, '新句'],
   'seq=%r' % (locals().get('seq'),))

# ---------------------------------------------------------------- 汇总
print('')
print('=' * 60)
print('PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - %s' % f)
sys.exit(1 if FAIL else 0)
