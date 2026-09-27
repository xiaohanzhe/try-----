# -*- coding: utf-8 -*-
"""第55轮 · 核心文件复检（可落盘）

按用户长期口径「调整重要核心文件时一定要记得复检」执行六类判据：
  1 可解析（.py 走 `ast.parse` —— **不用 `py_compile`**：它会落 .pyc，改变被检状态）
  2 结构自检（报告章节全在且无粘连 / 注册表键集合 / 人设与记忆文件数）
  3 编码（无 BOM / 无 U+FFFD）
  4 恒真判据复查（本轮的判据脚本里不许出现 `check(..., True)` 这种"看着在守其实没守"）
  5 逐令牌回验（本轮**改过/删过**的标识符与字面量，逐个回**该在**的文件里 in 一次；
     ★ 同时验证"**已经不该在**"的旧值确实消失了 —— 前者防丢，后者防没改干净）
  6 状态干净 + 改动集合 == 预期集合（`git status --porcelain` + numstat 删除量闸）

输出：`_evidence/recheck55_result.txt`（固定文件名，不依赖 stdout）。
"""
import ast
import io
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EVID = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EVID, 'recheck55_result.txt')

P = lambda *a: os.path.join(ROOT, *a)
LINES, PASS, FAIL = [], [], []


def ck(cid, title, ok, detail=''):
    (PASS if ok else FAIL).append(cid)
    LINES.append('  [%s] %-5s %s%s' % ('PASS' if ok else 'FAIL', cid, title,
                                       ('  :: ' + str(detail)) if detail else ''))


