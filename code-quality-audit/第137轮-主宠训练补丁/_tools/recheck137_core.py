# -*- coding: utf-8 -*-
"""第137轮产品侧复检（改过核心文件必须复检 —— user 口径 2026-09-23）。

复检**不改被测状态**：只用 `ast.parse`，不 `py_compile`（会产 `.pyc`，那是改变工作区）。

守什么：
A 语法能过（AST 解析全文件）
B 无 BOM / 无 U+FFFD（编码损坏的两种典型痕迹）
C 三个令牌在位：`PATCH_HEADER_RALSEI` 常量、`_with_ralsei_patch` 定义、**两处**调用
D ★★★ 它是 **模块级函数**（`Module.body` 里的 `FunctionDef`），**不是** `RalseiPet` 的方法
  —— 这条就是本轮的教训 4.2：写成方法后 `s7_event_speech F1` 当场 `AttributeError`
E 注释不与自己打架：lean 分支里"一个字节都不变"这句假断言已删
F 自检：无恒真判据 · 零外部盘

零 Qt（只读源码文本 + AST）、零网络、零外部盘。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
EV = os.path.join(ROUND, '_evidence')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


with io.open(MAIN_PY, 'r', encoding='utf-8', newline='') as f:
    src = f.read()
with io.open(MAIN_PY, 'rb') as f:
    raw = f.read()

# =============================================== A 语法
head(u'A 语法（不产 .pyc，只解析）')
_tree = None
try:
    _tree = ast.parse(src, filename=MAIN_PY)
    _err = u''
except SyntaxError as e:
    _err = u'%s: %s' % (e.lineno, e.msg)
check(u'A1 ast.parse 通过', _tree is not None, _err or u'%d 行' % src.count(u'\n'))

# =============================================== B 编码
head(u'B 编码卫生')
check(u'B1 无 BOM', not raw.startswith(b'\xef\xbb\xbf'))
_n_fffd = src.count(u'\ufffd')
check(u'B2 无 U+FFFD（替换字符）', _n_fffd == 0, u'%d 处' % _n_fffd)

# =============================================== C 令牌
head(u'C 三个令牌在位')
check(u'C1 `PATCH_HEADER_RALSEI` 常量赋值 1 处',
      src.count(u'PATCH_HEADER_RALSEI = ') == 1,
      u'%d 处' % src.count(u'PATCH_HEADER_RALSEI = '))
check(u'C2 `def _with_ralsei_patch(` 定义 1 处',
      src.count(u'\ndef _with_ralsei_patch(') == 1,
      u'%d 处' % src.count(u'\ndef _with_ralsei_patch('))
_n_call = src.count(u'system = _with_ralsei_patch(system)')
check(u'C3 调用点恰好 2 处（对话 + 预热）', _n_call == 2, u'%d 处' % _n_call)

# =============================================== D ★★★ 必须是模块级函数
head(u'D 它是模块级函数，不是 RalseiPet 的方法（本轮教训 4.2）')
_mod_fn = [n for n in _tree.body
           if isinstance(n, ast.FunctionDef) and n.name == '_with_ralsei_patch']
check(u'D1 `Module.body` 里有这个函数', len(_mod_fn) == 1, u'%d 个' % len(_mod_fn))

_cls = [n for n in _tree.body
        if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet']
_meth = []
if _cls:
    _meth = [n for n in _cls[0].body
             if isinstance(n, ast.FunctionDef)
             and n.name in ('_with_ralsei_patch', '_append_training_patch')]
check(u'D2 `RalseiPet` 里**没有**同名方法（写成方法 ⇒ 桩上 AttributeError）',
      not _meth, u'%s' % ([m.name for m in _meth] if _meth else u'0 个'))
# ★ 反控制：证明上面那条不是"因为压根找不到类"
check(u'D3 反控制：`RalseiPet` 类确实找到了（否则 D2 恒真）',
      len(_cls) == 1, u'%d 个' % len(_cls))

# =============================================== E 注释不自相矛盾
head(u'E 注释不与自己打架')
# ★★ 这条判据第一版是纯文本扫（`u'一个字节都不变' not in src`）⇒ **当场误伤自己**：
#   `chat_with_ai` lean 分支里那句"（本次改动之前这里写的是…）"是**引用**旧断言，
#   不是断言。这是"禁某 API/短语出现"类判据禁纯文本扫的第 **7** 次发作。
#   ⇒ 改成按行判：只有**带"之前这里写的"标记的引用行**才允许出现该短语。
_buf = [ln for ln in src.split(u'\n') if u'一个字节都不变' in ln]
_bad = [ln for ln in _buf if u'之前这里写的' not in ln]
check(u'E1 假断言已删（非引用行为 0；引用行放行）', not _bad,
      u'总 %d 处，其中非引用 %d 处' % (len(_buf), len(_bad)))
# ★ 正控制：拿一条**旧的假断言原文**喂同一个谓词，必须判坏。
#   否则 E1 可能只是"这个短语已经不出现了"的空跑。
_probe = [u'          `None` / `\'ralsei\'` \u21d2 老路径，**一个字节都不变**（人设、上下文）']
_probe_bad = [ln for ln in _probe if u'之前这里写的' not in ln]
check(u'E2 正控制：旧假断言原文喂同一谓词必须判坏', len(_probe_bad) == 1,
      u'%d 条' % len(_probe_bad))
check(u'E3 改成的是"不随轮次变"这个真说法',
      u'不随轮次变' in src)

# =============================================== F 自检
head(u'F 自检')
with io.open(os.path.abspath(__file__), 'r', encoding='utf-8', newline='') as f:
    _self = f.read()
_t = ast.parse(_self)
_bad = [n for n in ast.walk(_t)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == 'check' and len(n.args) >= 2
        and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad, u'%d 处' % len(_bad))
check(u'F2 零外部盘（只读仓库内的 main.py）',
      os.path.abspath(MAIN_PY).startswith(ROOT + os.sep))

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'main_bytes': len(raw), 'main_lines': src.count(u'\n') + 1,
       'calls': _n_call, 'module_level_fn': len(_mod_fn),
       'class_methods': [m.name for m in _meth]}
with io.open(os.path.join(EV, 'recheck137_core.json'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'recheck137_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
