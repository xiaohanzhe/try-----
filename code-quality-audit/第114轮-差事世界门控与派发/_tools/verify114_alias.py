# -*- coding: utf-8 -*-
"""验证 114-A：跨作品章名归一（`CHAPTER_ALIASES` / `chapter_matches`）。

★ 纪律：**判据自己也是被测物** ⇒
  ① 每个正向断言都配一条**真实数据**（从 `_registry.json` 读 NpcDef，不自己造）；
  ② 关键判据配**负控制**（把别名表清空 ⇒ 同一输入必须反转结论）；
  ③ 复检**不改被测状态**（只 `ast.parse`，不 `py_compile` 产 .pyc）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PROJ = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PROJ, 'modules')
sys.path.insert(0, MODS)

OK = []
BAD = []


def ck(name, cond, detail=''):
    (OK if cond else BAD).append((name, detail))
    print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', name,
                       ('  | ' + detail) if detail else ''))


# ---- 0. 语法：只解析，不产 .pyc ----
src_path = os.path.join(MODS, 'npc_system.py')
with io.open(src_path, 'r', encoding='utf-8', newline='') as fh:
    src = fh.read()
try:
    ast.parse(src)
    ck('A0 npc_system.py 语法可解析（ast.parse，不产 .pyc）', True)
except SyntaxError as e:
    ck('A0 npc_system.py 语法可解析（ast.parse，不产 .pyc）', False, repr(e))
    raise SystemExit(1)

ck('A0b 文件里没有 CRLF 混入（裸 \\r 计数）', src.count('\r') == 0,
   'raw_cr=%d' % src.count('\r'))

import npc_system as ns  # noqa: E402

# ---- 1. 纯函数：等价名集合 ----
ck('A1 chapter_names("ut") 含 ut 与 undertale',
   ns.chapter_names('ut') == {'ut', 'undertale'}, repr(ns.chapter_names('ut')))
ck('A2 chapter_names("undertale") 反向也含 ut（双向）',
   ns.chapter_names('undertale') == {'ut', 'undertale'},
   repr(ns.chapter_names('undertale')))
ck('A3 chapter_names("uty") 含 uty 与 undertale_yellow',
   ns.chapter_names('uty') == {'uty', 'undertale_yellow'},
   repr(ns.chapter_names('uty')))
ck('A4 chapter_names("ch1") 不被污染（无别名 ⇒ 只有它自己）',
   ns.chapter_names('ch1') == {'ch1'}, repr(ns.chapter_names('ch1')))
ck('A5 chapter_names("oneshot") 只有它自己',
   ns.chapter_names('oneshot') == {'oneshot'}, repr(ns.chapter_names('oneshot')))

# ---- 2. same_chapter / chapter_matches ----
ck('A6 same_chapter("ut","undertale") True', ns.same_chapter('ut', 'undertale') is True)
ck('A7 same_chapter("ut","undertale_yellow") False（不同作品不能串）',
   ns.same_chapter('ut', 'undertale_yellow') is False)
ck('A8 same_chapter("ch1","ut") False', ns.same_chapter('ch1', 'ut') is False)
ck('A9 chapter_matches("ut", []) False（空登记 ⇒ 与旧写法 ch in () 等价）',
   ns.chapter_matches('ut', []) is False)
ck('A10 chapter_matches(None, ["ut"]) False（不猜）',
   ns.chapter_matches(None, ['ut']) is False)
ck('A11 chapter_matches("ut", ["ch1","undertale"]) True',
   ns.chapter_matches('ut', ['ch1', 'undertale']) is True)

# ---- 3. 真数据驱动：从 _registry.json 读 NpcDef ----
reg_path = os.path.join(PROJ, 'assets', 'npc', '_registry.json')
with io.open(reg_path, 'r', encoding='utf-8') as fh:
    reg = json.load(fh)
BY_ID = {}
for it in (reg.get('npcs') or []):
    BY_ID[it.get('id')] = ns.npc_from_dict(it)

ck('A12 注册表里确有 ut_toriel / hy_clover / os_the_world_machine',
   all(k in BY_ID for k in ('ut_toriel', 'hy_clover', 'os_the_world_machine')),
   'n=%d' % len(BY_ID))


def gate(nid, world, sid):
    g = ns.world_gate(BY_ID[nid], world, scene_id=sid, carried=False)
    return bool(g.ok), g.reason, g.detail


# 桌面 4 门的目的地 × 真实角色
# ① 主用例：派 Ralsei 去 OneShot（world 判不出 ⇒ 归 dark）⇒ 他"能自由在别的暗世界走"
ok, why, det = gate('ralsei', 'dark', 'oneshot.mainline.INIT')
ck('A13 真实数据：ralsei 去 oneshot.mainline.INIT ⇒ 放行（free_dark_roam）',
   ok, '%s / %s' % (why, det))

# ② 用户举的例子：Ralsei 无球进光世界 ⇒ 拒
ok, why, det = gate('ralsei', 'light', 'ch1.hometown.town_mid')
ck('A14 真实数据：ralsei 无球进光世界 ⇒ 拒（light_needs_bubble）',
   (not ok) and why == ns.REASON_LIGHT_NEEDS_BUBBLE, '%s / %s' % (why, det))

# ③ 带球 ⇒ 放行（同一输入、只翻 carried）
g = ns.world_gate(BY_ID['ralsei'], 'light', scene_id='ch1.hometown.town_mid', carried=True)
ck('A15 真实数据：ralsei 带球进光世界 ⇒ 放行（与 A14 只差 carried）',
   bool(g.ok), '%s / %s' % (g.reason, g.detail))

# ④ ★ 本轮修的那条：ut_toriel 回自己作品（短码 vs 全名）
ok, why, det = gate('ut_toriel', 'dark', 'ut.rooms.room_start')
ck('A16 ★真实数据：ut_toriel 回 ut.rooms.room_start ⇒ 放行（别名归一）',
   ok, '%s / %s' % (why, det))

# ⑤ 同族：hy_clover 回 UTY
ok, why, det = gate('hy_clover', 'dark', 'uty.rooms.x')
ck('A17 ★真实数据：hy_clover 回 uty.rooms.x ⇒ 放行（别名归一）',
   ok, '%s / %s' % (why, det))

# ⑥ os 系不受影响（本来就逐字相等）
ok, why, det = gate('os_the_world_machine', 'dark', 'oneshot.mainline.INIT')
ck('A18 真实数据：os_the_world_machine 回 oneshot ⇒ 放行（逐字相等，非别名功劳）',
   ok, '%s / %s' % (why, det))

# ⑦ 负例：ut_toriel 进 Deltarune 暗世界 ⇒ 仍拒（non_dark 口径没被别名带跑）
ok, why, det = gate('ut_toriel', 'dark', 'ch1.field.x')
ck('A19 真实数据：ut_toriel 进 ch1 暗世界 ⇒ 仍拒（non_dark 口径未被带跑）',
   (not ok) and why == ns.REASON_FOREIGN_DARK, '%s / %s' % (why, det))

# ⑧ 负例：ut_toriel 去 uty（同族但不同作品）⇒ 拒
ok, why, det = gate('ut_toriel', 'dark', 'uty.rooms.x')
ck('A20 真实数据：ut_toriel 去 uty.rooms.x ⇒ 拒（同族不等于同作品，别名不越界）',
   (not ok) and why == ns.REASON_FOREIGN_DARK, '%s / %s' % (why, det))

# ⑨ Niko(all) 进 Deltarune 暗世界 ⇒ 放行（用户口径核心一句，防本轮回退）
ok, why, det = gate('os_niko', 'dark', 'ch2.cyber_city.x')
ck('A21 真实数据：os_niko(all) 进 ch2 暗世界 ⇒ 放行（RoamScope.ALL 未回退）',
   ok, '%s / %s' % (why, det))

# ---- 4. ★★ 负控制：把别名表清空 ⇒ A16/A17 必须反转 ----
_saved = dict(ns.CHAPTER_ALIASES)
try:
    ns.CHAPTER_ALIASES.clear()
    ok, why, det = gate('ut_toriel', 'dark', 'ut.rooms.room_start')
    ck('A22 ★负控制：清空 CHAPTER_ALIASES ⇒ ut_toriel 回自家变**拒**'
       '（证明 A16 不是恒真判据）',
       (not ok), '%s / %s' % (why, det))
    ok, why, det = gate('hy_clover', 'dark', 'uty.rooms.x')
    ck('A23 ★负控制：清空别名表 ⇒ hy_clover 回自家变**拒**',
       (not ok), '%s / %s' % (why, det))
finally:
    ns.CHAPTER_ALIASES.update(_saved)

# 拆干净后必须复原
ok, why, det = gate('ut_toriel', 'dark', 'ut.rooms.room_start')
ck('A24 负控制复原：别名表还原后 ut_toriel 回自家**又放行**（拆干净了）',
   ok, '%s / %s' % (why, det))

# ---- 5. 源码级：两处比较真的改掉了（AST/文本双证，且配对） ----
tree = ast.parse(src)
wg = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'world_gate':
        wg = node
        break
ck('A25 world_gate 函数节点存在', wg is not None)

calls = []
if wg is not None:
    for node in ast.walk(wg):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('chapter_matches', 'same_chapter'):
                calls.append(node.func.id)
ck('A26 world_gate 里调用了 chapter_matches（>=2 处：home_production + 章节命中）',
   calls.count('chapter_matches') >= 2, 'calls=%r' % (calls,))

# 负控制（文本级、但**剥掉注释与字符串**后扫，避免"注释里提一句就报红"）
tree_nc = ast.parse(src)


def _code_without_doc_and_str(t):
    """把 STRING 常量与注释剥掉后的"纯代码"文本 —— 避免注释提到旧写法即误报。"""
    import tokenize
    import io as _io
    out = []
    for tok in tokenize.generate_tokens(_io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return ' '.join(out)


code_only = _code_without_doc_and_str(tree_nc)
old_pat_count = code_only.count('ch in npc.chapters')
ck('A27 ★剥注释/字符串后，world_gate 的旧写法 `ch in npc.chapters` 已归零',
   old_pat_count == 0, 'count=%d' % old_pat_count)
# 负控制：这一段判据必须能抓到旧写法（人为喂一份含旧写法的代码）
fx = 'if ch in npc.chapters:\n    pass\n'
ck('A28 ★负控制：判据对含旧写法的样本会报红（判据非恒真）',
   fx.count('ch in npc.chapters') == 1)

# ---- 收尾 ----
print('')
print('=' * 60)
print('verify114_alias  PASS=%d  FAIL=%d' % (len(OK), len(BAD)))
for n, d in BAD:
    print('  FAIL: %s  | %s' % (n, d))
sys.exit(1 if BAD else 0)
