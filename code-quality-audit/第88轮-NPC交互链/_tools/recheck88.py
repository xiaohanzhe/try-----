# -*- coding: utf-8 -*-
u"""第88轮**自查/复检**（可落盘）：接线 + 零依赖 + 无残留 + 结构完整。

★ 与 `check88` 的分工：`check88` 守**行为与接线**（回归锁，进 `run_all.py`）；
  本脚本守**工程质量**（工作区无残留、模块纪律、可编译）——一次跑完打 PASS/FAIL，
  结果可直接贴进报告。

铁律 6 类判据（skill `core-file-recheck`）：
  ① 可编译 ② 结构自检 ③ 编码（无 BOM / 无 U+FFFD）
  ④ 恒真判据复查 ⑤ 逐令牌回验 ⑥ 工作区干净
"""
import ast
import io
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PKG = os.path.join(ROOT, 'ralsei_pet')
MODULE = os.path.join(PKG, 'modules', 'npc_interact.py')
MAIN = os.path.join(PKG, 'src', 'main.py')
TOOLS = os.path.join(ROOT, 'code-quality-audit', '第88轮-NPC交互链', '_tools')

_fail = []


def chk(name, cond):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', name))
    if not cond:
        _fail.append(name)


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


# ① 可编译（AST，不产 .pyc）
try:
    _mt = ast.parse(_read(MODULE))
    _ok_parse = True
except Exception as e:
    _ok_parse = False
    print('   module parse error: %s' % e)
chk('① npc_interact.py 可解析（ast.parse）', _ok_parse)
chk('① main.py 可解析（ast.parse）', (lambda: (
    ast.parse(_read(MAIN)) is not None))())

# ② 结构自检：模块必须有的顶层定义
if _ok_parse:
    _defs = set()
    _exports = getattr(_mt, 'body', [])
    for n in _exports:
        if isinstance(n, ast.FunctionDef):
            _defs.add(n.name)
    _need = ['ray_rect', 'rect_contains', 'rect_intersects', '_box_of',
             '_normalize_box', 'pick_nearest', 'facing_toward', 'face_actor',
             'resolve', 'describe']
    _missing = [d for d in _need if d not in _defs]
    chk('② 模块顶层函数齐全（%d 个）' % len(_need), not _missing)
    if _missing:
        print('   缺: %r' % _missing)
    # WIRING 常量在
    _names = {t.id for n in _exports if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    chk('② `WIRING` 说明常量存在', 'WIRING' in _names)

# ③ 编码：无 BOM / 无 U+FFFD
for _p, _tag in ((MODULE, 'npc_interact.py'), (MAIN, 'main.py')):
    with io.open(_p, 'rb') as fh:
        _raw = fh.read(3)
    chk('③ %s 无 BOM' % _tag, _raw != b'\xef\xbb\xbf')
    _txt = _read(_p)
    chk('③ %s 无 U+FFFD' % _tag, u'\ufffd' not in _txt)

# ④ 恒真判据复查：check88 里不许有 `check(..., True)` 这种占位
_c88 = _read(os.path.join(TOOLS, 'check88.py'))
_有占位 = False
for _n in ast.walk(ast.parse(_c88)):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'check' and len(_n.args) == 2:
        if isinstance(_n.args[1], ast.Constant) and _n.args[1].value is True:
            _有占位 = True
chk('④ check88 无 `check(..., True)` 恒真占位', not _有占位)

# ⑤ 逐令牌回验：本轮新增/改动的关键令牌必须在盘
_tokens = [
    (MODULE, 'def ray_rect('),
    (MODULE, 'DARKZONE_DARK = 1'),
    (MODULE, 'MIN_RAY_THICK'),
    (MODULE, 'if dx == 0.0 and dy == 0.0:'),
    (MAIN, 'import npc_interact as npc_interact_mod'),
    (MAIN, 'self._interact_facing = npc_interact_mod.FACE_DOWN'),
    (MAIN, 'def _npc_interact_pick(self):'),
    (MAIN, 'def _npc_face_actor(self, npc_id, face):'),
    (MAIN, 'def _npc_interact_speak(self, npc_id):'),
]
_bad_tok = []
for _p, _t in _tokens:
    if _t not in _read(_p):
        _bad_tok.append(_t)
chk('⑤ 本轮 %d 个关键令牌逐条在盘' % len(_tokens), not _bad_tok)
if _bad_tok:
    print('   缺: %r' % _bad_tok)
# 残留检查：不存在的旧方法名不许出现
chk('⑤ 无 `_npc_show_line` 残留（写错的方法名已清）',
    '_npc_show_line' not in _read(MAIN))

# 零依赖纪律：模块顶层只 import 标准库、函数体内零 import
_top = []
_fn_imp = []
for n in _mt.body:
    if isinstance(n, ast.Import):
        _top += [a.name.split('.')[0] for a in n.names]
    elif isinstance(n, ast.ImportFrom):
        _top.append((n.module or '').split('.')[0])
for fn in [x for x in ast.walk(_mt) if isinstance(x, ast.FunctionDef)]:
    for sub in fn.body:
        for x in ast.walk(sub):
            if isinstance(x, (ast.Import, ast.ImportFrom)):
                _fn_imp.append(fn.name)
chk('零依赖：顶层只 import 标准库 %r' % sorted(set(_top)),
    set(_top) <= {'logging', 'math', 'collections'})
chk('零依赖：函数体内零 import', not _fn_imp)

# ⑥ 工作区干净（只报，不判红 —— 报告期本来就有未提交改动）
_r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                    capture_output=True)
_out = (_r.stdout or b'').decode('utf-8', 'replace').strip()
print('⑥ git status --porcelain 行数: %d（报告期允许非空）'
      % (len(_out.splitlines()) if _out else 0))
for _l in _out.splitlines()[:20]:
    print('   ', _l)

print('=' * 66)
print('recheck88: FAIL %d 项 %s' % (len(_fail), _fail if _fail else ''))
print('=' * 66)
sys.exit(0 if not _fail else 1)
