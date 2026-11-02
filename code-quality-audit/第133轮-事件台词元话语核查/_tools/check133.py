# -*- coding: utf-8 -*-
"""第133轮回归锁：**事件台词链**（`guard_reaction`）装上元话语闸，且不许退化。

## 为什么这轮要单测这条链

第132轮的 `looks_like_meta_leak` 只接在**对话**链（`_clean_ai_reply` 第 0c 道）。
事件台词走另一条链：

    chat_with_ai(..., lean=True) → system = **整份人设**（`main.py` 14171 行：
    「只发 persona，一个字节都不变」）→ guard_reaction(first_sentence(reply, 24))

人设「语气示范」那几行正是泄漏源 ⇒ 两条链**共用同一个人设**，却只有一条装了闸。
这道不对称本身就是漏洞（第128轮的教训同样是"同一道闸只在一条链上生效"）。

## ★★★ 但本轮最重要的发现是一条**否定结果**，别把它读成"闸很有用"

本轮真机采了 **42 条**事件回复（14 个 TIER_AI 事件 × 3 采样）：
`meta_raw` / `meta_first` / `meta_final` **全部 0/42**，平均首句只有 **7.4 字**。
更关键的是第 131 轮那 3 条**真泄漏**——把它们按产品的 `first_sentence(raw, 24)`
截断之后再喂给闸，**3 条一条都命中不了**（`"…我不该"` / `"…先就着"` 被截在半句上）。

⇒ 两条结论，一起登记：
  ① 事件链的 24 字上限**本身就压掉了**这次观测到的泄漏形态（这是事实，不是功劳）；
  ② 所以「把对话链的做法照搬到事件链、对截断后的文本判」**救不了那 3 条**。
     本轮装闸的理由是**结构对称 + 显示窗口**（≤24 字内仍容得下「我不该用亮起来的开头」这样
     的整句自述），不是"修了一个观测到的 bug"。别在报告里把它写成"实测有效"。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 真实语料（本轮 42 条）：0 命中 · 加闸后输出**逐字不变**（回归，不是"效果"）
B 截断效应：那 3 条真泄漏截断后 0/3 命中 —— 钉住"闸能拦什么、不能拦什么"
C 闸的行为：三种形态全判退（**正控制真落进被测分支**）
C4 位置硬约束：剥括号后同一条样本**不再命中** ⇒ 闸必须排在 `strip` 之前（挪了必漏）
D 不误伤：42 条真机输出全放行 + 12 条踩边角的正常短反应全放行
D3 破坏性负控制：把规则表清空 ⇒ C 的三条必须全部失效（判据真依赖它）
E 接线：对话链与事件链调的是**同一个函数**（AST），不是两份实现
F 自检：恒真判据 / 分母 / 无 BOM / 零外部盘

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（直接调产品函数）；
不把方向性结论写成判据（真机数据会变），结论留报告。
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
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
EV133 = os.path.join(ROUND, '_evidence', 'event133.jsonl')
EV131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                     '_evidence', 'live7_131.jsonl')

if PET not in sys.path:
    sys.path.insert(0, PET)
from modules import event_speech as ESR                            # noqa: E402

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


def _rows(p):
    out = []
    with io.open(p, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


GUARD = ESR.guard_reaction
META = ESR.looks_like_meta_leak
STRIP = ESR.strip_action_parentheticals
FIRST = ESR.first_sentence
assert callable(GUARD) and callable(META), '产品里没有这两个函数'

# =============================================== A. 真实语料：42 条
head(u'A. 本轮真机 42 条事件回复：0 命中，且加闸后输出逐字不变')

check(u'A0 证据文件在', os.path.isfile(EV133), EV133)
rows = _rows(EV133)

check(u'A1 分母 ≥ 40 条（少于这个数不许下结论）', len(rows) >= 40,
      u'n=%d' % len(rows))
check(u'A2 采样覆盖 ≥ 12 个不同事件', len({r['kind'] for r in rows}) >= 12,
      u'%d 个' % len({r['kind'] for r in rows}))
check(u'A3 每条都有非空 first（否则"0 命中"可能只是空跑）',
      all((r.get('first') or '').strip() for r in rows),
      u'空 %d 条' % sum(1 for r in rows if not (r.get('first') or '').strip()))

# 0 命中：三个观测位分别判，不用"或"合并（否则某一位失灵看不出来）
check(u'A4 raw 段元话语命中 0 条（这条链压根没观测到该形态）',
      sum(1 for r in rows if META(r.get('raw') or '')) == 0,
      u'%d/%d' % (sum(1 for r in rows if META(r.get('raw') or '')), len(rows)))
check(u'A5 first 段命中 0 条',
      sum(1 for r in rows if META(r.get('first') or '')) == 0,
      u'%d/%d' % (sum(1 for r in rows if META(r.get('first') or '')), len(rows)))
check(u'A6 final 段命中 0 条',
      sum(1 for r in rows if META(r.get('final') or '')) == 0,
      u'%d/%d' % (sum(1 for r in rows if META(r.get('final') or '')), len(rows)))

# ★ 回归判据（不是效果判据）：拿**现在**的 guard_reaction 重算，必须与采证时逐字相同
_recomputed = [(r.get('first') or '', GUARD(r.get('first') or '')) for r in rows]
_diff = [(a, b, r.get('final') or '') for (a, b), r in zip(_recomputed, rows)
         if b != (r.get('final') or '')]
check(u'A7 加闸后这 42 条的输出**逐字不变**（没误伤任何一条，含被别的闸拦的）',
      not _diff, u'差异 %d 条%s' % (len(_diff), ('：%r' % (_diff[:2],)) if _diff else ''))

_mean_chars = sum(len(r.get('first') or '') for r in rows) / max(1, len(rows))
check(u'A8 首句平均 ≤ 12 字（记录"显示窗口有多短"这个事实，供解释泄漏为何少见）',
      _mean_chars <= 12, u'%.1f 字' % _mean_chars)

# =============================================== B. 截断效应
head(u'B. 第131轮那 3 条真泄漏：截到 24 字之后闸还认不认（否定结果）')

live = _rows(EV131)
_leaks = [r for r in live if META(r.get('reply') or '')]
check(u'B1 第131轮 42 条里真泄漏恰 3 条（分母守恒）',
      len(live) == 42 and len(_leaks) == 3,
      u'n_live=%d n_leaks=%d' % (len(live), len(_leaks)))

_cut = [(r, FIRST(r['reply'], ESR.EVENT_MAX_CHARS)) for r in _leaks]
check(u'B2 三条都被真的截短了（不是"原文就够短 ⇒ 结论无意义"）',
      all(f != (r['reply'] or '').strip() for r, f in _cut),
      u'未截短的 %d 条' % sum(1 for r, f in _cut
                          if f == (r['reply'] or '').strip()))
check(u'B3 截断之后这 3 条**一条都不命中**（24 字上限压掉了这次观测到的形态）',
      sum(1 for _r, f in _cut if META(f)) == 0,
      u'命中 %d/3' % sum(1 for _r, f in _cut if META(f)))
check(u'B4 所以"照搬对话链做法（对截断后文本判）"救不了这 3 条 —— '
      u'这是位置问题，不是闸的问题',
      all(not META(f) for _r, f in _cut))

# =============================================== C. 闸的行为（正控制）
head(u'C. 三种形态必须判退，且位置不能挪（挪了必漏）')

# 形态①：规则改成第一人称自述（真泄漏原文的首句形态）
S1 = u'我不该用亮起来的开头，先就着那件事问一句。'
# 形态②：直接引用模板
S2 = u'先就着你说的那件事问一句："这么说，你是觉得……"'
# 形态③：括注自评 —— **嵌在一句正常台词后面**，不是整句只有括号
S3 = u'嗯…（这里说的是你自己的事，而不是直接给出建议）'

check(u'C1 形态①（我不该 + 说话方式）判退', GUARD(S1) == '', repr(GUARD(S1)))
check(u'C2 形态②（问一句 + 冒号引模板）判退', GUARD(S2) == '', repr(GUARD(S2)))
check(u'C3 形态③（句中括注自评）判退', GUARD(S3) == '', repr(GUARD(S3)))

# ★ 位置：本条原本写的是"剥括号后就不命中 ⇒ 闸必须排在 strip 之前"。
#   **数据把它否掉了**：strip 只认动作/描述性旁白/引号台词，对「（这里说的是你自己的事…）」
#   这种**合规说明**根本不删（diag133.py 第 1 节：stripped == 原文，删了=False）。
#   ⇒ 对这一形态，两种顺序等价。判据改成"登记事实 + 两处都拦"，不再宣称硬约束。
_stripped = STRIP(S3)
check(u'C4 位置对形态③**不敏感**（strip 不删这种括注 ⇒ 剥前剥后都命中），'
      u'产品仍排在剥前：不依赖 strip 的实现细节',
      META(S3) and META(_stripped) and _stripped.strip() != '',
      u'strip 是否删过 = %s' % (_stripped != S3))
check(u'C4b 剥前剥后同判（不是"某一边碰巧命中"）',
      META(S3) == META(_stripped) is True)

check(u'C5 另外两道老闸还在（出戏 / 客服腔，不许被这次改动带塌）',
      GUARD(u'我只是一个程序，没有触觉。') == ''
      and GUARD(u'希望你今天过得愉快，还有什么可以帮你的吗？') == '',
      u'出戏=%r' % (GUARD(u'我只是一个程序，没有触觉。'),))
check(u'C6 空输入与纯空白返回空串', GUARD('') == '' and GUARD(u'   ') == '')

# =============================================== D. 不误伤
head(u'D. 不误伤：真机输出 + 踩边角的正常短反应')

_hit = [r.get('first') for r in rows
        if GUARD(r.get('first') or '') != (r.get('first') or '')]
check(u'D1 42 条真机 first 全部原样返回（0 条被新闸误判）', not _hit, repr(_hit[:3]))

OK_LINES = [
    u'谢谢你。', u'好痒。', u'我有点累了。', u'嗯，晚安。',
    u'我不该提这个的。',            # 「我不该」但后面不是说话方式 ⇒ 不许误判
    u'问一句也行吗？',              # 「问一句」但不带冒号 ⇒ 不许误判
    u'我不该说得那么急。',          # 「我不该 + 说」，仍不是"开头/语气" ⇒ 不许误判
    u'嗯，这里有点暗。',            # 含「这里」但不是「这里说」⇒ 不许误判
    u'我不是这个意思。',            # 不许因为写了「意思」就判
    u'有点辛苦了呢。', u'那边面包香气诱人。', u'好的，我躺下了。',
]
_bad = [x for x in OK_LINES if GUARD(x) != x]
check(u'D2 12 条踩边角的正常短反应全部原样放行', not _bad, repr(_bad))
check(u'D2b 负样本本身非空（不是拿空表算"全放行"）',
      len(OK_LINES) == 12 and all(x.strip() for x in OK_LINES))
# ★ 分工登记：句首括号的短句是被**老闸** look_like_narration 拦的，不是新闸。
#   第一版把 '（这里有点暗…）' 放进上面的负样本表 ⇒ 报红；红的是样本选错（产品没错）。
_lead_paren = u'（这里有点暗，我看不太清。）'
check(u'D2c 句首括号仍由老闸 `looks_like_narration` 拦（新闸不抢这道活）',
      GUARD(_lead_paren) == '' and ESR.looks_like_narration(_lead_paren)
      and not META(_lead_paren), repr(GUARD(_lead_paren)))

# 破坏性负控制：把规则表清空 ⇒ C 那三条必须**全部**失效（一条都不再判退）
_orig = ESR._META_LEAK_RES
try:
    ESR._META_LEAK_RES = ()
    _still = [x for x in (S1, S2, S3) if GUARD(x) == '']
finally:
    ESR._META_LEAK_RES = _orig
check(u'D3 破坏性负控制：清空规则表后 C1~C3 三条**全部**失效（仍判退应为 0）',
      len(_still) == 0, u'仍判退 %d/3' % len(_still))
check(u'D4 规则表已原样恢复（条数一致）', len(ESR._META_LEAK_RES) == len(_orig),
      u'%d → %d' % (len(_orig), len(ESR._META_LEAK_RES)))

# =============================================== E. 接线：同一个函数，两条链
head(u'E. 接线（AST）：对话链与事件链调的是**同一个**函数')

_es_src = _read(ES_PY)
_es_tree = ast.parse(_es_src)


def _func(tree, name):
    """**递归**找函数定义 —— `_clean_ai_reply` 是类方法，只看 `tree.body` 会漏（本轮踩过）。"""
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


_g = _func(_es_tree, 'guard_reaction')
check(u'E0 产品里真有 guard_reaction', _g is not None)
_calls = []
if _g is not None:
    for n in ast.walk(_g):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else '')
            if nm:
                _calls.append(nm)
check(u'E1 guard_reaction 里调用了 looks_like_meta_leak',
      'looks_like_meta_leak' in _calls, u'实际调用=%r' % (_calls,))
check(u'E1b 另外两道老闸也还在（没被替换掉）',
      'looks_out_of_character' in _calls and 'looks_like_assistant_speak' in _calls)

_main_tree = ast.parse(_read(MAIN_PY))
_imported = set()
for n in ast.walk(_main_tree):
    if isinstance(n, ast.ImportFrom) and (n.module or '').endswith('event_speech'):
        _imported |= {a.name for a in n.names}
check(u'E2 main.py 从 modules.event_speech **同一个**模块导入它（不是第二份实现）',
      'looks_like_meta_leak' in _imported, u'导入=%r' % (sorted(_imported),))

_clean = _func(_main_tree, '_clean_ai_reply')
_clean_calls = []
if _clean is not None:
    for n in ast.walk(_clean):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else '')
            if nm:
                _clean_calls.append(nm)
check(u'E3 对话链那道闸没退线（`_clean_ai_reply` 仍调用它）',
      'looks_like_meta_leak' in _clean_calls,
      # ★ 第140轮：extra 原来打"共 %d 个调用"—— 那是**时相量**
      #   （`_clean_ai_reply` 里任何一处新增调用都会让它变），判定一个字没变却报 DIFF，
      #   正是第138轮那条口径要禁的形状。改成只回显三闸在不在位（布尔，不随版本漂）。
      u'三闸在位=%r' % [(g in _clean_calls) for g in
                        ('looks_out_of_character', 'looks_like_assistant_speak',
                         'looks_like_meta_leak')])

_pkgs = []
for n in _es_tree.body:
    if isinstance(n, ast.Import):
        _pkgs += [a.name.split('.')[0] for a in n.names]
    elif isinstance(n, ast.ImportFrom) and n.module:
        _pkgs.append(n.module.split('.')[0])
_FORBIDDEN = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PyQt4',
              'main', 'modules', 'core', 'animation', 'npc_life'}
check(u'E4 `event_speech` 仍不 import 项目内模块、不 import Qt',
      not (set(_pkgs) & _FORBIDDEN), u'实际 import=%r' % (sorted(set(_pkgs)),))

# =============================================== F. 自检
head(u'F. 本套件自检')

_const_true = []
_self_tree = ast.parse(_read(os.path.abspath(__file__)))
for n in ast.walk(_self_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                _const_true.append(getattr(n, 'lineno', -1))
check(u'F1 本套件没有恒真判据（`check(..., True)` 一个都不许有）',
      not _const_true, u'%d 处' % len(_const_true))

with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'F2 本脚本无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'F3 证据文件都在仓库内（零外部盘）',
      all(os.path.abspath(p).startswith(ROOT + os.sep) for p in (EV133, EV131)),
      ROOT)

print(u'')
print(u'=' * 78)
print(u'check133：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
