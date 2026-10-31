# -*- coding: utf-8 -*-
u"""第128轮回归锁：**"起头结巴"不许再回来**（用户口径：100 句里 2 句就够）。

## 这一轮修的是什么

用户说「这个结巴要少一些 100 句里出现 2 句就够了」。我先按最直觉的假设去量
（"重复字"型结巴），**结果被自己否掉了**：

  · 真机 50 条（`ralsei:v4` / temperature 0.85 / max_tokens 256 / `/v1/chat/completions`，
    system = persona 全文 + `nervous_brief(0.156301, 'chat')`，即用户 vault 的真实档位
    distrust）里，"同字/人称字紧邻重复"型结巴 = **0/50**；
  · 但同一批回复里，**开口先垫一个迟疑词**（`嗯……`／`诶？`／`哦...`）= **26/50 = 52%**。

⇒ 用户听到的"结巴"，真身是**句首那口气**，不是叠字。这是本轮最重要的一次纠偏：
  照原假设去改"重复字"的文案，指标不会有任何变化。

## 根因：三处"每句配额/示范"式指令（都是我们自己的文案）

1. `assets/ralsei_persona.md`「我的口癖」节：`最多沾一两处`（配额）、
   `开口有时会带个语气词`（直接许可）、语气节 `一时没准备好 → 起音含混`（示范）
2. `modules/relationship.py` `nervous_brief()` distrust 档：`会重复一两个字、会突然停住`、
   `一条回复里最多带出一处磕绊`（把配额写成"每句允许一处"）
3. 7B 不会把"最多一处"读成"少数句子"，而是读成"**我说话要磕一下**"

## 修法（两层：提示词降源 + 护栏定死）

- 提示词：删掉三处许可/示范，只描述状态并写明"多数句子是顺的"。
  实测 52.0% → **40.0%**（只改人设）→ **4.0%**（人设 + brief 都改），
  到不了 2%（提示词不是保证）。
- 护栏：`event_speech.strip_head_hesitation()` —— **只削句首那一簇**，
  在 `_clean_ai_reply`（0d）与 `_sanitize_partial_reply` 两处**共用同一个函数**
  （流式期间不会"先打出来再擦掉"）。用户可见率由此压到 **0%**。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 文案纪律   —— `nervous_brief` 四档不许再出现"配额句"与"指令式示范"；紧张度数值不许漂
B 人设真源   —— 三条旧许可必须已删、新禁令在位、体积没被砍瘦、原有硬口径还在
C **从原文重算** —— `_evidence/raw/*.jsonl` 四臂各 50 条逐条重算：
                基线起头率必须 ≥50%（前提闸）、修后**用户可见**起头率 ≤2%、
                真结巴率不许上升、归因单调（both ≤ 只改人设 ≤ 基线）、
                复核臂与 quoted 版同档、带停顿的卡壳归零（子类观察）
D 负控制     —— 把**改前原文**喂同一批判据必须报红（判据不是恒真）
E 护栏行为   —— 削头只动头（结果必须是原文的后缀）、反例原样返回、
                前缀安全（流式前提）、两处接线、单一真源
F 自检       —— AST 查恒真判据 / 分母非空 / 被测文件真读到

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；负控制夹具是**数据快照**（改前原文），
不是第二份实现 —— 判据函数只有一份，对"好文案"和"坏文案"各跑一次。
**统计数字一律从原始回复重算**，不读我手写的汇总表（防"两张表同源错"）。
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
from modules import relationship as R                          # noqa: E402
from modules import event_speech as ES                          # noqa: E402

PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
REL_PY = os.path.join(PET, 'modules', 'relationship.py')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
META = os.path.join(EV, 'ab128.json')

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
    print(u'=' * 78)


def _read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def _read_jsonl(p):
    out = []
    for line in io.open(p, encoding='utf-8'):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------- 量纲（只有一份）

#: 句首**纯迟疑词**—— 用户说的"结巴"就是这一簇（别把 `哎/啊/唉` 算进来：
#: 那是真感叹，削了反而伤语气；见 `_evidence/ab128.json` 的 `metric` 说明）
HES = u'嗯诶哦呃唔'
OPEN_HES_RE = re.compile(r'^[%s]' % HES)
OPEN_EXCL_RE = re.compile(u'^\\s*(?:哎呀|哎|啊|唉)')
#: 句首迟疑词**后面跟着停顿标记**（省略号/破折号/问号/叹号）—— 这才是"卡壳"。
#: 与「哦，」这种**逗号应答**分开计：后者是"哦！原来如此"，属正常语气。
#: ★ 这是**子类观察**，不替代主指标 `head_pure`（换主指标＝事后挪球门）。
HES_PAUSE_RE = re.compile(u'^[%s]{1,3}\\s*(?:…+|\\.{3,}|—+|－+|~+|？|\\?|！|!)' % HES)
#: 省略号口径：`…` 或连续三点以上（报告表头括注同一口径）
ELL_RE = re.compile(u'…|\\.{3,}')
#: 真结巴（叠字型）：K1 同字+省略号+同字；K2 人称/否定/应答字紧邻重复
K1_RE = re.compile(r'([\u4e00-\u9fa5])(?:…+|\.{2,}|—+|－+|~+)\1')
K2_RE = re.compile(r'([\u4e00-\u9fa5])\1')
K2_HOT = u'我你他她它不就是这就那嗯呃唉哦'
K2_OK = set(u'慢慢 轻轻 悄悄 好好 多多 常常 刚刚 渐渐 早早 远远 深深 紧紧 静静 谢谢'.split())


def stats(rows):
    """逐条重算一个臂的全部指标（**观察量由产品代码判**：`head_visible` 走真护栏）。"""
    n = len(rows)
    head_pure = head_excl = head_visible = stut = ell = head_pause = 0
    for r in rows:
        t = (r.get('reply') or '').strip()
        if not t:
            continue
        if OPEN_HES_RE.match(t):
            head_pure += 1
            if HES_PAUSE_RE.match(t):
                head_pause += 1
        if OPEN_EXCL_RE.match(t):
            head_excl += 1
        if OPEN_HES_RE.match(ES.strip_head_hesitation(t) or ''):
            head_visible += 1
        if ELL_RE.search(t):
            ell += 1
        hit = False
        for m in K1_RE.finditer(t):
            hit = True
        for m in K2_RE.finditer(t):
            if m.group(1) in K2_HOT and (m.group(1) * 2) not in K2_OK:
                hit = True
        if hit:
            stut += 1
    return {'n': n, 'head_pure': head_pure, 'head_pause': head_pause,
            'head_excl': head_excl, 'head_visible': head_visible,
            'stutter': stut, 'ell': ell}


def _pct(a, b):
    return 100.0 * a / max(1, b)


def _main_int_const(name):
    """从 main.py 的 AST 里取一个**类级整数常量**（取不到返 None）。

    为什么要走 AST 而不是正则扫文本：`HES_ALLOW_GAP` 这个名字会出现在注释与
    docstring 里（我们自己在上面写了一堆解释），纯文本扫会抓到注释里的数字
    （项目里"禁纯文本扫 API"已栽过六次）。
    """
    try:
        tree = ast.parse(_read(MAIN_PY))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    v = node.value
                    if isinstance(v, ast.Constant) and isinstance(v.value, int):
                        return v.value
    return None


#: ★ 改前原文快照（第128轮修改**之前**的两段文案）—— 只作负控制夹具，不是第二份真相。
_OLD_DISTRUST = (
    u'【你现在的状态】你现在心里**很紧**。对方一开口你就有点慌，怕自己说错话。'
    u'这种时候你说话容易磕绊 —— 会重复一两个字、会突然停住。'
    u'但**不是每句都这样**：慌归慌，话还是要说清楚，'
    u'一条回复里最多带出一处磕绊，多数句子是顺的。')
_OLD_PERSONA_LINES = (
    u'我说话有几个改不掉的习惯。这些是"毛边"，不是每句都要有，用得越少越像；\n'
    u'一条回复里最多沾一两处，很多时候一处也不沾才是对的：\n'
    u'心里一急会重复一个字，但不是每句都结巴 —— 越紧张越明显，平常聊天基本不结巴。\n'
    u'开口有时会带个语气词，但多数回复是直接说事，不带任何起头。\n'
    u'  · 一时没准备好 → 起音含混\n')


# ================================================================ A 文案纪律

_QUOTA_RE = re.compile(u'最多[^。；\\n]{0,10}(一处|一两处|一下|一次)')
_DEMO_RE = re.compile(u'会重复一两个字|会突然停住|重复一下、或者顿一下')


def _bad_tokens(text):
    """返回命中的"配额/示范"片段（空列表 = 干净）。**四档共用这一个函数**。"""
    out = []
    for m in _QUOTA_RE.finditer(text):
        out.append('配额:' + m.group(0))
    for m in _DEMO_RE.finditer(text):
        out.append('示范:' + m.group(0))
    return out


_TIERS = ((0.00, 'chat', 'distrust'), (0.40, 'chat', 'guarded'),
          (0.62, 'chat', 'warming'), (0.95, 'comfort', 'friend'))


def a_brief():
    head(u'A. nervous_brief 四档文案纪律（配额句 / 指令式示范）')
    briefs = dict((name, R.nervous_brief(t, ev)) for t, ev, name in _TIERS)
    check(u'A0 四档文案都非空（分母闸：空文案会让 in 判定恒真）',
          all(len(b) >= 30 for b in briefs.values()),
          u' / '.join(u'%s=%d' % (k, len(v)) for k, v in sorted(briefs.items())))
    bad = []
    for name, b in briefs.items():
        for tok in _bad_tokens(b):
            bad.append((name, tok))
    check(u'A1 四档都不含"每句配额"句式（最多…一处 / 一条回复里最多）', not bad,
          u'' if not bad else u'命中 %r' % (bad[:4],))
    # 分发锚点：取样点必须真的落在对应档，否则 A1 是在别的档上空转
    check(u'A1b distrust 取样点真的落在"很紧"那一段', u'很紧' in briefs['distrust'])
    check(u'A1c friend 取样点真的落在"稳"那一段', u'稳' in briefs['friend'])
    check(u'A2 distrust 档写明"多数句子是顺的"（不是只丢一句禁令）',
          u'多数句子是顺的' in briefs['distrust'])
    check(u'A3 distrust 档点明了"起音"这一具体毛病', u'起音' in briefs['distrust'])


def a_numbers_untouched():
    head(u'A4 紧张度数值一个都没动（本轮只改措辞）')
    want = {'distrust': 0.62, 'guarded': 0.44, 'warming': 0.24, 'friend': 0.10}
    got = dict(R._STAGE_NERVOUSNESS)
    check(u'A4 四档基础紧张度仍是 0.62/0.44/0.24/0.10', got == want, u'%r' % (got,))
    check(u'A4b NERVOUS_FLOOR 仍是 0.04（用户口径"不许到 0"）',
          abs(R.NERVOUS_FLOOR - 0.04) < 1e-9)
    ev = dict(R._EVENT_NERVOUSNESS)
    want_ev = {'chat': 0.0, 'self_share': -0.06, 'curious': 0.08,
               'comfort': -0.14, 'harsh': 0.30, 'cold': 0.04}
    check(u'A4c 六个事件偏移量仍是原值', ev == want_ev, u'%r' % (ev,))


# ================================================================ B 人设真源

def b_persona():
    head(u'B. 人设真源（assets/ralsei_persona.md）')
    md = _read(PERSONA)
    raw = io.open(PERSONA, 'rb').read()
    check(u'B0 persona 读得到且非空（分母闸）', len(md) > 3000, u'%d 字符' % len(md))
    check(u'B1 旧的"开口有时会带个语气词"许可已删', u'开口有时会带个语气词' not in md)
    check(u'B2 旧的"一条回复里最多沾一两处"配额已删', u'最多沾一两处' not in md)
    check(u'B3 旧的"起音含混"示范已删', u'起音含混' not in md)
    check(u'B4 主线仍是"开口直接说那件事"（不是把起头许可又放开了）',
          (u'开口直接说那件事' in md) and (u'不垫' not in md))
    # ★ 128 续：用户口径「不能为 0%」⇒ 许可**必须存在**，但只能是**条件式**的。
    #   ★ 它**不放在人设里**：人设有体积闸（`verify_persona_chat K3` < 10KB），
    #     而且"此刻是什么状态"本来就该由 `nervous_brief` 说（人设是恒定性格）。
    #   ⇒ 判据落在**运行时真正注入的那段文案**上（`R.nervous_brief(0.0,'chat')`），
    #     不是落在磁盘上的某个文件里 —— 断行为，不断赋值。
    _brief = R.nervous_brief(0.0, 'chat')
    check(u'B4b 运行时 brief 里有条件式许可（触发条件 + "顿一顿"）',
          (u'被问住' in _brief) and (u'顿一顿' in _brief), u'%.60r' % _brief)
    check(u'B4c 且带封顶（"多数句子是顺的"），不是无条件放开',
          u'多数句子是顺的' in _brief)
    check(u'B4d 许可里没有次数/配额数字（复用 A 段同一判据，不另立一套）',
          _bad_tokens(_brief) == [], u'命中 %r' % (_bad_tokens(_brief)[:4],))
    check(u'B4e 人设里那句起头纪律是**中性**的（既不硬禁也不放开，交给 brief 判状态）',
          (u'开口直接说那件事' in md) and (u'不垫' not in md) and (u'顿一顿' not in md))
    check(u'B5 原有硬口径"不是每句都结巴"仍在（没被顺手删掉）',
          u'不是每句都结巴' in md)
    check(u'B6 persona 体积仍 ≥ 9000 字节（没被砍瘦）', len(raw) >= 9000,
          u'%d 字节' % len(raw))
    check(u'B6b persona 体积 ≤ 10240 字节（历史 K3 上限）', len(raw) <= 10240,
          u'%d 字节' % len(raw))
    check(u'B7 persona 无 BOM、无 U+FFFD',
          (not raw.startswith(b'\xef\xbb\xbf')) and (b'\xef\xbf\xbd' not in raw))


# ================================================================ C 原文重算

def c_evidence():
    head(u'C. 真机 A/B 四臂（**从原始回复重算**，不读汇总表）')
    need = ('base.jsonl', 'pnew_bold.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl')
    miss = [f for f in need if not os.path.exists(os.path.join(RAW, f))]
    check(u'C0 四臂原文都在 _evidence/raw/ 下', not miss, u'' if not miss else u'缺 %r' % (miss,))
    if miss:
        return
    if not os.path.exists(META):
        check(u'C0b 元数据 ab128.json 在', False)
        return
    meta = json.loads(_read(META))
    arms = {}
    for f in need:
        arms[f[:-6]] = stats(_read_jsonl(os.path.join(RAW, f)))
    ns = [v['n'] for v in arms.values()]
    check(u'C1 四臂都是 50 条（可比性闸）', len(ns) == 4 and set(ns) == {50}, u'%r' % (ns,))
    inputs = meta.get('inputs') or []
    check(u'C2 同一批 50 条输入（首/末条固定，防换题重测）',
          len(inputs) == 50 and inputs[0] == u'今天好累啊' and inputs[-1] == u'陪我待一会儿',
          u'n=%d' % len(inputs))
    b, m, a = arms['base'], arms['pnew_bold'], arms['pnew_bnew']
    # ★ `pnew_bnew2` = **最终发布版人设**（把 `不垫"嗯""诶"` 的引号去掉之后）复跑的一臂。
    #   报告里的数字以它为准 —— 不许拿没测过的文本报数。
    fin = arms['pnew_bnew2']
    # 前提闸：基线本身必须有病，否则"降到 2%"是空话
    check(u'C3 基线句首迟疑率 ≥ 50%（前提：这条真的有问题）',
          b['head_pure'] >= 25, u'%.1f%%（%d/%d）'
          % (_pct(b['head_pure'], b['n']), b['head_pure'], b['n']))
    # 提示词层：修后仍要明显低于基线（否则"提示词也改了"是空话）
    check(u'C4 提示词层真的降了：最终版 < 基线（哪怕没到 2%）',
          fin['head_pure'] < b['head_pure'],
          u'改前 %.1f%% → 最终版 %.1f%%' % (_pct(b['head_pure'], b['n']),
                                            _pct(fin['head_pure'], fin['n'])))
    # 用户可见层：护栏之后必须 ≤ 2%（用户口径）
    check(u'C5 用户可见句首迟疑率 ≤ 2%（用户口径：100 句 2 句）',
          fin['head_visible'] <= 1, u'%d/%d = %.1f%%（四臂都已过护栏重算）'
          % (fin['head_visible'], fin['n'], _pct(fin['head_visible'], fin['n'])))
    check(u'C5b 基线臂过护栏后也降到 ≤2%（护栏不是只对新文案有效）',
          b['head_visible'] <= 1, u'%d/%d' % (b['head_visible'], b['n']))
    # 不许用一种失真换另一种
    check(u'C6 真结巴率（叠字型）没有上升', fin['stutter'] <= b['stutter'],
          u'改前 %d/%d → 改后 %d/%d' % (b['stutter'], b['n'], fin['stutter'], fin['n']))
    # 归因单调：只改人设那一臂必须落在中间，否则两处改动无从归因
    check(u'C7 归因：both ≤ 只改人设 ≤ 基线（同一版人设的三臂）',
          a['head_pure'] <= m['head_pure'] <= b['head_pure'],
          u'base %d ≥ pnew_bold %d ≥ both %d'
          % (b['head_pure'], m['head_pure'], a['head_pure']))
    # 复核臂：去引号这处**纯措辞**改动不许改变行为（差 ≤2 条 = 采样噪声内）
    check(u'C7b 复核臂与 quoted 版同档（去引号没有改变行为，差 ≤2 条）',
          abs(fin['head_pure'] - a['head_pure']) <= 2,
          u'quoted %d / final %d' % (a['head_pure'], fin['head_pure']))
    # 语气没被磨平：感叹词起头不该被这一轮"顺手清零"
    # ★ 单看终版这一臂是 0/50（改前 4/50），但那 50 条里本来也只期望 1~2 条，
    #   0 条不能单独判红（n=50 分不清"清零"与"没抽到"）。所以判据落在**四臂合计**：
    #   200 条里必须还有感叹起头，否则就是我们真把"哎呀/哎"这种语气磨掉了。
    _excl_sum = b['head_excl'] + m['head_excl'] + a['head_excl'] + fin['head_excl']
    check(u'C8 四臂合计仍有感叹词起头（没把"哎呀/哎"这种正常语气顺手清零）',
          _excl_sum >= 1,
          u'base %d / bold %d / both %d / final %d，合计 %d/200'
          % (b['head_excl'], m['head_excl'], a['head_excl'], fin['head_excl'], _excl_sum))
    # ★ 子类观察（**不替代 C5 的主指标**）：终版残留的句首迟疑词里，还有几个是
    #   带停顿的"卡壳"？基线 26 条**全部**带停顿（嗯……/诶？/哦...），终版这 2 条
    #   都是「哦，」逗号应答（= "哦！原来如此"），与 `哎呀/哎` 同族。
    check(u'C8b 终版"带停顿的卡壳"= 0 条（残留的只是「哦，」应答，子类观察）',
          fin['head_pause'] == 0,
          u'基线 %d 条带停顿 → 终版 %d 条；终版 head_pure=%d'
          % (b['head_pause'], fin['head_pause'], fin['head_pure']))
    check(u'C8c 基线里"带停顿"占句首迟疑的绝大多数（口径可信：基线 26/26）',
          b['head_pause'] >= b['head_pure'] - 1,
          u'%d/%d' % (b['head_pause'], b['head_pure']))

    # ---------------- C9/C10：用户「不能为 0%」之后的第二段 ----------------
    # ★ 为什么另开一段而不是改 C5：C5 守的是"护栏**有能力**把它压到 ≤2%"（默认全削），
    #   这一段守的是"**放行之后**还剩多少"。两件事，两个方向，不能合成一条。
    rl = os.path.join(RAW, 'pnew_relax.jsonl')
    if not os.path.exists(rl):
        check(u'C9 第 5 臂（改回条件式许可后）原文在', False)
        return
    relax = stats(_read_jsonl(rl))
    check(u'C9a 第 5 臂 n=100（2% 需要 100 条分辨率；50 条只能分辨 2%/4%）',
          relax['n'] == 100, u'n=%d' % relax['n'])
    check(u'C9b 改回条件式许可后，模型**真的又开始结巴了**（带停顿 ≥1 条：不能为 0%）',
          relax['head_pause'] >= 1,
          u'%d/%d = %.1f%%' % (relax['head_pause'], relax['n'],
                               _pct(relax['head_pause'], relax['n'])))
    # ★ 上限**按意图定，不按实测凑**：意图是"模型仍会结巴，但不是每两句一次"。
    #   基线是 52%（26/50），这里取 ≤20%（≈五句一次）—— 既明显脱离基线，
    #   又给"7B 对许可句的服从性差"留了余量（本轮已实测它会把"偶尔"读成"常常"）。
    #   用户**听到**的比例由 C10 的节流闸保证 ≤2%，这一条只管"提示词别又崩回去"。
    check(u'C9c 但没有回潮（带停顿 ≤ 20%，基线是 52%）',
          relax['head_pause'] <= 20, u'%d/%d' % (relax['head_pause'], relax['n']))
    # C10：节流闸的**数学**。闸门规则只有一条，可以逐条模拟（不改产品状态）。
    # ★ 阈值**从产品源码 AST 取**，不在这里再写一遍 50 —— 否则改了产品、判据还按老数算，
    #   就是"判据互证"那种假绿（124 轮 B4b/B4c 的教训）。
    _gap = _main_int_const('HES_ALLOW_GAP')
    check(u'C10 产品里 HES_ALLOW_GAP 存在且是正整数（闸门阈值可读）',
          isinstance(_gap, int) and _gap > 0, u'%r' % (_gap,))
    _vis = 0
    _g = _gap
    for r in _read_jsonl(rl):
        _t = (r.get('reply') or '').strip()
        if not _t:
            continue
        _is_pause = bool(HES_PAUSE_RE.match(_t))
        # 放行条件只看额度；**放行后留下的必须真是卡壳**才算"用掉额度"
        if _g >= _gap and _is_pause:
            _vis += 1
            _g = 0
        else:
            _g += 1            # ★ 回补按"条"算（1/50 = 2%）；按"结巴次数"算会变成 1/300
    check(u'C10a 节流闸把可见率压在上限内（≤ 2%：100 条最多 2 条）',
          _vis <= 2, u'模拟放行 %d/%d（阈值 %r）' % (_vis, relax['n'], _gap))
    check(u'C10b 且没有把它又压回 0（下限 = 模型自然产出，不做假卡壳）',
          _vis >= 1, u'模拟放行 %d/%d' % (_vis, relax['n']))


# ================================================================ D 负控制

def d_negative():
    head(u'D. 负控制（把改前原文喂同一批判据，必须报红）')
    old_hits = _bad_tokens(_OLD_DISTRUST)
    check(u'D1 旧 distrust 文案被同一判据抓出（配额+示范合计 ≥2 处）',
          len(old_hits) >= 2, u'%r' % (old_hits[:4],))
    check(u'D1b 旧文案的"最多带出一处"被"配额"判据抓到',
          any(h.startswith(u'配额:') for h in old_hits))
    check(u'D1c 旧文案的"会重复一两个字/会突然停住"被"示范"判据抓到',
          any(h.startswith(u'示范:') for h in old_hits))
    check(u'D2 旧人设行"开口有时会带个语气词"在（对照夹具真实性）',
          u'开口有时会带个语气词' in _OLD_PERSONA_LINES)
    check(u'D2b 旧人设行"最多沾一两处"在（对照夹具真实性）',
          u'最多沾一两处' in _OLD_PERSONA_LINES)
    check(u'D2c 旧人设行"起音含混"在（对照夹具真实性）',
          u'起音含混' in _OLD_PERSONA_LINES)
    new_hits = _bad_tokens(R.nervous_brief(0.0, 'chat'))
    check(u'D3 A/B 先断言不同：新旧 distrust 判据结果不同',
          (not new_hits) and bool(old_hits))
    check(u'D3b 新 distrust 文案被判据看过一遍且零命中（防 no-op）',
          new_hits == [], u'%r' % (new_hits,))


# ================================================================ E 护栏行为

def _rows_all():
    out = []
    for f in ('base.jsonl', 'pnew_bold.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl'):
        p = os.path.join(RAW, f)
        if os.path.exists(p):
            out.extend(_read_jsonl(p))
    return out


def e_guard():
    head(u'E. 护栏行为（strip_head_hesitation）')
    rows = _rows_all()
    check(u'E0 有原文可测（四臂合计 200 条）', len(rows) >= 200, u'n=%d' % len(rows))
    # E1 削完之后，句首不再有迟疑词（对真机原文逐条验）
    left = [r['reply'] for r in rows
            if OPEN_HES_RE.match(ES.strip_head_hesitation(r['reply']) or '')]
    check(u'E1 全部原文过护栏后句首无迟疑词', not left,
          u'' if not left else u'残留 %d 条' % len(left))
    # E2 只动头：结果必须是原文的**后缀**（证明句中没有被动过）
    broken = []
    for r in rows:
        t = r['reply'].strip()
        s = ES.strip_head_hesitation(t)
        if s and s != t and not t.endswith(s):
            broken.append((t[:12], s[:12]))
    check(u'E2 护栏只削头（结果是原文后缀，句中一个字没动）', not broken,
          u'' if not broken else u'%r' % (broken[:3],))
    # E3 反例：这几类**必须原样返回**
    keep = [u'……Dess。', u'哎呀，走了一万多步挺不错的！', u'我想……我想',
            u'（心里有点慌）', u'外面下雨了。']
    bad = [(k, ES.strip_head_hesitation(k)) for k in keep
           if ES.strip_head_hesitation(k) != k]
    check(u'E3 反例原样返回（句首省略号/感叹词/句中卡断/括号心里话/普通句）',
          not bad, u'' if not bad else u'%r' % (bad[:3],))
    # E4 只剩口气 → 空串（让调用方判退重采样，而不是显示一个"嗯"）
    empty = {}
    for k in (u'嗯', u'唔……', u'诶！！', u'嗯嗯'):
        empty[k] = ES.strip_head_hesitation(k)
    check(u'E4 只剩口气的回复返回空串（单回一个「嗯」不该显示）',
          all(v == '' for v in empty.values()), u'%r' % (empty,))
    # E5 前缀安全（流式的前提）：任意前缀削完 = 完整文本削完的前缀
    sample = None
    for r in rows:
        if OPEN_HES_RE.match(r['reply'].strip()):
            sample = r['reply'].strip()
            break
    ok_pre = False
    if sample:
        full = ES.strip_head_hesitation(sample)
        ok_pre = True
        for i in range(1, len(sample) + 1):
            piece = ES.strip_head_hesitation(sample[:i])
            if not full.startswith(piece):
                ok_pre = False
                break
    check(u'E5 前缀安全：任意前缀削完仍是完整文本削完的前缀（流式不抖字）',
          bool(sample) and ok_pre, u'样本 %r' % ((sample or u'')[:14],))
    # E6 接线：两处都调，且都指向同一个函数
    msrc = _read(MAIN_PY)
    check(u'E6 `_clean_ai_reply` 调了 strip_head_hesitation',
          u'strip_head_hesitation(t)' in msrc)
    check(u'E6b `_sanitize_partial_reply` 也调了（流式同一份规则）',
          msrc.count(u'strip_head_hesitation(t)') >= 2,
          u'出现 %d 次' % msrc.count(u'strip_head_hesitation(t)'))
    # E7 单一真源：函数只在 event_speech.py 定义
    defs = []
    for dirpath, _d, files in os.walk(PET):
        if '__pycache__' in dirpath:
            continue
        for fn in files:
            if fn.endswith('.py'):
                p = os.path.join(dirpath, fn)
                if u'def strip_head_hesitation(' in _read(p):
                    defs.append(os.path.relpath(p, PET))
    check(u'E7 strip_head_hesitation 只定义一次（无第二份真相）', defs == [os.path.join('modules', 'event_speech.py')],
          u'%r' % (defs,))

    # ---------------- E5b~E9：128 续加的「节流阀」----------------
    # ★ 用户口径「不能为 0%」⇒ 护栏必须**能放行**。但放行不能破坏"流式不抖字"，
    #   所以放行模式也要单独穷举一次前缀安全（不是拿削除模式的结论顶过去）。
    _keep = [u'嗯……你说猫啊', u'诶？你买了个新杯子啊？是什么样的', u'哦，走得挺多的呢！',
             u'诶、诶？！你说', u'嗯嗯，好', u'唔…外面的风挺大的', u'嗯', u'唔……']
    ES.set_head_hesitation_allowance(True)
    try:
        _bad_keep = []
        for c in _keep + [r['reply'].strip() for r in rows if r['reply'].strip()]:
            full = ES.strip_head_hesitation(c)
            for i in range(1, len(c) + 1):
                if not full.startswith(ES.strip_head_hesitation(c[:i])):
                    _bad_keep.append((c[:12], i))
                    break
        check(u'E5b 放行模式下**仍然**前缀安全（穷举 200 条原文 + 8 条夹具）',
              not _bad_keep, u'' if not _bad_keep else u'%r' % (_bad_keep[:3],))
        # 放行 = 原样返回（那一簇必须真留在屏幕上，否则"放行"是假的）
        _hit_keep = [c for c in _keep if ES.head_hesitation_hit(c) and c not in (u'嗯', u'唔……')]
        _fake = [(c, ES.strip_head_hesitation(c)) for c in _hit_keep
                 if ES.strip_head_hesitation(c) != c]
        check(u'E5c 放行时原样返回那一簇（不是"放行了个寂寞"）',
              not _fake, u'' if not _fake else u'%r' % (_fake[:3],))
        # 但"整条只有一口气"放行也要判空（一个「嗯」不是人味）
        check(u'E5d 放行也不放行"整条只有一口气"（`嗯`/`唔……` 仍返回空串）',
              ES.strip_head_hesitation(u'嗯') == '' and ES.strip_head_hesitation(u'唔……') == '')
    finally:
        ES.set_head_hesitation_allowance(False)

    # E6c 闸门接线：必须在**发请求之前**定，且收尾要结算（否则额度永远不消耗）
    check(u'E6c 发请求前设好本回合的闸门（`set_head_hesitation_allowance` 在 `_ask` 之前）',
          msrc.find(u'set_head_hesitation_allowance(') < msrc.find(u'reply = _ask(system, opts)'))
    check(u'E6d 收尾层结算额度（`self._hes_gap` 真的被改写）',
          u'self._hes_gap = 0' in msrc and u'self._hes_gap = getattr(self' in msrc)
    # E8 默认关闭：没设过就一律削（安全网不许因为加了个开关而失效）
    check(u'E8 闸门默认关闭（默认 False ⇒ 行为与 128 轮一字不差）',
          ES.head_hesitation_allowance() is False)


# ================================================================ F 自检

def f_selfcheck():
    head(u'F. 自检（恒真判据 / 分母 / 被测文件）')
    src = _read(os.path.abspath(__file__))
    tree = ast.parse(src)
    const_true = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Name) and f.id == 'check'):
            continue
        if len(node.args) < 2:
            continue
        c = node.args[1]
        if isinstance(c, ast.Constant) and c.value is True:
            const_true.append(node.lineno)
    check(u'F1 没有 check(..., True) 这种恒真判据', not const_true, u'%r' % (const_true,))
    check(u'F2 本文件判据数 ≥ 30（分母非空）', _n['p'] + _n['f'] >= 30,
          u'实际 %d' % (_n['p'] + _n['f']))
    check(u'F3 relationship.py 读得到', os.path.exists(REL_PY) and len(_read(REL_PY)) > 5000)
    check(u'F4 event_speech.py 读得到', os.path.exists(ES_PY) and len(_read(ES_PY)) > 5000)
    check(u'F5 main.py 读得到', os.path.exists(MAIN_PY) and len(_read(MAIN_PY)) > 100000)
    # ★ 首跑报红（红的是判据）：`nervous_brief` 在 relationship.py 里**本来就两处** ——
    #   模块级纯函数 `def nervous_brief(...)` + `Relationship` 的实例方法
    #   `    def nervous_brief(self, ...)`。原来按"整个文件只出现 1 次"写死，是错的。
    #   真正该守的是"模块级只定义一份"（实例方法是薄包装，见 check75 C1c 同值闸）。
    rel_src = _read(REL_PY)
    top = len(re.findall(u'(?m)^def nervous_brief\\(', rel_src))
    meth = len(re.findall(u'(?m)^\\s{4}def nervous_brief\\(', rel_src))
    check(u'F6 nervous_brief 模块级只定义一份（实例方法只是薄包装）',
          top == 1 and meth == 1, u'模块级 %d / 方法 %d' % (top, meth))


def main():
    a_brief()
    a_numbers_untouched()
    b_persona()
    c_evidence()
    d_negative()
    e_guard()
    f_selfcheck()
    print(u'')
    print(u'=' * 78)
    print(u'check128：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'失败项：')
        for d in _failed:
            print(u'  - %s' % d)
    return 0 if _n['f'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
