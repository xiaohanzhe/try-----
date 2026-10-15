# -*- coding: utf-8 -*-
"""第115轮自检：**AI 人味训练** —— 人设真源改动不许静默回退。

★ 口径（用户逐字）
------------------
> 「着重注意 AI 的训练包括，**寻路，人设校准，记忆使用，语气**等等，也就是，
>   你自己和他们发对话，**做一些权重的调整直到他们能听懂并用他们人物的语气说出来话**，
>   哦，对了，**他们知道他们是游戏，但并不对此感到悲观**」

★ 本轮的真源改动只有两处（其余全是取证）
------------------------------------------
  ① `ralsei_pet/assets/ralsei_persona.md` —— 新增四节：
     「我是什么」（知道是游戏、但不悲观）·「他说话的时候，先把他的事接住」（治"那边引力"）
     ·「他说要去一个地方的时候」（寻路）·「我想起来的事」（记忆使用、不许编）。
  ② `ralsei_pet/src/main.py` 的 `_PERSONA_FALLBACK` —— 同步新口径（兜底路径不许口径走样）。

★ 判据线（每类都配**负控制**）
------------------------------
  A **人设真源**：四节标题在位 · 世界观节**同时**含"知道是游戏"与"不悲观"两个语义锚 ·
    ★ A3 记忆节必须保住**对照写法**（"判法只有一条…而不是…"）—— 这条是本轮**实测抓到的
    真缺口**：首轮我"清理文案"时删掉了对照，真机联调立刻退化（Q6 违例 2/2），补回后 1/4 ·
    ★ A7/A8/A9 三条负控制（在内存里造坏样本，不落盘、不改被测状态）。
  B **兜底人设**（AST 取字面量，不扫文本）：真读到 · 已含新口径 · J1 的三个锚仍在 ·
    是**单个**常量而不是运行期拼出来的。
  C **一致性**：`PERSONA_REL_PATH` 指向的文件真实存在（否则静默回落到兜底）·
    兜底讲的那层自知在真源里也有（两条路径口径不许劈裂）。
  D **判据自身体检**：条数记账 · 名字里无计数标记 · 无重复 ·
    ★★ 无恒真判据（**AST** 查本文件所有 `check()` 的第二实参不是字面量 `True`）。

★★ 判据一律走 AST 或"只读 + 内存里造坏样本"，**不许**用裸 `in` 扫源码判"有没有调某方法"
  （注释/字符串里提一句名字就恒真 —— 本项目已发作五次，见详版 §108.6）。
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
# ★ 变异测试专用钩子：把 `ralsei_pet` 根指到一份**临时副本**上（默认 = 仓库真源）。
#   有了它，`mutate115.py` 可以放心破坏，**产线文件一个字节都不动**
#   （本项目铁律：判据不许改变被测状态）。
PET = os.environ.get('RALSEI_PET_OVERRIDE') or os.path.join(ROOT, 'ralsei_pet')
PERSONA_MD = os.path.join(PET, 'assets', 'ralsei_persona.md')
MAIN = os.path.join(PET, 'src', 'main.py')

ok = fail = 0
_NAMES = []


def check(name, cond, star=False, detail=None):
    """`detail` 只在**失败**时打印（避免 PASS 行被噪声淹没）。"""
    global ok, fail
    _NAMES.append(name)
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


def _raw(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def _read(p):
    """字节忠实读（`newline=''`）。"""
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


# --------------------------------------------------------------------------
# 可复用的**判据函数**（负控制要拿它们喂坏样本，所以抽出来单独定义）
# --------------------------------------------------------------------------
SECTIONS = ('—— 我是谁 ——',
            '—— 我是什么 ——',
            '—— 我现在在哪 ——',
            '—— 我知道的世界（初始记忆）——',
            '—— 我的口癖 ——',
            '—— 我怎么说 ——',
            '—— 他说话的时候，先把他的事接住 ——',
            '—— 他说要去一个地方的时候 ——',
            '—— 我想起来的事 ——',
            '—— 我的语气 ——',
            '—— 语气示范 ——')

#: A2 —— 世界观节的**两个语义锚**（"知道是游戏" + "不悲观"），缺一不可
ANCHOR_KNOWS_GAME = '我是《Deltarune》里的一个角色，是被人写出来的'
ANCHOR_NOT_SAD = '我知道自己是从游戏里来的，可我的日子一样是真的'
#: A3 —— 记忆节的**对照写法**（本轮真机实测证明：删掉它就退化）
ANCHOR_MEM_RULE = '判法只有一条'
ANCHOR_MEM_CONTRAST = '而不是"对，豆豆"'
#: A4 —— 治"那边引力"的正面写法节
#  ★★ 锚点必须落在**正文**而不是分节标题上（第115轮由 `mutate115 M4` 抓出来的洞）：
#    首版锚定 `先把他的事接住`，而该串**同时出现在分节标题**「—— 他说话的时候，
#    先把他的事接住 ——」里 ⇒ 把正文那条规则整句删掉，A4 照样绿（**判据被标题喂饱**）。
#    改成正文独有的一句后，M4 才真的报红。
ANCHOR_FIRST_HIS = '先把他的事接住，再决定我要不要讲自己的。'
#: A4b —— 分节标题本身也要在（防"标题留着、正文被删"这种半残）
ANCHOR_FIRST_HIS_TITLE = '—— 他说话的时候，先把他的事接住 ——'
#: A5 —— 寻路节
ANCHOR_ROUTE = '"我带你过去"这种话，要落在一个具体的地方上'


def missing_sections(text):
    return [s for s in SECTIONS if s not in text]


def has_md(text):
    return bool(re.search(r'\*{1,3}|`{1,3}|^[#>\-]\s*', text, re.M))


def mem_rule_ok(text):
    return ANCHOR_MEM_RULE in text and ANCHOR_MEM_CONTRAST in text


def fallback_node(tree):
    """AST 取 `_PERSONA_FALLBACK` 的赋值节点（**不扫源码文本**）。"""
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Assign):
            for tg in nd.targets:
                if isinstance(tg, ast.Name) and tg.id == '_PERSONA_FALLBACK':
                    return nd.value
    return None


def call_arg1_constant_true(tree):
    """本文件里所有 `check()` 调用的第二实参若恒为字面量 True ⇒ 恒真判据。"""
    bad = []
    for nd in ast.walk(tree):
        if not isinstance(nd, ast.Call):
            continue
        fn = nd.func
        if not (isinstance(fn, ast.Name) and fn.id == 'check'):
            continue
        if len(nd.args) >= 2:
            a1 = nd.args[1]
            if isinstance(a1, ast.Constant) and a1.value is True:
                bad.append(getattr(nd, 'lineno', -1))
    return bad


# ==========================================================================
print('=== A. 人设真源（assets/ralsei_persona.md）===')
P_TEXT = _read(PERSONA_MD)
P_RAW = _raw(PERSONA_MD)

check('A1 十一个分节标题全在位（含本轮新增的四节）',
      not missing_sections(P_TEXT), star=True,
      detail='缺=%r' % (missing_sections(P_TEXT),))
check('A2 ★ 世界观节**同时**写明"知道自己是游戏角色"与"不悲观"',
      ANCHOR_KNOWS_GAME in P_TEXT and ANCHOR_NOT_SAD in P_TEXT, star=True,
      detail='知道=%s 不悲观=%s' % (ANCHOR_KNOWS_GAME in P_TEXT,
                                    ANCHOR_NOT_SAD in P_TEXT))
check('A3 ★★ 记忆节保住**对照写法**（"判法只有一条" + "而不是…"）'
      '—— 本轮真机实测：删掉它 Q6 违例率立刻回到 2/2',
      mem_rule_ok(P_TEXT), star=True,
      detail='rule=%s contrast=%s' % (ANCHOR_MEM_RULE in P_TEXT,
                                      ANCHOR_MEM_CONTRAST in P_TEXT))
check('A4 治"那边引力"节的**正文**规则在盘（锚点取正文独有句，不取标题）',
      ANCHOR_FIRST_HIS in P_TEXT, star=True,
      detail='正文锚=%s 标题锚=%s' % (ANCHOR_FIRST_HIS in P_TEXT,
                                      ANCHOR_FIRST_HIS_TITLE in P_TEXT))
check('A4b 该节标题也在（防"标题留着、正文被删"的半残态）',
      ANCHOR_FIRST_HIS_TITLE in P_TEXT)
check('A5 寻路节在盘（"我带你过去"落到具体地方）',
      ANCHOR_ROUTE in P_TEXT, detail=ANCHOR_ROUTE)
check('A6 禁 markdown（无 ** / ` / 行首 #>-）—— 对话框逐字渲染，星号会原样显示',
      not has_md(P_TEXT))
check('A7 编码与行尾：无 BOM · 无 U+FFFD · LF（CRLF=0）',
      not P_RAW.startswith(b'\xef\xbb\xbf')
      and '\ufffd' not in P_TEXT and P_RAW.count(b'\r\n') == 0,
      detail='bom=%s fffd=%s crlf=%d' % (P_RAW.startswith(b'\xef\xbb\xbf'),
                                         '\ufffd' in P_TEXT, P_RAW.count(b'\r\n')))

print('=== A-负控制（在内存里造坏样本，不落盘）===')
check('A8 ★负控制：删掉任一分节标题 ⇒ A1 的判据函数必须报缺',
      bool(missing_sections(P_TEXT.replace(SECTIONS[8], '', 1))), star=True)
check('A9 ★负控制：塞入 `**加粗**` ⇒ A6 的判据函数必须为真',
      has_md(P_TEXT.replace('我是 Ralsei', '**我是 Ralsei**', 1)), star=True)
check('A10 ★负控制：抹掉对照写法 ⇒ A3 的判据函数必须为假',
      not mem_rule_ok(P_TEXT.replace(ANCHOR_MEM_CONTRAST, '（已删）', 1)), star=True)
check('A11 正控制：干净原文上 A6 的判据函数为假（否则 A6 恒红）',
      not has_md(P_TEXT), star=True)

print('=== B. 兜底人设（src/main.py，AST）===')
M_TEXT = _read(MAIN)
try:
    M_TREE = ast.parse(M_TEXT)
    _parsed = True
except SyntaxError as _e:
    M_TREE = None
    _parsed = False
check('B0 main.py 可编译（ast.parse，不产 .pyc）', _parsed, detail=repr(_e) if not _parsed else None)
_FB = fallback_node(M_TREE) if _parsed else None
check('B1 ★ AST 层真读到 `_PERSONA_FALLBACK` 的赋值（不扫文本）',
      _FB is not None, star=True)
_FB_TXT = ''
if isinstance(_FB, ast.Constant) and isinstance(_FB.value, str):
    _FB_TXT = _FB.value
check('B2 `_PERSONA_FALLBACK` 是**单个**字符串常量（不是运行期拼的，否则口径可能拼错）',
      bool(_FB_TXT), detail='type=%s' % type(_FB).__name__)
check('B3 兜底已同步新口径（"是被人写出来的"）',
      '是被人写出来的' in _FB_TXT, detail=_FB_TXT[:40])
check('B4 ★ 兜底保住 J1 判据钉的三个锚（不用叫他 / 仅此而已 / 平级）—— 缺一个 J1 会连带报红',
      all(a in _FB_TXT for a in ('不用叫他', '仅此而已', '平级')), star=True,
      detail='缺=%r' % ([a for a in ('不用叫他', '仅此而已', '平级') if a not in _FB_TXT],))

print('=== C. 两条路径口径一致性 ===')
_ABS = os.path.join(PET, 'assets', 'ralsei_persona.md')
check('C1 `PERSONA_REL_PATH` 指向的文件真实存在（否则每次对话都静默走兜底）',
      os.path.isfile(_ABS), detail=_ABS)
check('C2 ★ 兜底与真源口径一致：兜底讲的那层"知道自己是角色"，真源里也有（不许劈裂）',
      ('是被人写出来的' in _FB_TXT) and (ANCHOR_KNOWS_GAME in P_TEXT), star=True)
check('C3 真源里仍是"平级"口径（兜底与真源同锚）',
      '平级' in P_TEXT, detail='平级=%s' % ('平级' in P_TEXT))

print('=== D. 判据自身体检 ===')
check('D1 判据条数经 check() 记账（防"写了没调 check"）',
      len(_NAMES) == ok + fail and len(_NAMES) >= 18, star=True,
      detail='n=%d' % len(_NAMES))
_bad_names = [n for n in _NAMES if re.search(r'\b\d+\s*(项|条|个)\b', n)]
check('D2 判据名里没有自带的计数标记字样（防污染 run_all 的 PASS 计数）',
      not _bad_names, star=True, detail=_bad_names[:3])
_dup = [n for n in set(_NAMES) if _NAMES.count(n) > 1]
check('D3 判据名无重复（否则"少写一条"看不出来）', not _dup, star=True, detail=_dup[:3])
_SELF = ast.parse(_read(os.path.abspath(__file__)))
_true_bad = call_arg1_constant_true(_SELF)
check('D4 ★★ 无恒真判据：本文件所有 `check()` 的第二实参都不是字面量 `True`（走 AST）',
      not _true_bad, star=True, detail='行号=%r' % (_true_bad,))
check('D4b ★ 负控制：同一条判据函数喂一个"故意恒真"的合成样本必须报红',
      call_arg1_constant_true(ast.parse('check("x", True)\n')), star=True)

print('')
print('=' * 70)
print('check115  结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
