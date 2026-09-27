# -*- coding: utf-8 -*-
"""第54轮 · 核心文件复检（可落盘）

按用户长期口径「调整重要核心文件时一定要记得复检」执行六类判据：
  1 可解析（.py 走 ast.parse —— **不用 py_compile**：它会落 .pyc，改变被检状态）
  2 结构自检（报告章节全在且无粘连 / animations.json 键集合 == 代码内置表）
  3 编码（无 BOM / 无 U+FFFD）
  4 恒真判据复查（★按 skill §二.2 的口径：常量 True 必须能找到**同名**的非恒真分支）
  5 逐令牌回验（本轮改/删过的标识符与文件名，逐个回原文件 in 一次）
  6 状态干净 + 改动集合 == 预期集合

输出：同级 `_evidence/recheck54_result.txt`（固定文件名，不依赖 stdout）。
"""
import ast
import io
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EVID = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EVID, 'recheck54_result.txt')

P = lambda *a: os.path.join(ROOT, *a)
LINES, PASS, FAIL = [], [], []


def ck(cid, title, ok, detail=''):
    (PASS if ok else FAIL).append(cid)
    LINES.append('  [%s] %-5s %s%s' % ('PASS' if ok else 'FAIL', cid, title,
                                       ('  :: ' + str(detail)) if detail else ''))


