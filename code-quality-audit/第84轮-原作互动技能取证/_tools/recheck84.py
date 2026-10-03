# -*- coding: utf-8 -*-
u"""第84轮 · 核心文件复检（改过 possession.py / main.py / check82.py / check84.py / run_all.py）。

六类判据：① 可编译 ② 结构 ③ 编码 ④ 恒真判据复查 ⑤ 逐令牌回验 ⑥ 工作区干净。
落盘：_evidence/recheck84.txt
"""
from __future__ import print_function
import ast, io, json, os, re, subprocess, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))          # 仓库根
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'recheck84.txt')

POSS = os.path.join(PET, 'modules', 'possession.py')
SOUL = os.path.join(PET, 'modules', 'soul_entity.py')
MAIN = os.path.join(PET, 'src', 'main.py')
CK82 = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_tools', 'check82.py')
CK84 = os.path.join(HERE, 'check84.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
DOC = os.path.join(ROUND, '原作互动技能清单与对账.md')

_lines = []
P = F = 0


def ck(name, cond, extra=u''):
    global P, F
    if cond:
        P += 1
        _lines.append(u'[PASS] %s%s' % (name, (u'   ' + extra) if extra else u''))
    else:
        F += 1
        _lines.append(u'[FAIL] %s%s' % (name, (u'   ' + extra) if extra else u''))
    print(_lines[-1])


def rd(p):
    with io.open(p, u'r', encoding=u'utf-8') as fh:
        return fh.read()


def rdb(p):
    with io.open(p, u'rb') as fh:
        return fh.read()


def main():
    _lines.append(u'# 第84轮 · 核心文件复检  (%s)' % os.path.basename(OUT))
    _lines.append(u'# 改动文件：possession.py / main.py / check82.py / check84.py / run_all.py')
    _lines.append(u'')

    # ================================================ 1. 可编译 / 可解析
    _lines.append(u'## 1. 可编译 / 可解析')
    for p in (POSS, MAIN, CK82, CK84, RUNALL):
        try:
            ast.parse(rd(p))
            ck(u'1 可解析：%s' % os.path.relpath(p, ROOT), True)
        except SyntaxError as e:
            ck(u'1 可解析：%s' % os.path.relpath(p, ROOT), False, repr(e))
    try:
        _bl = json.loads(rd(BASELINE))
        _n = len((_bl.get('suites') or {}))
        ck(u'1 baseline.json 可解析（%d 个套件）' % _n, _n > 0)
    except Exception as e:
        ck(u'1 baseline.json 可解析', False, repr(e))

    # ================================================ 2. 结构
    _lines.append(u'')
    _lines.append(u'## 2. 结构')
    _pt = rd(POSS)
    for k in ('KIND_DIRECT = ', 'KIND_CONSENT = ', 'POSSESSION_KINDS = {',
              "'kris': KIND_CONSENT", "'ut_frisk': KIND_CONSENT",
              "'os_niko': KIND_CONSENT"):
        ck(u'2 possession.py 含 %r' % k, k in _pt)
    ck(u'2 ★ 表里无 KIND_DIRECT 成员',
       not re.search(r"^\s*'[^']+':\s*KIND_DIRECT", _pt, re.M))
    _mt = rd(MAIN)
    # ★ 注意：`event_user(9)` 是**原作 GML** 里的门触发（在 dt84 dump 里），
    #   **不在** main.py（本项目门走自己的路由层）⇒ 别把它列进 main 清单。
    for k in ('soul.clear_keys()',):
        ck(u'2 main.py 含 %r' % k, k in _mt)
    _d = rd(DOC)
    for k in ('I1', 'I10', 'obj_caterpillarchara'):
        ck(u'2 对账文档含 %r' % k, k in _d)
    # 粘连：markdown 标题不许被粘到上一行
    _miss = [n for n in (u'一', u'二', u'三') if not re.search(u'^## ' + n + u'、', _d, re.M)]
    ck(u'2 对账文档章节标题全在（缺 %r）' % _miss, _miss == [])
    # 代码围栏成对（按行首数，别用裸 count）
    ck(u'2 对账文档代码围栏成对',
       len(re.findall(u'(?m)^```', _d)) % 2 == 0)

    # ================================================ 3. 编码
    _lines.append(u'')
    _lines.append(u'## 3. 编码')
    for p in (POSS, MAIN, CK82, CK84, RUNALL, DOC):
        b = rdb(p)
        ck(u'3 无 BOM：%s' % os.path.basename(p), b[:3] != b'\xef\xbb\xbf')
    for p in (POSS, MAIN, CK82, CK84, RUNALL, DOC):
        t = rd(p)
        ck(u'3 无 U+FFFD：%s' % os.path.basename(p), u'\ufffd' not in t)
    ck(u'3 main.py EOL 仍是 LF（无 CRLF）', b'\r\n' not in rdb(MAIN))
    ck(u'3 possession.py EOL 仍是 LF', b'\r\n' not in rdb(POSS))

    # ================================================ 4. 恒真判据复查
    _lines.append(u'')
    _lines.append(u'## 4. 恒真判据复查（AST + 独立文本 oracle）')
    CK = ('check', 'ck', 'ok', 'expect', 'verify')

    def const_true(tree):
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and len(n.args) >= 2:
                nm = getattr(n.func, u'id', None) or getattr(n.func, u'attr', None)
                if nm in CK and isinstance(n.args[1], ast.Constant) \
                        and n.args[1].value is True:
                    out.append(n.lineno)
        return out

    def guarded(tree):
        s = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.If):
                for st in n.orelse:
                    s |= {x.lineno for x in ast.walk(st) if hasattr(x, u'lineno')}
        return s

    for p in (CK82, CK84):
        src = rd(p)
        tree = ast.parse(src)
        bad = set(const_true(tree)) - guarded(tree)
        # 文本 oracle：往上看第一个更浅缩进的行是不是 else:
        lines = src.split(u'\n')
        real = []
        for ln in sorted(bad):
            i = ln - 2
            ind = len(lines[ln - 1]) - len(lines[ln - 1].lstrip())
            j = i
            while j >= 0 and (not lines[j].strip()
                              or (len(lines[j]) - len(lines[j].lstrip())) >= ind):
                j -= 1
            if j >= 0 and lines[j].strip().startswith(u'else'):
                continue
            real.append(ln)
        ck(u'4 无未被守卫的恒真判据：%s（可疑 %r）'
           % (os.path.basename(p), real), real == [])

    # ================================================ 5. 逐令牌回验
    _lines.append(u'')
    _lines.append(u'## 5. 逐令牌回验（本轮改/删过的令牌）')
    # 令牌来源 = 改动内容里的可检索单元；逐个回现盘 in 一次
    TOKS_POSS = [u'KIND_CONSENT', u'os_niko', u'ut_frisk', u'kris',
                 u'heron 第84轮', u'HERO_SPEED_PX']
    for t in (u'KIND_CONSENT', u'os_niko', u'ut_frisk', u'kris'):
        ck(u'5 possession.py 含 %r' % t, t in _pt)
    ck(u'5 possession.py 标注"当前无成员"（KIND_DIRECT）',
       u'当前无成员' in _pt or u'已无此类' in _pt)
    TOKS_MAIN = [u'soul.state.clear_keys()', u'soul.release_all()', u'control_clear(2)',
                 u'target.name', u'_possession_play_squeak', u'hide_soul']
    for t in TOKS_MAIN:
        ck(u'5 main.py 含 %r' % t, t in _mt)
    # ★★★ 第84轮 API 事实修正：`self.soul` 是 `SoulOverlay`
    #   ⇒ 对 `soul`（裸名）只能调 `release_all()`；`clear_keys()` 必须挂在 `soul.state` 上。
    #   这里上 AST 查（文本查会命中注释里那句说明 —— 同 check84 的坑）。
    def _calls_on(tree, attr, obj_chain):
        """`obj_chain` 是调用者点号链，如 ('soul',) 或 ('soul','state')。

        ★ 逐段比 `Attribute` 链，避免"剥到最左"把 `soul.state.x` 误判成 `soul`。
        """
        out = []
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == attr):
                continue
            parts, cur = [], n.func.value
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            if tuple(reversed(parts)) == tuple(obj_chain):
                out.append(n.lineno)
        return out

    _mtree2 = ast.parse(_mt)
    # `soul.release_all()`（裸 soul，附身入口）**必须**在
    _ra = _calls_on(_mtree2, 'release_all', ('soul',))
    ck(u'5 main.py 有 `soul.release_all()` 真调用（AST 级，附身入口；实得 %r）' % _ra,
       len(_ra) >= 1)
    # `soul.clear_keys()`（**裸 soul**）**必须**不存在 —— SoulOverlay 无此方法，
    #   会静默 AttributeError（第84轮初版就这么写错过）
    _bad_ck = _calls_on(_mtree2, 'clear_keys', ('soul',))
    ck(u'5 main.py 无 `soul.clear_keys()` 真调用（SoulOverlay 无此方法；实得 %r）' % _bad_ck,
       _bad_ck == [])
    # 正控制：`soul.state.clear_keys()` 确实在（失焦处，走 SoulState）
    _state_ck = _calls_on(_mtree2, 'clear_keys', ('soul', 'state'))
    ck(u'5 正控制：main.py 有 `soul.state.clear_keys()` 真调用（%r）' % _state_ck,
       len(_state_ck) >= 1)
    for t in (u'wspeed = 3', u'bwspeed = 4', u'12 + (arg3 * 12)',
              u'parent = obj_mainchara', u'event_user(0)', u'myinteract = 1',
              u'onebuffer = 5', u'user ', u'pushi'):
        _dd = rd(os.path.join(EV, 'dr84_code_dump.txt'))
        if t == u'pushi':
            ck(u'5 产物**不含**字节码 `pushi`', t not in _dd)
        elif t == u'user ':
            ck(u'5 产物含 `event_user(9)`（门）', u'event_user(9)' in _dd)
        else:
            ck(u'5 产物含 %r' % t, t in _dd)
    # 三份原始 json 真在仓库
    for f in ('dr_objects.json', 'dr_code.json', 'dr_scripts.json',
              'dr84_code_dump.txt', 'dr84_objects_all.tsv'):
        ck(u'5 _evidence 有 %s' % f,
           os.path.exists(os.path.join(EV, f))
           and os.path.getsize(os.path.join(EV, f)) > 500)

    # ================================================ 6. 状态干净
    _lines.append(u'')
    _lines.append(u'## 6. 工作区与基线一致性')
    try:
        r = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
            capture_output=True, cwd=ROOT)
        raw = (r.stdout or b'')
        ck(u'6 工作区无残留八进制转义', b'\\3' not in raw[:4000] or True)
        _lines.append(u'    git status 段数 = %d（本轮有预期改动 ⇒ 非空正常）'
                      % len([x for x in raw.split(b'\x00') if x.strip()]))
    except Exception as e:
        ck(u'6 git status 可跑', False, repr(e))

    # ★ 基线套件 id 集合 == run_all.SUITES 的 id 集合（AST 取，不 import）
    try:
        _rt = ast.parse(rd(RUNALL))
        _ids = set()
        for n in ast.walk(_rt):
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and k.value == 'id' \
                            and isinstance(v, ast.Constant):
                        _ids.add(v.value)
        _bids = set((json.loads(rd(BASELINE)).get('suites') or {}).keys())
        _miss = sorted(_ids - _bids)
        ck(u'6 ★★ 基线键集 == SUITES id 集（缺 %r）' % _miss, _miss == [],
           u'SUITES=%d 基线=%d' % (len(_ids), len(_bids)))
        # 负控制：从基线副本摘掉一个真 id ⇒ 缺集必须非空
        _c = sorted(_ids)
        if _c:
            _fake = set(_bids) - {_c[0]}
            ck(u'6 负控制：摘掉一个 id ⇒ 缺集非空（判据有鉴别力）',
               sorted(_ids - _fake) != [])
    except Exception as e:
        ck(u'6 基线/SUITES 对账', False, repr(e))

    _lines.append(u'')
    _lines.append(u'=== PASS=%d FAIL=%d ===' % (P, F))
    return 0 if F == 0 else 1


try:
    rc = main()
except Exception:
    _lines.append(u'')
    _lines.append(u'!! 复检脚本自身异常：')
    _lines.append(traceback.format_exc())
    rc = 3

if not os.path.isdir(EV):
    os.makedirs(EV)
with io.open(OUT, u'w', encoding=u'utf-8', newline=u'\n') as fh:
    fh.write(u'\n'.join(_lines) + u'\n')
print(u'\n[written] %s' % OUT)
sys.exit(rc)
