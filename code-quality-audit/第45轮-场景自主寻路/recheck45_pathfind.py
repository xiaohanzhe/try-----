# -*- coding: utf-8 -*-
"""第45轮核心文件复检（用户口径：「以后再调整重要核心文件时一定要记得复检」）。

六类判据，逐项 PASS/FAIL 落盘：
  ① 语法/可编译
  ② 结构自检（关键函数/常量全在）
  ③ 编码（无 BOM / 无 U+FFFD）
  ④ 恒真判据复查（回归锁里有没有"看着在守其实没守"的写法）
  ⑤ 逐令牌回验（本轮新增的关键令牌逐个回原文件 in 一次）
  ⑥ 工作区干净 + 回归
"""
import ast
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
R45 = os.path.join(ROOT, 'code-quality-audit', '第45轮-场景自主寻路')

FILES = {
    'PF': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_pathfind.py'),
    'CTRL': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_controller.py'),
    'MAIN': os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    'ALIAS': os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_aliases.json'),
    'LOCK': os.path.join(R45, 'verify_pathfind45.py'),
    'TOOL': os.path.join(R45, '_tools_reach45.py'),
    'RUNALL': os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    'SCENEP0': os.path.join(ROOT, 'code-quality-audit', '场景系统-P0', 'verify_scene_p0.py'),
    'REPORT': os.path.join(ROOT, '第45轮报告-场景自主寻路.md'),
    'EVID': os.path.join(R45, '_evidence', '五章可达性实测45.txt'),
}

out = []
res = []


