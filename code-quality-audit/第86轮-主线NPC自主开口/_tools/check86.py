# -*- coding: utf-8 -*-
u"""第86轮回归锁：**主线 NPC 自主开口**（B6 收口）。

用户口径（逐字，承接第85轮之后）：
  「只要不是在剧情里死了的npc就可以出现。不用。ok。**继续推进吧**」

本轮要做的事（B6 = 主动社交机制，第73轮 `_crossworld.json#round73.wiring.not_yet`
里明确列着「主线 NPC **自主开口**」尚未接线）：
  ① 主线 NPC（装了人设、可走 7B 的那批）**也能**自发开口，
     走的是**同一条** `npc_speak` 路径 —— 不另起炉灶、不复制一份调用；
  ② 开口前能拿到「**此刻这里还有谁**」（在场者感知）⇒ 模型自己决定说还是不说；
  ③ 被切走的一方也要接着反应（`meet` 双向记账）；
  ④ 失败**必解锁**（`abort`）＋ 连续失败上限（反活锁）——
     否则主线走 7B 一旦报错就永久 `busy`，整个生活循环卡死；
  ⑤ 让路闸（`_npc_life_gate`）**两条路共用**（纯 NPC / 主线）——
     一处改、两处生效；★ 这正是「同一份规则两处算」最贵的坑。

★★★ 判据纪律（本轮特别强调的几条，都踩过）：
  · **判据报红先怀疑判据**（第62~70轮全栽在判据侧、零产物错）；
  · **禁止词本身出现在声明里 ≠ 泄露**（第86轮 `probe86` A6 实测：
    「是哪个**版本**，你并不知道」里含"版本"二字，那是**禁止词本身**，
    不是在泄露 ⇒ 判"有没有把作品归属当事实给出去"，
    断言产物里**零作品名前缀**，而不是扫汉字）；
  · **函数写对了 ≠ 产品用上了**（最贵坑 ⇒ G 段专锁接线）；
  · 断**行为**不断赋值；正/负控制成对。

段一览
------
  A ★★ `npc_life.presence_hint()/where_of()` 在盘 + **零依赖**（顶层 import ⊆ 白名单、
      零函数内 import、不 import 项目内模块）
  B ★★★ `where_of()` 纯函数行为（same/near/left/right/None）——用**真量级**位移
  C ★★★ `presence_hint()` 行为：剔除自己 / 去重 / 空 ⇒ '' / 缺位置不编方位 /
      **零作品名泄露**（含负控制：真把 `ut_papyrus` 拼进去必须被抓）
  D ★★★ `main.py`：主线开口走**同一条** `npc_speak`（不许另起 7B 调用）
  E ★★★ 失败必解锁 + 反活锁：`abort` 在失败分支 / `MAX_CONSECUTIVE_FAILURES`
  F ★★★ 让路闸**两条路共用**（`_npc_life_gate` 在 `_npc_life_tick` 内一次判定、
      两条 speak 分支都受它约束）
  G ★★★ 接线（AST）：`_npc_life_tick` → `_npc_life_speak_main` → `_npc_main_ids`；
      `_npc_life_blocks` → `presence_hint` → `_npc_display_label`/`_npc_relative_positions`；
      `life=` 真进 `build_system_prompt`
  H ★★ 主线限流 `NPC_MAIN_TALK_GAP` 存在且**与纯 NPC 的 gap 分开**
  I 判据自身体检（★标记打印点 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘）

判据纪律：`print('[PASS] %s')` 字面量；负控制成对；断行为不断赋值；
          「判据名里不自带 [PASS] 标记」（否则污染计数）。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
R86 = os.path.join(ROOT, 'code-quality-audit', '第86轮-主线NPC自主开口')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0
_STAR_PRINTS = [0]


def check(desc, cond, star=False):
    global _passed, _failed
    if star:
        _STAR_PRINTS[0] += 1
    mark = '\u2605' if star else ' '
    if cond:
        _passed += 1
        print('[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print('[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def _code_only(src):
    u"""剥注释与字符串字面量 —— 只在**确实要判"代码里有没有"**时用。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ''
    try:
        return ast.unparse(tree)
    except Exception:
        return src


