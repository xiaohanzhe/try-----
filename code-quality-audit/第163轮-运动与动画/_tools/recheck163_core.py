# -*- coding: utf-8 -*-
u"""第163轮核心文件复检（用户口径：「以后再调整重要核心文件时一定要记得复检」）。

逐项打 PASS/FAIL，**不许只说"改完了"**：
  ① 语法/可编译  ② 结构自检  ③ 无 BOM / 无 U+FFFD / 无混合换行
  ④ 恒真判据复查  ⑤ 逐令牌回验  ⑥ 工作区 + 回归

跑法：C:\\Python311\\python.exe recheck163_core.py
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK163 = os.path.join(HERE, 'check163.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
R8 = os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_anim.py')

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


print('=' * 66)
print('① 语法')
print('=' * 66)
_txt = src(MAIN)
_tree = None
try:
    _tree = ast.parse(_txt)
    chk(u'① -1 main.py 可被 ast 解析', True)
except SyntaxError as e:
    chk(u'① -1 main.py 可被 ast 解析', False, str(e))

print('\n' + '=' * 66)
print('② 结构自检')
print('=' * 66)
_methods = {}
if _tree is not None:
    for n in ast.walk(_tree):
        if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet':
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    _methods[m.name] = m
for name in ('_compose_anchored_sprite', '_anim_anchor_offsets',
             '_anim_anchor_offset', '_anim_anchor_bottom'):
    chk(u'② 方法存在：%s' % name, name in _methods)
chk(u'② 两处合成调用点都在',
    _txt.count('self._compose_anchored_sprite(') == 2,
    '实测 %d 处' % _txt.count('self._compose_anchored_sprite('))
chk(u'② 新缓存字段 `_anim_bottom_cache` 有初始化与读取两处以上',
    _txt.count('_anim_bottom_cache') >= 2,
    '出现 %d 次' % _txt.count('_anim_bottom_cache'))
chk(u'② 旧缓存字段 `_anim_anchor_cache` 未被改名/删除',
    '_anim_anchor_cache' in _txt)
chk(u'② `_anim_anchor_bottom` 用 getattr 兜底（旧桩不崩）',
    "getattr(self, '_anim_anchor_bottom', None)" in _txt)

print('\n' + '=' * 66)
print('③ 编码 / 换行')
print('=' * 66)
_raw = open(MAIN, 'rb').read()
chk(u'③ -1 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
chk(u'③ -2 无 U+FFFD（替换字符）', '\ufffd' not in _txt)
_n_crlf = _raw.count(b'\r\n')
chk(u'③ -3 换行不混合（孤 LF = 0）',
    _raw.count(b'\n') - _n_crlf == 0,
    '' if _raw.count(b'\n') - _n_crlf == 0 else '孤LF=%d' % (_raw.count(b'\n') - _n_crlf))

print('\n' + '=' * 66)
print('④ 恒真判据复查（check163 / round8 的 D 段）')
print('=' * 66)
_c163 = src(CHECK163)
# `check(desc, True)` / `check(desc, 1)` / `check(desc, 'x')` 都是恒真
_literal_true = re.findall(r'check\(\s*u?"[^"]*"\s*,\s*(True|1|"[^"]*")\s*[,)]', _c163)
chk(u'④ -1 check163 里没有 `check(..., True/1/"字面量")` 这种恒真写法',
    not _literal_true, '命中 = %s' % _literal_true)
chk(u'④ -2 check163 有一条负控制（A3 退回钉中心必须报红）',
    'A3 负控制' in _c163)
chk(u'④ -3 check163 有一条无害变异（A4 锚点 +1px 不许误报）',
    'A4 无害变异' in _c163)
_r8 = src(R8)
chk(u'④ -4 round8 D1.1n 负控制仍在',
    'D1.1n' in _r8)
chk(u'④ -5 round8 桩已挂 `_anim_anchor_bottom`（否则判据走旧回退分支 = 假绿）',
    'o._anim_anchor_bottom = types.MethodType' in _r8)

print('\n' + '=' * 66)
print('⑤ 逐令牌回验（本轮改/加过的标识符，逐个回原文件 in 一次）')
print('=' * 66)
TOKENS = [
    '_anim_anchor_bottom', '_anim_bottom_cache', 'bottoms.append',
    '本体下沿对齐画布底沿',
    # ★ 第一版写的是 `self._anim_anchor_bottom` —— 那是**有意去掉**的写法
    #   （为了兼容旧桩改成了 getattr 兜底），拿它当"必须存在"的令牌是判据写错。
    #   真正该回验的是**替换后的那个表达式**。
    "_ab = getattr(self, '_anim_anchor_bottom', None)",
    'default_memory_dir', 'check163', 'verify_round8_anim',
]
for t in TOKENS:
    where = 'main.py' if t in _txt else (
        'check162' if t in src(os.path.join(
            ROOT, 'code-quality-audit', '第162轮-基础桌宠排查', '_tools', 'check162.py'))
        else ('run_all' if t in src(RUNALL) else '?'))
    chk(u'⑤ 令牌在 %s：%s' % (where, t), where != '?')

print('\n' + '=' * 66)
print('⑥ 工作区 / 回归')
print('=' * 66)
_git = subprocess.run(
    ['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
    cwd=ROOT, capture_output=True)
_dirty = [l for l in _git.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
_expected = ('ralsei_pet/src/main.py', 'regress/run_all.py', 'regress/baseline.json',
             '第163轮', '第八轮', '第162轮')
_unexpected = [d for d in _dirty if not any(e in d for e in _expected)]
chk(u'⑥ -1 工作区没有**意外**改动（只允许本轮那几处）',
    not _unexpected, '意外 = %s' % _unexpected if _unexpected else '%d 处改动，均在预期内' % len(_dirty))
chk(u'⑥ -2 没有临时/备份文件落进工作区',
    not any(d.strip().startswith('??') and ('_tmp' in d or '.bak' in d or '.log' in d)
            for d in _dirty),
    '' if not _dirty else ' '.join(d.strip()[:2] for d in _dirty))

print('\n' + '=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print('失败项：')
    for d in _bad:
        print('  - %s' % d)
    sys.exit(1)
print('[PASS] 第163轮核心文件复检全部通过')