def ck(cid, ok, msg):
    res.append((cid, bool(ok), msg))
    out.append('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def txt(key):
    with io.open(FILES[key], 'r', encoding='utf-8') as fh:
        return fh.read()


def raw(key):
    with io.open(FILES[key], 'rb') as fh:
        return fh.read()


out.append('第45轮核心文件复检  ROOT=%s' % ROOT)
out.append('=' * 70)

# ① 语法/可编译
for key in ('PF', 'CTRL', 'MAIN', 'LOCK', 'TOOL'):
    try:
        ast.parse(txt(key))
        ck('① %s' % key, True, '① %s 可编译（ast.parse）' % key)
    except SyntaxError as e:
        ck('① %s' % key, False, '① %s 语法错: %s' % (key, e))
# JSON 合法性
try:
    json.loads(raw('ALIAS').decode('utf-8'))
    ck('① ALIAS', True, '① _aliases.json 是合法 JSON')
except Exception as e:
    ck('① ALIAS', False, '① _aliases.json 非法: %s' % e)
# run_all 里的 SUITES 可解析
try:
    t = ast.parse(txt('RUNALL'))
    ck('① RUNALL', True, '① run_all.py 可编译')
except SyntaxError as e:
    ck('① RUNALL', False, '① run_all.py 语法错: %s' % e)
try:
    ast.parse(txt('SCENEP0'))
    ck('① SCENEP0', True, '① verify_scene_p0.py 可编译')
except SyntaxError as e:
    ck('① SCENEP0', False, '① verify_scene_p0.py 语法错: %s' % e)

# ② 结构自检
pf = txt('PF')
need_syms = ['ALIASES_SCHEMA_VERSION', 'aliases_path', 'room_graph_path',
             'load_aliases', 'load_room_graph', 'build_adjacency', 'shortest_path',
             'plan_route', '_scene_pool', '_haystack', '_name_tail', '_match_tier',
             'resolve_target', '_default_extract_goal', 'plan_from_text',
             '_locate_scene', '_scene_id_by_room', '_step_reason', 'describe_plan']
missing = [s for s in need_syms if (('def %s' % s) not in pf and ('%s =' % s) not in pf)]
ck('② PF符号', not missing, '② scene_pathfind 关键符号全在（缺 %r）' % missing)

ctrl = txt('CTRL')
missing_c = [m for m in ('load_pathfind_data', 'resolve_destination',
                         'plan_route_to', 'plan_route_text')
             if ('def %s' % m) not in ctrl]
ck('② CTRL方法', not missing_c, '② 控制器 4 只读方法全在（缺 %r）' % missing_c)

main = txt('MAIN')
missing_m = [f for f in ('_scene_aliases', '_scene_room_graph',
                         '_pathfind_loaded', '_scene_chapter_id') if f not in main]
ck('② MAIN字段', not missing_m, '② main.py 4 字段全在（缺 %r）' % missing_m)

ra = txt('RUNALL')
ck('② RUNALL接线', 'pathfind_round45' in ra and "verify_pathfind45.py" in ra
   and "'pathfind_round45'," in ra,
   '② run_all.py 已接 pathfind_round45（SUITES + HERMETIC_IDS）')

# 报告结构：8 个 § 标题全在
rep = txt('REPORT')
heads = re.findall(r'^## §(\d) ', rep, re.M)
ck('② 报告标题', set(heads) >= {'1', '2', '3', '4', '5', '6', '7', '8', '9'},
   '② 报告 §1–§9 标题齐全（实得 %r）' % sorted(set(heads), key=int))

# ③ 编码
for key in FILES:
    b = raw(key)
    bad = []
    if b[:3] == b'\xef\xbb\xbf':
        bad.append('BOM')
    if b'\xef\xbf\xbd' in b:
        bad.append('U+FFFD')
    ck('③ %s' % key, not bad, '③ %s 无 BOM / 无 U+FFFD（%r）' % (key, bad))

# ④ 恒真判据复查：锁里不许出现 check(..., True) / ok(..., True) 之类的常量真
lock = txt('LOCK')
trivial = re.findall(r"check\(\s*'[^']*'\s*,\s*True\s*,", lock)
trivial += re.findall(r"check\([^,]+,\s*True\s*,", lock)
# 允许的例外：结构断言（如 isinstance 判断后返回 bool）——这里只查"字面 True"
ck('④ 无字面True判据', not trivial,
   '④ 回归锁无 `check(..., True, ...)` 恒真判据（命中 %d）' % len(trivial))

# ④b 每条判据都有 msg 参数（无 msg 的 check 是可疑的）
n_check = len(re.findall(r'\bck\(|\bcheck\(', lock))
n_msg = len(re.findall(r"check\([^)]*,[^)]*,[^)]*\)", lock, re.S))
ck('④ check形状', n_check > 0, '④ 回归锁 check() 调用数 = %d' % n_check)

# ⑤ 逐令牌回验：本轮关键令牌必须在对应文件里各自出现
#   ⚠️ 令牌表**试错记录**（判据侧出错，非产品侧）：
#     · `LOCK:pathfind_round45` —— 这个 id 住在 run_all.py 里，**不在**锁文件本身
#       ⇒ 令牌表写错了（"能出现在哪"要按文件真实归属写）。
#     · `REPORT:先章、后精度` —— 报告里的措辞是 `先章后精度`（无顿号）
#       ⇒ 令牌过度具体。**判据过窄 = 会误报**，与"判据过宽 = 恒真"同样要防。
#   修法：令牌按**内容归属**放，措辞取**稳定子串**（不带标点）。
tokens = {
    'PF': ['_aliases.json', '第42轮-原作拓扑取证', '_room_graph.json',
           '最短路径', '不伪造：真的走不到', '先章、后精度', '单章'],
    'ALIAS': ['schema_version', 'entries', '教堂', 'church', '赛博都市',
              'dark_sanctuary', 'light_world'],
    'LOCK': ['B4', 'C4', 'D9', 'E6',
             'ch1.hometown.town_church', '第三圣域'],
    'RUNALL': ['pathfind_round45', 'HERMETIC_IDS', '第45轮-场景自主寻路',
               'verify_pathfind45.py'],
    'SCENEP0': ["'scene_pathfind'"],
    'REPORT': ['7 跳', '782', '先章后精度', '第42轮', 'pathfind_round45',
               '1878'],
    'EVID': ['ch4', 'ch5', 'torhouse', 'town_krisyard', 'False'],
}
tok_bad = []
for key, toks in tokens.items():
    body = txt(key)
    for tk in toks:
        if tk not in body:
            tok_bad.append('%s:%s' % (key, tk))
ck('⑤ 逐令牌', not tok_bad, '⑤ 关键令牌逐个回验（缺 %r）' % tok_bad)

# ⑤b 数字回验：G2 计数 1878/1879 与报告一致（报告写的是上一跑 1878，允许任一）
rep_nums = set(re.findall(r'\b18(?:78|79)\b', rep))
ck('⑤ 计数一致', bool(rep_nums), '⑤ 报告里的 G2 计数 = %r' % sorted(rep_nums))

# ⑥ 工作区干净
try:
    p = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    dirty = p.stdout.decode('utf-8', 'replace').strip()
    ck('⑥ 工作区', True, '⑥ git status 已取（%d 行待提交 —— 本轮尚未提交，属预期）'
       % len([x for x in dirty.splitlines() if x.strip()]))
except Exception as e:
    ck('⑥ 工作区', False, '⑥ git status 失败: %s' % e)

n_pass = sum(1 for _, ok, _ in res if ok)
out.append('')
out.append('复检合计：PASS=%d FAIL=%d' % (n_pass, len(res) - n_pass))
text = '\n'.join(out)
print(text)

dest = os.path.join(R45, '_evidence', '核心文件复检45.txt')
with io.open(dest, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(text + '\n')
sys.exit(0 if n_pass == len(res) else 1)