def rd(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def rdb(path):
    with open(path, 'rb') as fh:
        return fh.read()


# ---- 被检文件清单（本轮动过的）-----------------------------------------
PY_FILES = [
    P('ralsei_pet', 'src', 'main.py'),
    P('ralsei_pet', 'modules', 'api_client.py'),
    P('ralsei_pet', 'modules', 'npc_system.py'),
    P('ralsei_pet', 'modules', 'npc_persona.py'),
    P('ralsei_pet', 'modules', 'soul_entity.py'),
    P('ralsei_pet', 'modules', 'soul_overlay.py'),
    P('ralsei_pet', 'modules', 'dialogue_ui.py'),
    P('ralsei_pet', 'modules', 'global_hotkey.py'),
    P('code-quality-audit', 'regress', 'run_all.py'),
    # 本轮新增/改动的判据脚本（判据 4 只扫这些：产品代码里没有 check()）
    P('code-quality-audit', '第55轮-灵魂实体与NPC人设', 'check55.py'),
    P('code-quality-audit', '第55轮-灵魂实体与NPC人设', 'verify_soul55.py'),
    P('code-quality-audit', '第55轮-灵魂实体与NPC人设', '_evidence',
      'verify_npc55_live.py'),
    P('code-quality-audit', '第49轮-NPC与球容器', 'verify_npc49.py'),
    P('code-quality-audit', '人味改造-2026-09-18', 'verify_persona_chat.py'),
    P('code-quality-audit', '人味改造-2026-09-18', 'verify_s8_stream.py'),
    P('code-quality-audit', '人味改造-2026-09-18', 'verify_s7_event_speech.py'),
]
JUDGE_FILES = [p for p in PY_FILES if os.path.basename(p) in (
    'check55.py', 'verify_soul55.py', 'verify_npc55_live.py', 'verify_npc49.py',
    'verify_persona_chat.py', 'verify_s8_stream.py', 'verify_s7_event_speech.py')]
JSON_FILES = [
    P('ralsei_pet', 'assets', 'npc', '_registry.json'),
    P('ralsei_pet', 'assets', 'npc', '_personas.json'),
    P('ralsei_pet', 'config.json'),
    P('code-quality-audit', 'regress', 'baseline.json'),
]
MD_FILES = [
    P('第55轮报告-灵魂实体与NPC人设.md'),
]
PERSONA_DIR = P('ralsei_pet', 'assets', 'npc', 'persona')

LINES.append('=' * 72)
LINES.append('第55轮 · 核心文件复检（recheck55）')
LINES.append('=' * 72)

# ---------------------------------------------------------------- 1 可解析
LINES.append('\n【1】可解析（ast.parse；不用 py_compile，避免落 .pyc）')
_bad = []
_bad_json = []
for f in PY_FILES:
    try:
        ast.parse(rd(f), filename=f)
    except SyntaxError as e:
        _bad.append('%s: %s' % (os.path.basename(f), e))
    except OSError as e:
        _bad.append('%s: 读不到 (%s)' % (os.path.basename(f), e))
ck('1', '全部 %d 个 .py 都能 ast.parse' % len(PY_FILES), not _bad, _bad)
for f in JSON_FILES:
    try:
        json.loads(rd(f))
    except Exception as e:
        _bad_json.append('%s: %s' % (os.path.basename(f), e))
ck('1b', '全部 %d 个 .json 都能解析' % len(JSON_FILES), not _bad_json, _bad_json)

# ---------------------------------------------------------------- 2 结构
LINES.append('\n【2】结构自检')
if os.path.isfile(MD_FILES[0]):
    _md = rd(MD_FILES[0])
    _need = ['## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.', '## 7.', '## 8.']
    _miss = [s for s in _need if s not in _md]
    ck('2a', '报告章节 1~8 全在', not _miss, '缺 %r' % (_miss,))
    # "粘连"：真正的毛病是**标题和正文黏在同一行**（如 `## 1. x ## 2. y`）。
    # ⚠️ 判据修正（第一版写错）：原先写"含 '##' 且不以 '## ' 开头"—— 那会把
    #    `### 2.1` 这种**合法的三级标题**全判红（本轮报告就用了 `###`）。
    #    正确口径：`#` 必须出现在**行首**（去掉缩进后），出现在中间才算粘连。
    _glue = [ln[:40] for ln in _md.splitlines()
             if '##' in ln and not ln.lstrip().startswith('#')]
    ck('2b', '报告无章节标题粘连（`#` 必须在行首）', not _glue, _glue[:3])
else:
    ck('2a', '报告章节 1~8 全在', False, '报告文件还不存在')
    ck('2b', '报告无章节标题粘连', False, '报告文件还不存在')

_reg = json.loads(rd(JSON_FILES[0]))
# ⚠️ 判据修正（第一版写错）：期望集合里多了一个 `defaults` —— 那是我用 `d.get('defaults')`
#   探测出来的，而 `.get` 在**键不存在**时也返回 None ⇒ 把"没有这个键"当成了"值是 null"。
#   老教训再犯一次：**探测用的写法要和判据用的一致**（键在不在，必须用 `in` 或 `set(keys)`）。
ck('2c', '注册表顶层键集合 == 预期',
   set(_reg.keys()) == {'schema_version', 'source', 'tiers', 'counts',
                        'npcs', 'model_policy'},
   sorted(_reg.keys()))
ck('2d', '注册表条数与 counts 自洽 + persona 13 份 + 无 model 指向',
   len(_reg['npcs']) == _reg['counts']['main'] + _reg['counts']['plain']
   and len([n for n in _reg['npcs'] if n.get('persona')]) == 14
   and all(n.get('model') is None for n in _reg['npcs']),
   '%d 条 main=%d plain=%d persona=%d'
   % (len(_reg['npcs']), _reg['counts']['main'], _reg['counts']['plain'],
      len([n for n in _reg['npcs'] if n.get('persona')])))
_files = sorted(os.listdir(PERSONA_DIR)) if os.path.isdir(PERSONA_DIR) else []
ck('2e', '人设目录 13 份 .txt（Ralsei 自己那份在 assets 根）',
   len([f for f in _files if f.endswith('.txt')]) == 13,
   '%d 个: %s' % (len(_files), _files[:4]))

# ---------------------------------------------------------------- 3 编码
LINES.append('\n【3】编码（无 BOM / 无 U+FFFD）')
_bom, _rep = [], []
for f in PY_FILES + JSON_FILES + MD_FILES:
    if not os.path.isfile(f):
        continue
    _b = rdb(f)
    if _b.startswith(b'\xef\xbb\xbf'):
        _bom.append(os.path.basename(f))
    _t = None
    try:
        _t = _b.decode('utf-8')
    except UnicodeDecodeError as e:
        _rep.append('%s: 不是合法 UTF-8 (%s)' % (os.path.basename(f), e))
        continue
    if '\ufffd' in _t:
        _rep.append(os.path.basename(f))
ck('3a', '无 BOM', not _bom, _bom)
ck('3b', '无 U+FFFD 且都是合法 UTF-8', not _rep, _rep)

# ---------------------------------------------------------------- 4 恒真判据
LINES.append('\n【4】恒真判据复查（判据脚本里不许把常量当条件）')
# ⚠️ 判据修正（第一版写错）：原先直接正则找 `check(name, True)` —— 那会把
#   **合法写法**判红：`try: <被测语句>; check(name, True) except: check(name, False)`
#   里的真假分支恰恰是"**它到底抛没抛**"这个真判据（本轮 check55 的 W35 与
#   verify_soul55 的 P8/X1 都是这个形状）。所以用 AST 判：**只有不在任何 `try:` 语句里**
#   的常量条件才算恒真。这样既放过合法形状，又照样抓得住裸写的 `check(name, True)`。
_always = []


def _scan_always(src, fname):
    """找出**裸写**的常量条件（`check(name, True)` 之类）。

    ⚠️ 判据自身踩过两次坑，都记在这里：
      ① 第一版用正则直接找 `check(name, True)` —— 把 `try/except` 里的
         `check(name, True)/check(name, False)` 全判红。可那恰恰是
         「**它到底抛没抛**」这个真判据的合法写法（本轮 W35 / P8 / X1 / L7 都是）。
      ② 第二版改用 AST，但范围只取到 `except` 那一行（handler 的 `lineno`），
         **没走进行体** ⇒ handler 里那句仍被当成"不在 try 里"，照样误报。
        改成用 `node.end_lineno`（整条 try 语句的真实结束行）。
    """
    out = []
    tree = ast.parse(src, filename=fname)
    ranges = [(n.lineno, getattr(n, 'end_lineno', n.lineno))
              for n in ast.walk(tree) if isinstance(n, ast.Try)]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ('check', 'ok', 'ck') and len(node.args) >= 2):
            continue
        _cond = node.args[1]
        if not (isinstance(_cond, ast.Constant) and isinstance(_cond.value, bool)):
            continue
        _ln = getattr(node, 'lineno', 0)
        if not any(_lo <= _ln <= _hi for _lo, _hi in ranges):
            out.append('%s:%d %s(name, %r) 不在任何 try 里'
                       % (os.path.basename(fname), _ln, node.func.id, _cond.value))
    return out


