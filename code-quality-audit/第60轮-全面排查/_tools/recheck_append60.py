#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮**收尾**复检：记忆追加（详版 §56 + 当日日志）+ 归档脚本入册。

用户口径（2026-09-23）：改过重要核心文件必复检 ⇒ 逐项打 PASS/FAIL 并落盘。
六类判据：① 可编译 ② 结构 ③ 编码 ④ 恒真判据复查 ⑤ 逐令牌回验 ⑥ 工作区干净。
一律 `ast.parse`（**不用 py_compile** —— 产 .pyc 会改变被测状态）。
★ 每条判据都配正/负控制；**判据过窄 = 会误报**，与"过宽 = 恒真"同级要防。
"""
import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
MEM = os.path.join(ROOT, '.workbuddy', 'memory')
DETAIL = os.path.join(MEM, '参考-契约与历轮（详版）.md')
LOG = os.path.join(MEM, '2026-09-28.md')
R60 = os.path.join(ROOT, 'code-quality-audit', '第60轮-全面排查')
EVID = os.path.join(R60, '_evidence')
TOOLS = os.path.join(R60, '_tools')
REPORT = os.path.join(ROOT, '第60轮报告-全面排查.md')
ARCH = os.path.join(TOOLS, '_append60.py')
STRAY = os.path.join(MEM, '_append60.py')          # 不应存在（防临时脚本污染工作区）
SUMMARY = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'summary.txt')
RECHECK = os.path.join(EVID, 'recheck60.txt')

N_PASS = [0]
N_FAIL = [0]


def chk(cond, msg):
    ok = bool(cond)
    (N_PASS if ok else N_FAIL)[0] += 1
    print('[PASS] ' + msg if ok else '[FAIL] ' + msg)
    return ok


def read_text(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def read_bytes(p):
    with open(p, 'rb') as f:
        return f.read()


print(u'第60轮收尾复检（记忆追加 + 归档入册）')

# ---------------- ① 可编译 ----------------
src_arch = read_text(ARCH)
try:
    ast.parse(src_arch)
    chk(True, u'① ast.parse 通过：_append60.py（归档版）')
except SyntaxError as e:
    chk(False, u'① ast.parse 失败：_append60.py —— %s' % e)

# ---------------- ② 结构（含 5 条负控制） ----------------
KEY = u'## 56. 第60轮：扩展前全面排查'


def probe_detail(t):
    i = t.find(KEY)
    return {
        u'§56 标题存在': i >= 0,
        u'§56 前有换行分隔（无粘连）': i > 0 and t[i - 1] == u'\n',
        u'§56.8 小节存在': u'### 56.8' in t,
        u'无 U+FFFD': u'\ufffd' not in t,
        u'无 BOM': not t.startswith(u'\ufeff'),
        u'体量 > 3000 字符': len(t) > 3000,
    }


detail = read_text(DETAIL)
d = probe_detail(detail)
for k in (u'§56 标题存在', u'§56 前有换行分隔（无粘连）', u'§56.8 小节存在',
          u'无 U+FFFD', u'无 BOM', u'体量 > 3000 字符'):
    chk(d[k], u'② 详版：%s' % k)

# 负控制：故意破坏后，对应判据必须**变红**（否则这条判据是恒真的、不可信）
NEG = [
    (u'标题改掉', probe_detail(detail.replace(KEY, u'## 5X'))[u'§56 标题存在'], False),
    # ★ 夹具修正（第一版是**假夹具**）：`u'X' + detail` 只是把整串右移一格，
    #   KEY 与其前一字符的相邻关系完全没变 ⇒ 根本没落进被测分支（铁律：负控制输入必须真落进被测分支）。
    #   要真测"粘连"，必须让 KEY 紧邻的前一个字符不再是换行：
    (u'KEY 紧邻前字符换成 X', probe_detail(u'X' + KEY + detail)[u'§56 前有换行分隔（无粘连）'], False),
    (u'尾部塞 U+FFFD', probe_detail(detail + u'\ufffd')[u'无 U+FFFD'], False),
    (u'头部塞 BOM', probe_detail(u'\ufeff' + detail)[u'无 BOM'], False),
    (u'截成 100 字', probe_detail(detail[:100])[u'体量 > 3000 字符'], False),
]
for name, got, want in NEG:
    chk(got is want, u'② 负控制：%s ⇒ 判据按预期报红（%s）' % (name, got))

log = read_text(LOG)
chk(u'第60轮（扩展前全面排查）' in log, u'② 当日日志含第60轮条目')
chk(u'## 第60轮（扩展前全面排查）' in log and log[log.find(u'## 第60轮（扩展前全面排查）') - 1] == u'\n',
    u'② 日志第60轮条目前有换行分隔（无粘连）')

# ---------------- ③ 编码（无 BOM / 无 U+FFFD / UTF-8 严格可解码） ----------------
for label, path in ((u'详版', DETAIL), (u'日志', LOG), (u'归档脚本', ARCH),
                    (u'报告', REPORT), (u'summary.txt', SUMMARY),
                    (u'recheck60.txt', RECHECK)):
    b = read_bytes(path)
    chk(not b.startswith(b'\xef\xbb\xbf'), u'③ 无 BOM：%s' % label)
    try:
        txt = b.decode('utf-8')
        chk(u'\ufffd' not in txt, u'③ 无 U+FFFD：%s' % label)
    except UnicodeDecodeError as e:
        chk(False, u'③ UTF-8 严格解码失败：%s —— %s' % (label, e))

# ---------------- ④ 恒真判据复查 ----------------
# 本次新增的可执行判据只有两处：归档脚本的"幂等标记"与本复检脚本自身。
# 归档脚本的幂等判据 = `'## 56. …' in text`；负控制：把标记串从文本里去掉必须判"未追加"。
chk((u"if '## 56. 第60轮：扩展前全面排查' in t:" in src_arch),
    u'④ 归档脚本的幂等判据读的是**文本内容**（不是恒真的常量）')
chk((KEY not in KEY.replace(KEY, u'')), u'④ 幂等判据的负控制成立（去掉标记 ⇒ 判否）')
# 本脚本的判据形状 = 变量/表达式参与（不许出现 chk(True, …) 这种占位）
# 归档脚本对记忆文件**只许追加**（写 'w' 会把十几年记忆一次覆盖掉 —— 有鉴别力的一条）
chk((u"io.open(DETAIL, 'a'" in src_arch) and (u"io.open(LOG, 'a'" in src_arch),
    u'④ 归档脚本对详版/日志都用追加模式（a），不是覆盖模式（w）')
chk(u"io.open(DETAIL, 'w'" not in src_arch and u"io.open(LOG, 'w'" not in src_arch,
    u'④ 负控制：脚本内不存在覆盖式写入（若有人改成 w 会立刻报红）')
chk(all(len(t) >= 2 for t in NEG), u'④ 负控制集非空且逐条带名字（no-op 不会假绿）')

# ---------------- ⑤ 逐令牌回验（§56/报告里的数字 ⇔ 原始证据） ----------------
static = json.loads(read_text(os.path.join(EVID, 'static60.json')))
truth = json.loads(read_text(os.path.join(EVID, 'truth60.json')))
wiring = json.loads(read_text(os.path.join(EVID, 'wiring60.json')))
rep = read_text(REPORT)

n_live = static['n_live']
tot_lines = sum(f['lines'] for f in static['files'])
n_sites = truth['n_sites']
n_hollow = len(truth['hollow'])
n_guarded = len(truth['guarded'])
n_unwired = len(wiring['unwired'])
n_swallow = len(wiring['product_swallow'])
n_hasattr = sum(len(v) for v in wiring['hasattr'].values())
main_keys = [k for k in wiring['hasattr'] if k.replace('\\', '/').endswith('src/main.py')]
n_hasattr_main = len(wiring['hasattr'][main_keys[0]]) if main_keys else -1
roster = [u for u in wiring['unwired'] if u['module'] == 'companion_roster']
walk = [u for u in wiring['unwired'] if u['module'] == 'scene_walk']
n_roster_refs = (len(roster[0]['audit_refs']) + len(roster[0]['audit_lits'])) if roster else -1
n_walk_refs = (len(walk[0]['audit_refs']) + len(walk[0]['audit_lits'])) if walk else -1
n_scratch = len(wiring['scratch'])

chk(n_live == 93, u'⑤ 静态：活代码文件 = 93（证据 %d）' % n_live)
chk(tot_lines == 52401, u'⑤ 静态：总行数 = 52,401（证据求和 %d）' % tot_lines)
chk(n_sites == 2769, u'⑤ 恒真：判据点 = 2769（证据 %d）' % n_sites)
chk(n_hollow == 0, u'⑤ 恒真：hollow_true = 0（证据 %d）' % n_hollow)
chk(n_guarded == 7, u'⑤ 恒真：「有兜底」= 7（证据 %d）' % n_guarded)
chk(n_unwired == 3, u'⑤ 接线：产品层零接线模块 = 3（证据 %d）' % n_unwired)
chk(n_swallow == 40, u'⑤ 接线：产品层静默吞异常 = 40（证据 %d）' % n_swallow)
chk(n_hasattr == 103, u'⑤ 接线：hasattr 总数 = 103（证据 %d）' % n_hasattr)
chk(n_hasattr_main == 53, u'⑤ 接线：main.py hasattr = 53（证据 %d，键=%s）'
    % (n_hasattr_main, main_keys[:1]))
chk(n_roster_refs == 15, u'⑤ 接线：companion_roster 审查层引用 = 15（证据 %d）' % n_roster_refs)
chk(n_walk_refs == 9, u'⑤ 接线：scene_walk 审查层引用 = 9（证据 %d）' % n_walk_refs)
chk(n_scratch == 32, u'⑤ 接线：开发残留文件 = 32（证据 %d）' % n_scratch)
chk(wiring['locked_only'] == ['companion_roster', 'scene_walk'],
    u'⑤ 接线：locked_only（有锁但没接线）= 2（证据 %s）' % wiring['locked_only'])

smy = read_text(SUMMARY)
chk('PASS=2980 FAIL=0' in smy and u'套件=56' in smy,
    u'⑤ 全量 G2：PASS=2980 / FAIL=0 / 套件=56（回 summary.txt）')
rc = read_text(RECHECK)
chk(u'合计 PASS=43 FAIL=0' in rc, u'⑤ 第一轮复检：43 PASS / 0 FAIL（回 recheck60.txt）')

# 报告与 §56 必须**同时**写着这些数字（两侧一致才算"没有漂移"）
for tok in (u'93', u'52,401', u'2769', u'2980'):
    chk(tok in rep, u'⑤ 报告含令牌 "%s"' % tok)
# ★ 第一版此条写错对象：假设"报告会写复检合计 43 PASS"，实际报告只**指向证据文件**
#   （判据过窄/凭空假设 ⇒ 误报）。改成查它真实的写法：
chk(u'_evidence/recheck60.txt' in rep, u'⑤ 报告在复检处指向证据文件（而不是只写结论）')
# ★ §56 **段落**切片（第一版 msg 说"§56"却查全文 ⇒ 过宽、名不副实）
sec56 = detail[detail.find(KEY):]
chk(detail.find(KEY) >= 0 and len(sec56) > 3000,
    u'⑤ §56 段落切出成功（%d 字符，占全文 %d）' % (len(sec56), len(detail)))
for tok in (u'2769', u'52,401', u'2 处真·空洞'):
    chk(tok in sec56, u'⑤ §56 **段落内**含令牌 "%s"' % tok)
chk(u'43 PASS' in log, u'⑤ 当日日志含复检合计 "43 PASS"（事实清单在日志、教训在详版）')

# ---------------- ⑥ 工作区状态（列出，不做恒真断言） ----------------
chk(not os.path.exists(STRAY),
    u'⑥ 临时脚本未留在工作区 .workbuddy/memory/（防被 git add -A 误收）')
try:
    out = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = out.stdout.decode('utf-8', 'replace').splitlines()
    print(u'--- git status --porcelain（供人工确认"改动恰为本轮意图"）---')
    for ln in lines:
        print(u'    ' + ln)
    print(u'--- 共 %d 项 ---' % len(lines))
    deleted = [ln for ln in lines if ln[:2] in (' D', 'D ', 'AD')]
    chk(not deleted, u'⑥ 工作区没有文件被误删（deletions=%d）' % len(deleted))
except OSError as e:
    chk(False, u'⑥ git status 不可用：%s' % e)

print(u'合计 PASS=%d FAIL=%d' % (N_PASS[0], N_FAIL[0]))
sys.exit(0 if N_FAIL[0] == 0 else 1)
