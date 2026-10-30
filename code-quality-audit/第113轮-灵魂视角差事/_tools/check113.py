# -*- coding: utf-8 -*-
"""第113轮 §109.5「灵魂视角」自检：NPC 差事（npc_errand）机制层。

★ 口径（用户逐字，详版 §109.5）：
  「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
     甚至**我中途进去的时候也能看到过程**」
  「那个可派 ralsei 做任务那个**只是个例子，任何人都可以**」（★ 收窄纠正）

★ 四条判据线（每类都配**负控制**）：
  A 结构层 —— 模块零依赖（AST 的 `import` 节点，**不是**文本扫）
  B 行为层 —— 生命周期 traveling → working → done + 结果产出 + `scene_now` 真分叉
  C 主体泛化 —— 「任何人都可以」：无白名单 + 负控制证明判据有鉴别力
  D 解耦层 —— 不碰显示（AST 名字/属性 + 负控制）
  E 接线层 —— main 里真调（AST 结构化；顺序判定用 lineno 但**不回显**）
  F 零回归 —— 没派过 / 关闸 ⇒ 一个字节都不动
  G 序列化 —— 往返保真 + 坏数据不半成品还原

★★ 本套件刻意**不**用「源码里 `in` 某字符串」判"不 import 某模块"——
  docstring/注释里提一句名字就会恒真（本项目已发作五次，见详版 §108.6）。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(PKG, 'modules'))

from modules import npc_errand as E   # noqa: E402

MOD = os.path.join(PKG, 'modules', 'npc_errand.py')
MAIN = os.path.join(PKG, 'src', 'main.py')

#: 项目内模块名（判"零依赖"用；只跟 `import` 节点比，不扫文本）。
_PROJ_MODS = {
    'data_store', 'logger_utils', 'lazy_log', 'npc_roam', 'npc_intent',
    'npc_persona', 'npc_placement', 'npc_plan_store', 'npc_life', 'npc_system',
    'scene_system', 'scene_camera', 'scene_render', 'scene_routing',
    'desk_doors', 'soul_entity', 'ghost_system', 'memory_system',
}

ok = fail = 0


def check(name, cond, star=False, detail=None):
    """`detail` = 可选诊断串（**只**在失败时打印，避免 PASS 行被噪声淹没）。"""
    global ok, fail
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


def _src(p):
    """★★ 字节忠实读（`newline=''`）—— 要数 `\r\n` 时绝不能让 universal newlines 归一化掉。"""
    with open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def _parse(p):
    return ast.parse(_src(p))


def _toplevel_imports(tree):
    """**顶层** import 的顶层包名（函数内 import 不算）。"""
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            out.add((node.module or '').split('.')[0])
    return out


def _imports_all(tree):
    """**所有** import 的顶层包名（含函数内）—— 判"不 import 项目模块"用。"""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            out.add((n.module or '').split('.')[0])
    return out


def _func_level_imports(tree):
    """函数体内 import 的所在函数名列表（零依赖纪律：必须为空）。"""
    bad = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(fn):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    bad.append(fn.name)
    return bad


def _attr_names(tree):
    """源码里出现的**标识符 / 属性名**（判"提到某 API"用 AST，不扫文本）。"""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _method(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _call_names(fn):
    """函数体内**调用的**方法名 / 函数名。"""
    out = set()
    if fn is None:
        return out
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


def _first_call_lineno(fn, names):
    """函数体内首次出现这些调用名的最小行号（**只用于比较，不回显**）。"""
    best = None
    if fn is None:
        return None
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm in names and (best is None or sub.lineno < best):
                best = sub.lineno
    return best


_et = _parse(MOD)
_mt = _parse(MAIN)
_main_src = _src(MAIN)

# ===========================================================================
print('=== A. 结构与零依赖（AST，禁文本扫）===')
_ti = _toplevel_imports(_et)
check('A1 ★ npc_errand 顶层 import 只有标准库 collections',
      _ti <= {'collections'}, star=True, detail=sorted(_ti))
check('A2 ★ 零函数内 import', not _func_level_imports(_et),
      star=True, detail=_func_level_imports(_et))
_allimp = _imports_all(_et)
check('A3 ★ 不 import 任何项目内模块（**只看 import 节点**，不看 docstring 提没提）',
      not (_allimp & _PROJ_MODS), star=True, detail=sorted(_allimp & _PROJ_MODS))
# A3b 负控制：判据真能抓到"import 了项目模块"
_FAKE_A = 'from data_store import get_store\n'
check('A3b ★ 负控制：A3 真能抓到 `from data_store import …`',
      bool(_imports_all(ast.parse(_FAKE_A)) & _PROJ_MODS), star=True)
# A4 文档：零依赖是**契约**，模块抬头必须写明（用 AST 取 docstring，不扫源码）
_doc = ast.get_docstring(_et) or ''
check('A4 抬头写明零依赖纪律（防"下次随手加 import 项目模块"）',
      '零依赖' in _doc, star=True)

# ===========================================================================
print('=== B. 生命周期 traveling → working → done ===')
T = 5000.0
_b = E.ErrandBoard()
_e = _b.assign(T, 'ralsei', 'oneshot.carriage', '送信', travel=60, work=120)
check('B1 assign ⇒ 立刻 status=traveling', _e is not None and _e.status == E.TRAVELING,
      star=True, detail=(_e.status if _e else None))
check('B2 ★ traveling 期 scene_now() 为 None —— "在路上"**不改位置**',
      _e.scene_now() is None, star=True)
check('B3 ★ 对照：traveling 的 scene_now ≠ working 的（有鉴别力，防恒真）',
      E.Errand('a', 's', 'w', 0, 1, 2, status=E.TRAVELING).scene_now() is None
      and E.Errand('a', 's', 'w', 0, 1, 2, status=E.WORKING).scene_now() == 's',
      star=True)
_o1 = _b.step(T + 60)
check('B4 到点 ⇒ arrived=[(nid, dest)]', _o1['arrived'] == [('ralsei', 'oneshot.carriage')],
      star=True, detail=_o1)
check('B5 ★ working 期 scene_now() == dest（我进场能看到他在那）',
      _e.scene_now() == 'oneshot.carriage', star=True)
check('B6 ★ working 期 working_positions() 含他（宿主据此压覆盖）',
      _b.working_positions() == [('ralsei', 'oneshot.carriage')], star=True,
      detail=_b.working_positions())
check('B7 working 期 active_of 有 / working_of 有',
      _b.active_of('ralsei') is _e and _b.working_of('ralsei') is _e, star=True)
_o2 = _b.step(T + 60 + 120)
check('B8 到点 ⇒ finished 且 result **非空**（"产生结果"）',
      len(_o2['finished']) == 1 and bool(_o2['finished'][0][1].result), star=True,
      detail=_o2)
check('B9 ★ done 后不再占用：len==0 且 working_positions 空',
      len(_b) == 0 and _b.working_positions() == [], star=True)
check('B10 result_of 可查（结果**持久**，不依赖过程存活性）',
      'ralsei' in _b.result_of('ralsei'), star=True, detail=_b.result_of('ralsei'))
check('B11 take_results 取走即清',
      bool(_b.take_results()) and _b.take_results() == [], star=True)

# ===========================================================================
print('=== C. 主体泛化：任何人都可以（用户口径逐字）===')
_b2 = E.ErrandBoard()
_npcs = ['ralsei', 'kris', 'susie', 'os_niko', 'ut_frisk', 'ut_sans', '随便谁']
_all_ok = all(_b2.assign(T, n, 'sc', 'w') is not None for n in _npcs)
check('C1 ★★ assign 接受**任意** npc_id（主角团 / OneShot / Undertale / 无关名字）',
      _all_ok and len(_b2) == len(_npcs), star=True, detail=len(_b2))
_as_fn = _method(_et, 'assign')
_as_strs = {c.value for c in ast.walk(_as_fn)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)} if _as_fn else set()
check('C2 ★★ assign 里**没有**具体角色名（有白名单 ⇒ 违反"任何人都可以"）',
      _as_fn is not None and not (_as_strs & {'ralsei', 'kris', 'susie', 'niko'}),
      star=True, detail=sorted(_as_strs))
_FAKE_C = 'def assign(npc_id):\n    if npc_id != "ralsei":\n        return None\n'
check('C2b ★ 负控制：C2 真能抓到角色名白名单',
      'ralsei' in {c.value for c in ast.walk(ast.parse(_FAKE_C))
                   if isinstance(c, ast.Constant) and isinstance(c.value, str)},
      star=True)
# C3 看板**单人单差事**（覆盖而非排队）—— 语义要明确，不然"派两次"行为说不清
_b2.assign(T, 'ralsei', 'sc_other', '另一件事')
check('C3 同一人再派 ⇒ **覆盖**旧差事（一人同时只办一件事）',
      _b2.active_of('ralsei').dest_scene == 'sc_other', star=True)

# ===========================================================================
print('=== D. 与显示解耦（§109.5 要点 1/2）===')
_dn = _attr_names(_et)
_DISPLAY_API = {'switch', 'travel_to', 'SceneCanvas', 'SceneCamera',
                'paintEvent', 'grabWindow', 'set_screen_doors'}
check('D1 ★★ npc_errand **不碰显示**：不出现 switch/travel_to/画布/相机名（AST 名字）',
      not (_dn & _DISPLAY_API), star=True, detail=sorted(_dn & _DISPLAY_API))
_FAKE_D = 'def f(scene):\n    scene.switch("x")\n'
check('D1b ★ 负控制：D1 真能抓到 `scene.switch(...)`',
      bool(_attr_names(ast.parse(_FAKE_D)) & _DISPLAY_API), star=True)
check('D2 ★ 抬头写明"与显示解耦"（口径落在文件里，不只在判据里）',
      '显示' in _doc, star=True)

# ===========================================================================
print('=== E. main 接线（AST 结构化，禁纯文本扫）===')
_tick = _method(_mt, '_npc_errand_tick')
check('E1 ★ main 有 _npc_errand_tick 方法', _tick is not None, star=True)
_cn = _call_names(_tick)
check('E2 ★ _npc_errand_tick 真调 roam.put（把在办的人压在目的地）',
      'put' in _cn, star=True, detail=sorted(k for k in _cn if k in ('put', 'drop')))
check('E3 ★ _npc_errand_tick 真调 roam.drop（办完撤覆盖 ⇒ 回落静态归属）',
      'drop' in _cn, star=True)
check('E4 ★ _npc_errand_tick 真重建身体（否则"人到了、画还在旧场景"）',
      '_npc_seed_bodies' in _cn, star=True)
# 顺序：errand_tick 必须排在 roam_tick **之后**
_host = None
for n in ast.walk(_mt):
    if isinstance(n, ast.FunctionDef):
        _hc = _call_names(n)
        if '_npc_roam_tick' in _hc and '_npc_errand_tick' in _hc:
            _host = n
            break
_ln_roam = _first_call_lineno(_host, {'_npc_roam_tick'})
_ln_errand = _first_call_lineno(_host, {'_npc_errand_tick'})
_order = (_ln_roam is not None and _ln_errand is not None and _ln_roam < _ln_errand)
check('E5 ★★★ 主循环里 errand_tick 排在 roam_tick **之后**（顺序即优先级：差事压过自发）',
      _order, star=True)
_FAKE_E = 'def m(self):\n    self._npc_errand_tick(x)\n    self._npc_roam_tick(x)\n'
_fe = ast.parse(_FAKE_E).body[0]
_la = _first_call_lineno(_fe, {'_npc_roam_tick'})
_lb = _first_call_lineno(_fe, {'_npc_errand_tick'})
check('E5b ★ 负控制：E5 真能抓到"顺序反了"',
      _la is not None and _lb is not None and not (_la < _lb), star=True)
_commit = _method(_mt, '_npc_errand_commit')
_ccn = _call_names(_commit)
check('E6 ★ _npc_errand_commit 真把结果落进记忆（remember + save）',
      'remember' in _ccn and 'save' in _ccn, star=True,
      detail=sorted(k for k in _ccn if k in ('remember', 'save')))
_ae = _method(_mt, 'assign_errand')
_aecn = _call_names(_ae)
check('E7 ★ assign_errand 是对外唯一入口，且真调 board.assign',
      _ae is not None and 'assign' in _aecn, star=True)
# 开关
_sw = any(isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Name) and t.id == 'NPC_ERRAND_ENABLED' for t in n.targets)
    for n in ast.walk(_mt))
check('E8 ★ 有 NPC_ERRAND_ENABLED 总开关（一键封口）', _sw, star=True)
# 开关真被读（不是"定义了不用"）
check('E9 ★ 开关真被 _npc_errand_tick 读（防"定义了没人读"的假开关）',
      _tick is not None and any(
          isinstance(x, ast.Attribute) and x.attr == 'NPC_ERRAND_ENABLED'
          for x in ast.walk(_tick)), star=True)
# 看板真建立
check('E10 ★ main 里真建看板 ErrandBoard(',
      'ErrandBoard(' in _main_src, star=True)

# ===========================================================================
print('=== F. 零回归（没派过 / 关闸）===')
_b3 = E.ErrandBoard()
check('F1 ★★ 没派过 ⇒ step 恒空 & working_positions 空 & len==0',
      _b3.step(T) == {'arrived': [], 'finished': []}
      and _b3.working_positions() == [] and len(_b3) == 0, star=True)
_b4 = E.ErrandBoard(enabled=False)
check('F2 ★★ 关闸 ⇒ assign 拒绝 + step 不动（"一个字节都不改"）',
      _b4.assign(T, 'ralsei', 'x', 'y') is None
      and _b4.step(T + 1e9) == {'arrived': [], 'finished': []}
      and _b4.working_positions() == [] and len(_b4) == 0, star=True)
_b5x = E.ErrandBoard.from_dict({'enabled': False, 'active': [
    {'npc_id': 'x', 'dest_scene': 's', 'what': 'w',
     'start': 0.0, 'arrive_at': 1.0, 'finish_at': 2.0}]})
check('F2b ★★ 关闸时**即便表里已有记录**，step 也不推进（真"一个字节都不改"）',
      len(_b5x) == 1
      and _b5x.step(T + 1e9) == {'arrived': [], 'finished': []}
      and _b5x.active_of('x').status == E.TRAVELING,
      star=True, detail=(_b5x.active_of('x').status if len(_b5x) == 1 else None))
check('F3 ★ 负控制：**开着**时同一调用成功 —— 证明 F2 测的是开关，不是恒假',
      E.ErrandBoard().assign(T, 'ralsei', 'x', 'y') is not None, star=True)

# ===========================================================================
print('=== G. 序列化 + 容错 ===')
_b5 = E.ErrandBoard()
_b5.assign(T, 'ralsei', 'sc1', 'w1')
_b5.assign(T, 'kris', 'sc2', 'w2')
_b6 = E.ErrandBoard.from_dict(_b5.to_dict())
check('G1 ★ 往返保真（人数 + 目的地 + 时刻）',
      len(_b6) == 2
      and _b6.active_of('ralsei').dest_scene == 'sc1'
      and abs(_b6.active_of('ralsei').arrive_at - _b5.active_of('ralsei').arrive_at) < 1e-9,
      star=True)
check('G2 ★ 坏数据 ⇒ **不半成品还原**（宁丢一条差事，不要"某人永远回不了家"）',
      E.Errand.from_dict({'npc_id': 'a'}) is None
      and E.Errand.from_dict(None) is None
      # ★ 缺**时间字段**也必须拒 —— 否则会还原出"working 但没有 finish_at"
      #   ⇒ 该 NPC 被**永远**压在某个场景上（"回不了家"）。
      and E.Errand.from_dict({'npc_id': 'a', 'dest_scene': 's'}) is None
      # ★ 正控制：字段**齐**时必须真还原（否则上面的"拒"可能只是恒拒）
      and E.Errand.from_dict({'npc_id': 'a', 'dest_scene': 's', 'what': 'w',
                              'start': 0.0, 'arrive_at': 1.0,
                              'finish_at': 2.0}) is not None
      and len(E.ErrandBoard.from_dict({'active': [{'npc_id': 'a'}]})) == 0,
      star=True)
check('G3 ★ 自定义 result 直达（调用方可给业务结果文本）',
      (lambda bb: (bb.assign(T, 'x', 's', 'w', travel=1, work=1, result='办妥了。'),
                   bb.step(T + 1), bb.step(T + 2),
                   bb.result_of('x') == '办妥了。')[-1])(E.ErrandBoard()), star=True)

# ===========================================================================
print('=== H. 常量契约 ===')
check('H1 三段状态常量齐备（traveling / working / done）',
      (E.TRAVELING, E.WORKING, E.DONE) == ('traveling', 'working', 'done'), star=True)
check('H2 reason 前缀可用于区分"自主挪窝"与"被派出"',
      isinstance(E.REASON_PREFIX, str) and E.REASON_PREFIX
      and E.Errand('a', 's', 'w', 0, 1, 2).reason().startswith(E.REASON_PREFIX),
      star=True)
check('H3 ★ 默认时长 > 0（"不是瞬移"：出门办事要有过程）',
      float(E.DEFAULT_TRAVEL_SECONDS) > 0.0 and float(E.DEFAULT_WORK_SECONDS) > 0.0,
      star=True)
check('H4 名额上限存在（防无限积累）', int(E.MAX_ERRANDS) > 0, star=True)

print('结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