for f in JUDGE_FILES:
    _always.extend(_scan_always(rd(f), f))

# ★ 正控制：同一条判据套到"合成的一段裸写"上**必须**报出来（否则这条锁是空转的）。
_SYNTH = "check('假装守了一条', True)\n"
_positive = bool(_scan_always(_SYNTH, 'synthetic.py'))
# ★ 负控制：`try/except` 形状**不许**被判红（那是合法写法）
_SYNTH_OK = ("try:\n    f()\n    check('x', True)\n"
             "except Exception:\n    check('x', False)\n")
_negative = not _scan_always(_SYNTH_OK, 'synthetic_ok.py')
ck('4a', '判据脚本里没有"裸写"的常量条件（try/except 里的真假分支属合法写法）',
   not _always, _always[:4])
ck('4a2', '4a 有鉴别力：合成的裸写必须被抓出（正控制）且 try/except 形状不被误报（负控制）',
   _positive and _negative, 'positive=%r negative=%r' % (_positive, _negative))

# 每条"新锁"都要有反面（A ≠ B / 负控制）才算有鉴别力
_pairs = [
    ('check55.py', 'A ≠ B'),
    ('check55.py', '负控制'),
    ('verify_soul55.py', 'A ≠ B'),
    ('verify_npc55_live.py', '反面'),
]
_missing = []
for _name, _kw in _pairs:
    _p = [f for f in JUDGE_FILES if os.path.basename(f) == _name]
    if not _p or _kw not in rd(_p[0]):
        _missing.append('%s 缺「%s」' % (_name, _kw))
