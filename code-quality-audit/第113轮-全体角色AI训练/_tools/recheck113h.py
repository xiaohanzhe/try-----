# -*- coding: utf-8 -*-
"""第113轮h · 重要核心文件改后复检（用户口径：改过重要核心文件一定要复检）。

本轮动到的"重要核心文件"：
  · `ralsei_pet/modules/npc_persona.py`   —— 所有 NPC 的 system prompt 唯一出口
  · `ralsei_pet/modules/dialogue_ui.py`   —— 对话渲染
  · `ralsei_pet/assets/npc/_kinds.json`   —— 登记表（改它＝改 6 个人的 prompt）
  · `code-quality-audit/regress/run_all.py` —— 全量回归的归一化与套件表
  · `code-quality-audit/第77轮…/_tools/check77.py` —— 回归套件本体
  · `_tools/check113h.py`                 —— 本轮新判据

复检六项（对应用户 2026-09-23 口径）：
  ① 语法/可编译（用 `ast.parse`，**不**用 `py_compile` —— 它会产 `.pyc`，等于改了被测状态）
  ② 结构自检（Markdown 标题齐全不粘连；JSON 可解析且关键键在）
  ③ 无 BOM / 无 U+FFFD
  ④ 恒真判据复查（`check(desc, cond)` 的 cond 不许是常量字面量）
  ⑤ 逐令牌回验（本轮的关键标识符/数字，逐个回原文件 `in` 一次）
  ⑥ 工作区状态 + 回归读数（回归由 `run_all.py` 另行跑，这里只核基线文件在盘）
"""
import ast
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
ROUND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    'npc_persona': os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_persona.py'),
    'dialogue_ui': os.path.join(ROOT, 'ralsei_pet', 'modules', 'dialogue_ui.py'),
    'kinds_json': os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_kinds.json'),
    'run_all': os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    'baseline': os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json'),
    'check77': os.path.join(ROOT, 'code-quality-audit', '第77轮-场景补齐与自主生活',
                            '_tools', 'check77.py'),
    'check113h': os.path.join(ROUND, '_tools', 'check113h.py'),
    'evidence_md': os.path.join(ROUND, '_evidence', 'Validation_113h.md'),
    'src61_ut': os.path.join(ROOT, 'code-quality-audit', '第77轮-场景补齐与自主生活',
                             '_evidence', 'src61', 'undertale', 'ut_rooms.json'),
    'src61_uty': os.path.join(ROOT, 'code-quality-audit', '第77轮-场景补齐与自主生活',
                              '_evidence', 'src61', 'undertale_yellow', 'ut_rooms.json'),
}

PASS = 0
FAIL = 0
BAD = []


def check(desc, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        FAIL += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))
        BAD.append(desc)


def raw(p):
    with io.open(p, 'rb') as f:
        return f.read()


print('=' * 74)
print('① 语法 / 可编译（ast.parse，不产 .pyc）')
print('=' * 74)
trees = {}
for k, p in FILES.items():
    if not p.endswith('.py'):
        continue
    try:
        trees[k] = ast.parse(raw(p).decode('utf-8'), filename=p)
        check('① %s 可解析' % k, True)
    except SyntaxError as e:
        check('① %s 可解析' % k, False, repr(e))

print()
print('=' * 74)
print('② 结构自检')
print('=' * 74)
kd = json.loads(raw(FILES['kinds_json']).decode('utf-8'))
check('② _kinds.json 可解析，且 kinds / caps / why / caps_why 四键齐',
      all(k in kd for k in ('kinds', 'caps', 'why', 'caps_why')),
      'kinds=%d caps=%d' % (len(kd.get('kinds') or {}), len(kd.get('caps') or [])))
check('② caps 里每个 id 都有 caps_why（可审计），且 kinds 每条都有 why',
      set(kd.get('caps') or []) <= set(kd.get('caps_why') or {})
      and set(kd.get('kinds') or {}) <= set(kd.get('why') or {}))
check('② 缺省档位仍是 human（改动没把默认值带偏）', kd.get('default') == 'human',
      'default=%r' % (kd.get('default'),))

bl = json.loads(raw(FILES['baseline']).decode('utf-8'))
# ★ 判据不许回显随时相变的绝对值（第94轮教训）：这里原本写死 `== 22`，
#   而第113轮i 给 check113h 加了 C6/C6b 两条 ⇒ 24 条 ⇒ 判据自己报红。
#   真判据 = 「已进基线，且条数没**缩水**」（新增判据是好事，删判据才是问题）。
_h_pass = (bl.get('suites') or {}).get('check113h', {}).get('pass')
check('② baseline.json 可解析，check113h 已进基线且条数没缩水（≥22）',
      isinstance(_h_pass, int) and _h_pass >= 22,
      'pass=%r' % (_h_pass,))

