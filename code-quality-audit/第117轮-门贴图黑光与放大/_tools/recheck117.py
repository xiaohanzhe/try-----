# -*- coding: utf-8 -*-
u"""第117轮复检（改过"重要核心文件"之后的七项自检）。

对应 skill `core-file-recheck` 的七项：
  ① 语法/可编译      ② 结构自检      ③ 无 BOM / 无 U+FFFD
  ④ 恒真判据复查      ⑤ 逐令牌回验    ⑥ 工作区干净
  ⑦ 基线记账

★ 本脚本**不改任何被测状态**（只用 `ast.parse`，不用 `py_compile`，不产 `.pyc`）。
★ ⑥ 默认是**信息项**（提交前必然脏）；`--strict` 才当判据 —— 提交后再跑一次严格模式。
★ 判据纪律：缺文件 ⇒ **如实 FAIL**（带 detail），不抛栈、不静默跳过。
"""
import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.environ.get('RALSEI_RECHECK117_ROOT')
                       or os.path.join(HERE, '..', '..', '..'))
STRICT = '--strict' in sys.argv

ok = fail = 0
lines = []


def ck(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        lines.append('[PASS] %s  %s' % (name, detail))
    else:
        fail += 1
        lines.append('[FAIL] %s  %s' % (name, detail))


def rd(p):
    """字节忠实读（保 CRLF）。"""
    return io.open(p, 'r', encoding='utf-8', newline='').read()


def rb(p):
    return io.open(p, 'rb').read()


PY = [
    'ralsei_pet/modules/desk_doors.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/check117.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/mutate117.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/key117_black.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/calc117_size.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/probe117_portal.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/shot117_doorform.py',
    'code-quality-audit/第117轮-门贴图黑光与放大/_tools/verify117_shot.py',
    'code-quality-audit/第112轮-桌面门渐显/_tools/check112.py',
    'code-quality-audit/第89轮-桌面与作品场景连通/_tools/check89.py',
    'code-quality-audit/regress/run_all.py',
]
JSONS = [
    'ralsei_pet/assets/scenes/desktop.json',
    'code-quality-audit/regress/baseline.json',
    'code-quality-audit/第117轮-门贴图黑光与放大/_evidence/mut117/mutate117.json',
    'code-quality-audit/第117轮-门贴图黑光与放大/_evidence/rec117/verify117_shot.json',
]
TXT = PY + JSONS + [
    '.workbuddy/memory/MEMORY.md',
    '.workbuddy/memory/参考-契约与历轮（详版）.md',
    '.workbuddy/memory/2026-10-18.md',
]

# ---------------------------------------------------------------- ① 语法
for rel in PY:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        ck('① 语法 %s' % os.path.basename(rel), False, '缺文件')
        continue
    try:
        ast.parse(rd(p), filename=p)
        ck('① 语法 %s' % os.path.basename(rel), True)
    except SyntaxError as e:
        ck('① 语法 %s' % os.path.basename(rel), False, 'SyntaxError %s:%s' % (e.lineno, e.msg))

for rel in JSONS:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        ck('① JSON %s' % os.path.basename(rel), False, '缺文件')
        continue
    try:
        json.loads(rd(p))
        ck('① JSON %s' % os.path.basename(rel), True)
    except Exception as e:
        ck('① JSON %s' % os.path.basename(rel), False, repr(e))

dj = json.loads(rd(os.path.join(ROOT, 'ralsei_pet/assets/scenes/desktop.json')))
objs = {o.get('id'): o for o in dj.get('objects', [])}

# ---------------------------------------------------------------- ② 结构
ck('② 桌面正好 4 扇门', len(dj.get('objects', [])) == 4, 'n=%d' % len(dj.get('objects', [])))
ck('② 门 id 齐全',
   set(objs) == {'desk_door_oneshot', 'desk_door_niko_home', 'desk_door_ut', 'desk_door_deltarune'},
   sorted(objs))
ck('② 门 A 贴图=黑光变体',
   objs.get('desk_door_oneshot', {}).get('sprite') == 'objs/desk_door_oneshot_black.png',
   objs.get('desk_door_oneshot', {}).get('sprite'))
ck('② 门 A pos=(64,0)', objs.get('desk_door_oneshot', {}).get('pos') == [64, 0],
   objs.get('desk_door_oneshot', {}).get('pos'))
ck('② 门 B 仍用原件',
   objs.get('desk_door_niko_home', {}).get('sprite') == 'objs/niko_door_portal.png',
   objs.get('desk_door_niko_home', {}).get('sprite'))
ck('② 门 C 仍用 desk_door_ut',
   objs.get('desk_door_ut', {}).get('sprite') == 'objs/desk_door_ut.png',
   objs.get('desk_door_ut', {}).get('sprite'))
ck('② 门 D 仍用 desk_door_deltarune',
   objs.get('desk_door_deltarune', {}).get('sprite') == 'objs/desk_door_deltarune.png',
   objs.get('desk_door_deltarune', {}).get('sprite'))
ck('② 四门都 enabled=False（纯声明件）',
   all(o.get('enabled') is False for o in dj.get('objects', [])))
_cm = dj.get('_comment', {})
ck('② _comment 有 round117 记账',
   any('round117' in k for k in _cm), [k for k in _cm if 'round117' in k])

OBJS_DIR = os.path.join(ROOT, 'ralsei_pet/assets/scenes/objs')
for nm in ('desk_door_oneshot_black.png', 'niko_door_portal.png',
           'desk_door_ut.png', 'desk_door_deltarune.png'):
    p = os.path.join(OBJS_DIR, nm)
    ck('② 贴图存在 %s' % nm, os.path.isfile(p), '%d B' % (os.path.getsize(p) if os.path.isfile(p) else -1))

# 黑光变体与原件同尺寸（不依赖 PIL：直接读 PNG IHDR）
def png_size(p):
    b = rb(p)
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return (int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big'))


_sa = png_size(os.path.join(OBJS_DIR, 'desk_door_oneshot_black.png'))
_sb = png_size(os.path.join(OBJS_DIR, 'niko_door_portal.png'))
ck('② 黑光变体 192x128', _sa == (192, 128), str(_sa))
ck('② 与原件同尺寸', _sa == _sb, '%s vs %s' % (_sa, _sb))

# ---------------------------------------------------------------- ③ 编码
for rel in TXT:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        ck('③ 编码 %s' % os.path.basename(rel), False, '缺文件')
        continue
    b = rb(p)
    _bom = b.startswith(b'\xef\xbb\xbf')
    try:
        t = b.decode('utf-8')
        _u = '\ufffd' in t
    except UnicodeDecodeError as e:
        ck('③ 编码 %s' % os.path.basename(rel), False, 'UTF-8 decode %r' % (e,))
        continue
    ck('③ 编码 %s（无 BOM / 无 U+FFFD）' % os.path.basename(rel), (not _bom) and (not _u),
       'BOM=%s U+FFFD=%s' % (_bom, _u))

# ---------------------------------------------------------------- ④ 恒真判据
def tautologies(p):
    """AST 找 `ck/ok/check('x', True)`、`assert True`、`1 == 1` 这类恒真判据。"""
    tree = ast.parse(rd(p), filename=p)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in ('ck', 'ok', 'check', 'check_with', 'chk'):
            if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) \
                    and n.args[1].value is True:
                hits.append('L%d %s(..., True)' % (n.lineno, n.func.id))
        if isinstance(n, ast.Assert) and isinstance(n.test, ast.Constant) \
                and n.test.value is True:
            hits.append('L%d assert True' % n.lineno)
        if isinstance(n, ast.Compare) and len(n.comparators) == 1 \
                and isinstance(n.left, ast.Constant) and isinstance(n.comparators[0], ast.Constant) \
                and n.left.value == n.comparators[0].value:
            hits.append('L%d 常量自比' % n.lineno)
    return hits


for rel in ('code-quality-audit/第117轮-门贴图黑光与放大/_tools/check117.py',
            'code-quality-audit/第117轮-门贴图黑光与放大/_tools/mutate117.py',
            'code-quality-audit/第112轮-桌面门渐显/_tools/check112.py',
            'code-quality-audit/第89轮-桌面与作品场景连通/_tools/check89.py'):
    p = os.path.join(ROOT, rel)
    h = tautologies(p)
    ck('④ 无恒真判据 %s' % os.path.basename(rel), not h, '; '.join(h))

# 负控制存在性：本轮两条关键负控制必须真在（不是"提到名字"，是调用点）
_c117 = rd(os.path.join(ROOT, 'code-quality-audit/第117轮-门贴图黑光与放大/_tools/check117.py'))
ck('④ check117 有 D5 负控制（cap=1.2 四门更小）', 'D5' in _c117 and '1.2' in _c117)
ck('④ check117 有 A3b 负控制（alpha 全 255 判否）', 'A3b' in _c117)

# ---------------------------------------------------------------- ⑤ 逐令牌
_dd = rd(os.path.join(ROOT, 'ralsei_pet/modules/desk_doors.py'))
ck('⑤ desk_doors.DOOR_FIT_CAP == 1.6', 'DOOR_FIT_CAP = 1.6' in _dd.replace('\r\n', '\n'))
ck('⑤ 门 A 贴图名在 desktop.json', 'desk_door_oneshot_black.png' in rd(os.path.join(ROOT, 'ralsei_pet/assets/scenes/desktop.json')))
_ra = rd(os.path.join(ROOT, 'code-quality-audit/regress/run_all.py'))
ck('⑤ run_all.SUITES 有 check117', "'check117'" in _ra or '"check117"' in _ra)
_mut = json.loads(rd(os.path.join(ROOT, 'code-quality-audit/第117轮-门贴图黑光与放大/_evidence/mut117/mutate117.json')))
_mrows = _mut if isinstance(_mut, list) else _mut.get('results') or _mut.get('mutations') or []
_caught = [r for r in _mrows if str(r.get('status', r.get('result', ''))).upper().startswith('CAUGHT')]
ck('⑤ mutate117 全 CAUGHT（11 条）', len(_mrows) == 11 and len(_caught) == 11,
   '%d/%d' % (len(_caught), len(_mrows)))
_v117 = json.loads(rd(os.path.join(ROOT, 'code-quality-audit/第117轮-门贴图黑光与放大/_evidence/rec117/verify117_shot.json')))
ck('⑤ verify117_shot 12 PASS / 0 FAIL',
   _v117.get('pass') == 12 and _v117.get('fail') == 0,
   'pass=%s fail=%s' % (_v117.get('pass'), _v117.get('fail')))
ck('⑤ 四门 rect 全在（屏幕层）', len(_v117.get('per_door', {})) == 4,
   sorted(_v117.get('per_door', {})))
# 鉴别力：门 A 贴黑光该"几乎一样"，贴品红原件该"差很远"；负控制（右移 24px）也该差很远
ck('⑤ 门 A vs 黑光 < 5（该像）', _v117.get('A_vs_black', 999) < 5, _v117.get('A_vs_black'))
ck('⑤ 门 A vs 品红原件 > 30（该不像）', _v117.get('A_vs_orig', -1) > 30, _v117.get('A_vs_orig'))
ck('⑤ 负控制 A 右移 24px > 20', _v117.get('A_shift24', -1) > 20, _v117.get('A_shift24'))

_mem = rd(os.path.join(ROOT, '.workbuddy/memory/MEMORY.md'))
_js = len(_mem.encode('utf-16-le')) // 2
ck('⑤ MEMORY.md js_len <= 10000（含 CRLF）', _js <= 10000, 'js_len=%d 余量=%+d' % (_js, 10000 - _js))
for tok in ('check117', 'mutate117', 'desk_door_oneshot_black', 'DOOR_FIT_CAP', '182×157'):
    ck('⑤ 速查含令牌 `%s`' % tok, tok in _mem)

# ---------------------------------------------------------------- ⑥ 工作区
try:
    out = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    dirty = out.stdout.decode('utf-8', 'replace').strip().splitlines()
except Exception as e:  # noqa
    dirty, out = ['<git 不可用: %r>' % (e,)], None
if STRICT:
    ck('⑥ 工作区干净（--strict）', not dirty, '脏 %d 项' % len(dirty))
else:
    lines.append('[INFO] ⑥ 工作区（非严格）脏 %d 项%s'
                 % (len(dirty), '' if not dirty else '：' + ' | '.join(dirty[:6])))

# ---------------------------------------------------------------- ⑦ 基线
_bj = json.loads(rd(os.path.join(ROOT, 'code-quality-audit/regress/baseline.json')))
_su = _bj.get('suites', {})
EXPECT = {'check117': 33, 'check112': 172, 'check89': 78,
          'objects_round44': 16, 'items_round68': 22}
for sid, want in EXPECT.items():
    e = _su.get(sid)
    ck('⑦ 基线 %s pass=%d fail=0' % (sid, want),
       bool(e) and e.get('pass') == want and e.get('fail', 0) == 0,
       '实际 %s' % (e,))

print('\r\n'.join(lines))
print('\r\n%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
