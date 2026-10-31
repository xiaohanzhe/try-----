# -*- coding: utf-8 -*-
u"""第128轮复检（`core-file-recheck` 套路）：改过核心文件后逐项打 PASS/FAIL 并落盘。

覆盖的改动面（9 个 .py + 1 个 md + 1 份证据目录）
------------------------------------------------
产品：
1. `ralsei_pet/assets/ralsei_persona.md`  ——「我的口癖」节删配额/许可、语气节改示范
2. `ralsei_pet/modules/relationship.py`    —— `nervous_brief` distrust/guarded 两档文案
3. `ralsei_pet/modules/event_speech.py`    —— 新增 `strip_head_hesitation`
4. `ralsei_pet/src/main.py`                —— 0d 步 + 流式清洗 + import
锁/探针：
5. `第128轮-结巴率收敛/_tools/check128.py`（新锁，54 条）
6. `第128轮-结巴率收敛/_tools/gen_ab128.py`（证据生成器，手工跑）
7. `regress/run_all.py`（登记 check128）
8. `人味改造-2026-09-18/verify_persona_chat.py`（C7/C18/C18b/D4 期望值）
9. `人味改造-2026-09-18/verify_s8_stream.py`（C10d 期望值）
10. `人味改造-2026-09-18/verify_persona_worldview.py`（`_apply_gates` 补 0d）
11. `第128轮-结巴率收敛/_evidence/report128.md`

七段：① 语法 ② 结构 ③ 编码行尾 ④ 恒真判据 + 正/负控制 ⑤ 逐令牌回验
      ⑥ 报告对账 ⑦ 干净度
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
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
REL_PY = os.path.join(PET, 'modules', 'relationship.py')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
CHK = os.path.join(HERE, 'check128.py')
GEN = os.path.join(HERE, 'gen_ab128.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
VP_CHAT = os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                       'verify_persona_chat.py')
VP_WORLD = os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                        'verify_persona_worldview.py')
VP_S8 = os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                     'verify_s8_stream.py')
REPORT = os.path.join(ROUND, '_evidence', 'report128.md')
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')

_n = {'p': 0, 'f': 0}
_failed = []


def chk(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def sec(t):
    print(u'')
    print(u'=' * 78)
    print(t)
    print(u'=' * 78)


def rb(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def txt(p):
    return rb(p).decode('utf-8')


# =============================================== ① 语法（不产 .pyc）
sec(u'① 语法：9 个 .py 全部 `ast.parse` 通过（**不**产 .pyc）')

PYS = [REL_PY, ES_PY, MAIN_PY, CHK, GEN, RUNALL, VP_CHAT, VP_WORLD, VP_S8]
_bad = []
for p in PYS:
    try:
        ast.parse(txt(p))
    except SyntaxError as e:
        _bad.append((os.path.basename(p), str(e)))
chk(u'①-1 九个脚本语法全通过', not _bad, u'%s' % (_bad,))
chk(u'①-2 分母非空（真的是 9 个文件）', len(PYS) == 9, u'n=%d' % len(PYS))
_dup = len(set(os.path.abspath(p) for p in PYS)) == len(PYS)
chk(u'①-3 清单里没有重复路径（否则"9 个"是刷的）', _dup)

# =============================================== ② 结构
sec(u'② 结构：0d 步的位置、两处接线、单一真源、锁的登记')

main_src = txt(MAIN_PY)
es_src = txt(ES_PY)

chk(u'②-1 event_speech 里定义了 strip_head_hesitation',
    u'def strip_head_hesitation(text):' in es_src)
chk(u'②-2 main.py 从 event_speech import 了它',
    u'strip_head_hesitation,' in main_src)

# 0d 必须排在 0c（出戏/客服腔）**之前**：用行号比，不用文本顺序猜
i_0d = main_src.find(u't = strip_head_hesitation(t)')
i_0c = main_src.find(u'if looks_out_of_character(t) or looks_like_assistant_speak(t):')
chk(u'②-3 收尾层 0d 在 0c 之前（先削口气再判出戏，否则 ^ 起锚的正则被挡住）',
    -1 < i_0d < i_0c, u'0d@%d 0c@%d' % (i_0d, i_0c))

# 两处调用：收尾 `_clean_ai_reply` 与流式 `_sanitize_partial_reply`
n_call = main_src.count(u't = strip_head_hesitation(t)')
chk(u'②-4 两处都调（收尾护栏 + 流式清洗），少一处流式就会"打出来再擦掉"',
    n_call == 2, u'出现 %d 次' % n_call)
i_san = main_src.find(u'def _sanitize_partial_reply')
i_clean = main_src.find(u'def _clean_ai_reply')
chk(u'②-5 两次调用分属这两个函数（不是都堆在一处）',
    -1 < i_san < i_clean
    and i_san < main_src.find(u't = strip_head_hesitation(t)') < i_clean
    and main_src.find(u't = strip_head_hesitation(t)') < i_clean + 4000
    and main_src.rfind(u't = strip_head_hesitation(t)') > i_clean,
    u'san@%d clean@%d' % (i_san, i_clean))

# 削完必须**重跑**实义字符闸（`诶？！` → `！` 这种）
chk(u'②-6 削完重跑一次"实义字符"闸（否则孤零零一个问号会被当台词显示）',
    main_src.find(u"if not t or not re.search(r'[0-9A-Za-z\\u4e00-\\u9fff]', t):")
    > i_0d)

# 单一真源：函数只在 event_speech 里定义
defs = []
for dirpath, _d, files in os.walk(PET):
    if '__pycache__' in dirpath:
        continue
    for fn in files:
        if fn.endswith('.py'):
            p = os.path.join(dirpath, fn)
            if u'def strip_head_hesitation(' in txt(p):
                defs.append(os.path.relpath(p, PET))
chk(u'②-7 strip_head_hesitation 只有一份实现', defs == [os.path.join('modules', 'event_speech.py')],
    u'%r' % (defs,))

# 探针 `_apply_gates` 必须补上 0d，否则 W2 会红
chk(u'②-8 `verify_persona_worldview._apply_gates` 已补 0d',
    u'_STRIP_HES(t)' in txt(VP_WORLD))

runall_src = txt(RUNALL)
chk(u'②-9 run_all.py 已登记 check128',
    u"'id': 'check128'," in runall_src and u'第128轮-结巴率收敛' in runall_src)
chk(u'②-10 登记的是真路径（脚本文件存在）',
    os.path.exists(os.path.join(ROOT, 'code-quality-audit', '第128轮-结巴率收敛',
                                '_tools', 'check128.py')))

# =============================================== ③ 编码 / 行尾
sec(u'③ 编码与行尾：4 个产品文件保持各自原有行尾，无 BOM、无 U+FFFD')


def eol_kind(b):
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n')
    if crlf == 0:
        return 'LF'
    if crlf == lf:
        return 'CRLF'
    return 'MIXED'


WANT = ((PERSONA, 'LF'), (REL_PY, 'LF'), (MAIN_PY, 'CRLF'), (ES_PY, 'CRLF'))
for p, want in WANT:
    b = rb(p)
    k = eol_kind(b)
    chk(u'③-%s 行尾仍是 %s（不混行尾）' % (os.path.basename(p), want), k == want, u'实测 %s' % k)
    chk(u'③-%s 无 BOM / 无 U+FFFD' % os.path.basename(p),
        (not b.startswith(b'\xef\xbb\xbf')) and (b'\xef\xbf\xbd' not in b))

# 体积闸：persona 没被砍瘦、也没超历史上限
pb = len(rb(PERSONA))
chk(u'③-5 persona 体积在 [9000, 10240] 字节（改前 9991 → 改后 %d）' % pb,
    9000 <= pb <= 10240, u'%d' % pb)

for p in (CHK, GEN, RUNALL, REPORT, os.path.abspath(__file__)):
    b = rb(p)
    chk(u'③-%s 无 BOM / 无 U+FFFD' % os.path.basename(p),
        (not b.startswith(b'\xef\xbb\xbf')) and (b'\xef\xbf\xbd' not in b))

# =============================================== ④ 恒真判据 + 正/负控制
sec(u'④ 判据体检：无恒真、有正控制、负控制真的落进被测分支')

chk_src = txt(CHK)
tree = ast.parse(chk_src)
const_true = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id == 'check' and len(node.args) >= 2:
            c = node.args[1]
            if isinstance(c, ast.Constant) and c.value is True:
                const_true.append(node.lineno)
chk(u'④-1 check128 里没有 `check(..., True)`', not const_true, u'%r' % (const_true,))

n_check = len(re.findall(u'(?m)^\\s+check\\(u\'', chk_src)) + len(
    re.findall(u'(?m)^\\s+check\\(u"', chk_src))
chk(u'④-2 check128 判据数 ≥ 40（分母非空）', n_check >= 40, u'n=%d' % n_check)

# 正控制：反例清单必须被 E3 真断言（不是空集）
chk(u'④-3 正控制：E3 的反例清单非空且逐条断言', u'keep = [' in chk_src
    and u'if ES.strip_head_hesitation(k) != k' in chk_src)

# 负控制：把护栏换成"恒等函数" ⇒ E1 判据必须报红（**内存里算，不改产品文件**）
sys.path.insert(0, PET)
from modules import event_speech as ES      # noqa: E402
from modules import relationship as R       # noqa: E402
rows = []
for fn in ('base.jsonl', 'pnew_bold.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl'):
    p = os.path.join(RAW, fn)
    if os.path.exists(p):
        for line in io.open(p, encoding='utf-8'):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
HES = u'嗯诶哦呃唔'
OPEN = re.compile(u'^[%s]' % HES)
#: 带停顿的"真卡壳"（与 check128 `HES_PAUSE_RE` 同口径，但**在这里独立重写一遍** ——
#: 不 import 判据文件，否则同一处写错会两边一起绿，那就不叫独立重算了）
HES_PAUSE = re.compile(u'^[%s]{1,3}\\s*(?:…+|\\.{3,}|—+|－+|~+|？|\\?|！|!)' % HES)
left_real = [r for r in rows if OPEN.match(ES.strip_head_hesitation(r['reply'].strip()) or '')]
left_null = [r for r in rows if OPEN.match(r['reply'].strip())]
chk(u'④-4 负控制：护栏换成恒等函数后，同一判据报红（说明它真的在判东西）',
    (not left_real) and len(left_null) > 0,
    u'真护栏残留 %d / 恒等函数残留 %d' % (len(left_real), len(left_null)))
chk(u'④-5 A/B 先断言不同：两种实现的结果集合不同（否则判据是空的）',
    len(left_real) != len(left_null))

# =============================================== ⑤ 逐令牌回验
sec(u'⑤ 逐令牌回验：报告里点名的每个数字/名字，逐个回原文件 `in` 一次')

rep = txt(REPORT)
TOKENS = [
    (u'52.0%', rep),
    (u'26/50', rep),
    (u'9,991', rep),
    (u'9,992', rep),
    (u'strip_head_hesitation', rep),
    (u'0d', rep),
    (u'前缀安全', rep),
    (u'2.16%', rep),
    (u'35.69%', rep),
    (u'3,696', rep),
    # ---- 128 续（用户「不能为 0%」之后新增的锚）----
    (u'12.0%', rep),
    (u'17.0%', rep),
    (u'pnew_relax', rep),
    (u'HES_ALLOW_GAP', rep),
    (u'_hes_gap', rep),
    (u'不能为 0%', rep),
    (u'2.0%', rep),
    (u'12.1%', rep),
]
miss_tok = [t for t, src in TOKENS if t not in src]
chk(u'⑤-1 报告里的关键令牌都在（%d 个）' % len(TOKENS), not miss_tok,
    u'' if not miss_tok else u'缺 %r' % (miss_tok,))

# 反向：报告点名的文件真的存在（★ 首跑这条报红是**我的令牌写错了**：
#   报告里写的是 `event_speech.strip_head_hesitation` / `_evidence/raw/`，
#   不是 `event_speech.py` / `ab128.json`。判据要贴着报告的实际写法。）
FILES_IN_REPORT = ['ralsei_persona.md', 'relationship.py', 'event_speech',
                   'main.py', 'check128.py', '_evidence/raw', 'ab128.json']
miss_f = [f for f in FILES_IN_REPORT if f not in rep]
chk(u'⑤-2 报告点名的文件都在正文里提过', not miss_f, u'' if not miss_f else u'缺 %r' % (miss_f,))

# 产品侧令牌：新文案的关键句必须在源码里
rel_src = txt(REL_PY)
chk(u'⑤-3 新 distrust 文案的锚句在 relationship.py 里（128 续改过，锚句跟着换）',
    u'别把紧张演成口头禅' in rel_src and u'多数句子是顺的' in rel_src)
# ★ 首跑这条报红也是判据错：改前的文案被**逐字引用在 docstring 里**当教训，
#   所以"全文搜不到旧句"永远为假。真正该守的是**运行时产出的文案**里没有配额句
#   —— 断行为，不断赋值（这正是本项目反复踩的那条）。
_bad_brief = []
for _t, _e in ((0.0, 'chat'), (0.0, 'harsh'), (0.40, 'chat'), (0.95, 'comfort')):
    _b = R.nervous_brief(_t, _e)
    for _tok in (u'最多', u'会重复一两个字', u'会突然停住', u'最多一处'):
        if _tok in _b:
            _bad_brief.append((_t, _e, _tok))
chk(u'⑤-4 运行时文案里旧配额句/示范已消失（断行为，不搜源码注释）',
    not _bad_brief, u'' if not _bad_brief else u'%r' % (_bad_brief[:4],))
md = txt(PERSONA)
# ★ 128 续：人设那句已改成**中性**（凭许可塞进人设会撞 `verify_persona_chat K3` 的
#   10KB 体积闸：实测 10,067 B 直接红）。所以这里不再要求"新禁令在位"，
#   而是判三件事：旧许可没了、旧硬禁令没了、中性句在位，且 brief 侧的许可没漏进人设。
_old_perm = [t for t in (u'开口有时会带个语气词', u'最多沾一两处',
                         u'起音含混', u'不垫') if t in md]
chk(u'⑤-5 人设起头纪律已是**中性**：旧许可/旧禁令都消失、中性句在位、许可没漏进人设',
    (not _old_perm) and (u'开口直接说那件事' in md) and (u'顿一顿' not in md),
    u'' if not _old_perm else u'残留 %r' % (_old_perm,))
chk(u'⑤-6 人设原有硬口径"不是每句都结巴"仍在', u'不是每句都结巴' in md)

# =============================================== ⑥ 报告对账
sec(u'⑥ 报告对账：报告表格里写的数字 == 从 200 条原文**独立重算**的值')

K1 = re.compile(r'([\u4e00-\u9fa5])(?:…+|\.{2,}|—+|－+|~+)\1')
K2 = re.compile(r'([\u4e00-\u9fa5])\1')
HOT = u'我你他她它不就是这就那嗯呃唉哦'
OKW = set(u'慢慢 轻轻 悄悄 好好 多多 常常 刚刚 渐渐 早早 远远 深深 紧紧 静静 谢谢'.split())
OPEN_EXCL = re.compile(u'^\\s*(?:哎呀|哎|啊|唉)')
ELL = re.compile(u'…|\\.{3,}')       # ★ 与报告表头括注同一口径：`…` 或连续三点以上


def recount(rows_):
    n = hp = he = st = el = 0
    for r in rows_:
        t = (r.get('reply') or '').strip()
        if not t:
            continue
        n += 1
        if OPEN.match(t):
            hp += 1
        if OPEN_EXCL.match(t):
            he += 1
        if ELL.search(t):
            el += 1
        bad = bool(K1.search(t))
        for m in K2.finditer(t):
            if m.group(1) in HOT and (m.group(1) * 2) not in OKW:
                bad = True
        if bad:
            st += 1
    return n, hp, he, st, el


# ★ 这条判据的"独立"在哪：左边是**报告正文里写的数字**（人手写的那张表），
#   右边是**从 raw 原文重算**的数字。两边都不是我这次写判据时随口给的常量 ——
#   上一版把 26/20/1 硬编码成期望值，那属于"三份拷贝互相印证"，一起错就一起绿。
_ROW_RE = re.compile(
    u'^\\|\\s*`([a-z0-9_]+)`\\s*\\|([^|]*)\\|([^|]*)\\|'
    u'\\s*\\*\\*(\\d+)/50 = ([\\d.]+)%\\*\\*\\s*\\|\\s*(\\d+)\\s*\\|\\s*(\\d+)\\s*\\|\\s*(\\d+)\\s*\\|\\s*$',
    re.M)
_tbl = {m.group(1): m for m in _ROW_RE.finditer(rep)}
chk(u'⑥-0 报告 A/B 表里四臂齐全（base / pnew_bold / pnew_bnew / pnew_bnew2）',
    sorted(_tbl) == ['base', 'pnew_bnew', 'pnew_bnew2', 'pnew_bold'],
    u'解析到 %r' % (sorted(_tbl),))

for fn in ('base.jsonl', 'pnew_bold.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl'):
    arm = fn[:-6]
    p = os.path.join(RAW, fn)
    rr = [json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()]
    n, hp, he, st, el = recount(rr)
    m = _tbl.get(arm)
    chk(u'⑥-%s 原文 %d 条（报告按 50 条计）' % (arm, n), n == 50, u'实测 %d' % n)
    if m is None:
        chk(u'⑥-%s 报告表里能找到这一行' % arm, False)
        continue
    mac_hp, mac_pct = int(m.group(4)), float(m.group(5))
    chk(u'⑥-%s 句首迟疑：报告 %d（%s%%） == 重算 %d' % (arm, mac_hp, m.group(5), hp),
        mac_hp == hp and abs(100.0 * mac_hp / 50 - mac_pct) < 0.051,
        u'实测 %d/50 = %.2f%%' % (hp, 100.0 * hp / n))
    chk(u'⑥-%s 感叹词起头：报告 %s == 重算 %d' % (arm, m.group(6), he),
        int(m.group(6)) == he, u'实测 %d' % he)
    chk(u'⑥-%s 真结巴：报告 %s == 重算 %d（这一列必须是 0）' % (arm, m.group(7), st),
        int(m.group(7)) == st and st == 0, u'实测 %d' % st)
    chk(u'⑥-%s 含省略号：报告 %s == 重算 %d' % (arm, m.group(8), el),
        int(m.group(8)) == el, u'实测 %d' % el)

# 百分比要能从条数推出来（防"数字写好看"）
_bad_pct = []
for arm, m in _tbl.items():
    if abs(100.0 * int(m.group(4)) / 50 - float(m.group(5))) >= 0.051:
        _bad_pct.append((arm, m.group(4), m.group(5)))
chk(u'⑥-7 每行"N/50 = P%"自洽', not _bad_pct, u'' if not _bad_pct else u'%r' % (_bad_pct,))

# =============================================== ⑦ 干净度
sec(u'⑦ 干净度：目录构成、不依赖临时区/外部盘、工作区无杂物')

tools = sorted(f for f in os.listdir(HERE) if f.endswith('.py'))
chk(u'⑦-1 `_tools/` 恰好 3 个脚本（check / gen / recheck）', len(tools) == 3, u'%r' % (tools,))
ev_items = sorted(os.listdir(EV))
chk(u'⑦-2 `_evidence/` 只有 report128.md + ab128.json + raw/',
    set(ev_items) == {'report128.md', 'ab128.json', 'raw'}, u'%r' % (ev_items,))
raw_items = sorted(os.listdir(RAW))
# 4 个 A/B 臂（各 50）+ 1 个「不能为 0%」之后的自然产出臂（100 条）
chk(u'⑦-3 `_evidence/raw/` 恰好五份原文（四臂 + relax 100 条）',
    raw_items == ['base.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl',
                  'pnew_bold.jsonl', 'pnew_relax.jsonl'],
    u'%r' % (raw_items,))

# ★ 回归不许依赖临时区：check128 / recheck128 里不许出现外部盘路径。
#   注意：**判据自己不能把那个字面量写进来**（首跑就是这么红的 —— 判据里写了
#   待搜的盘符前缀，于是自己命中自己）。所以路径前缀在这里**拼**出来，
#   连注释里也不写那个字面量。
_DRIVE = u'D' + u':'
_bad_path = []
for p in (CHK, os.path.abspath(__file__)):
    s = txt(p)
    for _pat in (_DRIVE + u'\\', _DRIVE + u'/'):
        if _pat in s:
            _bad_path.append((os.path.basename(p), _pat))
chk(u'⑦-4..5 check128 / recheck128 不含外部盘路径（回归可在任意机器上跑）',
    not _bad_path, u'' if not _bad_path else u'%r' % (_bad_path,))
chk(u'⑦-6 证据生成器如实标注了临时区来源（它是手工跑的，不进 G2）',
    (u'_tmp128' in txt(GEN)) and (u'临时区' in txt(GEN)))

# 报告不许出现"绝对路径的临时目录"
chk(u'⑦-7 报告里没有临时区路径', u'_tmp' not in rep)

# =============================================== ⑧ 第 5 臂对账（不能为 0% 之后）
sec(u'⑧ 第 5 臂对账：报告里的 17/100 与 12/100 == 从原文独立重算')

_rp = os.path.join(RAW, 'pnew_relax.jsonl')
chk(u'⑧-1 第 5 臂原文在（100 条）', os.path.exists(_rp))
if os.path.exists(_rp):
    _rows = [json.loads(l) for l in io.open(_rp, encoding='utf-8') if l.strip()]
    _n2 = _hp2 = _pp2 = 0
    for r in _rows:
        t = (r.get('reply') or '').strip()
        if not t:
            continue
        _n2 += 1
        if OPEN.match(t):
            _hp2 += 1
        if HES_PAUSE.match(t):
            _pp2 += 1
    chk(u'⑧-2 第 5 臂 n=100', _n2 == 100, u'n=%d' % _n2)
    # 报告写的是 "17（17.0%）" 与 "12（12.0%）" —— 从原文重算必须对得上。
    # ★ 首版判据绑死了列结构（`| 臂 | 说明 | N | 值 | 值 |`），报告后来多了一列
    #   "中性人设 + brief 条件式许可"，正则就整个不匹配了 —— 这是判据过窄，
    #   不是报告错。改成**宽松解析**：先找到臂名那一行，再取该行里所有"加粗的 N（P%）"。
    _row = u''
    for _line in rep.splitlines():
        if u'`pnew_relax`' in _line and _line.lstrip().startswith(u'|'):
            _row = _line
            break
    chk(u'⑧-3 报告表格里能找到第 5 臂那一行', bool(_row))
    _pairs = re.findall(u'\\*\\*(\\d+)（([\\d.]+)%）\\*\\*', _row)
    chk(u'⑧-3b 该行里恰有两个加粗的「N（P%）」列（不绑死列号）',
        len(_pairs) == 2, u'%r' % (_pairs,))
    if len(_pairs) == 2:
        _hp_rep, _hp_pct = int(_pairs[0][0]), float(_pairs[0][1])
        _pp_rep, _pp_pct = int(_pairs[1][0]), float(_pairs[1][1])
        chk(u'⑧-4 句首迟疑：报告 %d == 重算 %d' % (_hp_rep, _hp2),
            _hp_rep == _hp2, u'实测 %d/%d' % (_hp2, _n2))
        chk(u'⑧-5 带停顿卡壳：报告 %d == 重算 %d（这一条是"不能为 0%%"的正面证据）'
            % (_pp_rep, _pp2),
            _pp_rep == _pp2, u'实测 %d/%d' % (_pp2, _n2))
        # ★ 加这条的理由：条数对了、百分比还是老数，是"改了半截"最常见的形状
        #   （本项目 124 轮就吃过"两个数互证、其实一起错"的亏）。
        chk(u'⑧-5b 百分比列与条数自洽（%d/100 → %.1f%%）'
            % (_pp2, 100.0 * _pp2 / _n2),
            abs(_pp_pct - 100.0 * _pp2 / _n2) < 0.05, u'报告写 %.1f%%' % _pp_pct)
        chk(u'⑧-6 且重算值满足 >0 与 ≤20%（既是"不为 0"又不是回潮）',
            0 < _pp2 <= 20, u'%d/%d' % (_pp2, _n2))
    # 节流阀：按产品源码里的阈值模拟，可见必须正好落在 1~2 条（= 1%~2%）
    _msrc = txt(MAIN_PY)
    _m = re.search(u'(?m)^\\s+HES_ALLOW_GAP = (\\d+)\\s*$', _msrc)
    chk(u'⑧-7 产品里 HES_ALLOW_GAP 可读（AST 级别的锚，不是注释里的数字）', bool(_m))
    if _m:
        _gap2 = int(_m.group(1))
        _g, _vis = _gap2, 0
        for r in _rows:
            t = (r.get('reply') or '').strip()
            if not t:
                continue
            if _g >= _gap2 and HES_PAUSE.match(t):
                _vis += 1
                _g = 0
            else:
                _g += 1
        chk(u'⑧-8 节流阀模拟：可见 ≥1 条（不为 0）', _vis >= 1, u'%d/%d' % (_vis, _n2))
        chk(u'⑧-9 节流阀模拟：可见 ≤2 条（≤2%）', _vis <= 2, u'%d/%d' % (_vis, _n2))

print(u'')
print(u'=' * 78)
print(u'recheck128：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
