# -*- coding: utf-8 -*-
"""第138轮回归锁：**判据的输出里不许含"时相量"**（行号 / 文件体积 / 字面量出现次数）。

## 病是什么

`run_all.py` 的判据是「输出逐行比对」⇒ 一条判据只要把**随版本漂移的绝对数**打进 extra，
它就会在**判定完全没变**的情况下报 DIFF，逼人逐个归因。实测代价：

| 判据 | 一改注释就变的东西 | 真语义 |
|---|---|---|
| `check129 D5` | `main=747019`（字节数） | 越过 100KB 阈值（防"文件没读到"） |
| `check132 D3/D4` | `[(15187, [...])]` / `行号=[15187]` | 三道闸在**同一个 if** 里 |
| `check134 B1c2` | `原文出现 19 次`（`'ralsei'` 计数） | 变异后 B1c 必须 False |
| `check135 F1` | `第 [12438] 行` | `first_sentence(...)` 被调用 1 处 |
| `check135 G4` | `'。！？!?/n…'`（常量全文） | `_SENTENCE_ENDS` 含句号 |
| `check137 D1~D3` | `[14234]` / `chat [14229] vs [14234]` | 处数 = 1、调用排在 prompt 之后 |

第137轮之内**咬了两次**（改代码一次、改注释一次），一共 5 条全绿 DIFF。
第129/132/135 轮也各咬过一次 —— 累计 8 次，每次都要人工确认"这不是行为变化"。

## 本轮怎么改

**不改判定，只改 extra**：语义是处数/顺序/越阈值，就只回显处数/布尔/`n/m`。
判据的**鉴别力一点没降**（下面是 B/C 两段要证明的）。

## 本套件守什么

A 扫描：全部 `_tools/*.py` 里的 `check(...)` / `ok(...)`，
  extra 位置**不许**出现 `.lineno`、**不许**出现 `len(_read(...))` 这类体积表达式
B 改写到位：上面 6 条判据的**新形状**逐个在位（旧形状不得回潮）
C 正控制：拿一段**旧写法**的假源码喂 A 的检测函数，必须抓到（否则 A 是空跑）
D 分母闸：扫到的文件数 / 检出的 check 调用数都必须够大（防空集恒真）
E 鉴别力自证：把 B 段的判据用"改坏的数据"再跑一遍，必须判红
F 自检：无恒真判据 / 零外部盘 / 无 BOM
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
AUDIT = os.path.join(ROOT, 'code-quality-audit')
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


def extra_of(call):
    """取出一次 `check`/`ok` 调用的**输出位**实参。

    ★★★ 这里有个坑，实测过：全仓 `check` 的签名有 **24 种**、`ok` 有 **16 种**
    （`desc, cond, detail` / `name, ok, detail` / `cond, msg` / `tid, title, cond, detail`
    / `m` / `msg` …）。**不能靠签名猜位置** —— 第一版对 `ok` 一律取 `args[1]`，
    于是 `check107 E8b`（`ok(name, cond, detail)`）的条件位 `_pm_init.lineno != _rp_init.lineno`
    被判成"行号回显"，那是**误报**：它在判两个函数不同行，detail 只打了布尔。

    实测出来的规则：**输出位 = 第 3 个位置实参（下标 2）**；若还有第 4 个（下标 3），
    那只会出现在 `tid, title, cond, detail` 这一族，也是输出位。
    两参形态（`cond, msg` / `desc, cond`）取不到输出位 ⇒ **本轮不查，登记为已知盲区**
    （它们都是 `smoke_*` / `probe_*`，不进 `SUITES`，不产生基线 DIFF）。
    """
    out = []
    if len(call.args) >= 3:
        out.append(call.args[2])
    if len(call.args) >= 4:
        out.append(call.args[3])
    return out


def _is_check(call):
    """只认 `check(...)` / `ok(...)` —— 不加这一层，任何 3 参调用都会被当判据。"""
    name = getattr(call.func, 'id', '') or getattr(call.func, 'attr', '')
    return name in ('check', 'ok')


def _prints_lineno(e):
    """这个**直接**被输出出去的表达式，会不会把行号印出来？

    ★★★ 第一版只看"输出位子树里有没有 `.lineno`"，于是 `check107 E8b` 被误判：
       它写的是 `u'都在=%s 同一行=%s' % (bool(...), bool(... .lineno == ... .lineno))`
       —— `.lineno` 只是**参与算布尔**，打印出来的是 True/False。那是**合规写法**。

    真正会印出行号的就两种形状：
      (1) 直接把 `.lineno` 当 % 的一个元素：`u'第 %s 行' % (n.lineno,)`
      (2) 把"取 .lineno 的列表推导"当元素：`u'%r' % ([n.lineno for n in x],)`
    `bool(...)` 包一层就安全 ⇒ 显式放行。

    ★ 已知盲区（本判据**抓不到**，只能靠人）：`u'%r' % (_same_if,)` 里那个变量
      装着 `(lineno, ...)` 元组 —— 静态源码里看不出有行号。这一类靠 B 段逐个钉。
    """
    if isinstance(e, ast.Attribute) and e.attr == 'lineno':
        return True
    if isinstance(e, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return any(isinstance(s, ast.Attribute) and s.attr == 'lineno'
                   for s in ast.walk(e))
    if isinstance(e, (ast.List, ast.Tuple)):
        return any(_prints_lineno(x) for x in e.elts)
    # bool(...) / 比较 / 算术 ⇒ 算出来是布尔或数，不算"印行号"
    return False


def find_lineno(tree):
    """输出位里把行号**印出来** ⇒ 时相量回显。"""
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not _is_check(n):
            continue
        for slot in extra_of(n):
            for sub in ast.walk(slot):
                if not (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Mod)):
                    continue
                right = sub.right
                elems = right.elts if isinstance(right, ast.Tuple) else [right]
                if any(_prints_lineno(e) for e in elems):
                    hits.append(getattr(n, 'lineno', 0))
    return hits


def find_size(tree):
    """输出位里出现 `len(_read(...))` / `len(<x>.encode(...))` ⇒ 体积回显。

    ★ 只认 `len(...)` 套在"读文件"或"编解码"上 —— 不误伤 `len(_call)`（处数，**合法**）。
    """
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not _is_check(n):
            continue
        for slot in extra_of(n):
            for sub in ast.walk(slot):
                if not (isinstance(sub, ast.Call)
                        and getattr(sub.func, 'id', '') == 'len'
                        and sub.args):
                    continue
                a0 = sub.args[0]
                if not isinstance(a0, ast.Call):
                    continue
                f0 = getattr(a0.func, 'id', '') or getattr(a0.func, 'attr', '')
                if f0 in ('_read', 'encode'):
                    hits.append(getattr(n, 'lineno', 0))
    return hits


# =============================================== A 全量扫描
head(u'A 全量扫描：所有判据的输出里不许有时相量')

# ★★ 只扫**进了 `SUITES` 的脚本** —— 那才是"会产生基线 DIFF"的那一批。
#   一次性复检脚本（`recheck*.py`）打印行号/体积是**诊断需要**，不进 SUITES、不产生 DIFF；
#   把它们一起判红，等于把"守基线"扩大成"守所有脚本"，会逼出一堆无意义改动。
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')


def _suite_scripts():
    """从 `run_all.py` 的 `SUITES = [...]` 解析每个条目的 `script=` 路径。

    不 `import run_all`（它有主流程），只做 AST 取值：
    `os.path.join(ROOT, 'code-quality-audit', ..., 'checkXXX.py')` 的后半段全是常量。
    """
    tree = ast.parse(_read(RUN_ALL))
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign)
                and any(getattr(t, 'id', '') == 'SUITES' for t in n.targets)):
            continue
        if not isinstance(n.value, ast.List):
            continue
        for el in n.value.elts:
            if not isinstance(el, ast.Dict):
                continue
            for k, v in zip(el.keys, el.values):
                if getattr(k, 'value', '') != 'script' or not isinstance(v, ast.Call):
                    continue
                parts, ok = [], True
                for a in v.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        parts.append(a.value)
                    else:
                        ok = False
                if ok and parts:
                    out.append(os.path.join(ROOT, *parts))
    return sorted(set(out))


_targets = [p for p in _suite_scripts() if os.path.exists(p)]
_missing = [p for p in _suite_scripts() if not os.path.exists(p)]

_bad_ln, _bad_sz, _n_calls, _parse_err = [], [], 0, []
for _p in _targets:
    try:
        _tree = ast.parse(_read(_p))
    except SyntaxError as e:
        _parse_err.append((os.path.basename(_p), e.lineno))
        continue
    _n_calls += sum(1 for n in ast.walk(_tree)
                    if isinstance(n, ast.Call)
                    and (getattr(n.func, 'id', '') in ('check', 'ok')
                         or getattr(n.func, 'attr', '') in ('check', 'ok')))
    for _l in find_lineno(_tree):
        _bad_ln.append(u'%s:%s' % (os.path.relpath(_p, ROOT), _l))
    for _l in find_size(_tree):
        _bad_sz.append(u'%s:%s' % (os.path.relpath(_p, ROOT), _l))

check(u'A1 进 SUITES 的判据不接受 `.lineno` 回显', not _bad_ln,
      u'%d 处 %s' % (len(_bad_ln), _bad_ln[:5] if _bad_ln else u''))
check(u'A2 进 SUITES 的判据不接受文件体积（`len(_read(...))`）回显', not _bad_sz,
      u'%d 处 %s' % (len(_bad_sz), _bad_sz[:5] if _bad_sz else u''))
check(u'A3 全部目标都能解析（不许有语法坏件被静默跳过）',
      not _parse_err, u'%d 个 %s' % (len(_parse_err), _parse_err[:3] if _parse_err else u''))
# ★ 分母闸之一：`SUITES` 里登记的脚本必须**真的存在**（路径写错会变成"扫了个空"）
check(u'A4 `SUITES` 里的脚本路径全部存在（否则 A1/A2 扫了个空集）',
      not _missing, u'缺 %d 个 %s' % (len(_missing), _missing[:3] if _missing else u''))

# =============================================== B 本轮改写到位
head(u'B 本轮 6 处改写逐个到位（旧形状不许回潮）')
_SRC = {
    u'check129': os.path.join(AUDIT, u'第129轮-复读与出戏', '_tools', 'check129.py'),
    u'check132': os.path.join(AUDIT, u'第132轮-提示词泄漏护栏', '_tools', 'check132.py'),
    u'check134': os.path.join(AUDIT, u'第134轮-训练线收口', '_tools', 'check134.py'),
    u'check135': os.path.join(AUDIT, u'第135轮-事件截断吊尾巴', '_tools', 'check135.py'),
    u'check137': os.path.join(AUDIT, u'第137轮-主宠训练补丁', '_tools', 'check137.py'),
}
_txt = {}
for _k, _p in _SRC.items():
    _txt[_k] = _read(_p) if os.path.exists(_p) else u''

check(u'B0 五份判据文件都在（分母非空）',
      all(_txt[_k] for _k in _SRC), u'%d/5' % sum(1 for _k in _SRC if _txt[_k]))
# 新形状：只回显"几/几"或布尔
check(u'B1 `check129 D5` 改成 `n/2 过阈`',
      u'%d/2 过阈' in _txt[u'check129'])
check(u'B2 `check132 D3` 改成并列闸名单、D4 改成处数',
      u'个 if；并列闸=' in _txt[u'check132'] and u'处均 return None' in _txt[u'check132'])
# ★★ B3 第一版是**纯文本扫**（`u'原文出现 %d 次' not in _txt`），当场被自己的注释误伤 ——
#   我在那处写着"旧写法 `u'原文出现 %d 次' % _n_mut` …"，注释里就有这句话。
#   这是"禁某短语出现"类判据禁纯文本扫的**第 8 次**发作（第137轮刚记过第 7 次）。
#   ⇒ 改 AST：只查**输出位**里还有没有引用 `_n_mut` 这个计数。
_t134 = ast.parse(_txt[u'check134'])
_b3_bad = []
for _nd in ast.walk(_t134):
    # ★ 循环变量**不能叫 `_n`** —— 那是本 harness 的计数器 `_n = {'p':0,'f':0}`，
    #   覆盖掉以后 `_n['p'] += 1` 直接 TypeError（本轮实测踩了）。
    if not (isinstance(_nd, ast.Call) and _is_check(_nd)):
        continue
    for _slot in extra_of(_nd):
        if any(isinstance(s, ast.Name) and s.id == '_n_mut'
               for s in ast.walk(_slot)):
            _b3_bad.append(_nd)
check(u'B3 `check134 B1c2` 的输出位不再引用 `_n_mut`（计数回显）',
      u'变异后 B1c=%r' in _txt[u'check134'] and not _b3_bad,
      u'%d 处' % len(_b3_bad))
check(u'B4 `check135 F1` 只回显处数、G4 不再打印常量全文',
      u"u'%d 处' % len(_call)" in _txt[u'check135']
      and u"u'%r' % ENDS" not in _txt[u'check135'])
check(u'B5 `check137 D1~D3` 只回显处数 / 布尔',
      u"u'%d 处' % len(_chat_p)" in _txt[u'check137']
      and u'chat=%s prewarm=%s' in _txt[u'check137'])

# =============================================== C 正控制：检测函数真的能抓
head(u'C 正控制：旧写法喂回检测函数，必须抓到')
_OLD = u'''
def _demo():
    check(u'D1 旧写法', len(_x) == 1, u'%r' % (_x,))
    check(u'D5 旧写法', True, u'main=%d' % len(_read(MAIN_PY)))
'''
_old_tree = ast.parse(_OLD)
check(u'C1 旧的 `.lineno` 写法能被抓到（构造样本）',
      len(find_lineno(ast.parse(u"check(u'd', True, u'%r' % ([n.lineno for n in x],))"))) == 1)
check(u'C2 旧的体积写法能被抓到（构造样本）',
      len(find_size(_old_tree)) == 1, u'%d 处' % len(find_size(_old_tree)))
# ★ 反向：合法的 `len(_call)`（处数）**不许**被判成体积回显 —— 否则新闸会误伤所有判据
check(u'C3 反控制：`len(_call)`（处数）不许被判成体积回显',
      not find_size(ast.parse(u"check(u'd', True, u'%d' % len(_call))")))

# ★ 反控制（本轮真踩过）：`check107 E8b` 写的是
#   `u'都在=%s 同一行=%s' % (bool(a.lineno is not None), bool(a.lineno == b.lineno))`
#   —— `.lineno` 只参与算布尔，打印出来是 True/False，**合规**。
#   第一版判据把它判红，说明规则太粗。这条反控制钉住"算布尔不算印行号"。
check(u'C4 反控制：`bool(a.lineno == b.lineno)`（算布尔，不印行号）不许被判红',
      not find_lineno(ast.parse(
          u"ok(u'd', a.lineno == b.lineno, "
          u"u'\u90fd\u5728=%s \u540c\u4e00\u884c=%s' % "
          u"(bool(a.lineno is not None), bool(a.lineno == b.lineno)))")))
# ★ 同时钉住"盲区还是盲区"：`%r` 打一个**装着行号的变量**，静态抓不到。
#   登记它，是为了让下一个人知道"这条闸不是万能的"。
_BLIND = ast.parse(u"check(u'd', True, u'%r' % (_same_if,))")
check(u'C5 盲区如实登记：`%r` 打"装着行号的变量"本闸抓不到（不假装它万能）',
      len(find_lineno(_BLIND)) == 0)

# =============================================== D 分母闸
head(u'D 分母闸（防空集恒真）')
# ★★★ 第146轮：extra **不许回显那两个计数**（原来是 `u'%d 个' % len(_targets)` /
#   `u'%d 处' % _n_calls`）。它们**必然随套件数变化** ⇒ 每加一个套件，本套件就报一次
#   DIFF（判定一个字没变，只是回显的数变了）。第144轮把这两个数**落盘**那一半冻了，
#   但**输出**这一半没动 —— 结果是每轮仍要 `--only check138 --update` 一次。
#   口径照本套件守的那条：语义是"越阈值"就只回显**布尔**，具体数值留在
#   `regress/_out/phase138.live.json`（已忽略、不入库）。
#   直接证明见 `第146轮/_tools/check146.py` B 段：**临时给 SUITES 加一条探针，
#   本套件的输出必须逐行不变**。
check(u'D1 扫到的判据文件 ≥ 100 个', len(_targets) >= 100,
      u'过阈=%s（闸门 ≥100）' % (len(_targets) >= 100))
check(u'D2 扫到的 `check`/`ok` 调用 ≥ 2000 处', _n_calls >= 2000,
      u'过阈=%s（闸门 ≥2000）' % (_n_calls >= 2000))

# =============================================== E 鉴别力自证
head(u'E 鉴别力自证：改坏数据，那几条新判据必须会红')
# 拿 check129 D5 的**真数据**重算一遍：临时把阈值抬到"永远过不了"，`n/2` 必须变 0
_MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
_ES = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')
if os.path.exists(_MAIN) and os.path.exists(_ES):
    _real = sum([len(_read(_MAIN)) > 100000, len(_read(_ES)) > 10000])
    _kill = sum([len(_read(_MAIN)) > 10 ** 9, len(_read(_ES)) > 10 ** 9])
    check(u'E1 D5 的谓词有鉴别力（阈值抬到 1GB ⇒ 0/2）',
          _real == 2 and _kill == 0, u'真=%d 抬阈值后=%d' % (_real, _kill))
else:
    check(u'E1 D5 的谓词有鉴别力（阈值抬到 1GB ⇒ 0/2）', False, u'产品文件没找到')

# =============================================== F 自检
head(u'F 自检')
_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'F2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'F3 零外部盘（扫的都在仓库内）', os.path.abspath(AUDIT).startswith(ROOT + os.sep))
# ★ 本文件自己也必须过 A 段那两条闸 —— 否则"守别人的人自己不守"
check(u'F4 本文件自己不回显行号 / 体积',
      not find_lineno(_self) and not find_size(_self))

# =============================================== 落盘
# ★★★ 第144轮：**不再写 `_evidence/phase138.json`**，改写到 `regress/_out/`。
#   病根：这个文件里有两个**必然随套件数变化**的计数（`files_scanned` /
#   `calls_scanned`），而每加一个判据套件、每加一条判据，它们就会变。
#   ⇒ `git log -- <该文件>` 显示它从第138轮起 **连续 6 个提交（138~143）全被改**，
#   每轮 commit 都捎带一个语义无关的改动，review 时纯噪声。
#   ★ 为什么不是"就让它变"：它是**证据文件**，证据的语义是"当时量到的东西"，
#     而不是"此刻的实时值" —— 一个会自己变的历史证据，谁都不能拿它做对账。
#   ★ 为什么不是"干脆不落盘"：当前扫描面还是有人想看的，所以仍然写一份，
#     只是写到 `code-quality-audit/regress/_out/`（`.gitignore` 已忽略整个目录）——
#     **证据冻结在仓库里，活计数留在工作区外**。
#   ★ 冻结后的 `phase138.json` 由 `check144` 钉住（内容必须逐字等于 138 轮那份）。
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'files_scanned': len(_targets), 'calls_scanned': _n_calls,
       'bad_lineno': len(_bad_ln), 'bad_size': len(_bad_sz)}
_LIVE = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')
if not os.path.isdir(_LIVE):
    os.makedirs(_LIVE)
with io.open(os.path.join(_LIVE, 'phase138.live.json'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check138：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
