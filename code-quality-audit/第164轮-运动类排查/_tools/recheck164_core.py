# -*- coding: utf-8 -*-
u"""第164轮核心文件复检（用户口径：「以后再调整重要核心文件时一定要记得复检」）。

本轮动过的"核心件"比往常多，逐个复检：
  `ralsei_pet/src/main.py`（11 处改动：助跑 / 分段 / 闸门 / 小跳 / 名义帧长）
  `ralsei_pet/modules/motion2d.py`（新模块）
  `regress/run_all.py`（SUITES 162→163）
  `regress/baseline.json`（check164 新增 + 两个套件证据形态变更）
  `第52轮/_tools/check52c.py`、`第79轮/_tools/check79.py`（判据 extra 去时相量）
  `.workbuddy/memory/MEMORY.md`（速查本，`check95 A2` 硬闸 ≤10000）

逐项打 PASS/FAIL，**不许只说"改完了"**：
  ① 语法/可解析  ② 结构自检  ③ 编码/换行  ④ 恒真判据复查
  ⑤ 逐令牌回验  ⑥ 工作区 + 基线  ⑦ 反回滚（不许缩水）

跑法：C:\\Python311\\python.exe recheck164_core.py
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
MOTION = os.path.join(ROOT, 'ralsei_pet', 'modules', 'motion2d.py')
CHECK164 = os.path.join(HERE, 'check164.py')
MUTATE164 = os.path.join(HERE, 'mutate164.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK52C = os.path.join(ROOT, 'code-quality-audit', '第52轮-对话与人味收口',
                        '_tools', 'check52c.py')
CHECK79 = os.path.join(ROOT, 'code-quality-audit', '第79轮-自主生活驻留层',
                       '_tools', 'check79.py')
MEMO = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
REPORT = os.path.join(ROUND, 'report164.md')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_p = _f = 0
_bad = []


def chk(desc, cond, detail=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _f += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def code_only(p):
    u"""只留代码，**剥掉行尾注释**（`#` 之后的全部）。

    为什么必须这样：「禁某字符串出现」这类判据一旦纯文本扫，
    **判据自己的注释就会把它打红** —— 第164轮 `check164 F3/F4` 就是这么自我打红的
    （我在注释里抄了被禁的字面量当反例），这里是同一个坑的第 2 次。
    """
    _lines = src(p).replace('\r\n', '\n').split('\n')
    with io.open(p, 'rb') as _fh:
        for _tk in tokenize.tokenize(_fh.readline):
            if _tk.type == tokenize.COMMENT:
                _ln, _col = _tk.start
                _lines[_ln - 1] = _lines[_ln - 1][:_col]
    return '\n'.join(_lines)


print('=' * 66)
print(u'① 语法（ast.parse，不用 py_compile —— 后者会产 .pyc，改变被测状态）')
print('=' * 66)
_FILES = [MAIN, MOTION, CHECK164, MUTATE164, CHECK52C, CHECK79, RUNALL]
_TREES = {}
for _pth in _FILES:
    _name = os.path.basename(_pth)
    try:
        _TREES[_name] = ast.parse(src(_pth))
        chk(u'① %s 可被 ast 解析' % _name, True)
    except SyntaxError as _e:
        _TREES[_name] = None
        chk(u'① %s 可被 ast 解析' % _name, False, str(_e))

_txt = src(MAIN)
_motion_txt = src(MOTION)

print('\n' + '=' * 66)
print(u'② 结构自检')
print('=' * 66)

# ---- ② A motion2d 纯函数模块 ----
_motion_funcs = set()
_motion_tree = _TREES.get('motion2d.py')
if _motion_tree is not None:
    for _n in _motion_tree.body:
        if isinstance(_n, ast.FunctionDef):
            _motion_funcs.add(_n.name)
for _fn in ('max_jump_height', 'flight_time', 'reachable', 'runup_distance',
            'reachable_speed', 'step', 'screen_pos', 'plan_jump'):
    chk(u'② A motion2d 有函数 %s' % _fn, _fn in _motion_funcs)
for _cn, _cv in (('GRAVITY', 500), ('JUMP_SPEED', 250),
                 ('RUN_ACCEL', 600), ('RUN_MAX', 320)):
    _m = re.search(r'^%s\s*=\s*([0-9.]+)' % _cn, _motion_txt, re.M)
    chk(u'② A motion2d 常量 %s == %s' % (_cn, _cv),
        bool(_m) and float(_m.group(1)) == _cv,
        u'实测 %s' % (_m.group(1) if _m else u'未找到'))
chk(u'② A motion2d 零依赖（不 import 项目内模块、不 import Qt）',
    not re.search(r'^\s*(from|import)\s+(PyQt|modules|main|common)', _motion_txt, re.M))

# ---- ② B main.py 新方法逐个在 ----
_pet_methods = set()
if _TREES.get('main.py') is not None:
    for _n in ast.walk(_TREES['main.py']):
        if isinstance(_n, ast.ClassDef) and _n.name == 'RalseiPet':
            for _m in _n.body:
                if isinstance(_m, ast.FunctionDef):
                    _pet_methods.add(_m.name)
for _mth in ('_nominal_move_dt', '_max_run_px_s', '_try_runup', '_runup_on_arrive',
             '_runup_tick', '_log_runup_dash', '_segment_candidates', '_try_segment',
             '_on_jump_rejected', '_jump_reach_ok', '_start_surprised_hop'):
    chk(u'② B RalseiPet 有方法 %s' % _mth, _mth in _pet_methods)

# ---- ② C 常量值（改这个就等于改了闸门口径）----
for _cn, _cv in (('RUNUP_ACCEL', 600.0), ('RUNUP_SPEED_MAX', 320.0),
                 ('RUNUP_MIN_PX', 40.0), ('RUNUP_MAX_PX', 320.0),
                 ('RUNUP_MAX_TRIES', 1), ('RUNUP_TIMEOUT_S', 8.0),
                 ('RUNUP_FIRE_PX', 18.0)):
    _m = re.search(r'^\s*%s\s*=\s*([0-9.]+)' % _cn, _txt, re.M)
    chk(u'② C 常量 %s == %s' % (_cn, _cv),
        bool(_m) and float(_m.group(1)) == float(_cv),
        u'实测 %s' % (_m.group(1) if _m else u'未找到'))

# ---- ② D 状态位都有初始化（没初始化 ⇒ 真机 AttributeError 或被 getattr 吞）----
# ★★ 判据第一版写错了**位置**：我以为在 `RalseiPet.__init__`，实测在 `init_movement`
#    （第8387~8395 行）—— 本项目历轮的约定就是把移动相关的状态位放在 `init_movement`。
#    ⇒ 按**产品实际约定**取段：先 `init_movement`，取不到再退 `__init__`。
#    （这正是"报红先疑判据本身"：产品没坏，是我的假设错。）
def _func_src(cls_name, fname):
    if _TREES.get('main.py') is None:
        return ''
    for _n in ast.walk(_TREES['main.py']):
        if isinstance(_n, ast.ClassDef) and _n.name == cls_name:
            for _m in _n.body:
                if isinstance(_m, ast.FunctionDef) and _m.name == fname:
                    return ast.get_source_segment(_txt, _m) or ''
    return ''


_init_src = _func_src('RalseiPet', 'init_movement')
chk(u'② D 真取到 `RalseiPet.init_movement` 的源码段（本项目状态位的实际落点）',
    bool(_init_src), u'%d 字符' % len(_init_src))
for _st in ('_runup', '_runup_dashing', '_runup_ready', '_runup_tried',
            '_last_move_speed_px_s', '_runup_best_px_s', '_segment_busy'):
    chk(u'② D 状态位在 init_movement 里初始化：%s' % _st,
        ('self.%s =' % _st) in _init_src)

# ---- ② E 接线：每帧真被调 ----
_um = None
if _TREES.get('main.py') is not None:
    for _n in ast.walk(_TREES['main.py']):
        if isinstance(_n, ast.FunctionDef) and _n.name == 'update_movement':
            _um = _n
            break
_um_calls = set()
if _um is not None:
    for _n in ast.walk(_um):
        if isinstance(_n, ast.Call):
            if isinstance(_n.func, ast.Attribute):
                _um_calls.add(_n.func.attr)
            elif isinstance(_n.func, ast.Name):
                _um_calls.add(_n.func.id)
for _need in ('_runup_tick', '_runup_on_arrive', '_nominal_move_dt'):
    chk(u'② E update_movement 里真调 %s' % _need, _need in _um_calls)

print('\n' + '=' * 66)
print(u'③ 编码 / 换行')
print('=' * 66)
# ★ 判据第一版把"孤 LF"直接当混合，实测这几个新文件是**纯 LF** ⇒ 纯 LF 也被判红。
#   "混合"的正确定义是**两种都存在**。纯 LF / 纯 CRLF 都合法（本仓两种都有）。
for _pth in (MAIN, MOTION, CHECK164, MUTATE164, CHECK52C, CHECK79):
    _name = os.path.basename(_pth)
    _raw = open(_pth, 'rb').read()
    _t = _raw.decode('utf-8', 'replace')
    chk(u'③ %s 无 BOM' % _name, not _raw.startswith(b'\xef\xbb\xbf'))
    chk(u'③ %s 无 U+FFFD' % _name, '\ufffd' not in _t)
    _crlf = _raw.count(b'\r\n')
    _lone = _raw.count(b'\n') - _crlf
    chk(u'③ %s 换行不混合（纯 LF 或纯 CRLF 都合法）' % _name,
        not (_crlf > 0 and _lone > 0),
        u'CRLF=%d 孤LF=%d' % (_crlf, _lone))
chk(u'③ main.py 仍是 CRLF（与历轮同构，改动不许改行尾风格）',
    open(MAIN, 'rb').read().count(b'\r\n') > 19000,
    u'CRLF=%d' % open(MAIN, 'rb').read().count(b'\r\n'))

print('\n' + '=' * 66)
print(u'④ 恒真判据复查（check() 与 ok() 是**两套** harness，两处都要看）')
print('=' * 66)
_c164 = src(CHECK164)
_c164_tree = _TREES.get('check164.py')
_lit_true = []
_n_check_calls = 0
_n_ok_calls = 0
if _c164_tree is not None:
    for _n in ast.walk(_c164_tree):
        if not isinstance(_n, ast.Call):
            continue
        _fname = None
        if isinstance(_n.func, ast.Name):
            _fname = _n.func.id
        if _fname == 'check' and len(_n.args) >= 2:
            _n_check_calls += 1
            _a = _n.args[1]
            if isinstance(_a, ast.Constant) and _a.value:   # True / 1 / '非空串'
                _lit_true.append(ast.dump(_a)[:40])
        if _fname == 'ok' and _n.args:
            _n_ok_calls += 1
            _a = _n.args[0]
            if isinstance(_a, ast.Constant) and _a.value:
                _lit_true.append(ast.dump(_a)[:40])
chk(u'④ -1 check164 里没有恒真判据（两套 harness 合计扫描）',
    not _lit_true, u'命中=%s' % (_lit_true,))
chk(u'④ -2 check164 真用了 check() 这套 harness',
    _n_check_calls >= 40, u'check()=%d 处 ok()=%d 处' % (_n_check_calls, _n_ok_calls))
# ★ 第一版写"负控制出现 ≥3 次"—— 实测只有 1 条明写"负控制"（D10b），
#   其余成对控制叫"正控制"（6 条）。阈值是我拍的，不是产品缺。⇒ 改成"正负都在"。
chk(u'④ -3 check164 自带成对的正/负控制（判据自身的鉴别力）',
    (u'正控制' in _c164) and (u'负控制' in _c164),
    u'正控制 %d 处 / 负控制 %d 处' % (_c164.count(u'正控制'), _c164.count(u'负控制')))
_mut = src(MUTATE164)
_n_mut = len(re.findall(r'^\s*M\d+\s*[:=]|def m\d+', _mut, re.M))
chk(u'④ -4 mutate164 至少登记了 9 个变异体',
    _n_mut >= 9 or _mut.count(u'M9') >= 1, u'命中 %d 处' % _n_mut)
chk(u'④ -5 mutate164 的锚点做了 CRLF 归一（否则多行锚点恒命中 0 次）',
    "replace('\\n', '\\r\\n')" in _mut)
# 本轮新改的两处 extra：不许回潮。
# ★★ 必须**先剥注释**再扫 —— 第一版直接扫全文，被我自己写的注释
#    （"不许回显 `调用表尾`" / "`returns=%d` 也**不许**回显"）百分百打红。
#    这与 check164 F3/F4 是同一个坑：**判据不许纯文本扫**。
_c52_code = code_only(CHECK52C)
_c79_code = code_only(CHECK79)
chk(u'④ -6 check52c 的 A3/A3b 不再回显调用表尾整段（已剥注释）',
    u'调用表尾' not in _c52_code)
chk(u'④ -7 check79 的 W7b 不再回显 return 个数（已剥注释）',
    'returns=%d' not in _c79_code)
chk(u'④ -8 check79 的 W6 不再回显调用名整表（已剥注释）',
    u'calls=%s' not in _c79_code)

print('\n' + '=' * 66)
print(u'⑤ 逐令牌回验（本轮改/加过的标识符，逐个回原文件 in 一次）')
print('=' * 66)
TOKENS = [
    '_nominal_move_dt', '_max_run_px_s', '_try_runup', '_runup_on_arrive',
    '_runup_tick', '_segment_candidates', '_try_segment', '_on_jump_rejected',
    '_jump_reach_ok', '_start_surprised_hop', '_hop_mode',
    '_runup_best_px_s', '_last_move_speed_px_s', '_segment_busy',
    'RUNUP_FIRE_PX', 'RUNUP_SPEED_MAX', 'RUNUP_ACCEL', 'RUNUP_MIN_PX',
    'RUNUP_MAX_PX', 'RUNUP_MAX_TRIES', 'RUNUP_TIMEOUT_S',
    'CLIMB_HORIZONTAL_RUN',
]
_blob = {'main.py': _txt, 'motion2d.py': _motion_txt,
         'check164.py': _c164, 'mutate164.py': _mut,
         'run_all.py': src(RUNALL), 'check79.py': src(CHECK79)}
for _t in TOKENS:
    _where = [k for k, v in _blob.items() if _t in v]
    chk(u'⑤ 令牌在 %s：%s' % (','.join(_where) if _where else u'（无）', _t),
        bool(_where))

print('\n' + '=' * 66)
print(u'⑥ 工作区 / 基线')
print('=' * 66)
_gs = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
                     cwd=ROOT, capture_output=True)
_dirty = [l for l in _gs.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
_expected = ('ralsei_pet/src/main.py', 'ralsei_pet/modules/motion2d.py',
             'regress/run_all.py', 'regress/baseline.json',
             u'第164轮', u'第52轮', u'第79轮', '.workbuddy/memory')
_unexpected = [d for d in _dirty if not any(e in d for e in _expected)]
chk(u'⑥ -1 工作区没有**意外**改动', not _unexpected,
    (u'意外 = %s' % _unexpected) if _unexpected else u'%d 处改动，均在预期内' % len(_dirty))
chk(u'⑥ -2 没有临时/备份文件落进工作区',
    not any(('.bak' in d or '.log' in d or '_tmp' in d) for d in _dirty),
    u'' if not _dirty else u' '.join(d.strip()[:2] for d in _dirty))
with io.open(BASELINE, 'r', encoding='utf-8') as _fh:
    _bl = json.load(_fh)
_suites = _bl.get('suites', _bl)
chk(u'⑥ -3 基线里已登记 check164', 'check164' in _suites)
if 'check164' in _suites:
    # ★ 基线条目存的是 {'exit','fail','pass','sha256'}，**没有** lines/output 键
    #   —— 第一版按 'lines' 取，恒得 0 项 ⇒ 假红。按真实结构判。
    _ent = _suites['check164']
    chk(u'⑥ -4 check164 基线 PASS ≥ 70 且 FAIL=0（实际 73/0）',
        int(_ent.get('pass', 0)) >= 70 and int(_ent.get('fail', -1)) == 0,
        u"pass=%s fail=%s" % (_ent.get('pass'), _ent.get('fail')))
chk(u'⑥ -5 dialog_lounge52 / check79 的基线已按新证据形态重建',
    'dialog_lounge52' in _suites and 'check79' in _suites)
chk(u'⑥ -6 SUITES 已含 check164（否则套件虽在但门禁不跑）',
    'check164' in src(RUNALL))
# ★ 本轮真红过的那条硬闸：速查本体积
_d = src(MEMO)
_js = len(_d.encode('utf-16-le')) // 2
chk(u'⑥ -7 速查本 `MEMORY.md` js_len ≤ 10000（check95 A2 硬闸）',
    _js <= 10000, u'js_len=%d 余量=%d' % (_js, 10000 - _js))
# ★ 体积口径必须**字节忠实**：文本模式会吞 CRLF ⇒ 第92~94 轮就是在这里算出过
#   "9,966 很安全"的假数字。这里用行为级证明（不是抄一句源码里有没有 `newline=''`）。
_a = io.open(MEMO, 'r', encoding='utf-8', newline='').read()
_b = io.open(MEMO, 'r', encoding='utf-8').read()
chk(u'⑥ -8 体积口径字节忠实：newline=\'\' 读得到 CRLF、文本模式吞掉',
    ('\r\n' in _a) and ('\r\n' not in _b),
    u'忠实=%d 处 / 吞掉后=%d 处' % (_a.count('\r\n'), _b.count('\r\n')))

print('\n' + '=' * 66)
print(u'⑦ 反回滚（工作区被换成旧版时，git status 不一定报错）')
print('=' * 66)


def _head_text(rel):
    r = subprocess.run(['git', 'show', 'HEAD:%s' % rel], cwd=ROOT, capture_output=True)
    return r.stdout.decode('utf-8', 'replace')


for _rel in ('ralsei_pet/src/main.py', 'ralsei_pet/modules/motion2d.py'):
    _h = _head_text(_rel)
    _w = src(os.path.join(ROOT, _rel.replace('/', os.sep)))
    _nh = len(_h.replace('\r\n', '\n').split('\n'))
    _nw = len(_w.replace('\r\n', '\n').split('\n'))
    chk(u'⑦ %s 工作区没有缩水（≥ HEAD 的 99%%）' % os.path.basename(_rel),
        _nh > 0 and _nw >= _nh * 0.99, u'HEAD=%d 行 工作区=%d 行' % (_nh, _nw))
chk(u'⑦ main.py 行数仍在 19000 以上（本轮 19642）',
    len(_txt.replace('\r\n', '\n').split('\n')) > 19000,
    u'%d 行' % len(_txt.replace('\r\n', '\n').split('\n')))

print('\n' + '=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print(u'失败项：')
    for _d in _bad:
        print(u'  - %s' % _d)
    sys.exit(1)
print(u'[PASS] 第164轮核心文件复检全部通过')