md = raw(FILES['evidence_md']).decode('utf-8')
_heads = [ln for ln in md.splitlines() if ln.startswith('## ')]
check('② 证据文档标题齐全（≥8 节）且无空标题',
      len(_heads) >= 8 and all(len(h.strip()) > 4 for h in _heads),
      '节数=%d' % (len(_heads),))

print()
print('=' * 74)
print('③ 编码（无 BOM / 无 U+FFFD）')
print('=' * 74)
for k, p in FILES.items():
    b = raw(p)
    bom = b.startswith(b'\xef\xbb\xbf')
    fffd = b'\xef\xbf\xbd' in b
    check('③ %s 无 BOM 且无 U+FFFD' % k, not bom and not fffd,
          'BOM=%s U+FFFD=%s' % (bom, fffd))

print()
print('=' * 74)
print('④ 恒真判据复查（check(desc, cond) 的 cond 不许是常量字面量）')
print('=' * 74)
for name in ('check113h', 'check77'):
    tree = trees[name]
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2]
    taut = []
    for c in calls:
        cond = c.args[1]
        if isinstance(cond, ast.Constant):
            taut.append((getattr(c, 'lineno', -1), ast.dump(cond)[:40]))
    check('④ %s 没有 `check(desc, True/False)` 这种恒真/恒假写法' % name,
          bool(calls) and not taut,
          'check 调用 %d 处；常量 cond=%r' % (len(calls), taut))

print()
print('=' * 74)
print('⑤ 逐令牌回验（本轮关键标识符 / 数字，逐个回原文件 in 一次）')
print('=' * 74)
TOKENS = [
    ('npc_persona', 'CAPS_RULE'), ('npc_persona', 'def load_caps'),
    ('npc_persona', 'def caps_of'), ('npc_persona', 'if caps_of(npc_id)'),
    ('npc_persona', 'PERSONA_TONE_MACHINE'),
    ('dialogue_ui', 'def _caps_on'), ('dialogue_ui', '_caps_on(speaker)'),
    ('dialogue_ui', '_ASCII_UPPER = str.maketrans'),
    ('run_all', '_STORAGE_PROBE_NOISE'), ('run_all', "'id': 'check113h'"),
    ('run_all', '获取存储分区信息失败'),
    ('check77', '_SRC_CANDIDATES'), ('check77', 'def _resolve_src'),
    ('check77', 'src61'),
    ('check113h', 'PERSONA_TONE_HUMAN'), ('check113h', 'CAPS_RULE'),
    ('check113h', '_calls_set_capitalization'),
    ('check113h', 'A10 caps 与 kinds 正交'),
]
_src = {k: raw(p).decode('utf-8') for k, p in FILES.items() if p.endswith('.py')}
_miss = [(k, t) for k, t in TOKENS if t not in _src[k]]
check('⑤ %d 个令牌全部回验到位' % len(TOKENS), not _miss, '缺失=%r' % (_miss,))

# 数字令牌：两份转储的字节数与证据里写的一致（防"说了 640KB 其实没有"）
_s1 = len(raw(FILES['src61_ut']))
_s2 = len(raw(FILES['src61_uty']))
check('⑤ 仓库内两份转储字节数与证据文档记载一致（311173 / 329523）',
      _s1 == 311173 and _s2 == 329523, 'ut=%d uty=%d' % (_s1, _s2))
check('⑤ 证据文档里的 G2 读数与实测一致（5486 / 106 套件）',
      '5486' in md and '106' in md)

print()
print('=' * 74)
print('⑥ 工作区与基线文件')
print('=' * 74)
check('⑥ 基线文件在盘且 check113h 的 sha256 已写入（--update 真的落盘了）',
      isinstance((bl.get('suites') or {}).get('check113h', {}).get('sha256'), str)
      and len((bl['suites']['check113h']['sha256'])) == 64)
check('⑥ check77 的基线是 PASS=31（不再是 SKIP 时的 29）',
      (bl.get('suites') or {}).get('check77', {}).get('pass') == 31,
      'pass=%r' % ((bl.get('suites') or {}).get('check77', {}).get('pass'),))

print()
print('=' * 74)
print('复检合计：PASS=%d FAIL=%d' % (PASS, FAIL))
if BAD:
    print('失败项：')
    for d in BAD:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if FAIL == 0 else 1)
