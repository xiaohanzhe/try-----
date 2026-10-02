# -*- coding: utf-8 -*-
"""第76轮收尾复检（core-file-recheck 六类判据 + 逐令牌回验）。

对象：
  1) 第76轮报告-能走能切与视角跟随灵魂.md
  2) ralsei_pet/src/main.py（R4 改动）
  3) code-quality-audit/regress/baseline.json + run_all.py
  4) code-quality-audit/第76轮-.../_tools/*.py

落盘：_evidence/recheck76.txt
"""
import ast
import io
import json
import os
import re
import subprocess
import sys

# ★ 起点哨兵：若这里没留下痕迹，说明进程在 import 期就被杀了（清理守卫的典型症状）。
try:
    io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_evidence',
                         '_recheck76_start.txt'), 'w', encoding='utf-8',
            newline='\n').write('started\n')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EVID = os.path.join(HERE, '..', '_evidence')
os.makedirs(EVID, exist_ok=True)
OUT = os.path.join(EVID, 'recheck76.txt')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_L = []
_p = _f = 0


def ck(name, cond, extra=''):
    global _p, _f
    if cond:
        _p += 1
        _L.append('[PASS] %s%s' % (name, (' :: ' + extra) if extra else ''))
    else:
        _f += 1
        _L.append('[FAIL] %s%s' % (name, (' :: ' + extra) if extra else ''))


def info(name, extra=''):
    _L.append('#  [info] %s%s' % (name, (' :: ' + extra) if extra else ''))


RPT = os.path.join(ROOT, '第76轮报告-能走能切与视角跟随灵魂.md')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
BASE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
TOOLS = os.path.join(ROOT, 'code-quality-audit', '第76轮-灵魂附身与视角跟随', '_tools')


def read(p, enc='utf-8'):
    with io.open(p, 'r', encoding=enc) as f:
        return f.read()


def read_b(p):
    with open(p, 'rb') as f:
        return f.read()


_L.append('=== 第76轮收尾复检 ===')
_L.append('ROOT = %s' % ROOT)
_L.append('')

# =============================================== 1. 可编译 / 可解析
_L.append('## 1. 可编译 / 可解析')

_py = [MAIN, RUNALL, os.path.join(TOOLS, 'check_r0_76.py'),
       os.path.join(TOOLS, 'check_r4_76.py'),
       os.path.join(TOOLS, 'tamper_r4_76.py'),
       os.path.join(TOOLS, 'live_r4_76.py'),
       os.path.join(TOOLS, 'probe_r0_76.py'),
       os.path.join(TOOLS, 'live_windows76.py')]
for p in _py:
    nm = os.path.basename(p)
    try:
        ast.parse(read(p))          # ★ 不产 .pyc（复检不许改变被测状态）
        ck('1.1 ast.parse %s' % nm, True)
    except Exception as e:
        ck('1.1 ast.parse %s' % nm, False, repr(e))

try:
    _bj = json.loads(read(BASE))
    ck('1.2 baseline.json 可解析', True, 'suites=%d' % len(_bj.get('suites', {})))
except Exception as e:
    ck('1.2 baseline.json 可解析', False, repr(e))

_rpt = read(RPT)
ck('1.3 报告代码围栏成对（按行首数）',
   len(re.findall(r'(?m)^```', _rpt)) % 2 == 0,
   'fences=%d' % len(re.findall(r'(?m)^```', _rpt)))
_L.append('')

# =============================================== 2. 结构自检
_L.append('## 2. 结构自检（报告章节）')
_body = re.sub(r'(?ms)^```.*?^```[ \t]*$', '', _rpt)
_miss = [n for n in range(9) if not re.search(r'^## ' + str(n) + r'\. ', _body, re.M)]
ck('2.1 报告 0~8 章全在', not _miss, '缺失=%r' % (_miss,))
_glued = [i for i, l in enumerate(_body.split('\n'), 1)
          if '##' in l and not l.lstrip().startswith('##')]
ck('2.2 报告无标题粘连', not _glued, '粘连行=%r' % (_glued[:5],))
_h1 = len(re.findall(r'(?m)^# ', _body))
ck('2.3 报告恰 1 个一级标题', _h1 == 1, 'h1=%d' % _h1)
_L.append('')

# =============================================== 3. 编码
_L.append('## 3. 编码')
for p in [RPT, MAIN, BASE, RUNALL] + _py:
    b = read_b(p)
    nm = os.path.basename(p)
    ck('3.1 无 BOM %s' % nm, b[:3] != b'\xef\xbb\xbf')
    ck('3.2 无 U+FFFD %s' % nm, b'\xef\xbf\xbd' not in b)
_L.append('')

# =============================================== 4. 恒真判据复查（AST）
_L.append('## 4. 恒真判据复查（AST + 守卫豁免）')
CK = ('check', 'ck', 'ok', 'expect', 'verify')


def scan_const_true(path):
    t = ast.parse(read(path))
    guarded = set()
    for n in ast.walk(t):
        if isinstance(n, ast.If):
            for st in n.orelse:
                guarded |= {x.lineno for x in ast.walk(st) if hasattr(x, 'lineno')}
    out = []
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and len(n.args) >= 2:
            fn = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
            if fn in CK and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
                if n.lineno not in guarded:
                    out.append(n.lineno)
    return out