def rd(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def rdb(path):
    with open(path, 'rb') as fh:
        return fh.read()


# ---- 被检文件清单 -------------------------------------------------------
PY_FILES = [
    P('ralsei_pet', 'src', 'main.py'),
    P('ralsei_pet', 'modules', 'sprite_loader.py'),
    P('ralsei_pet', 'modules', 'autonomous_agent.py'),
    P('ralsei_pet', 'modules', 'logger_utils.py'),
    P('code-quality-audit', 'regress', 'run_all.py'),
    P('code-quality-audit', 'regress', '_seed_runner.py'),
    P('code-quality-audit', '架构改造-H4H5', 'extract_animations_json.py'),
    P('code-quality-audit', '第八轮', 'verify_round8_anim.py'),
    P('code-quality-audit', '第52轮-对话与人味收口', '_tools', 'check52c.py'),
    P('code-quality-audit', '第54轮-电梯坐姿与底层修复', '_tools', 'check54a.py'),
]
JSON_FILES = [
    P('ralsei_pet', 'assets', 'animations.json'),
    P('code-quality-audit', 'regress', 'baseline.json'),
]
MD_FILES = [
    P('第54轮报告-电梯坐姿与底层修复.md'),
    P('code-quality-audit', '第54轮-电梯坐姿与底层修复', '_evidence', 'elevator_evidence.md'),
]
# 审计/锁脚本（判据 4 只扫这些：产品代码没有 check()）
JUDGE_FILES = [p for p in PY_FILES if p.endswith(('check54a.py', 'check52c.py',
                                                  'verify_round8_anim.py'))]

LINES.append('=== 1. 可解析（.py 走 ast.parse；不落 .pyc）===')
for p in PY_FILES:
    try:
        ast.parse(rd(p))
        ck('C1-' + os.path.basename(p), '可解析：' + os.path.basename(p), True)
    except Exception as exc:
        ck('C1-' + os.path.basename(p), '可解析：' + os.path.basename(p), False, repr(exc))
for p in JSON_FILES + [P('ralsei_pet', 'assets', 'animations.json')]:
    try:
        json.load(io.open(p, encoding='utf-8'))
        ck('J1-' + os.path.basename(p), '可 json.load：' + os.path.basename(p), True)
    except Exception as exc:
        ck('J1-' + os.path.basename(p), '可 json.load：' + os.path.basename(p), False, repr(exc))

LINES.append('')
LINES.append('=== 2. 结构自检 ===')
rep = rd(MD_FILES[0])
miss = [n for n in range(10) if not re.search(r'^## ' + str(n) + r'\. ', rep, re.M)]
glued = [i for i, l in enumerate(rep.split('\n'), 1) if '##' in l and not l.startswith('##')]
ck('S1', '报告章节 0..9 全在', not miss, '缺=%s' % miss)
ck('S2', '标题无粘连（## 都在行首）', not glued, '粘连行=%s' % glued)
ck('S3', '报告代码围栏成对', rep.count('```') % 2 == 0, 'count=%d' % rep.count('```'))

# 报告里的关键数字必须与产物一致（防止报告吹牛）
anim = json.load(io.open(P('ralsei_pet', 'assets', 'animations.json'), encoding='utf-8'))
ngroups = len(anim['groups'])
ck('S4', 'animations.json 组数 == 报告里的 114', ngroups == 114 and '114 组' in rep, 'n=%d' % ngroups)
n_entries = len(os.listdir(P('deltarune_ralsei')))
n_png = len([n for n in os.listdir(P('deltarune_ralsei')) if n.lower().endswith('.png')])
# ★ 判据修正（第54轮复检当场抓到）：报告写的是"**文件数** 1112→1116"，
#   而初版判据只数 `.png`（1115）⇒ 过窄误报。库里另有 1 个无扩展名的历史文件
#   `豆包给的建议`（早已入库，非本轮引入）。改为一并断言两个口径。
ck('S5', '素材库条目数 == 报告里的 1116（其中 PNG 1115 + 1 个无扩展名历史文件）',
   n_entries == 1116 and n_png == 1115 and '1116' in rep,
   'entries=%d png=%d' % (n_entries, n_png))

LINES.append('')
LINES.append('=== 3. 编码（无 BOM / 无 U+FFFD）===')
for p in PY_FILES + JSON_FILES + MD_FILES:
    raw = rdb(p)
    bom = raw[:3] == b'\xef\xbb\xbf'
    bad = '\ufffd' in raw.decode('utf-8', 'replace')
    ck('E-' + os.path.basename(p), '无 BOM 且无 U+FFFD：' + os.path.basename(p),
       (not bom) and (not bad), 'bom=%s fffd=%s' % (bom, bad))

LINES.append('')
LINES.append('=== 4. 恒真判据复查（同名非恒真分支口径）===')
for p in JUDGE_FILES:
    src = rd(p)
    calls = re.findall(r"check\(\s*'([^']*)'\s*,\s*([^,\)]+)", src)
    seen = {}
    for nm, arg in calls:
        seen.setdefault(nm, set()).add(arg.strip())
    bad = sorted(nm for nm, args in seen.items() if args == {'True'})
    ck('T-' + os.path.basename(p), '无"只以常量 True 出现"的 check：' + os.path.basename(p),
       not bad, '可疑=%s' % bad)

LINES.append('')
LINES.append('=== 5. 逐令牌回验 ===')
TOKENS = {
    'ralsei_pet/assets/animations.json': ['sit', 'sit_rest', 'legacy',
                                          'spr_ralsei_sit_0.png', 'spr_ralsei_sit_3.png'],
    'ralsei_pet/modules/sprite_loader.py': ['"sit":', '"sit_rest":', 'spr_ralsei_sit_2.png'],
    'ralsei_pet/src/main.py': ['_lounge_since', '_idle_lounge_tick', "'sit'",
                              'play_animation_once("sit"', 'animation.fps'],
    'ralsei_pet/modules/logger_utils.py': ['_SafeEmitStreamHandler', 'handleError',
                                           'emit_failures', 'def doRollover'],
    'ralsei_pet/modules/autonomous_agent.py': ['已硬拒绝'],
    'code-quality-audit/regress/run_all.py': ['sit_round54'],
    'code-quality-audit/regress/baseline.json': ['sit_round54'],
    'code-quality-audit/架构改造-H4H5/extract_animations_json.py': ['CARRIED_KEYS', 'roundtrip'],
    'code-quality-audit/第八轮/verify_round8_anim.py': ['_idle_lounge_tick'],
    'code-quality-audit/第54轮-电梯坐姿与底层修复/_tools/check54a.py':
        ['_lounge_since', '_idle_loop_active', '_SafeEmitStreamHandler'],
}
for rel, toks in TOKENS.items():
    text = rd(P(*rel.split('/')))
    lost = [t for t in toks if t not in text]
    ck('K-' + os.path.basename(rel), '令牌全在：' + os.path.basename(rel), not lost,
       '丢失=%s' % lost)

# 素材四帧真实存在且是真 PNG
for i in range(4):
    fp = P('deltarune_ralsei', 'spr_ralsei_sit_%d.png' % i)
    ok = os.path.exists(fp) and rdb(fp)[:8] == b'\x89PNG\r\n\x1a\n'
    ck('K-png%d' % i, '真 PNG 在位：spr_ralsei_sit_%d.png' % i, ok)

LINES.append('')
LINES.append('=== 6. 状态干净 / 改动集合 ==')
try:
    # ★ 判据修正（第54轮复检当场抓到）：`git status --porcelain` 默认 `core.quotepath=true`，
    #   会把中文路径转义成八进制（`\347\254\25454...`），前缀匹配必然落空 ⇒ 过窄误报。
    #   改用 `-z`（NUL 分隔、**不转义**）+ surrogateescape 解码 —— 与既定口径一致。
    st = subprocess.run(['git', 'status', '--porcelain', '-z'], cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    paths = []
    for part in st.split(b'\x00'):
        if not part.strip():
            continue
        entry = part.decode('utf-8', 'surrogateescape')
        paths.append(entry[3:].strip().strip('"'))
    paths = sorted(paths)
    LINES.append('  git status --porcelain -z（共 %d 项）：' % len(paths))
    for w in paths:
        LINES.append('    ' + w)
    EXPECT_PREFIX = ('code-quality-audit/', 'ralsei_pet/', 'deltarune_ralsei/', '第54轮报告')
    unexpected = [w for w in paths if not w.startswith(EXPECT_PREFIX)]
    # 负控制：换成旧写法（默认转义输出）必须**匹配不上** —— 证明本修正确实必要，
    # 而不是"放宽判据把红刷绿"。
    st_old = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    old_paths = [l[3:].strip().strip('"') for l in
                 st_old.decode('utf-8', 'replace').splitlines() if l.strip()]
    ck('G0', '负控制：默认（转义）输出确实会漏判中文路径（证明用 -z 是必要的）',
       any('\\347' in w for w in old_paths))
    ck('G1', '改动集合只含本轮预期目录（无临时/备份文件混入）', not unexpected,
       '意外=%s' % unexpected)
    ck('G2', '没有被顺手改到的 .pyc / 临时产物', not [w for w in paths if w.endswith('.pyc')])
    # 删除行数守卫（防止 git add -A 把删除提交上去）
    ns = subprocess.run(['git', 'diff', '--numstat'], cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    dels = 0
    for line in ns.decode('utf-8', 'replace').splitlines():
        parts = line.split('\t')
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            dels += int(parts[1])
    ck('G3', '工作区删除行数远低于 1000 停手线', dels < 1000, 'deletions=%d' % dels)
except Exception as exc:
    ck('G1', 'git 状态可读', False, repr(exc))

top = ['核心文件复检（第54轮）', '=' * 60]
tail = ['', '=' * 60, 'PASS=%d  FAIL=%d' % (len(PASS), len(FAIL))]
if FAIL:
    tail += ['', 'FAIL 明细：']
    for f in FAIL:
        tail += [l for l in LINES if l.strip().startswith('[FAIL]') and (' ' + f + ' ') in l]
text = '\n'.join(top + LINES + tail) + '\n'
os.makedirs(EVID, exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(text)
print(text)
print('已落盘：%s' % OUT)
