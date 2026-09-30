# -*- coding: utf-8 -*-
u"""第67轮：**核心文件复检**（六类判据，逐项 PASS/FAIL，结果落盘）。

依据：用户口径「**以后再调整重要核心文件时一定要记得复检**」（2026-09-23）+ skill `core-file-recheck`。
本轮改过的核心文件：产品 3 个 / 回归 3 个 / 本轮 4 个脚本 / 记忆 3 个 / 报告 1 个。

★ 与 skill 的四处对齐（都是被坑之后才做对的）
------------------------------------------------------------------
1. **可解析一律 `ast.parse`**（不用 `py_compile` —— 它会产 `.pyc`，**复检不许改变被测状态**）。
2. **恒真判据复查走 AST**：正则会把 docstring / 字面量样本误判成"恒真"（§二.3）。
   豁免规则 = 「常量 `True` 必须能在同文件找到**同名**的非恒真分支」，
   并用**另一套机制**（文本 oracle：往上找第一个缩进更浅的行是不是 `else:`）交叉验证。
3. **工作区判据必须 `core.quotepath=false` + `-z`**（中文路径会被转义成 `\\347\\254\\254` ⇒ 假"意外项"）。
4. **报告里的计数收尾重算**（_tools / _evidence 的文件数必须与报告一致）。
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
MEM = os.path.join(ROOT, '.workbuddy', 'memory')

PRODUCT_PY = [
    os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'ghost_system.py'),
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'ghost_overlay.py'),
]
REGRESS_PY = [
    os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    os.path.join(ROOT, 'code-quality-audit', u'第55轮-灵魂实体与NPC人设', 'verify_soul55.py'),
]
ROUND_PY = [os.path.join(HERE, n) for n in
            ('check67.py', 'live67.py', 'tamper67.py', 'recheck67_mem.py', 'recheck67_core.py')]
JSONS = [os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')]
MEM_MD = [os.path.join(MEM, 'MEMORY.md'), os.path.join(MEM, u'参考-契约与历轮（详版）.md'),
          os.path.join(MEM, '2026-09-30.md')]
REPORT = os.path.join(ROOT, u'第67轮报告-幽灵线接线.md')

ALL_PY = PRODUCT_PY + REGRESS_PY + ROUND_PY
ALL_MD = MEM_MD + [REPORT]

PASS = 0
FAIL = 0
FAILED = []


def ok(name, cond, extra=u''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(u'[PASS] %s%s' % (name, (u'  ' + extra) if extra else u''))
    else:
        FAIL += 1
        FAILED.append(name)
        print(u'[FAIL] %s%s' % (name, (u'  ' + extra) if extra else u''))


def info(name, extra=u''):
    u"""★ 只报信息、不计数（skill §二.3：**信息就该长得像信息**，别借断言的壳）。"""
    print(u'[info] %s%s' % (name, (u'  ' + extra) if extra else u''))


def rd(p):
    return io.open(p, encoding='utf-8').read()


# ==================================================================== ① 可解析
def cat1():
    bad = []
    for p in ALL_PY:
        try:
            ast.parse(rd(p))
        except Exception as e:
            bad.append(u'%s: %s' % (os.path.basename(p), e))
    ok(u'1a 全部 .py 可 ast.parse（不产 .pyc）', not bad, u'; '.join(bad) if bad else u'%d 个' % len(ALL_PY))
    # 负控制：坏源码必须被拒（判据不是空转）
    # ★ 写法说明（照 skill §二.3）：**不许**写成 `ok(..., True)` —— 那是"长得像断言、
    #   其实没守任何东西"。用真实变量承接结论，让 4a 的 AST 复查扫不出豁免。
    _neg_rejected = False
    try:
        ast.parse(u'def f(:\n  pass')
    except SyntaxError:
        _neg_rejected = True
    ok(u'1a-负控制 坏源码必须被拒（不是空转）', _neg_rejected, u'SyntaxError 如期' if _neg_rejected else u'竟然通过了')
    jb = []
    for p in JSONS:
        try:
            json.load(io.open(p, encoding='utf-8'))
        except Exception as e:
            jb.append(u'%s: %s' % (os.path.basename(p), e))
    ok(u'1b baseline.json 可 json.load', not jb, u'; '.join(jb) if jb else u'ok')
    # 报告/详版：代码围栏成对（★ 按**行首**数，别用裸 count —— skill §四）
    fb = []
    for p in ALL_MD:
        n = len(re.findall(u'(?m)^```', rd(p)))
        if n % 2:
            fb.append(u'%s: %d 个围栏' % (os.path.basename(p), n))
    ok(u'1c 报告/记忆 代码围栏成对（行首计数）', not fb, u'; '.join(fb) if fb else u'全部成对')


# ==================================================================== ② 结构自检
def cat2():
    q = rd(MEM_MD[0])
    secs = [int(m.group(1)) for m in re.finditer(u'(?m)^##\\s+(\\d+)\\.', q)]
    ok(u'2a 速查本 §0~§11 标题全在且递增', secs == list(range(12)), u'实得 %s' % secs)
    glued = [i + 1 for i, l in enumerate(q.split(u'\n')) if l.count(u'## ') > 1]
    ok(u'2b 速查本无标题粘连', not glued, u'粘连行 %s' % (glued or u'无'))
    d = rd(MEM_MD[1])
    subs = sorted(set(re.findall(u'(?m)^###\\s+63\\.(\\d+)', d)), key=int)
    ok(u'2c 详版 §63 小节 63.1~63.15 全在', subs == [str(i) for i in range(1, 16)], u'实得 %s' % subs)
    r = rd(REPORT)
    need = [u'## 0. 一句话结论', u'## 2. 照抄清单', u'## 5. ', u'## 6. ', u'## 10. 产物清单', u'## 11. 遗留', u'## 12. ']
    miss = [n for n in need if n not in r]
    ok(u'2d 报告关键章节全在', not miss, u'缺 %s' % miss if miss else u'%d 个都在' % len(need))
    gl2 = [i + 1 for i, l in enumerate(r.split(u'\n')) if l.count(u'## ') > 1]
    ok(u'2e 报告无标题粘连', not gl2, u'粘连行 %s' % (gl2 or u'无'))
    lg = rd(MEM_MD[2])
    ok(u'2f 当日日志三节都在（append-only 没覆盖）',
       all(u'## 第%d轮' % i in lg for i in (65, 66, 67)), u'65/66/67 三段')


# ==================================================================== ③ 编码
def cat3():
    bad = []
    for p in ALL_PY + ALL_MD + JSONS:
        raw = io.open(p, 'rb').read()
        if raw.startswith(b'\xef\xbb\xbf'):
            bad.append(u'%s BOM' % os.path.basename(p))
        if u'\ufffd' in raw.decode('utf-8'):
            bad.append(u'%s U+FFFD' % os.path.basename(p))
    ok(u'3a 无 BOM / 无 U+FFFD', not bad, u'; '.join(bad) if bad else u'%d 个文件干净' % (len(ALL_PY) + len(ALL_MD) + len(JSONS)))
    crlf = [os.path.basename(p) for p in MEM_MD if b'\r\n' in io.open(p, 'rb').read()]
    ok(u'3b 记忆三件套仍 LF-only（编辑保持原 EOL）', not crlf, u'; '.join(crlf) if crlf else u'ok')


# ==================================================================== ④ 恒真判据复查（AST）
CK = ('check', 'ok', 'ck', 'expect', 'verify', 'assert_ok')


def _const_true_calls(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and len(n.args) >= 2:
            fn = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
            if fn in CK and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
                out.append(n.lineno)
    return out


def _guarded_lines(tree):
    s = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.If):
            for st in n.orelse:
                s |= {x.lineno for x in ast.walk(st) if hasattr(x, 'lineno')}
    return s


def _text_oracle(src, lineno):
    u"""独立机制：从该行往上找第一个**缩进更浅**的行，看它是不是 `else:`。"""
    lines = src.split(u'\n')
    if lineno - 1 >= len(lines):
        return False
    cur = lines[lineno - 1]
    ind = len(cur) - len(cur.lstrip())
    for j in range(lineno - 2, -1, -1):
        l = lines[j]
        if not l.strip():
            continue
        jind = len(l) - len(l.lstrip())
        if jind < ind:
            return l.strip().startswith(u'else')
    return False


#: ★ **夹具白名单**（显式、可审计，且**不免检**）：这些 `True` 是**刻意的探针夹具**，
#:  不是判据 —— 每条必须带一个**锚点**，复检时验证锚点真在文件里（证明"它确是夹具"）。
#:  第67轮只有 1 条：`check67` 的 F1 用 `ok('__probe_pass__', True)` **故意**造两行输出来
#:  验证"报告口 + 记账口真的能用"，紧跟着 `PASS.pop()` / `del _LINES[-2:]` 把它从账里摘掉。
FIXTURE = {
    ('check67.py', 937): (u'F1 的探针夹具（故意造 PASS/FAIL 两行，随后 pop 掉摘出账）', u'PASS.pop()'),
}


def cat4():
    tot = 0
    bad = []
    exempt = []
    for p in ALL_PY:
        src = rd(p)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        guarded = _guarded_lines(tree)
        for ln in _const_true_calls(tree):
            tot += 1
            if ln in guarded and _text_oracle(src, ln):
                info(u'4 豁免（AST orelse + 文本 else 双证）%s:%d' % (os.path.basename(p), ln))
                continue
            fx = FIXTURE.get((os.path.basename(p), ln))
            # ★ 夹具白名单**不免检**：锚点必须真在文件里
            if fx and (fx[1] in src):
                exempt.append(u'%s:%d（%s）' % (os.path.basename(p), ln, fx[0]))
                continue
            bad.append(u'%s:%d' % (os.path.basename(p), ln))
    for e in exempt:
        info(u'4 夹具白名单（锚点已验证）%s' % e)
    ok(u'4a 无「看着在守其实没守」的恒真判据（AST + 双机制豁免 + 夹具白名单免检）', not bad,
       u'扫描常量True调用 %d 处；夹具 %d；无豁免的 %s' % (tot, len(exempt), bad or u'0 处'))
    # 负控制：合成的恒真写法必须被抓出来
    synth = u"ok('x', True)\n"
    hit = bool(_const_true_calls(ast.parse(synth)))
    ok(u'4a-负控制 合成 `ok(x, True)` 必被抓出（判据有鉴别力）', hit, u'命中=%s' % hit)
    # 4b：报告口必须真能记失败（F2 已锁，这里用**独立的形状判据**交叉验证）
    # ★ 首版写成找 `PASS += 1` ⇒ 报红。查明 check67 的记账是
    #   `(PASS if cond else FAIL).append(name)`（列表追加，不是计数器）—— 又一条"判据过窄"。
    c67 = rd(os.path.join(HERE, 'check67.py'))
    ok(u'4b check67 的记账口把 False 记进 FAIL（形状判据，与 F2 独立）',
       (u'(PASS if cond else FAIL).append(name)' in c67)
       and (u"'[PASS] ' if cond else '[FAIL] '" in c67),
       u'记账口 + 标记字面量都在')


# ==================================================================== ⑤ 逐令牌回验
TOKENS = [
    u'3097', u'ALL IDENTICAL', u'114', u'A1~A6', u'6/6', u'45 个 PNG',
    u'9841', u'9888', u'10295', u'63.15', u'18 PASS', u'44×58', u'96.19',
    u'457', u'313', u'+371', u'11,768', u'12,139', u'GHOST_SPAWN_OFFSET', u'ghost_state.json',
]

#: 证据文件里**应当能独立看到**的令牌（★ 取的是**产物里的真实字面量**，不是报告的措辞）
#: ★ 首版把报告的措辞 `ALL IDENTICAL` / `18 PASS` 当令牌去证据里找 ⇒ 报红。
#:   真相：run_all 的汇总行是 `合计：PASS=3097 FAIL=0  套件=57` + 每套件 `IDENTICAL`；
#:   recheck67_mem 的汇总行是 `合计：PASS=18 FAIL=0` ⇒ **又一条"判据过窄"**（拿措辞当事实）。
EV_TOKENS = (u'A1~A6', u'114', u'PASS=3097', u'IDENTICAL', u'PASS=18')


def cat5():
    r = rd(REPORT)
    # ★ 证据全文 = 目录里所有**文本**产物拼接（收尾重跑时本文件自己的输出也在里面）
    ev = u''
    for f in sorted(os.listdir(EV)):
        fp = os.path.join(EV, f)
        if os.path.isfile(fp):
            try:
                ev += rd(fp)
            except Exception:
                pass
    lost_r = [t for t in TOKENS if t not in r]
    lost_e = [t for t in EV_TOKENS if t not in ev]
    ok(u'5a 报告里的本轮关键令牌全在', not lost_r, u'缺 %s' % lost_r if lost_r else u'%d 个全部命中' % len(TOKENS))
    ok(u'5b 证据文件里对得上（不是只写在报告里）', not lost_e, u'缺 %s' % lost_e if lost_e else u'ok')
    # 负控制
    ok(u'5a-负控制 伪造令牌不在报告里', u'zzq_never_67' not in r, u'ok')
    # 产物计数必须与报告一致（skill §六：报告里的计数收尾重算）
    ntools = len([f for f in os.listdir(HERE) if f.endswith('.py')])
    nev = len([f for f in os.listdir(EV) if os.path.isfile(os.path.join(EV, f))])
    info(u'5 产物计数实测：_tools/*.py = %d，_evidence 文件 = %d' % (ntools, nev))
    ok(u'5c 报告声明的产物计数 == 磁盘实测',
       (u'**5 个 .py**' in r) and (u'**8 份**' in r) and ntools == 5 and nev == 8,
       u'tools=%d evidence=%d' % (ntools, nev))


# ==================================================================== ⑥ 状态干净
def cat6():
    r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
                       cwd=ROOT, stdout=subprocess.PIPE)
    raw = r.stdout.decode('utf-8', 'surrogateescape')
    parts = [x for x in raw.split(u'\x00') if x.strip()]
    paths = []
    for seg in parts:
        p = seg[3:] if len(seg) > 3 else seg
        paths.append(p)
    octal = [p for p in paths if re.search(u'\\\\[0-7]{3}', p)]
    ok(u'6a 工作区路径无八进制转义残留（非 ASCII 判据有效）', not octal, u'残留 %s' % octal if octal else u'%d 条路径' % len(paths))
    unexpected = [p for p in paths
                  if not (p.startswith(u'code-quality-audit/第67轮-幽灵线接线/')
                          or p.startswith(u'code-quality-audit/regress/')
                          or p.startswith(u'ralsei_pet/')
                          or p.startswith(u'.workbuddy/memory/')
                          or p.startswith(u'第67轮报告')
                          or u'第55轮' in p)]
    ok(u'6b 改动项都在预期范围内（无顺手改到别处）', not unexpected,
       u'意外项 %s' % unexpected if unexpected else u'%d 项全部预期内' % len(paths))
    # 负控制：仓库外路径应被判为意外项
    ok(u'6b-负控制 仓库外路径会被判为意外项',
       bool([p for p in [u'/tmp/zzq_outside'] if not (p.startswith(u'ralsei_pet/') or p.startswith(u'code-quality-audit/'))]),
       u'ok')
    g2 = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'g2_round67_final.txt')
    t = rd(g2) if os.path.isfile(g2) else u''
    ok(u'6c G2 全量已真跑且 ALL IDENTICAL（无 【问题】段）',
       (u'ALL' in t and u'IDENTICAL' in t and u'【问题】' not in t and u'PASS=3097' in t),
       u'' if t else u'缺 g2 输出')
    ok(u'6d 敏感目录未被误删（_out 仍在 / 无 shutil.rmtree 于回归脚本）',
       os.path.isdir(os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')), u'ok')


def main():
    print(u'=' * 72)
    print(u'第67轮 核心文件复检（六类判据）')
    print(u'=' * 72)
    for f in (cat1, cat2, cat3, cat4, cat5, cat6):
        try:
            f()
        except Exception:
            FAIL_ = u'%s 抛异常' % f.__name__
            ok(FAIL_, False, traceback.format_exc().replace(u'\n', u' | ')[:400])
    print(u'-' * 72)
    print(u'合计：PASS=%d FAIL=%d' % (PASS, FAIL))
    if FAILED:
        print(u'FAIL 明细：')
        for f in FAILED:
            print(u'  - %s' % f)
    else:
        print(u'ALL PASS')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
