# -*- coding: utf-8 -*-
"""第57轮 · 核心产物复检（六类判据）—— `recheck57.py`。

复检对象（本轮**新增/改动**的文件）
----------------------------------
* `第57轮-模型并发实测/check57.py`（新判据脚本）
* `第57轮-模型并发实测/_tools/bench_ollama_concurrency.py`（新实测工具）
* `第57轮-模型并发实测/_tools/bench_prefix_cache.py`（新实测工具）
* `code-quality-audit/regress/run_all.py`（**核心文件**：新登记了 `model_conc57`）
* `第57轮报告-7B模型并发上限.md` + `_evidence/*.json`

六类判据（与用户口径"改重要核心文件必须复检"逐条对应）
-----------------------------------------------------
  1 可解析（`ast.parse`，**不用 `py_compile`**：它会落 `.pyc` 改变被检状态）
  2 结构自检（报告章节 / check57 分段 / run_all 登记 / evidence 在位）
  3 编码（无 BOM / 无 U+FFFD / 合法 UTF-8）
  4 **恒真判据复查**（扫本轮判据脚本里的"裸常量条件"；配正/负控制）
  5 **逐令牌回验**（报告里的关键数字/路径逐个回原文件 `in` 一次；含**反向**）
  6 工作区干净（无意外 R/D；删除行数 < 1000）
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
RDIR = os.path.abspath(os.path.join(HERE, '..'))          # 第57轮目录
ROOT = os.path.abspath(os.path.join(RDIR, '..', '..'))    # 仓库根

CHECK57 = os.path.join(RDIR, 'check57.py')
BENCH1 = os.path.join(HERE, 'bench_ollama_concurrency.py')
BENCH2 = os.path.join(HERE, 'bench_prefix_cache.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
REPORT = os.path.join(ROOT, '第57轮报告-7B模型并发上限.md')
EVID = os.path.join(RDIR, '_evidence')

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('  [PASS] %s %s' % (name, extra))
    else:
        print('  [FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def rb(p):
    with open(p, 'rb') as fh:
        return fh.read()


print('=' * 78)
print('【1】可解析（AST，不落 .pyc）')
print('=' * 78)
_py_files = [CHECK57, BENCH1, BENCH2, RUNALL]
for p in _py_files:
    rel = os.path.relpath(p, ROOT)
    try:
        src = rd(p)
        ast.parse(src)
        check('1  ast.parse 通过 :: %s' % rel, True)
    except Exception as e:                                            # noqa: BLE001
        check('1  ast.parse 通过 :: %s' % rel, False, str(e))
check('1c 本轮**没有**用 py_compile（否则会落 .pyc 改变被检状态）',
      all('.pyc' not in rd(p) for p in _py_files))


print()
print('=' * 78)
print('【2】结构自检')
print('=' * 78)
_rep = rd(REPORT)
_need_secs = ['## 1. 结论先行', '## 2. 复检结果', '## 3. 实测方法',
              '## 4. 三条实测结论', '## 5. 产品接线事实', '## 6. 本机硬约束',
              '## 7. 建议', '## 8. 遗留与如实登记']
_missing = [s for s in _need_secs if s not in _rep]
check('2a  报告 8 个章节全在且无退化（无标题粘连）', not _missing,
      '缺=%s' % _missing if _missing else '8/8')

_c57 = rd(CHECK57)
_segs = ['【A】', '【B】', '【C】', '【D】']
check('2b  check57 四段齐全（A 配置 / B 接线 / C 实测 / D 结论）',
      all(s in _c57 for s in _segs),
      '缺=%s' % [s for s in _segs if s not in _c57] if not all(
          s in _c57 for s in _segs) else '4/4')

_ra = rd(RUNALL)
check('2c  run_all.py 已登记 model_conc57 到 SUITES', "'model_conc57'" in _ra)
check('2d  run_all.py 的登记指向第57轮目录与 check57.py',
      '第57轮-模型并发实测' in _ra and 'check57.py' in _ra)
# ★ 与 npc_place56 的关键区别：check57 **不跑真机** ⇒ 不该进 HERMETIC_IDS。
#    （误登记会让人以为它有真实存储副作用，掩盖"它其实是只读套件"这个事实）
_herm = _ra.split('HERMETIC_IDS')[1].split('})')[0] if 'HERMETIC_IDS' in _ra else ''
check('2e  ★ model_conc57 **不在** HERMETIC_IDS（它不跑 RalseiPet，是纯只读套件）',
      'model_conc57' not in _herm, 'HERMETIC 段里出现=%s'
      % ('model_conc57' in _herm))

_ev1 = os.path.join(EVID, 'conc_same_model.json')
_ev2 = os.path.join(EVID, 'prefix_cache.json')
check('2f  并发实测证据在位', os.path.isfile(_ev1), os.path.basename(_ev1))
check('2g  前缀缓存证据在位', os.path.isfile(_ev2), os.path.basename(_ev2))
_pc13 = os.path.join(EVID, 'prefix_cache_13.json')
print('  · 13 人档证据：%s' % ('在位' if os.path.isfile(_pc13) else '未跑/缺失（check57 C7b 会自动跳过）'))


print()
print('=' * 78)
print('【3】编码（无 BOM / 无 U+FFFD）')
print('=' * 78)
_txt_files = _py_files + [REPORT, _ev1, _ev2]
_bad_bom, _bad_fffd = [], []
for p in _txt_files:
    if not os.path.isfile(p):
        continue
    raw = rb(p)
    try:
        t = raw.decode('utf-8')
    except Exception as e:                                            # noqa: BLE001
        _bad_fffd.append('%s(%s)' % (os.path.basename(p), e))
        continue
    if raw[:3] == b'\xef\xbb\xbf':
        _bad_bom.append(os.path.basename(p))
    if '\ufffd' in t:
        _bad_fffd.append(os.path.basename(p))
check('3a  无 BOM', not _bad_bom, '违规=%s' % _bad_bom if _bad_bom else 'ok')
check('3b  无 U+FFFD 且都是合法 UTF-8', not _bad_fffd,
      '违规=%s' % _bad_fffd if _bad_fffd else 'ok')


print()
print('=' * 78)
print('【4】恒真判据复查（判据脚本里不许把常量当条件）')
print('=' * 78)


def naked_const_checks(src):
    """找 `check(<name>, <裸常量>, ...)` —— 看着在守、其实没守的形状。

    ⚠️ 只抓**第二参数是 ast.Constant** 的调用（True/False/数字/字符串字面量）。
    `check('x', a == b)` / `check('x', func())` 都是**真判据**，不许误报。
    """
    out = []
    try:
        tree = ast.parse(src)
    except Exception:                                                 # noqa: BLE001
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Name) and f.id == 'check'):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            out.append(getattr(node, 'lineno', -1))
    return out


_hits = naked_const_checks(_c57)
check('4a  check57 里没有"裸常量条件"', not _hits, '命中行=%s' % _hits if _hits else '0 处')

# 正控制：合成的裸写必须被抓出
_SYN = ("def check(a, b, c=''):\n    pass\n"
        "check('假判据', True, 'x')\n"
        "check('真判据', 1 == 1)\n"
        "check('真判据2', len([]) > 0)\n")
_syn_hits = naked_const_checks(_SYN)
check('4b  正控制：合成 `check(x, True)` 必须被抓出（且 `1 == 1` 这种表达式**不**误报）',
      _syn_hits == [3], '合成命中行=%s（期望 [3]）' % _syn_hits)

# 负控制：run_all.py 里没有 check() 这种写法 ⇒ 判据在别的文件上不空转
check('4c  负控制：同一判据扫 run_all.py 得 0 处（证明它没在乱报）',
      naked_const_checks(_ra) == [])

# ★ 本轮真实抓过一条：B3 曾写成 `check('B3 ...', True)`，已改为 print 登记。
# ⚠️ 这里**必须用 AST 判**，不能用 `"check('B3" in src` —— 修复时留的注释里
#    恰好含这个字符串，用 `in` 会**假报红**（判据过窄 = 会误报，与"过宽 = 恒真"
#    同样是本项目的元级坑；本判据第一版就是这么写错的）。
def has_check_named(src, prefix):
    """是否存在**真的调用** `check('<prefix>...', ...)`（注释/字符串里提不算）。"""
    try:
        tree = ast.parse(src)
    except Exception:                                                 # noqa: BLE001
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Name) and f.id == 'check' and node.args):
            continue
        a0 = node.args[0]
        if (isinstance(a0, ast.Constant) and isinstance(a0.value, str)
                and a0.value.startswith(prefix)):
            return True
    return False


check('4d  ★ 反向：被改掉的恒真判据 `check(\'B3 …\', True)` 已不是**真调用**了'
      '（AST 判，注释里提到不算）',
      not has_check_named(_c57, 'B3'))
check('4e  改后的登记仍在（不许"删掉判据"当作修复）',
      '如实登记 B3' in _c57)
check('4d2 正控制：同一 AST 判据在合成样本上必须命中',
      has_check_named("check('B3 假的', True)\n", 'B3'))


print()
print('=' * 78)
print('【5】逐令牌回验（报告的关键数字/路径逐个回原文件 in 一次）')
print('=' * 78)


def _conc_stats():
    """从证据现算"报告里该出现的数"，而不是把数硬写在判据里。"""
    j = json.loads(rd(_ev1))
    cold, hot, dec = [], [], []
    for w in j.get('waves') or []:
        for r in w.get('rows') or []:
            if not r or r.get('err'):
                continue
            pt = r.get('prompt_eval_count') or 0
            if pt:
                mst = (r.get('prompt_eval_duration') or 0) / 1e6 / pt
                (hot if mst < 5.0 else cold).append(mst)
            et = r.get('eval_count') or 0
            if et >= 10:
                dec.append((r.get('eval_duration') or 0) / 1e6 / et)
    return cold, hot, dec


_cold, _hot, _dec = _conc_stats()
_tok_checks = [
    ('5a  run_all.py 里同时有 model_conc57 与第57轮目录名',
     ("'model_conc57'" in _ra and '第57轮-模型并发实测' in _ra, '')),
    ('5b  check57 的 D 段含 OLLAMA_NUM_PARALLEL 与 keep_alive',
     ('OLLAMA_NUM_PARALLEL' in _c57 and 'keep_alive' in _c57, '')),
    ('5c  报告含"串行"/"排队"这条核心结论措辞',
     (('串行' in _rep and '排队' in _rep), '')),
    ('5d  报告里的冷 prefill 下界与证据现算值一致（%.2f）' % min(_cold),
     (('%.2f' % min(_cold)) in _rep, '')),
    ('5e  报告里的冷 prefill 上界与证据现算值一致（%.2f）' % max(_cold),
     (('%.2f' % max(_cold)) in _rep, '')),
    ('5f  报告里的热 prefill 下界与证据现算值一致（%.3f）' % min(_hot),
     (('%.3f' % min(_hot)) in _rep, '')),
    ('5g  报告里的 decode 下界与证据现算值一致（%.1f）' % min(_dec),
     (('%.1f' % min(_dec)) in _rep, '')),
    ('5h  报告里的 decode 上界与证据现算值一致（%.1f）' % max(_dec),
     (('%.1f' % max(_dec)) in _rep, '')),
]
for _name, (_c, _x) in _tok_checks:
    check(_name, _c, _x)

# （"报告声称未改产品代码"的反向核验放在 §6 —— 那里才拿得到 `git status`）


print()
print('=' * 78)
print('【6】工作区状态')
print('=' * 78)
import subprocess                                                      # noqa: E402

try:
    _st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout
except Exception as e:                                                # noqa: BLE001
    _st = ''
    print('  · git status 取不到：%s' % e)
_lines = [l for l in _st.splitlines() if l.strip()]
_rd_lines = [l for l in _lines if l[:2].strip() in ('R', 'D') or
             (len(l) > 2 and l[0] in 'RD') or (len(l) > 2 and l[1] in 'RD')]
check('6a  工作区里没有意外的改名/删除记录（R/D 行）', not _rd_lines,
      'R/D=%s' % _rd_lines if _rd_lines else '0 条')
print('  · git status 条目数 = %d（本轮新增产物尚未提交，属正常）' % len(_lines))

_numstat = ''
try:
    _numstat = subprocess.run(['git', 'diff', '--cached', '--numstat'], cwd=ROOT,
                              capture_output=True, text=True,
                              encoding='utf-8', errors='replace').stdout
except Exception as e:                                                # noqa: BLE001
    print('  · numstat 取不到：%s' % e)
_del = 0
for l in _numstat.splitlines():
    parts = l.split('\t')
    if len(parts) >= 2 and parts[1].isdigit():
        _del += int(parts[1])
check('6b  暂存区删除行数 < 1000（`git add -A` 误删守卫）', _del < 1000,
      '删除行数=%d' % _del)

# ★ 反向核验：报告声称"本轮未改任何产品代码" ⇒ ralsei_pet/ 下不应有 .py 改动。
#   （这条**必须是真判据**：recheck57 的第一版把它写成 `check(..., True)`，
#     那就是"看着在守、其实没守"——本条自己就是 §4 要防的形状。）
_pet_py = [l for l in _lines
           if 'ralsei_pet/' in l.replace('\\', '/') and l.rstrip().endswith('.py')]
check('6c  ★ 反向：报告声称"未改任何产品代码" ⇒ `ralsei_pet/` 下无 `.py` 改动',
      not _pet_py, '改动=%s' % _pet_py if _pet_py else '0 个 .py（与报告一致）')

print()
print('-' * 78)
print('结果：PASS=%d FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
if FAILS:
    print('失败项：%s' % FAILS)
sys.exit(1 if FAILS else 0)
