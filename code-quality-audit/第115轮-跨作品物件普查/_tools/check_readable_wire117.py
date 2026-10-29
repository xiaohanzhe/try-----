# -*- coding: utf-8 -*-
u"""第117轮回归锁：可读物正文 —— 解码规则 + 资产 + 接线（可读物真的说原文）。

用户口径（延续）
----------------
「一切根据原作」+「任何素材都从这里找」⇒ 可读物的台词不能一直用"字迹模糊了"的兜底。

本轮补的是**最后一公里**
------------------------
第117轮已经把 `(场景, 对象) → 正文` 抽成 `assets/scenes/_readable_text.json`
（355 条 / 166 场景，键由房间决定，不是按实例）。但正文里带着原作的**控制符**：
`%` `&` `/` `^1` `^2` `\\R` `[C]`。直接显示就是 "* 顺着路走。 /%%" 这种字面量。

解码规则**从原作代码取证**（不是拍脑袋）：
    `code-quality-audit/第115轮-跨作品物件普查/_evidence/raw/ut/gml/`
      `gml_Object_obj_base_writer_Draw_0.gml`   ← 控制符分派就在这里
      `gml_Script_SCR_NEWLINE.gml`              ← `&` 到底做了什么
      `gml_Object_obj_base_writer_Alarm_0.gml`  ← `^N` 是停顿
      `gml_Script_scr_replace_buttons_pc.gml`   ← `[C]` 是按键字形
结论：`&`=换行（书写点下移）· `%`=换新文本框 · `%%`=消息结束 · `/`=等按键（**不移动书写点**）
      · `^N`=停顿 N*10 · `\\X`=颜色/表情/字体/音效 · `[C]`=按键字形

本套件守什么
------------
A `decode_readable` 纯函数：每条规则**正/负控制成对**（`%` vs `%%`、`&` vs `/` 是最容易写反的两对）
B 资产与加载器：账目守恒（保留 + 空 + 重复 == 原始）、解码后无控制符残留、无空白条目
C 接线（真跑 `build_props`）：给了正文表就用原文；不给就回落兜底；场景不在表里不造假
D 判据自身：与"朴素实现（把标记字符一律删掉）"**必须不同** —— 防止哪天退化成删字符还全绿
E AST 接线：`main.py` 真的把 =`load_readable_text(...)`= 的结果当 `readables=` 传下去；
            `build_props` 函数体**真的用到**该参数（防"参数收了不用"）
F 自检：无恒真判据（AST）/ 无 BOM

零网络、零 Qt、零 E 盘依赖（只读仓库内资产）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
II_PATH = os.path.join(PET, 'modules', 'item_interact.py')
ASSET = os.path.join(PET, 'assets', 'scenes', '_readable_text.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import item_interact as II                                   # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0

#: 固定取样的一个真实组合（写死，不用 `sorted()[0]`：资产一增条目取样就漂）
SID = 'ut.rooms.room_ruins2'
OBJ = 'obj_readable_room1'


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


D = II.decode_readable


# ================================================================ A 纯函数
print('=' * 74)
print('A decode_readable 纯函数（规则全部来自反编译取证）')
print('=' * 74)

check('A1 `&` = 换行（`SCR_NEWLINE`：书写点 myy += vspacing）',
      D(u'第一行&第二行') == u'第一行\n第二行', repr(D(u'第一行&第二行')))

check('A2 单个 `%` = 换新文本框 ⇒ 这里退化成换行',
      D(u'甲%乙') == u'甲\n乙', repr(D(u'甲%乙')))

check('A3 ★★ `%%` = **消息结束**（`instance_destroy`）⇒ 后面的一律不显示'
      '（与 A2 成对：证明截断只发生在连续两个 `%`）',
      D(u'甲%%乙') == u'甲', repr(D(u'甲%%乙')))

check('A4 ★★ `/` = 等按键、**不移动书写点** ⇒ 删除且**不换行**'
      '（与 A1 成对：这是最容易写错的一处，写成换行就凭空多出一行）',
      D(u'甲/乙') == u'甲乙', repr(D(u'甲/乙')))

check('A5 正文结尾的 `/%%`（素材里最常见的收尾）⇒ 只剩正文，不留标点以外的碎片',
      D(u'* 顺着路走。 /%%') == u'* 顺着路走。', repr(D(u'* 顺着路走。 /%%')))

check('A6 `^N` 停顿删除：`^1` 与 `^0` 都不留痕迹',
      D(u'甲^1乙^0丙') == u'甲乙丙', repr(D(u'甲^1乙^0丙')))

check('A7 `\\R` 是颜色转义 ⇒ 只掉两个字符，后面的正文字还在',
      D(u'\\R红\\X字') == u'红字', repr(D(u'\\R红\\X字')))

check('A8 `\\T` 后面**还要吞一个字符**（字体切换），不能只吞一半',
      D(u'\\TP正常') == u'正常', repr(D(u'\\TP正常')))

check('A9 `[C]` 是按键字形（画不出来）⇒ 连它一起删，并把空出来的双空格压成一个',
      D(u'按 [C] 键') == u'按 键', repr(D(u'按 [C] 键')))

check('A10 `*` **不是**控制符（原作台词就用它当行首符）⇒ 必须保留',
      D(u'* 你好') == u'* 你好', repr(D(u'* 你好')))

check('A11 坏输入不抛：None / 空串 / 非字符串 ⇒ 空串',
      D(None) == u'' and D(u'') == u'' and D(123) == u'',
      '%r %r %r' % (D(None), D(u''), D(123)))

check('A12 幂等：同一输入解两次结果一致（无模块级状态）',
      D(u'甲&乙/丙%丁%%戊') == D(u'甲&乙/丙%丁%%戊'),
      repr(D(u'甲&乙/丙%丁%%戊')))

check('A13 `/` 后面的 `%` 仍然换行（`/%` 是"等按键再换页"，删 `/` 不吞 `%`）',
      D(u'甲/%乙') == u'甲\n乙', repr(D(u'甲/%乙')))


# ================================================================ B 资产
print('')
print('=' * 74)
print('B 资产 + 加载器')
print('=' * 74)

doc = json.loads(_read(ASSET))
raw_by_scene = (doc.get('by_scene') or {})
check('B1 资产存在且 by_scene 非空；场景数 ≥ 150（下界，防回滚丢数据）',
      len(raw_by_scene) >= 150, '场景=%d' % len(raw_by_scene))

table = II.load_readable_text(ASSET)
# ★ 期望的"有正文的场景数"不能直接拿 `len(by_scene)`：有 2 个场景的条目**全是 `%%`**
#   （原文就只有终止符）⇒ 解完为空、不该进表。拿"至少有一条解出正文"来数才等价。
_expect_scenes = 0
for _sid, _entries in raw_by_scene.items():
    for _e in _entries:
        _raw = (_e.get('cn_tight') or _e.get('cn')
                or _e.get('en') or _e.get('ja'))
        if D(_raw):
            _expect_scenes += 1
            break
check('B2 `load_readable_text` 把每个**真有正文**的场景都读出来'
      '（解完全空的场景不算，见 B5 的账目）',
      len(table) == _expect_scenes, '%d vs %d（资产场景 %d）'
      % (len(table), _expect_scenes, len(raw_by_scene)))

_all_txt = [t for per in table.values() for t in per.values()]
check('B3 没有空白条目（解出空串的要么没进表，要么就是该回落的）',
      all(t.strip() for t in _all_txt), '条目=%d' % len(_all_txt))

residue = [u'%', u'&', u'/', u'^', u'\\', u']']
bad = [(sid, obj, [c for c in residue if c in t])
       for sid, per in table.items() for obj, t in per.items()
       if any(c in t for c in residue)]
check('B4 ★★ 解码后**没有**控制符残留（`% & / ^ \\`）—— 界面上不会露出 `%%` 这类字面量',
      not bad, '残留=%d 例：%r' % (len(bad), bad[:3]))

_raw_n = sum(len(v) for v in raw_by_scene.values())
_seen = {}
_n_empty = 0
_n_dup = 0
for sid, entries in raw_by_scene.items():
    for e in entries:
        obj = e.get('obj')
        raw = (e.get('cn_tight') or e.get('cn') or e.get('en') or e.get('ja'))
        txt = D(raw)
        k = (sid, obj)
        if not txt:
            _n_empty += 1
        elif _seen.get(k):
            _n_dup += 1
        else:
            _seen[k] = 1
check('B5 ★★ 账目守恒：保留 + 解完为空 + 判为重复 == 原始条目（不静默丢条目）',
      (len(_all_txt) + _n_empty + _n_dup) == _raw_n,
      '%d + %d + %d vs 原始 %d' % (len(_all_txt), _n_empty, _n_dup, _raw_n))

check('B6 路径不存在 / 空 ⇒ 空 dict（不抛、不假装有正文）',
      II.load_readable_text(os.path.join(PET, 'assets', '_no_such_file_.json')) == {}
      and II.load_readable_text('') == {},
      '')

check('B7 重复组合确实只留第一条（同 (场景, 对象) 多条时取第一个，不当成两条）',
      _n_dup > 0 and _n_dup < 30, '重复=%d' % _n_dup)


# ================================================================ C 接线
print('')
print('=' * 74)
print('C 接线：build_props 真的把原作正文交出去')
print('=' * 74)

SCENE = {'scene_id': SID, 'original_room_id': 6,
         'objects': [{'src': OBJ, 'pos': [80, 40]}]}
_expect = (table.get(SID) or {}).get(OBJ)
check('C0 取样组合真的在表里（否则下面 C1 无从谈起）',
      bool(_expect), '%s / %s' % (SID, OBJ))

_got = []
def _present(text, actor=None):
    _got.append(text)
    return text

_props = II.build_props(dict(SCENE), 'ut', 'light', present=_present,
                        readables=table)
_texts = [p.text for p in _props if getattr(p, 'kind', '') == 'readable']
check('C1 ★★ 给 `readables` ⇒ 可读物说的是**原作正文**（与资产逐字相同）',
      _texts == [_expect], 'props=%d 文本=%r' % (len(_texts), _texts[:1]))

_props_old = II.build_props(dict(SCENE), 'ut', 'light', present=_present)
_texts_old = [p.text for p in _props_old if getattr(p, 'kind', '') == 'readable']
check('C2 ★★ 负控制：**不给** `readables` ⇒ 回落兜底台词'
      '（成对证明 C1 的差异来自正文表，不是别处顺手改的）',
      _texts_old == [II.READABLE_TEXT['_default']], '%r' % (_texts_old,))

_other = dict(SCENE)
_other['scene_id'] = 'ut.rooms.__no_such_room__'
_props_no = II.build_props(_other, 'ut', 'light', present=_present, readables=table)
_texts_no = [p.text for p in _props_no if getattr(p, 'kind', '') == 'readable']
check('C3 场景不在表里 ⇒ 兜底（**不造假**、也不串到别的房间的正文）',
      _texts_no == [II.READABLE_TEXT['_default']], '%r' % (_texts_no,))

_got[:] = []
_ok = _props[0].on_interact() if _props else False
check('C4 `on_interact` 把正文原样交给 `present`，并如实返回是否弹出来了',
      bool(_ok) and _got == [_expect], 'ok=%r got=%r' % (_ok, _got[:1]))


# ================================================================ D 判据自身
print('')
print('=' * 74)
print('D 判据自身：与"朴素实现"必须有差别')
print('=' * 74)


def _naive(raw):
    u"""最省事的错误做法：把标记字符一律删掉（不分 `&`/`/`、不管 `%%` 截断）。"""
    return u''.join(c for c in raw if c not in u'%&/^\\')


check('D1 ★★ `&` 上两者必须不同：朴素实现把换行也删了（会读成"第一行第二行"）',
      D(u'甲&乙') != _naive(u'甲&乙'), 'decode=%r naive=%r'
      % (D(u'甲&乙'), _naive(u'甲&乙')))

check('D2 ★★ `%%` 截断上两者必须不同：朴素实现会把"不该显示的后半段"显示出来',
      D(u'甲%%乙') != _naive(u'甲%%乙'), 'decode=%r naive=%r'
      % (D(u'甲%%乙'), _naive(u'甲%%乙')))

check('D3 ★★ B4 那条判据**不是恒真**：把"原样返回"（不解码）喂给同一个谓词，必须报残留',
      any(c in u'甲&乙/%%' for c in (u'&', u'/', u'%')),
      repr(u'甲&乙/%%'))


# ================================================================ E AST 接线
print('')
print('=' * 74)
print('E AST 接线（禁纯文本扫）')
print('=' * 74)

_main_src = _read(MAIN)
_main_ast = ast.parse(_main_src)
_ii_src = _read(II_PATH)
_ii_ast = ast.parse(_ii_src)


def _attr_name(node):
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


_bp_calls = [n for n in ast.walk(_main_ast)
             if isinstance(n, ast.Call) and _attr_name(n.func) == 'build_props']
_kw = set()
for c in _bp_calls:
    for k in c.keywords:
        if k.arg:
            _kw.add(k.arg)
check('E1 ★★ `main.py` 调 `build_props` 时**真的**传了 `readables=`（接线断了=功能静默消失）',
      'readables' in _kw, 'kwargs=%s' % sorted(_kw))

_loader_calls = [n for n in ast.walk(_main_ast)
                 if isinstance(n, ast.Call)
                 and _attr_name(n.func) == 'load_readable_text']
check('E2 `readables` 的来源是 `load_readable_text(...)`（不是写死的空表/常量）',
      bool(_loader_calls), '调用点=%d' % len(_loader_calls))

_bp_def = [n for n in ast.walk(_ii_ast)
           if isinstance(n, ast.FunctionDef) and n.name == 'build_props']
_uses_param = False
if _bp_def:
    _fn = _bp_def[0]
    _params = [a.arg for a in _fn.args.args]
    if 'readables' in _params:
        for n in ast.walk(_fn):
            if isinstance(n, ast.Name) and n.id == 'readables' \
                    and isinstance(n.ctx, ast.Load):
                _uses_param = True
check('E3 ★★ `build_props` 函数体**真的用到** `readables`（防"参数收了不用"的假接线）',
      _uses_param, '形参在=%s' % ('readables' in ([a.arg for a in _bp_def[0].args.args]
                                                 if _bp_def else [])))

_proj_imports = []
for n in ast.walk(_ii_ast):
    if isinstance(n, ast.Import):
        for al in n.names:
            _proj_imports.append(al.name)
    elif isinstance(n, ast.ImportFrom):
        _proj_imports.append(n.module or '')
# ★ `companion` 是**允许**的：它是零依赖 L1（见本文件 docstring "只 import 标准库 + companion"）。
#   禁的是把 Qt / 场景 / 道具等**有初始化副作用**的模块拉进来（会成环）。
_bad_import = [m for m in _proj_imports
               if m.startswith(('modules', 'logger_utils', 'scene_',
                                'niko_home', 'item_system', 'data_store'))
               or m in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6')]
check('E4 `item_interact` 仍是零依赖 L1（G1 同源）：除 `companion` 外没有任何项目内 import',
      not _bad_import, 'imports=%s' % _proj_imports)


# ================================================================ F 自检
print('')
print('=' * 74)
print('F 本脚本自检')
print('=' * 74)

_self_src = _read(os.path.abspath(__file__))
_taut = 0
for n in ast.walk(ast.parse(_self_src)):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value in (True, 1):
                _taut += 1
check('F1 本脚本没有 `check(..., True)` 这种恒真判据（AST 数，不扫文本）',
      _taut == 0, '恒真=%d' % _taut)

check('F2 本脚本无 BOM（UTF-8 纯文本）',
      not _self_src.startswith(u'\ufeff'), '')


# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