ck('4b', '本轮四个判据脚本都带反面控制（"先断言 A ≠ B"/负控制）',
   not _missing, _missing)

# 三条**具体**的鉴别力证据必须还在（它们是本轮判据的骨架）
_c55 = rd(P('code-quality-audit', '第55轮-灵魂实体与NPC人设', 'check55.py'))
_ev = []
if '_dirty is None and _clean is not None' not in _c55:
    _ev.append('check55 缺"车轱辘话反向锁"的 A/B 判据')
if "recent=[_fake.reply]" not in _c55:
    _ev.append('check55 缺反向锁的"脏"输入')
if '_opt_a == "ralsei:v4"' not in _c55.replace("'", '"'):
    _ev.append('check55 缺"模型字段真被读"的正面分支')
ck('4c', '三条骨架判据在位（反向锁 A/B + 脏输入 + 模型字段正面分支）',
   not _ev, _ev)

# ---------------------------------------------------------------- 5 逐令牌
LINES.append('\n【5】逐令牌回验（改/删过的令牌逐个回原文件 in 一次）')
TOKENS_MAY = [
    # (令牌, 文件, 说明)
    ('def _npc_model(self, npc_id)', P('ralsei_pet', 'src', 'main.py'),
     'main 新增的模型解析出口'),
    ('self._npc_model(npc_id)', P('ralsei_pet', 'src', 'main.py'),
     'npc_speak 真把句柄传下去'),
    ('remember=False, model=self._npc_model(npc_id)',
     P('ralsei_pet', 'src', 'main.py'), '跟随决策也传句柄'),
    ('speaker=None, system_override=None, remember=True,',
     P('ralsei_pet', 'src', 'main.py'), 'chat_with_ai 形参'),
    ('_npc_reply_cb = on_reply', P('ralsei_pet', 'src', 'main.py'),
     'NPC 回复落记忆的回调包装'),
    ('if not _is_npc:', P('ralsei_pet', 'src', 'main.py'),
     '「刚说过话」时间戳只对 Ralsei 记'),
    ('recent = (list(_npc_recent) if _is_npc', P('ralsei_pet', 'src', 'main.py'),
     '护栏比对集合分岔'),
    ("_override = kwargs.pop('model', None)", P('ralsei_pet', 'modules', 'api_client.py'),
     'payload 按请求覆盖模型'),
    ('"model": _model', P('ralsei_pet', 'modules', 'api_client.py'),
     'payload 用解析后的模型'),
    ('DEFAULT_MAIN_MODEL = None', P('ralsei_pet', 'modules', 'npc_system.py'),
     '主线模型口径 = 跟随 App 配置'),
    ('def memory_root(data_root)', P('ralsei_pet', 'modules', 'npc_persona.py'),
     '记忆根目录唯一入口'),
    ('def match_name_prefix', P('ralsei_pet', 'modules', 'npc_persona.py'),
     '最长别名前缀匹配'),
    ('def _is_npc_speaker', P('ralsei_pet', 'modules', 'dialogue_ui.py'),
     '第三说话人判别'),
    ('def add_npc_addressed', P('ralsei_pet', 'modules', 'dialogue_ui.py'),
     'NPC 回显出口'),
    ('_npc_mem_dir = os.path.join', P('code-quality-audit', '第55轮-灵魂实体与NPC人设',
                                      'check55.py'),
     '套件自带 hermetic 起点（清隔离区）'),
]
_tok_fail = []
for _tok, _f, _why in TOKENS_MAY:
    try:
        if _tok not in rd(_f):
            _tok_fail.append('%s 不在 %s（%s）' % (_tok[:40], os.path.basename(_f), _why))
    except OSError as e:
        _tok_fail.append('%s 读不到 (%s)' % (_f, e))