for p in _py:
    nm = os.path.basename(p)
    if nm.startswith('live_') or nm.startswith('probe_'):
        info('4.x 跳过真机/探针脚本 %s（无判据函数）' % nm)
        continue
    bad = scan_const_true(p)
    ck('4.1 无未豁免的常量 True 判据 %s' % nm, not bad, '行号=%r' % (bad,))
_L.append('')

# =============================================== 5. 逐令牌回验
_L.append('## 5. 逐令牌回验（本轮改过/引用的关键令牌）')
_toks = [
    # 本轮新增标识符
    '_camera_target_rect', '_screen_point_to_room_rect', 'travel_to',
    'reachable_destinations', 'travel_to_scene', '_travel_feedback_fail',
    'DoorProp', 'door_letter_of', 'route_for_door', 'DOOR_LETTERS',
    # 数据/路径
    '_routes.json', 'cc_prison_cells', 'cc_prisonlancer',
    # 套件名
    'check_r0_76', 'check_r4_76', 'tamper_r4_76', 'live_r4_76',
]
_main = read(MAIN)
_ii = read(os.path.join(ROOT, 'ralsei_pet', 'modules', 'item_interact.py'))
_sc = read(os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_controller.py'))
_run = read(RUNALL)
_all = _main + _ii + _sc + _run
for t in _toks:
    ck('5.1 令牌在位 %s' % t, t in _all)
_L.append('')

# ★ 令牌口径守卫：这些是本轮**新写**的，不该在别处有第二份定义
for t in ['def _camera_target_rect', 'def _screen_point_to_room_rect',
          'def travel_to', 'def door_letter_of', 'def route_for_door',
          'class DoorProp']:
    n = _all.count(t)
    ck('5.2 唯一真源 %s（出现 %d 次）' % (t, n), n == 1)
_L.append('')

# =============================================== 6. R4 关键事实回验
_L.append('## 6. R4 关键事实回验')
ck('6.1 产品不写 soul.state.size()', 'state.size()' not in _main)
ck('6.2 产品写 soul.state.size', 'soul.state.size' in _main)
_se = read(os.path.join(ROOT, 'ralsei_pet', 'modules', 'soul_entity.py'))
_t = ast.parse(_se)
_prop = False
_func = False
for n in ast.walk(_t):
    if isinstance(n, ast.ClassDef) and n.name == 'SoulState':
        for s in n.body:
            if isinstance(s, ast.FunctionDef):
                if s.name == 'size':
                    _prop = any(isinstance(d, ast.Name) and d.id == 'property'
                                for d in s.decorator_list)
                if s.name == 'center':
                    _func = True
ck('6.3 SoulState.size 是 property（真源码 AST）', _prop)
ck('6.4 SoulState.center 是方法（真源码 AST）', _func)
ck('6.5 camera_follow 锚点 = _camera_target_rect',
   len(re.findall(r'camera_follow\([^)]*\)', _main)) == 1
   and '_camera_target_rect(' in re.findall(r'camera_follow\([^)]*\)', _main)[0])
_L.append('')

# =============================================== 7. 基线一致性
_L.append('## 7. 基线一致性')
_suites = _bj['suites']
ck('7.1 baseline 含 check_r0_76', 'check_r0_76' in _suites)
ck('7.2 baseline 含 check_r4_76', 'check_r4_76' in _suites)
ck('7.3 check_r0_76 PASS==38', _suites.get('check_r0_76', {}).get('pass') == 38,
   str(_suites.get('check_r0_76', {}).get('pass')))
ck('7.4 check_r4_76 PASS==21', _suites.get('check_r4_76', {}).get('pass') == 21,
   str(_suites.get('check_r4_76', {}).get('pass')))
_none = [k for k, v in _suites.items() if v is None]
ck('7.5 无 None 条目', not _none, '%r' % (_none,))
_all_fail = sum(v.get('fail', 0) for v in _suites.values() if v)
ck('7.6 基线总 FAIL==0', _all_fail == 0, 'fail=%d' % _all_fail)
info('7.7 套件数 = %d，总 PASS = %d'
     % (len(_suites), sum(v.get('pass', 0) for v in _suites.values() if v)))
_L.append('')

# =============================================== 8. 工作区
_L.append('## 8. 工作区状态')
_r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
                    cwd=ROOT, capture_output=True)
_items = [x for x in _r.stdout.decode('utf-8', 'replace').split('\0') if x.strip()]
info('8.0 变更项 %d 个' % len(_items))
for it in _items:
    info('       %s' % it)
# 负控制：仓库外路径必须被判为意外
_QUIET_OK = ('ralsei_pet/src/main.py', 'regress/baseline.json', 'regress/run_all.py',
             '第76轮报告', '_tools/check_r0_76.py', '_tools/check_r4_76.py',
             '_tools/tamper_r4_76.py', '_tools/live_r4_76.py', '_evidence/')
_bad = [it for it in _items if not any(k in it for k in _QUIET_OK)]
ck('8.1 无意外变更项', not _bad, '%r' % (_bad,))
ck('8.2 负控制：伪造路径必判意外',
   not any(k in 'E:/Download/whatever.txt' for k in _QUIET_OK))
_L.append('')

_L.append('=== 复检：PASS=%d FAIL=%d ===' % (_p, _f))
if _f:
    _L.append('')
    _L.append('## FAIL 明细')
    for l in _L:
        if l.startswith('[FAIL]'):
            _L.append(l)

_txt = '\n'.join(_L)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(_txt)
print(_txt)
print('\nwritten:', OUT)
sys.exit(1 if _f else 0)
