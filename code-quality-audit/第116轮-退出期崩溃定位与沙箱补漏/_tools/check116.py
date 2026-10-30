# -*- coding: utf-8 -*-
u"""第116轮自检：**退出期崩溃定位 + 沙箱补漏** —— 两件事都不许"自称完成"。

★ 本轮为什么存在
----------------
  第115轮的遗留单里登记了两项，本轮逐项落地：
    ① `rec96` 退出码 `3221225477`（0xC0000005）**登记待查**；
    ② `_OOC_PATTERNS` 里 `'人工智能'`/`'没有感觉'` 两个裸词的误伤风险（登记待议）。
  而查 ① 的过程中**撞出更严重的一件**：
    ③ ★★★ 真机录制脚本的**沙箱是假的** ——
       11 个 `rec*.py` 里**只有 `rec114.py` 有沙箱**，`rec96/105/106/107/109~113`
       全是裸跑；`replay115.py` 头部却写着"各 rec*.py 自带沙箱（不碰用户角色记忆）"。
       实测：第115轮那次重放**确实写进了用户真实的 `E:\\RalseiMemory\\`**
       （`npc_memory/*.json` mtime = 2026-10-16 03:57:48）。
  ③ 的根因值得单独记：**`data_store` 只是包装层**，路径真源在 `memory_store`；
     记忆系统**直接**用 `memory_store`（绕过对 `data_store.vault_root` 的猴补丁），
     而 `memory_store.find_device_dir()` 里 **`RALSEI_MEMORY_DIR` 优先级最高**
     ⇒ 只设 `RALSEI_DATA_DIR` **拦不住**。

★ 判据线（每类都配**负控制**）
------------------------------
  A **尺子本身可信**（`_shared/vault_guard.py`）：不是"它有这个函数"，
    而是**真造出增/删/改三种变化**，看它**必须**一次不漏地报出来（A2 正控）；
    再**什么都不动**，看它**必须**报一致（A3 负控）。尺子不准，后面全白搭。
  B **闸门齐不齐**（AST，不扫文本）：`diag96_exit.py` 与 `replay115.py`
    必须**真的**给 `os.environ` / 子进程 `env` 赋上三把闸
    （`RALSEI_MEMORY_DIR` / `RALSEI_DATA_DIR` / `RALSEI_DESKTOP`）。
    ★ 判据读的是**赋值语句的 AST 下标常量**，所以"注释里提一句名字"喂不饱它。
  C **假声明已被拆掉**：`replay115.py` 里那句"各 rec*.py 自带沙箱"必须**不在**，
    且补正说明**在**。
  D **判据自身体检**：条数记账 · 名字里无计数标记 · 无重复 ·
    无恒真判据（AST 查本文件所有 `check()` 的第二实参不是字面量 `True`）。
  E **本轮三处视觉缺陷不许静默回退**（用户逐字报的「门在闪现，黑底也没去干净，
    并且对话框也是闪现，而且你门的形式也没用对」四条里，落在代码侧的三条）：
      · E1 桌面画布吃**工作区**尺寸（盖满整屏 ⇒ Windows 当全屏应用 ⇒ 反复收放任务栏）；
      · E2 屏幕层门**真读 alpha**（原只 `drawPixmap`），且 A/B 恒满实、C/D 随距离；
      · E3 三角符文门 = **巨门框**桌面版（用户 10-13 逐字裁定，不许回退）；
      · E4 对话框 `fade_plan` 纯函数（已可见且在稳态 ⇒ **不重淡入**，治"对话框闪现"）；
      · E5 `_show_scene_layer` 的 `raise_()` 被条件守卫（不再每帧无条件抢顶层）。
    每条尽量配**正控/负控**成对（E1c/E2e/E3b/E4c/E4f/E5b）。

★★ 端到端那一层（真跑一次录屏、再用尺子量用户记忆库）**不放在本文件里** ——
  它要起 GUI、约 40 s，且**与单实例锁互斥**（不能在别的 GUI 测试跑着时跑）。
  见 `_tools/live116_sandbox.py`。
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.environ.get('RALSEI_ROUND116_ROOT')
                       or os.path.join(HERE, '..', '..', '..'))
CQA = os.path.join(ROOT, 'code-quality-audit')

#: ★ 第116轮补：**根可覆盖**，给 `mutate116.py` 用（变异只改临时树，产线一个字节不动）。
#: 为什么不学 `check115` 用 `RALSEI_PET_OVERRIDE` 只覆盖 `ralsei_pet`：
#: 本套件同时要判 `code-quality-audit/_shared/vault_guard.py` 与两个录制脚本，
#: 它们都在 CQA 下 ⇒ 必须整棵 ROOT 一起指过去。
#: ★ 默认（不设该环境变量）= 老行为，回归里一个字节都不变。

GUARD = os.path.join(CQA, '_shared', 'vault_guard.py')
DIAG = os.path.join(CQA, '第96轮-用户视角录制复核', '_tools', 'diag96_exit.py')
REPLAY = os.path.join(CQA, '第115轮-AI人味训练', '_tools', 'replay115.py')

ok = fail = 0
_NAMES = []


def check(name, cond, star=False, detail=None):
    u"""`detail` 只在**失败**时打印（避免 PASS 行被噪声淹没）。"""
    global ok, fail
    _NAMES.append(name)
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


def _read(p):
    with io.open(p, 'rb') as fh:
        return fh.read().decode('utf-8', 'replace')


def _tree(p):
    return ast.parse(_read(p))


def sec(t):
    print('\n=== %s ===' % t)


# 本轮**新增/改动**的四个文件（判据只认它们存在；缺了就如实 FAIL，不抛）
REQUIRED = [GUARD, DIAG, REPLAY]

sec(u'A. 尺子本身可信（vault_guard）')

_missing = [p for p in REQUIRED if not os.path.isfile(p)]
check(u'A1 三个关键文件都在盘上', not _missing,
      detail=u'缺: %r' % (_missing,))
_tmp = tempfile.mkdtemp(prefix='check116_')

_guard_mod = None
_import_ok = False
_import_err = None
try:
    sys.path.insert(0, os.path.join(CQA, '_shared'))
    import vault_guard as _guard_mod
    _import_ok = True
except Exception as e:                                   # noqa: BLE001
    _guard_mod = None
    _import_err = e
# ★ 这里**不许**写 `check(..., True)`：本文件 D4 就是专门抓这种恒真判据的。
#   用一个**可能为假**的变量承载结论。
check(u'A1b `vault_guard` 可导入', _import_ok, detail=repr(_import_err))

if _guard_mod is not None:
    # ---- A2 正控：真造 增 / 删 / 改 三种变化，必须一次不漏 ----
    _d = os.path.join(_tmp, 'sand')
    os.makedirs(os.path.join(_d, 'sub'), exist_ok=True)
    _keep = os.path.join(_d, 'keep.txt')
    _gone = os.path.join(_d, 'sub', 'gone.txt')
    _mut = os.path.join(_d, 'mut.txt')
    with io.open(_keep, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'keep\n')
    with io.open(_gone, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'gone\n')
    with io.open(_mut, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'before\n')
    _b = _guard_mod.snapshot(_d, ())
    # 造变化
    with io.open(_mut, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'after!\n')                    # 改（内容 + 大小都变）
    os.remove(_gone)                             # 删
    with io.open(os.path.join(_d, 'new.txt'), 'w', encoding='utf-8',
                 newline='\n') as fh:
        fh.write(u'new\n')                       # 增
    _a = _guard_mod.snapshot(_d, ())
    _added, _removed, _changed = _guard_mod.compare(_b, _a)
    check(u'A2 正控：增/删/改三种变化**一次不漏**',
          len(_added) == 1 and len(_removed) == 1 and len(_changed) == 1
          and _added[0] == 'new.txt' and _removed[0] == 'sub/gone.txt'
          and _changed[0][0] == 'mut.txt',
          detail=u'added=%r removed=%r changed=%r' % (_added, _removed,
                                                      [c[0] for c in _changed]))
    # ---- A3 负控：什么都不动，必须报一致 ----
    _c = _guard_mod.snapshot(_d, ())
    _a2, _r2, _c2 = _guard_mod.compare(_a, _c)
    check(u'A3 负控：静止不动 ⇒ 必须报"完全一致"',
          not _a2 and not _r2 and not _c2,
          detail=u'added=%r removed=%r changed=%r' % (_a2, _r2, _c2))
    # ---- A4 边界：根不存在 ⇒ 返回 None（不许抛） ----
    try:
        _n = _guard_mod.snapshot(os.path.join(_tmp, 'no_such_dir_xyz'), ())
        check(u'A4 根不存在 ⇒ 返回 None 且不抛', _n is None, detail=repr(_n))
    except Exception as e:                           # noqa: BLE001
        check(u'A4 根不存在 ⇒ 返回 None 且不抛', False, detail=repr(e))
    # ---- A5 负控：忽略前缀真的生效（否则 logs/ 一涨就假红） ----
    # ★★★ 夹具必须**保真**（首版这里把整段脚本崩掉了，教训记下来）：
    #   `snapshot()` 本轮新增了硬闸「扫到 **0 个文件** ⇒ 返回 `None`」
    #   （防"空指纹假绿"，见 vault_guard.py 的 `_scan` 说明）。
    #   首版夹具**只**放被忽略的 `logs/a.log` ⇒ 忽略后剩 0 个 ⇒ 撞空库闸返 `None`
    #   ⇒ `compare(None, …)` 抛 `TypeError`，把 A 段之后**全部判据**静默崩掉。
    #   ⇒ 这说明它当时测的**不是**"忽略生效"，而是"空库兜底"。留一个**不被忽略**
    #     的文件，才是真正在测忽略逻辑。
    _d2 = os.path.join(_tmp, 'sand2')
    os.makedirs(os.path.join(_d2, 'logs'), exist_ok=True)
    with io.open(os.path.join(_d2, 'keep2.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'k\n')                     # 不被忽略 ⇒ 保证 `snapshot` 非空
    with io.open(os.path.join(_d2, 'logs', 'a.log'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'1\n')
    _b2 = _guard_mod.snapshot(_d2, ('logs/',))
    with io.open(os.path.join(_d2, 'logs', 'a.log'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'22222\n')
    _c2s = _guard_mod.snapshot(_d2, ('logs/',))
    # ★ 夹具自检：两份指纹都必须**非空**；若为 None，判据会如实报红而不是崩掉。
    check(u'A5 夹具非空（两份指纹都不是 None）',
          (_b2 is not None) and (_c2s is not None),
          detail=u'base=%r cur=%r' % (_b2 is None, _c2s is None))
    _x, _y, _z = _guard_mod.compare(_b2 or {}, _c2s or {})
    check(u'A5 负控：`--ignore` 前缀真的能把 logs/ 排除',
          not _x and not _y and not _z,
          detail=u'added=%r removed=%r changed=%r' % (_x, _y, _z))
    # ---- A5b 正控：**不带**忽略前缀时，同一处改动**必须**被报出来 ----
    #   （否则 A5 可能只是"compare 恒返回空"而假绿 —— 正负成对才可信）
    #   ★★ 首版这里又错了一次（正控自己写歪）：拿**带忽略**的 `_b2` 当基线去比
    #     **不带忽略**的当前值 —— 基线里压根没有 `logs/a.log`，差异自然落进
    #     **新增**而不是**变化**，于是 `changed=[]` 报红。**正控的 A/B 必须同口径**。
    #   ⇒ 重新在"同一口径（都不忽略）"下各拍一份，中间只动 `logs/a.log`。
    _b_no = _guard_mod.snapshot(_d2, ())
    with io.open(os.path.join(_d2, 'logs', 'a.log'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'4444444\n')               # 再改一次（长度也变）
    _c_no = _guard_mod.snapshot(_d2, ())
    _x2, _y2, _z2 = _guard_mod.compare(_b_no or {}, _c_no or {})
    check(u'A5b 正控：不带忽略 ⇒ 同一处 logs/ 改动**必须**被报出来',
          (not _x2) and (not _y2) and len(_z2) == 1 and _z2[0][0] == 'logs/a.log',
          detail=u'added=%r removed=%r changed=%r'
                 % (_x2, _y2, [c[0] for c in _z2]))
else:
    for _n in (u'A2 正控：增/删/改三种变化**一次不漏**',
               u'A3 负控：静止不动 ⇒ 必须报"完全一致"',
               u'A4 根不存在 ⇒ 返回 None 且不抛',
               u'A5 夹具非空（两份指纹都不是 None）',
               u'A5 负控：`--ignore` 前缀真的能把 logs/ 排除',
               u'A5b 正控：不带忽略 ⇒ 同一处 logs/ 改动**必须**被报出来'):
        check(_n, False, detail=u'`vault_guard` 没导进来，没法验')


def _subscript_env_keys(path):
    u"""AST 取 `os.environ['K'] = ...` / `env['K'] = ...` 里的**下标常量键**。

    ★ 为什么必须是 AST：裸 `'RALSEI_MEMORY_DIR' in src` 会被**注释**喂饱
      —— 上一条注释里写一句闸名，文本扫描就说"有"，而代码里根本没赋值
      （本项目同类误报已发作五次，见详版 §108.6）。
    """
    keys = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Subscript):
                continue
            # 目标必须形如 `os.environ[...]` 或 `env[...]`
            base = tgt.value
            is_env = (isinstance(base, ast.Attribute) and base.attr == 'environ') \
                or (isinstance(base, ast.Name) and base.id == 'env')
            if not is_env:
                continue
            sl = tgt.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                keys.add(sl.value)
    return keys


def _say_args(path):
    u"""AST 取所有 `say(...)` 调用的**字符串常量实参**。

    ★ 为什么要这么绕（C1 首版就是这么红的）：
      C1 一开始写的是裸 `'各 rec*.py 自带' not in 源码` —— 结果**报红**，
      因为我在"补正说明"里**引用**了那句假话（「首版头部写的是「各 rec*.py 自带…」」）。
      判据分不清"**还这么说**"与"**在引用它说错在哪**"。
      ⇒ 改成只看**真正的 `say(...)` 对外输出**里有没有这句 ——
        这才是"重放器还在对外宣称沙箱"的语义。
    """
    out = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'say':
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(a.value)
    return out


sec(u'B. 沙箱闸门齐不齐（AST 查赋值语句的下标常量）')

if os.path.isfile(DIAG) and os.path.isfile(REPLAY):
    _dk = _subscript_env_keys(DIAG)
    _rk = _subscript_env_keys(REPLAY)
    _want = {'RALSEI_MEMORY_DIR', 'RALSEI_DATA_DIR', 'RALSEI_DESKTOP'}
    check(u'B1 `diag96_exit.py` 三把闸都**真的赋了值**',
          _want <= _dk, detail=u'实到 %r' % (sorted(_dk),))
    check(u'B2 `replay115.py` 三把闸都**真的注入子进程 env**',
          _want <= _rk, detail=u'实到 %r' % (sorted(_rk),))
    # ★ B3 是 B1/B2 的**负控制**：AST 取键这件事本身必须能区分"真赋值"与"只提名字"，
    #   否则 B1/B2 只是恒真。这里现造一段"注释+字符串里提到名字但没赋值"的源码，
    #   断言取键函数**取不到**它。
    _probe = os.path.join(_tmp, 'probe_env.py')
    with io.open(_probe, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u"# RALSEI_MEMORY_DIR 只是注释里提一句\n"
                 u"NAME = 'RALSEI_DATA_DIR'\n"
                 u"OTHER = {'RALSEI_DESKTOP': 1}\n")
    _pk = _subscript_env_keys(_probe)
    check(u'B3 负控制：只"提名字"（注释/字符串/字典字面量）⇒ 取键函数必须取不到',
          not (_want & _pk), detail=u'误取到 %r' % (sorted(_pk),))
    # ★ B4：闸门必须**在 import main 之前**设好 —— 顺序反了等于没设（本轮踩的就是这个）
    _dl, _il, _ordered = [], [], False
    try:
        _lines = _read(DIAG).splitlines()
        _dl = [i for i, l in enumerate(_lines, 1)
               if 'os.environ[' in l and 'RALSEI_MEMORY_DIR' in l]
        _il = [i for i, l in enumerate(_lines, 1)
               if 'import main as M' in l]
        _ordered = bool(_dl) and bool(_il) and max(_dl) < min(_il)
    except Exception:
        _ordered = False
    check(u'B4 `diag96_exit.py` 的闸门设在 `import main` **之前**', _ordered,
          detail=u'env 行=%r / import main 行=%r' % (_dl, _il))
else:
    for _n in (u'B1 `diag96_exit.py` 三把闸都**真的赋了值**',
               u'B2 `replay115.py` 三把闸都**真的注入子进程 env**',
               u'B3 负控制：只"提名字"（注释/字符串/字典字面量）⇒ 取键函数必须取不到',
               u'B4 `diag96_exit.py` 的闸门设在 `import main` **之前**'):
        check(_n, False, detail=u'脚本不在盘，无法校验')

sec(u'C. 假声明已被拆掉')

if os.path.isfile(REPLAY):
    _rsrc = _read(REPLAY)
    _false = u'各 rec*.py 自带'
    # ★ C1 只看**真正对外 `say(...)` 的输出**（引用它说错在哪，不算"还这么说"）
    _bad_says = [s for s in _say_args(REPLAY) if _false in s]
    check(u'C1 重放器**对外输出**里不再有那句假声明',
          not _bad_says, detail=u'命中 %r' % (_bad_says,))
    # ★ C1b 正控：判据必须**抓得住**真说了假话的输出（否则 C1 是恒真）
    _probe2 = os.path.join(_tmp, 'probe_say.py')
    with io.open(_probe2, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u"def say(m=''):\n    print(m)\n"
                 u"say(u'\u2605 沙箱：各 rec*.py 自带 RALSEI_DATA_DIR')\n")
    _hit = [s for s in _say_args(_probe2) if _false in s]
    check(u'C1b 正控：真对外这么说 ⇒ 判据必须抓住', len(_hit) == 1,
          detail=u'命中 %r' % (_hit,))
    check(u'C2 补正说明在位（写清了只有 rec114 有沙箱、以及真源头是 RALSEI_MEMORY_DIR）',
          (u'只有 `rec114.py` 有沙箱' in _rsrc)
          and (u'真源头' in _rsrc))
    check(u'C3 重放器已接上外部尺子（跑前拍指纹 / 跑后比对）',
          ('vg.snapshot()' in _rsrc) and ('vg.compare(' in _rsrc))
else:
    for _n in (u'C1 重放器**对外输出**里不再有那句假声明',
               u'C1b 正控：真对外这么说 ⇒ 判据必须抓住',
               u'C2 补正说明在位（写清了只有 rec114 有沙箱、以及真源头是 RALSEI_MEMORY_DIR）',
               u'C3 重放器已接上外部尺子（跑前拍指纹 / 跑后比对）'):
        check(_n, False, detail=u'`replay115.py` 不在盘')

sec(u'E. 本轮三处视觉缺陷不许静默回退（用户逐字报的）')

# 用户 2026-10-16 逐字：
#   「你要不要自己看看他啥情况啊，**门在闪现**，**黑底也没去干净**，
#     并且**对话框也是闪现**，而且，**你门的形式也没用对**」
#   「你自己录屏然后逐帧分析去」
# 逐帧取证结论（`probe116_doors.py` / `band116.py` / `z*_116.py`）：
#   ① 门在闪现 + 对话框也是闪现 = **同一条根因**：桌面画布铺满**整屏**（含任务栏那
#      72px）被 Windows 当全屏应用 ⇒ shell 反复收/放任务栏 ⇒ 屏幕最下那条带以
#      **6.25 Hz** 在「我们的窗口 ↔ 任务栏」之间翻。负控制（不起桌宠）0 次变化；
#      A/B：画布 2560×**1600** ⇒ 5.72 Hz / 2560×**1528**（工作区）⇒ 0.00 Hz。
#   ② 黑底 = 门 C/D 的原作贴图本身就是黑底卡片（纯黑 76.4% / 82.6%），而「渐显」
#      那条路**根本没接到屏幕层**（alpha 在房间层无消费者）⇒ C/D 恒为实心黑块。
#   ③ 对话框闪现 = `show_dialogue()` **无条件** `setStartValue(0.0)` ⇒ 每来一条
#      消息先整个隐到全透明再淡回来（真机 30 s 里塌陷 3 次）。
_MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
_CV = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_canvas.py')
_DU = os.path.join(ROOT, 'ralsei_pet', 'modules', 'dialogue_ui.py')
_DJSON = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'desktop.json')


def _fns(tree):
    u"""函数名 → `FunctionDef` 节点（同名取最后一个）。"""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            out[n.name] = n
    return out


def _called_attrs(node):
    u"""节点内所有 `X.attr(...)` 形式的**被调属性名**集合。"""
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            s.add(n.func.attr)
    return s


def _bare_call_attrs(fn):
    u"""**函数体顶层**（不在 If/Try/For/While 里）的裸调用属性名。

    ★ 为什么必须"顶层"：E5 要问的是「`raise_()` 有没有被条件守卫」。
      `ast.walk` 会钻进 `if` 里面 ⇒ 守卫过的调用也会被数到 ⇒ 判据恒真。
    """
    out = []
    for st in (getattr(fn, 'body', None) or []):
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            f = st.value.func
            if isinstance(f, ast.Attribute):
                out.append(f.attr)
            elif isinstance(f, ast.Name):
                out.append('!' + f.id)
    return out


def _probe_fn(src, fname):
    u"""从一段源码里取函数节点（给**负控制**造假样本用）。取不到 ⇒ None。"""
    try:
        return _fns(ast.parse(src)).get(fname)
    except Exception:                                    # noqa: BLE001
        return None


# ---- E1 桌面画布用**工作区**尺寸（不盖任务栏）----
_m_tree = _tree(_MAIN)
_m_fns = _fns(_m_tree)
_dls = _m_fns.get('_desktop_layer_size')
_e1_detail = []
_e1 = False
if _dls is None:
    _e1_detail.append(u'`_desktop_layer_size` 不在盘')
else:
    _da = _called_attrs(_dls)
    _e1 = ('availableGeometry' in _da) and ('geometry' in _da)
    if not _e1:
        _e1_detail.append(u'未调 availableGeometry/geometry：%r' % (sorted(_da),))
check(u'E1 ★★★ 桌面画布吃**工作区**尺寸（`_desktop_layer_size` 真调 `availableGeometry`）'
      u'—— 铺满整屏会被 Windows 当全屏应用，shell 反复收放任务栏',
      _e1, detail=u'; '.join(_e1_detail))
_usl = _m_fns.get('_update_scene_layer')
_e1b = False
if _usl is not None:
    _uc = _called_attrs(_usl)
    _e1b = ('_scene_is_desktop_scene' in _uc) and ('_desktop_layer_size' in _uc)
check(u'E1b ★★★ `_update_scene_layer` 里**桌面分支**真用 `_desktop_layer_size`'
      u'（且受 `_scene_is_desktop_scene` 守卫 —— 非桌面场景仍走第107轮整屏口径）',
      _e1b, detail=u'实调 %r' % (sorted(_called_attrs(_usl)) if _usl else [],))
_e1c = False
_fake1 = _probe_fn(u"def _desktop_layer_size(self):\n"
                   u"    return (1920, 1080)\n", '_desktop_layer_size')
if _fake1 is not None:
    _e1c = ('availableGeometry' not in _called_attrs(_fake1))
check(u'E1c ★★ 负控制：E1 的提取器有鉴别力（假函数不调 `availableGeometry` ⇒ 必判否）',
      _e1c)

# ---- E2 门渐显（alpha）真接到屏幕层 ----
_dsd = _m_fns.get('_desktop_screen_doors')
_cv_tree = _tree(_CV)
_psd = _fns(_cv_tree).get('_paint_screen_doors')
check(u'E2a ★★★ `_desktop_screen_doors` 真调 `screen_reveal_alpha`'
      u'（渐显从"房间坐标"改到"**屏幕像素**口径"）',
      _dsd is not None and 'screen_reveal_alpha' in _called_attrs(_dsd))
def _opacity_arg_kinds(fn):
    u"""函数里所有 `setOpacity(x)` 的**实参种类**：`'const'` / `'expr'`。

    ★★ 为什么必须看实参（第116轮**变异 M4 逼出来的真缺陷**）：
      E2b 首版只判「`_paint_screen_doors` 里出现了 `setOpacity`」。可该函数
      `finally` 里本来就有 `painter.setOpacity(1.0)`（还原画家状态）⇒ 把
      「按逐门 alpha 落笔」那句删掉，**判据仍然绿**：被还原语句喂饱了。
      这正是本项目记过的"判据被别处/别的句子喂饱"（第115轮 `A4` 同类）。
      ⇒ 改判**实参不是常量**：只有 `setOpacity(a)`（`a` 来自门条的 alpha）才算数，
        `setOpacity(1.0)` 这种常量还原**不算**。
    """
    out = []
    if fn is None:
        return out
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'setOpacity' and n.args):
            out.append('const' if isinstance(n.args[0], ast.Constant) else 'expr')
    return out


check(u'E2b ★★★ `_paint_screen_doors` 真按**逐门 alpha** 落笔'
      u'（`setOpacity` 的实参是变量而非常量还原 ⇒ 渐显在屏幕层真有消费者）',
      'expr' in _opacity_arg_kinds(_psd),
      detail=u'setOpacity 实参种类 %r' % (_opacity_arg_kinds(_psd),))
_fake_psd = _probe_fn(u"def _paint_screen_doors(self, painter):\n"
                      u"    painter.setOpacity(1.0)\n", '_paint_screen_doors')
check(u'E2b2 ★★ 正控：只有常量 `setOpacity(1.0)`（还原）⇒ 必须判否',
      'expr' not in _opacity_arg_kinds(_fake_psd),
      detail=u'假样本种类 %r' % (_opacity_arg_kinds(_fake_psd),))
_DR = None
_dr_err = None
try:
    sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
    import door_reveal as _DR                          # noqa: E402
except Exception as _e:                                 # noqa: BLE001
    _DR = None
    _dr_err = _e
if _DR is not None:
    _SW, _SH = 2560, 1528
    _DRECT = (2423.0, 741.0, 2560.0, 859.0)            # 门 D 的屏幕矩形（真机实测）
    _ON = _DR.screen_reveal_alpha('desktop', 'D', _DRECT, _DRECT, _SW, _SH)
    _OFF = _DR.screen_reveal_alpha('desktop', 'D', (0.0, 0.0, 8.0, 8.0),
                                   _DRECT, _SW, _SH)
    check(u'E2c ★★★ 行为级：贴门 ⇒ 满实；远离 ⇒ 下限（渐显真的**随距离变**）',
          abs(_ON - _DR.MAX_ALPHA) < 1e-9 and abs(_OFF - _DR.MIN_ALPHA) < 1e-9,
          detail=u'on=%r off=%r' % (_ON, _OFF))
    _AE = _DR.screen_reveal_alpha('desktop', 'A', (0.0, 0.0, 8.0, 8.0),
                                  _DRECT, _SW, _SH)
    _BE = _DR.screen_reveal_alpha('desktop', 'B', (0.0, 0.0, 8.0, 8.0),
                                  _DRECT, _SW, _SH)
    check(u'E2d ★★★ 用户口径「oneshot 和 niko 的家不变」：A/B **恒**满实（极差 0）',
          _AE == _DR.MAX_ALPHA and _BE == _DR.MAX_ALPHA,
          detail=u'A=%r B=%r' % (_AE, _BE))
    check(u'E2e ★★ 负控制：屏幕尺寸非法 ⇒ 返 `MAX_ALPHA`'
          u'（保守侧 = **保住可见**，不是把门变看不见 —— 那是功能性损失）',
          _DR.screen_reveal_alpha('desktop', 'D', _DRECT, _DRECT, 0, 0)
          == _DR.MAX_ALPHA)
else:
    for _n in (u'E2c ★★★ 行为级：贴门 ⇒ 满实；远离 ⇒ 下限（渐显真的**随距离变**）',
               u'E2d ★★★ 用户口径「oneshot 和 niko 的家不变」：A/B **恒**满实（极差 0）',
               u'E2e ★★ 负控制：屏幕尺寸非法 ⇒ 返 `MAX_ALPHA`'
               u'（保守侧 = **保住可见**，不是把门变看不见 —— 那是功能性损失）'):
        check(_n, False, detail=u'`door_reveal` 导不进来：%r' % (_dr_err,))

# ---- E3 门 D 的贴图口径（★ 改过一次，不许再被"回退"）----
def _door_sprite_of(data, src):
    for o in (data.get('objects') or []):
        if isinstance(o, dict) and o.get('src') == src:
            return o.get('sprite')
    return None


def _door_d_ok(data):
    u"""门 D 必须是**巨门框的桌面变体**。

    ★★★ 为什么这条值得单独钉：第116轮曾据一份**摘要的转述**（只看到 10-12 那次
    AskUserQuestion「三角符文门 → spr_shortcut_door」）把 D 回退成 `spr_shortcut_door_0`。
    **那是错的** —— 10-13 那次 AskUserQuestion（选项「先保持现状（推荐）/ 换成金边拱门框
    / 换成青灰双开门」）用户回「**不是啊，是哪个门框似的哪个门**」**覆盖**了前一次。
    取证：`find116_all_ask.py` → `_evidence/rec116/find116_all_ask.txt`（:26499 / :24690）。
    """
    return _door_sprite_of(data, 'obj_doorD') == 'objs/desk_door_deltarune.png'


_dj_data = {}
try:
    with io.open(_DJSON, encoding='utf-8') as _fh:
        _dj_data = json.load(_fh)
except Exception:                                        # noqa: BLE001
    _dj_data = {}
check(u'E3 ★★★ 三角符文门 = **巨门框**桌面版（用户 10-13「不是啊，是哪个门框似的'
      u'哪个门」）—— 不许再被回退成 `spr_shortcut_door`',
      _door_d_ok(_dj_data), detail=u'got=%r' % (_door_sprite_of(_dj_data, 'obj_doorD'),))
check(u'E3b ★★ 正控：E3 抓得住"被回退成 `spr_shortcut_door`"',
      not _door_d_ok({'objects': [{'src': 'obj_doorD',
                                   'sprite': 'objs/spr_shortcut_door_0.png'}]}))

# ---- E4 对话框不再"每来一条消息就整个隐到全透明再淡回来" ----
_du_tree = _tree(_DU)
_du_fns = _fns(_du_tree)
_sd_fn = _du_fns.get('show_dialogue')


def _literal_zero_start(fn):
    u"""函数里**字面量** `setStartValue(0.0)` 的条数（= 无条件从全透明起步的老写法）。"""
    if fn is None:
        return None
    n = 0
    for sub in ast.walk(fn):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == 'setStartValue' and sub.args
                and isinstance(sub.args[0], ast.Constant)
                and sub.args[0].value == 0.0):
            n += 1
    return n


check(u'E4a ★★★ `dialogue_ui` 有纯函数 `fade_plan`（该不该重淡入的唯一真源）',
      'fade_plan' in _du_fns)
_z0 = _literal_zero_start(_sd_fn)
check(u'E4b ★★★ `show_dialogue` 里**再无**字面量 `setStartValue(0.0)`'
      u'（老写法 = 每来一条消息先整个隐到全透明 ⇒ 用户看到的"对话框闪现"）',
      (_z0 == 0), detail=u'字面量 0.0 起步 = %r 处' % (_z0,))
_fake_sd = _probe_fn(u"def show_dialogue(self):\n"
                     u"    self._fade_anim.setStartValue(0.0)\n", 'show_dialogue')
check(u'E4c ★★ 正控：`_literal_zero_start` 抓得住老写法',
      (_literal_zero_start(_fake_sd) == 1))
_DU_MOD = None
_du_err = None
try:
    if os.path.join(ROOT, 'ralsei_pet', 'modules') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
    import dialogue_ui as _DU_MOD                      # noqa: E402
except Exception as _e:                                 # noqa: BLE001
    _DU_MOD = None
    _du_err = _e
if _DU_MOD is not None and hasattr(_DU_MOD, 'fade_plan'):
    _FP = _DU_MOD.fade_plan
    # 真机实测：Windows 上 windowOpacity() 回读取整 ⇒ 稳态是 0.976（写入 0.98）
    _r_steady = _FP(True, 0.976)
    _r_hidden = _FP(False, 0.0)
    _r_mid = _FP(True, 0.2)
    check(u'E4d ★★★ 行为级：**已可见 + 已在稳态（含取整容差）** ⇒ 不重淡入、直接钉稳态',
          _r_steady[1] is False and abs(_r_steady[0] - _DU_MOD.STEADY_OPACITY) < 1e-9,
          detail=u'fade_plan(True,0.976)=%r' % (_r_steady,))
    check(u'E4e ★★★ 行为级：不可见 ⇒ 从 0 淡入；可见但没到位 ⇒ **从当前值**续淡'
          u'（起点绝不低于当前值 ⇒ 任何路径都不会"忽然全隐"）',
          _r_hidden == (0.0, True) and _r_mid[1] is True
          and abs(_r_mid[0] - 0.2) < 1e-9,
          detail=u'hidden=%r mid=%r' % (_r_hidden, _r_mid))
    check(u'E4f ★★ 负控制：两种输入必须给**不同**结果（防实现退化成恒等）',
          _r_steady != _r_hidden)
else:
    for _n in (u'E4d ★★★ 行为级：**已可见 + 已在稳态（含取整容差）** ⇒ 不重淡入、直接钉稳态',
               u'E4e ★★★ 行为级：不可见 ⇒ 从 0 淡入；可见但没到位 ⇒ **从当前值**续淡'
               u'（起点绝不低于当前值 ⇒ 任何路径都不会"忽然全隐"）',
               u'E4f ★★ 负控制：两种输入必须给**不同**结果（防实现退化成恒等）'):
        check(_n, False, detail=u'`dialogue_ui` 导不进来/无 `fade_plan`：%r' % (_du_err,))

# ---- E5 场景层不再"每帧抢一次顶层" ----
_ssl = _m_fns.get('_show_scene_layer')
_e5 = False
if _ssl is not None:
    _e5 = ('raise_' not in _bare_call_attrs(_ssl))
check(u'E5 ★★★ `_show_scene_layer` 里 `raise_()` **被条件守卫**（不再每帧无条件抢顶层）'
      u'—— 与"永远置顶"的任务栏反复争位就是那条带高频闪的机理',
      _e5, detail=u'函数体顶层裸调用 = %r'
      % (_bare_call_attrs(_ssl) if _ssl else [],))
_fake_ssl = _probe_fn(u"def _show_scene_layer(self):\n"
                      u"    self.scene_canvas.raise_()\n", '_show_scene_layer')
check(u'E5b ★★ 负控制：E5 抓得住"无条件 `raise_()`"的老写法',
      ('raise_' in _bare_call_attrs(_fake_ssl)))


sec(u'D. 判据自身体检')

# ★★ D 段记账的两个坑（首版各踩了一次，写下来免得后人再犯）：
#   ① `check()` 是**先求值 cond、再把名字登记进 `_NAMES`**。所以 D1 自己求值时
#      `_NAMES` 里**还没有 D 段任何一条** ⇒ 只能拿它数 A/B/C/E。
#   ② 想数"总数"，必须放在**最后一条**，此时看到的是"前面全部 + D1~D4"。
_PRE_D_EXPECT = 35        # A=8 · B=4 · C=4 · E=19（E2b2 是本轮变异 M4 逼出来的）
check(u'D1 A/B/C/E 段条数记账 = %d' % _PRE_D_EXPECT,
      len(_NAMES) == _PRE_D_EXPECT, detail=u'实到 %d' % len(_NAMES))
# D2 名字里不许带"计数标记"（否则一改名就假红）
#   ★ 天然的自我排除：D2 求值时 `_NAMES` 只到 D1 ⇒ 它管的是 A/B/C（+D1）。
#     这够用 —— 这条判据的用途就是"**以后改 A/B/C 时**别把计数写进名字"。
check(u'D2 判据名里不含计数标记（"第N条"/"共N项"）',
      not any(('第' in n and '条' in n) or ('共' in n and '项' in n)
              for n in _NAMES))
# D3 无重名
check(u'D3 判据名无重复', len(set(_NAMES)) == len(_NAMES))
# D4 ★★ 无恒真判据：AST 查本文件所有 `check(name, X)` 的第二实参不是字面量 True
_src_self = _read(os.path.abspath(__file__))
_taut = []
for _node in ast.walk(ast.parse(_src_self)):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and len(_node.args) >= 2:
        _a = _node.args[1]
        if isinstance(_a, ast.Constant) and _a.value is True:
            _taut.append(getattr(_node, 'lineno', -1))
check(u'D4 无恒真判据（`check(..., True)` 字面量）', not _taut,
      detail=u'行号 %r' % (_taut,))
# D5 ★★ 反"判据崩掉吞掉后面"：D1~D4 必须**都真的登记过**
#    （本项目 115 轮踩过：一条判据抛异常 ⇒ 后面整段静默消失，看着还是绿）
check(u'D5 D1~D4 都真的跑到（没有崩掉吞掉）',
      len(_NAMES) == _PRE_D_EXPECT + 4, detail=u'实到 %d' % len(_NAMES))

# ---- 清理临时区（**只动自己建的 mkdtemp**，绝不碰仓库/用户目录）----
try:
    shutil.rmtree(_tmp, ignore_errors=True)
except Exception:
    pass

print(u'\n合计 PASS=%d FAIL=%d（共 %d 条）' % (ok, fail, ok + fail))
sys.exit(1 if fail else 0)