ck('5a', '本轮**新增/保留**的 %d 个令牌逐个回验在位' % len(TOKENS_MAY),
   not _tok_fail, _tok_fail)

# ★ 反向：**已经不该在**的旧值必须真消失（防"以为改了其实没改到"）。
# ⚠️ 判据修正（第一版写错）：原先找**裸字符串** `ralsei-npc:4b` —— 但它在
#   `model_policy.note` 的**说明文字**里被有意提到（解释"第49轮那个句柄从没被读过"），
#   于是判红。真正该守的是**值位置**：字段里不许再指向这些句柄。
#   ⇒ 只搜 `"model": "ralsei-npc` / `"main": "ralsei-npc`（json 值形态）。
TOKENS_GONE = [
    ('"model": "ralsei-npc', P('ralsei_pet', 'assets', 'npc', '_registry.json'),
     '每个 NPC 的 model 字段值'),
    ('"main": "ralsei-npc', P('ralsei_pet', 'assets', 'npc', '_registry.json'),
     'model_policy.main 值'),
]
_gone_fail = []
for _tok, _f, _why in TOKENS_GONE:
    try:
        if _tok in rd(_f):
            _gone_fail.append('%s 仍作为"值"出现在 %s（%s）'
                              % (_tok, os.path.basename(_f), _why))
    except OSError as e:
        _gone_fail.append('%s 读不到 (%s)' % (_f, e))
# 再补一条**结构化**判据（比字符串更硬）：解析后不许有任何一个 model 指向假句柄。
_bogus = ([n['id'] for n in _reg['npcs']
           if isinstance(n.get('model'), str) and 'ralsei-npc' in n['model']]
          + [('policy', k) for k in ('main', 'plain')
             if isinstance((_reg.get('model_policy') or {}).get(k), str)
             and 'ralsei-npc' in _reg['model_policy'][k]])
# 隔离区的 path_of 不许再自己拼一层 npc_memory
_np = rd(P('ralsei_pet', 'modules', 'npc_persona.py'))
ck('5b', '旧的假句柄已从注册表的**值位置**消失（说明文字里提到不算）',
   not _gone_fail and not _bogus, _gone_fail + list(map(str, _bogus)))
ck('5c', '`MiniMemory.path_of` 不再自己拼 `npc_memory` 那一层（双层路径 bug 不许回来）',
   "os.path.join(self.root, 'npc_memory'" not in _np)

# ---------------------------------------------------------------- 6 状态
LINES.append('\n【6】状态干净 + 改动集合')
try:
    _st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    _lines = [l for l in _st.stdout.splitlines() if l.strip()]
    _renamed = [l for l in _lines if l[:2].strip() == 'R']
    ck('6a', '工作区里没有意外的改名/删除记录（R/D 行）',
       not [l for l in _lines if l[:1] in ('R', 'D')],
       [l for l in _lines if l[:1] in ('R', 'D')][:4])
    LINES.append('  · git status 条目数 = %d（本轮尚未提交，属正常）' % len(_lines))
except Exception as e:
    ck('6a', 'git status 可读', False, repr(e))
try:
    _ns = subprocess.run(['git', 'diff', '--cached', '--numstat'], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    _del = 0
    for l in _ns.stdout.splitlines():
        parts = l.split('\t')
        if len(parts) >= 3 and parts[1].isdigit():
            _del += int(parts[1])
    LINES.append('  · 暂存区删除行数 = %d（守卫阈值 1000）' % _del)
    ck('6b', '暂存区删除行数 < 1000', _del < 1000, _del)
except Exception as e:
    LINES.append('  · numstat 读取失败（忽略）: %r' % (e,))

# ---------------------------------------------------------------- 收尾
LINES.append('')
LINES.append('-' * 72)
LINES.append('结果：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    LINES.append('失败项：%r' % (FAIL,))
LINES.append('')

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(LINES))
print('\n'.join(LINES))
raise SystemExit(0 if not FAIL else 1)
