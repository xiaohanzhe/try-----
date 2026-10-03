# -*- coding: utf-8 -*-
"""第82轮核心文件复检 —— 六类判据，逐项 PASS/FAIL 落盘。

改过的核心文件：
  1. ralsei_pet/src/main.py        （R5 接线，+326/−10）
  2. ralsei_pet/modules/possession.py（新建，569 行）
  3. code-quality-audit/regress/run_all.py（--update 预登记键集）
  4. code-quality-audit/regress/baseline.json（重固，套件 73→74）
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))

_files = {
    'main': os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    'poss': os.path.join(ROOT, 'ralsei_pet', 'modules', 'possession.py'),
    'runall': os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    'baseline': os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json'),
}

_lines = []
P = F = 0


def chk(tag, cond):
    global P, F
    if cond:
        P += 1
        _lines.append('[PASS] %s' % tag)
    else:
        F += 1
        _lines.append('[FAIL] %s' % tag)


def rd(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def raw(p):
    with open(p, 'rb') as fh:
        return fh.read()


_lines.append('=== 第82轮核心文件复检 ===')
_lines.append('')

# ---- ① 可编译（AST，不产 .pyc） ----
for k in ('main', 'poss', 'runall'):
    if os.path.exists(_files[k]):
        try:
            ast.parse(rd(_files[k]))
            chk('① 可编译 %s' % k, True)
        except SyntaxError as e:
            chk('① 可编译 %s（%s）' % (k, e), False)

# ---- ② 结构自检：possession.py 关键定义齐全、无粘连 ----
_psrc = rd(_files['poss'])
for sym in ('CONFIRM_KEY', 'HERO_SPEED_PX', 'TURN_BACK_STEP', 'MODE_FREE',
            'MODE_ASKING', 'MODE_POSSESSED', 'MODE_REFUSED', 'KIND_DIRECT',
            'KIND_CONSENT', 'KIND_FORBIDDEN', 'POSSESSION_KINDS'):
    chk('② possession 常量 %s' % sym, sym in _psrc)
for fn in ('def kind_of', 'def is_possessable', 'def needs_consent',
           'def target_from_registry', 'def build_targets', 'def describe_mode',
           'def _entry_get'):
    chk('② possession 函数 %s' % fn, fn in _psrc)
for m in ('def request', 'def grant', 'def refuse', 'def stop',
          'def release_key', 'def release_all', 'def clear_keys',
          'def press', 'def drive', 'def clamp_to', 'def describe'):
    chk('② PossessionState 方法 %s' % m, m in _psrc)

# ---- ③ 无 BOM / 无 U+FFFD ----
for k, p in _files.items():
    if not os.path.exists(p):
        continue
    b = raw(p)
    chk('③ %s 无 BOM' % k, not b.startswith(b'\xef\xbb\xbf'))
    txt = rd(p)
    chk('③ %s 无 U+FFFD' % k, '\ufffd' not in txt)

# ---- ④ 恒真判据复查：possession.py 里不得有 `if True:` / 恒真断言 ----
_t = ast.parse(_psrc)
_bad_true = []
for n in ast.walk(_t):
    if isinstance(n, ast.If):
        tv = n.test
        if isinstance(tv, ast.Constant) and tv.value is True:
            _bad_true.append(getattr(n, 'lineno', '?'))
chk('④ possession 无 `if True:` 恒真分支（%r）' % _bad_true, not _bad_true)

# main.py R5 段不得有恒真守卫
_msrc = rd(_files['main'])
_r5 = _msrc[_msrc.find('POSSESSION_ENABLED'):]
chk('④ main R5 段无 `if True:`', 'if True:' not in _r5)

# ---- ⑤ 逐令牌回验：报告/记忆里引用的关键令牌逐个回原文件 in 一次 ----
_tokens = {
    'main': ['POSSESSION_ENABLED', 'init_possession', 'toggle_possession',
             'FOCUS_OUT' if False else 'focusOutEvent', '_possession_tick',
             '_possession_play_squeak', 'snd_squeak',
             'from modules import possession as possession_mod'],
    'poss': ['HERO_SPEED_PX = 3.0', 'TURN_BACK_STEP = 2.0', 'FRAME_HZ = 30',
             'MAX_DT = 0.1', "CONFIRM_KEY = 'z'", "'os_niko': KIND_CONSENT",
             "'kris': KIND_DIRECT", "'ut_frisk': KIND_DIRECT"],
    'runall': ['PENDING_UPDATE', '预登记新套件进基线键集'],
}
for k, toks in _tokens.items():
    src = rd(_files[k])
    for tk in toks:
        chk('⑤ 令牌回验 %s ⇐ %r' % (k, tk), tk in src)

# ---- ⑥ 工作区/基线自洽 ----
try:
    bl = json.loads(rd(_files['baseline']))
    n = len(bl.get('suites') or {})
    chk('⑥ baseline 套件数 == 74（实得 %d）' % n, n == 74)
    chk('⑥ baseline 含 check82', 'check82' in (bl.get('suites') or {}))
    # 无残留哨兵
    _pend = [k for k, v in (bl.get('suites') or {}).items()
             if v.get('sha256') == 'PENDING_UPDATE']
    chk('⑥ baseline 无残留 PENDING_UPDATE 哨兵（%r）' % _pend, not _pend)
except Exception as e:
    chk('⑥ baseline 可解析（%s）' % e, False)

# ---- 额外：磁盘文件数实证（"写了 N 个文件"必须查磁盘） ----
_e = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_evidence')
_tl = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_tools')
_e_n = len([x for x in os.listdir(_e)]) if os.path.isdir(_e) else -1
_t_n = len([x for x in os.listdir(_tl)]) if os.path.isdir(_tl) else -1
chk('额外 _evidence 目录存在且非空（%d 个）' % _e_n, _e_n > 0)
chk('额外 _tools 目录存在且非空（%d 个）' % _t_n, _t_n > 0)
chk('额外 check82.py 在盘',
    os.path.exists(os.path.join(_tl, 'check82.py')))
chk('额外 live_r5_82.py 在盘',
    os.path.exists(os.path.join(_tl, 'live_r5_82.py')))

_lines.append('')
_lines.append('=' * 60)
_lines.append('结果：PASS=%d FAIL=%d' % (P, F))
if F:
    _lines.append('失败项：%s' % [l for l in _lines if l.startswith('[FAIL]')])
_lines.append('=' * 60)

OUT = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_evidence',
                   'recheck82.txt')
io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines) + '\n')
print('\n'.join(_lines))
print('written:', OUT)
sys.exit(0 if F == 0 else 1)