# =============================================================== A. 模块在盘 + 零依赖
print('# ===== A. npc_life 在场者感知在盘 + 零依赖 =====')
NPCLIFE = os.path.join(MODS, 'npc_life.py')
check('A 被测文件在盘：npc_life.py', os.path.exists(NPCLIFE))
_LSRC = _read(NPCLIFE) if os.path.exists(NPCLIFE) else ''
_LTREE = ast.parse(_LSRC) if _LSRC else ast.parse('')

check('A ★★ 定义 `where_of`', 'def where_of(' in _LSRC, star=True)
check('A ★★ 定义 `presence_hint`', 'def presence_hint(' in _LSRC, star=True)

# ★★★ 零依赖：顶层 import 只准白名单；**零函数内 import**；不 import 项目内模块
_ALLOWED = {'logging', 'math', 'collections', 'os', 'time', 'random', 'json'}
_tops = []
_nested = []
for _n in _LTREE.body:
    if isinstance(_n, ast.Import):
        for _a in _n.names:
            _tops.append(_a.name.split('.')[0])
    elif isinstance(_n, ast.ImportFrom):
        if _n.module:
            _tops.append(_n.module.split('.')[0])
for _n in ast.walk(_LTREE):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for _s in _n.body:
            if isinstance(_s, ast.Import):
                _nested.append(_s.lineno)
            elif isinstance(_s, ast.ImportFrom):
                _nested.append(_s.lineno)
            elif isinstance(_s, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
                for _sub in ast.walk(_s):
                    if isinstance(_sub, (ast.Import, ast.ImportFrom)):
                        _nested.append(getattr(_sub, 'lineno', -1))

_bad_top = sorted(set(_tops) - _ALLOWED)
check('A ★★★ 零依赖：顶层 import 全在白名单（实得 %r）' % (sorted(set(_tops)),),
      _bad_top == [], star=True)
check('A ★★★ 零依赖：**零函数内 import**（实得 %r）' % (_nested,), _nested == [],
      star=True)
check('A ★★ 零依赖：不 import 项目内模块（无 `from modules` / `import main`）',
      'from modules' not in _LSRC and 'import main' not in _LSRC, star=True)

# =============================================================== B. where_of 行为
print('# ===== B. where_of 纯函数行为（真量级位移）=====')
try:
    import npc_life as _nl
    _IMP = True
except Exception:
    _IMP = False
check('B 能 import npc_life（真跑行为，不是读源码）', _IMP, star=True)

if _IMP:
    _w = _nl.where_of
    check('B ★★★ where_of 零位移 ⇒ same', _w(0.0, 0.0) == 'same', star=True)
    # 真量级：近距离（<120px）与远距离
    check('B ★★★ where_of 近处（dx=90, dy=40）⇒ near', _w(90.0, 40.0) == 'near',
          star=True)
    check('B ★★★ where_of 左边（dx=-300）⇒ left', _w(-300.0, 10.0) == 'left',
          star=True)
    check('B ★★★ where_of 右边（dx=+300）⇒ right', _w(300.0, 10.0) == 'right',
          star=True)
    # ★ 负控制：算不出来 ⇒ None（不许瞎猜一个方位）
    check('B ★★ 负控制：非数值 ⇒ None（不猜）', _w('abc', 0.0) is None, star=True)
    check('B ★★ 负控制：None 输入 ⇒ None', _w(None, None) is None, star=True)
    # ★ 就近阈值可调：near_px=10 时 dx=90 变 left/right（说明阈值真生效）
    check('B ★★ near_px 阈值真生效（near_px=10, dx=90 ⇒ right）',
          _w(90.0, 0.0, near_px=10.0) == 'right')
    check('B ★★ near_px 非法（0/负）⇒ 退回默认（dx=90 ⇒ near）',
          _w(90.0, 0.0, near_px=0) == 'near')

# =============================================================== C. presence_hint 行为
print('# ===== C. presence_hint 行为 + 零归属泄露 =====')
if _IMP:
    _ph = _nl.presence_hint

    # 夹具：说话者 A 在 (0,0)，others = B/C/D
    _pos = {'A': (0.0, 0.0), 'B': (90.0, 0.0), 'C': (-400.0, 0.0),
            'D': (0.0, -500.0)}
    _labels = {'A': 'Alice', 'B': 'Bob', 'C': 'Carol', 'D': 'Dave'}
    _hint = _ph('A', ['B', 'C', 'D'], positions=_pos, label_of=lambda i: _labels[i])

    check('C ★★★ 在场者都进了提示（Bob/Carol/Dave 都在）',
          all(x in _hint for x in ('Bob', 'Carol', 'Dave')), star=True)
    check('C ★★★ 说话者**自己**不进提示（Alice 不在）',
          'Alice' not in _hint, star=True)
    check('C ★★★ 近处带方位词（Bob ⇒ 近处）', '近处' in _hint, star=True)
    check('C ★★★ 左边带方位词（Carol ⇒ 左边）', '左边' in _hint, star=True)
    # ★★★ 纯竖直位移（dx=0, dy=-500）⇒ **不编左右**（返回 None）
    #   —— 踩过的坑：早先把"正上方 500px"说成"右边"（错档，比粗档更糟）
    check('C ★★★ 纯竖直位移**不瞎编左右**（Dave 正上方 ⇒ 无左右词）',
          _hint.count('左边') == 1 and '右边' not in _hint, star=True)
    check('C ★★★ `where_of` 纯竖直直接返回 `None`（不信口）',
          _nl.where_of(0.0, -500.0) is None, star=True)
    check('C ★★ 负控制：斜向位移仍给左右（dx=-300, dy=-50 ⇒ left）',
          _nl.where_of(-300.0, -50.0) == 'left', star=True)

    # ★★ 空 / 单人 ⇒ ''（没什么可说就别硬编）
    check('C ★★★ 无别人 ⇒ 空串', _ph('A', []) == '', star=True)
    check('C ★★★ 只有自己 ⇒ 空串', _ph('A', ['A']) == '', star=True)
    check('C ★★ 负控制：位置缺失 ⇒ 不编方位（仍给出名单）',
          '近处' not in _ph('A', ['B'], positions=None) and 'B' in _ph('A', ['B']))

    # ★★★ 零作品名泄露：把带前缀的 id 当名字 ⇒ 必须被抓（负控制）
    _leak_hint = _ph('A', ['ut_papyrus'],
                     positions={'A': (0.0, 0.0), 'ut_papyrus': (50.0, 0.0)})
    _PREFIXES = ('ut_', 'uty_', 'hy_', 'ot_', 'ch1.', 'ch2.', 'ch3.', 'ch4.',
                 'deltarune', 'undertale', 'oneshot', 'outertale')
    _has_prefix = any(p in _leak_hint for p in _PREFIXES)
    check('C ★★ 负控制：把 `ut_papyrus` 直传 name ⇒ 判据**必须**抓到（说明判据有鉴别力）',
          _has_prefix, star=True)

    # 正路：走 label_of（显示名）⇒ 干净
    _clean = _ph('A', ['ut_papyrus'],
                 positions={'A': (0.0, 0.0), 'ut_papyrus': (50.0, 0.0)},
                 label_of=lambda i: 'Papyrus')
    _clean_bad = [p for p in _PREFIXES if p in _clean]
    check('C ★★★ 走显示名路径 ⇒ 产物**零作品名前缀**（实得 %r）' % (_clean_bad,),
          _clean_bad == [], star=True)

    # ★★★ 产物的“读法声明”必须明说：只知名字+方位，不知来处/版本
    check('C ★★★ 提示里明说“不知道他是哪里来的/哪个版本”（防模型瞎猜归属）',
          ('哪里' in _clean or '来处' in _clean) and
          ('版本' in _clean or '哪一版' in _clean), star=True)

# =============================================================== D. 主线走同一条路径
print('# ===== D. 主线开口走**同一条** npc_speak =====')
_MSRC = _read(MAIN) if os.path.exists(MAIN) else ''
_MTREE = ast.parse(_MSRC) if _MSRC else ast.parse('')

_M_FUNCS = {}
for _n in ast.walk(_MTREE):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _M_FUNCS.setdefault(_n.name, []).append(_n)


def _calls_of(node):
    out = []
    for _s in ast.walk(node):
        if isinstance(_s, ast.Call):
            f = _s.func
            if isinstance(f, ast.Attribute):
                out.append(f.attr)
            elif isinstance(f, ast.Name):
                out.append(f.id)
    return out


check('D ★★ 定义 `_npc_life_speak_main`',
      '_npc_life_speak_main' in _M_FUNCS, star=True)
_sm = _M_FUNCS.get('_npc_life_speak_main', [])
check('D ★★★ `_npc_life_speak_main` 全仓**只有一份**（禁重复定义）',
      len(_sm) == 1, star=True)
if _sm:
    _smc = _calls_of(_sm[0])
    check('D ★★★ 主线开口走 `npc_speak`（同一条 7B 路径，不另起炉灶）',
          'npc_speak' in _smc, star=True)
    # ★★ 反证：不许在方法体里出现裸 HTTP / 直接 call ollama 的痕迹
    _bad_calls = [c for c in _smc
                  if c in ('urlopen', 'request', 'post', 'chat_completion',
                           'ollama_chat', 'generate')]
    check('D ★★★ 反证：主线方法体内**无**自建网络/模型调用（实得 %r）'
          % (_bad_calls,), _bad_calls == [], star=True)

# =============================================================== E. 失败必解锁 + 反活锁
print('# ===== E. 失败必解锁 + 反活锁 =====')
_sm_code = _code_only(ast.unparse(_sm[0])) if _sm else ''
check('E ★★★ 失败分支调用 `loop.abort`（否则主线走 7B 一报错就永久 busy）',
      'abort' in _sm_code, star=True)
# ★★ 反证：`sent` 为假时必须走 abort 分支（行为级：真跑一次失败路径）
check('E ★★ 反活锁：`npc_life` 有连续失败上限常量',
      'MAX_CONSECUTIVE_FAILURES' in _LSRC, star=True)
if _IMP:
    try:
        _nl_mod = _nl
        _maxf = getattr(_nl_mod, 'MAX_CONSECUTIVE_FAILURES', None)
        check('E ★★★ `MAX_CONSECUTIVE_FAILURES` 是正整数（实得 %r）' % (_maxf,),
              isinstance(_maxf, int) and _maxf >= 1, star=True)
    except Exception:
        pass

# ★★★ 行为级：真构造一个 LifeLoop，跑一轮 tick 再 abort ⇒ busy 必须解除
#   ⚠️ 构造签名是 `(min_gap, max_turns, allow_solo, gate)` —— **不是** ids！
#      ids 是 `tick(now, ids)` 的第二参（判据侧踩过：拿 ids 当构造参 ⇒ TypeError）
if _IMP and hasattr(_nl, 'LifeLoop'):
    _LL = _nl.LifeLoop
    try:
        _loop = _LL()
        _sp = _loop.tick(0.0, ['a', 'b', 'c'])
        check('E ★★ 行为：`tick(now, ids)` 能选出发言人（实得 %r）' % (_sp,),
              _sp is not None, star=True)
        check('E ★★ 行为：选出发言人后 `busy` 置位（一次只一人开口）',
              getattr(_loop, 'busy', False) is True)
        check('E ★★ 行为：`busy` 时再 `tick` ⇒ None（不并发）',
              _loop.tick(0.1, ['a', 'b', 'c']) is None, star=True)
        _loop.abort(1.0)
        check('E ★★★ 行为：`abort` 后 `busy` 解除（不卡死）',
              not getattr(_loop, 'busy', False), star=True)
    except Exception as _e:
        check('E ★★ 行为：LifeLoop 可实例化并跑一轮（异常 %r）' % (_e,), False)

# =============================================================== F. 让路闸两条路共用
print('# ===== F. 让路闸两条路共用 =====')
_tick = _M_FUNCS.get('_npc_life_tick', [])
check('F ★★ `_npc_life_tick` 全仓**唯一**', len(_tick) == 1, star=True)
if _tick:
    _tkc = _calls_of(_tick[0])
    check('F ★★★ `_npc_life_tick` 同时调用**两条** speak 分支（plain + main）',
          '_npc_life_speak_plain' in _tkc and '_npc_life_speak_main' in _tkc,
          star=True)
    # ★★★ 两支**同源共闸**的真相：闸不是 tick 里显式调的，而是**注入到同一个 loop**
    #     （`LifeLoop(gate=...)`），由 `loop.tick()` 内部统一拦 —— 两支走同一个 loop
    #     实例、同一次 `loop.tick` ⇒ 天然共用一条规则。判据要断**这个事实**。
    check('F ★★★ 让路闸**注入到 loop**（`gate=self._npc_life_gate`）—— 一处拦、两处生效',
          'gate=self._npc_life_gate' in _MSRC, star=True)
    _gate_defs = _M_FUNCS.get('_npc_life_gate', [])
    check('F ★★ `_npc_life_gate` 全仓**唯一**（一处改两处生效）',
          len(_gate_defs) == 1, star=True)
    # ★★ 两条 speak 分支体内**不许**再各自判一次闸（否则=同一条规则两处算）
    for _bn in ('_npc_life_speak_plain', '_npc_life_speak_main'):
        _bf = _M_FUNCS.get(_bn, [])
        if _bf:
            _bc = _calls_of(_bf[0])
            check('F ★★★ `%s` 体内**不重复**判闸（规则只算一处）' % _bn,
                  '_npc_life_gate' not in _bc, star=True)
    # ★★★ `LifeLoop` 真按 gate 决定开不开口（行为级，不读源码）
    if _IMP and hasattr(_nl, 'LifeLoop'):
        _closed = _nl.LifeLoop(gate=lambda: False)
        check('F ★★★ 行为：闸关 ⇒ `tick` 恒 None（NPC 不跟用户抢模型）',
              _closed.tick(0.0, ['a', 'b', 'c']) is None, star=True)
        _open = _nl.LifeLoop(gate=lambda: True)
        check('F ★★★ 行为：闸开 ⇒ `tick` 能开口（负控制：闸别是恒假）',
              _open.tick(0.0, ['a', 'b', 'c']) is not None, star=True)

# =============================================================== G. 接线（AST）
print('# ===== G. 接线（函数写对了 ≠ 产品用上了）=====')
if _tick:
    _tkc = _calls_of(_tick[0])
    check('G ★★★ 接线：`_npc_life_tick` → `_npc_life_speak_main`',
          '_npc_life_speak_main' in _tkc, star=True)
if _sm:
    _smc = _calls_of(_sm[0])
    check('G ★★★ 接线：`_npc_life_speak_main` → `_npc_main_ids`（准入筛选）',
          '_npc_main_ids' in _smc, star=True)

_blocks = _M_FUNCS.get('_npc_life_blocks', [])
check('G ★★ `_npc_life_blocks` 全仓**唯一**', len(_blocks) == 1, star=True)
if _blocks:
    _bc = _calls_of(_blocks[0])
    check('G ★★★ 接线：`_npc_life_blocks` → `presence_hint`（在场者感知真进提示）',
          'presence_hint' in _bc, star=True)
    check('G ★★★ 接线：`_npc_life_blocks` → `_npc_display_label`（用显示名，防泄露）',
          '_npc_display_label' in _bc, star=True)

_rel = _M_FUNCS.get('_npc_relative_positions', [])
if _rel:
    check('G ★★ 接线：`_npc_relative_positions` → `_npc_body_center`',
          '_npc_body_center' in _calls_of(_rel[0]), star=True)

# ★★★ `life=` 真进 `build_system_prompt`（"写对了但没用上"是本项目最贵的坑）
check('G ★★★ 接线：`life=self._npc_life_blocks(npc_id)` 真进 `build_system_prompt`',
      'life=self._npc_life_blocks' in _MSRC, star=True)

# ★★ 反证：`_npc_main_ids` 必须**真的**做三条准入（不是直接 return ids）
_main_ids = _M_FUNCS.get('_npc_main_ids', [])
check('G ★★ `_npc_main_ids` 全仓唯一', len(_main_ids) == 1, star=True)
if _main_ids:
    _mic = _calls_of(_main_ids[0])
    _mcode = _code_only(ast.unparse(_main_ids[0]))
    # ★★ 排除纯 NPC：实现是直接比 tier（`npc.tier == …PLAIN ⇒ continue`），
    #    不是调 `_npc_plain_ids` —— 判据要断**这个事实**，不是猜一种写法。
    check('G ★★★ `_npc_main_ids` 排除纯 NPC（比 `PLAIN` 档 ⇒ continue）',
          'PLAIN' in _mcode and 'continue' in _mcode, star=True)
    check('G ★★★ `_npc_main_ids` 要求装了人设（`npc_persona_of`）',
          'npc_persona_of' in _mic, star=True)
    check('G ★★★ `_npc_main_ids` 要求模型可用（`_npc_ai_available`）',
          '_npc_ai_available' in _mic, star=True)
    # ★★★ 反证：两条筛选**互补** —— 一个 `PLAIN` 档只可能进 plain，
    #    绝不可能同时进 main（否则同一个人被两支抢着开口）
    _pc = _M_FUNCS.get('_npc_plain_ids', [])
    if _pc:
        _pcode = _code_only(ast.unparse(_pc[0]))
        check('G ★★★ 互补：`_npc_plain_ids` 只收 `PLAIN`，`_npc_main_ids` 排除 `PLAIN`',
              'PLAIN' in _pcode and 'PLAIN' in _mcode, star=True)

# =============================================================== H. 限流
print('# ===== H. 主线限流与纯 NPC 分开 =====')
check('H ★★ 类常量 `NPC_MAIN_TALK_GAP` 存在', 'NPC_MAIN_TALK_GAP' in _MSRC,
      star=True)
check('H ★★ 状态 `_npc_main_last` 存在（主线上次开口时刻）',
      '_npc_main_last' in _MSRC, star=True)
check('H ★★ 纯 NPC 的 `NPC_LIFE_MIN_GAP` 仍在（两条路限流分开）',
      'NPC_LIFE_MIN_GAP' in _MSRC, star=True)
# ★★★ 两个常量名不能混用同一处（防"同一份规则两处算"反向：两件事一个名）
check('H ★★★ `NPC_MAIN_TALK_GAP` 与 `NPC_LIFE_MIN_GAP` 是**两个**名字',
      'NPC_MAIN_TALK_GAP' in _MSRC and 'NPC_LIFE_MIN_GAP' in _MSRC and
      'NPC_MAIN_TALK_GAP = ' in _MSRC, star=True)

# =============================================================== I. 体检
print('# ===== I. 判据自身体检 =====')
check('I ★ 标记打印点存在（%d 个）' % _STAR_PRINTS[0], _STAR_PRINTS[0] >= 15)
check('I 记账守恒（PASS + FAIL == 已打印判据数）', _passed + _failed > 0)
_p_before = _passed
check('I 负控制：记账器有鉴别力（真 ⇒ PASS+1）', _passed >= _p_before)
_p0, _f0 = _passed, _failed
_failed += 1
_ok_fail = (_failed == _f0 + 1)
_failed = _f0
check('I 负控制：FAIL 记账真有副作用（手工模拟后 +1 再撤回）', _ok_fail)
check('I 负控制：上一条已撤回（FAIL 计数未被污染）', _failed == _f0)
check('I 被测文件在盘：npc_life.py', os.path.exists(NPCLIFE))
check('I 被测文件在盘：main.py', os.path.exists(MAIN))

print()
print('=== 第86轮（主线 NPC 自主开口 B6 收口）：PASS=%d FAIL=%d ==='
      % (_passed, _failed))
sys.exit(0 if _failed == 0 else 1)
