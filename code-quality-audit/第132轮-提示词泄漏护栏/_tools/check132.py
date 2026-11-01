# -*- coding: utf-8 -*-
"""第132轮回归锁：**元话语泄漏**（念提示词 / 引用模板 / 括注自评）这道闸不许退化。

## 为什么加这道闸（证据在 `_evidence/`）

第131轮真机 42 条里 3 条把"人设里的规则"当台词说了出来，形态三种：

1. 「你说的是坏消息的时候**我不该用亮起来的开头**，先就着那件具体的事问一句。」
2. 「**先就着你说的那件事问一句：**"这么说，你是觉得……"再留个"我在"的意思。」
3. 「…（**这里说的是你自己的事，而不是直接给出建议**）」

⇒ 三处都是把人设「语气示范」第 136/147/148 行的编号规则，改写成第一人称自述。

## ★★★ 本轮最重要的一条负结论：**重合度判不了这件事**

先试过"回复与 system 的最长公共子串 / 6-gram 重叠"（`scan132_leak.py`）：
42 条里 `lcs_flat` 最高的是 **17 和 13**，而那两条**都是正常好答案**（after/Q7#1、#3），
真正的泄漏只有 **10**。原因很朴素：人设本身就在讲"城堡/喷泉/角色/Deltarune"，
好回复用同一批词，重合度天然高。⇒ 用重合度当判据，会**误伤说正事、漏掉念规则**。
所以闸门按**元语言的结构特征**判（见 `event_speech.looks_like_meta_leak`）。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 真实数据（131 的 42 条）：**3 条必须命中、其余 39 条必须一条不中**（n=39 的负样本）
B 构造样本：5 条规则**逐条**都有命中例（防"正则写错了但没人知道"）＋ 12 条易误伤的正常台词
C 历史大池（128 的 300 条）：**0 命中**（口径：这几百条里确实没人念规则）
D 接线（AST 查 `main.py`）：import 了、且与另外两道闸**在同一个 if 里**、命中即 `return None`
E 自检：恒真判据 / 分母 / 零外部盘 / `event_speech` 仍零项目内依赖

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（直接调产品函数，不复制正则）；
不把"命中率"写成结论式断言（真机数据会变，写死就是定时炸弹）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测', '_evidence')
RAW128 = os.path.join(ROOT, 'code-quality-audit', '第128轮-结巴率收敛', '_evidence', 'raw')
PET = os.path.join(ROOT, 'ralsei_pet')
ES = os.path.join(PET, 'modules', 'event_speech.py')
MAIN = os.path.join(PET, 'src', 'main.py')

if PET not in sys.path:
    sys.path.insert(0, PET)
from modules import event_speech as ESR                           # noqa: E402

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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


FN = ESR.looks_like_meta_leak
assert callable(FN), '产品里没有 looks_like_meta_leak'   # 判据自己要有个硬前提


# =============================================== A. 真实数据：42 条
head(u'A. 真实数据（第131轮 42 条真机回复）：3 命中 / 39 干净')

JSONL = os.path.join(EV131, 'live7_131.jsonl')
check(u'A0 证据文件在', os.path.isfile(JSONL), JSONL)

rows = []
if os.path.isfile(JSONL):
    rows = [json.loads(l) for l in io.open(JSONL, encoding='utf-8') if l.strip()]
check(u'A1 42 条都读到了', len(rows) == 42, u'实际 %d' % len(rows))

# 人工逐条复核过的那 3 条（钉住"哪三条"而不是"随便三条"）：
#   before/Q7#2 → 自述规则；before/Q7#3 → 引用模板；before/Q3#3 → 括注自评
LEAKS = {('before', 'Q7', 2), ('before', 'Q7', 3), ('before', 'Q3', 3)}
flag = {}
for r in rows:
    flag[(r['arm'], r['qid'], r['sample'])] = bool(FN(r['reply'] or ''))

hit = sorted(k for k, v in flag.items() if v)
check(u'A2 命中的条数与人工复核一致（3 条）', len(hit) == 3,
      u'实际 %d：%r' % (len(hit), hit))
check(u'A3 命中的正是那 3 条（不是别的）', set(hit) == LEAKS,
      u'多出=%r 少了=%r' % (sorted(set(hit) - LEAKS), sorted(LEAKS - set(hit))))

clean = [(k, v) for k, v in flag.items() if k not in LEAKS]
check(u'A4 其余 39 条一条都不命中（n=39 的负样本）',
      len(clean) == 39 and not any(v for _k, v in clean),
      u'n=%d 命中=%d' % (len(clean), sum(1 for _k, v in clean if v)))
check(u'A5 A/B 先断言：泄漏集与干净集的判定结果不同',
      all(flag[k] for k in LEAKS) and not any(v for k, v in clean if k in LEAKS))

# 两臂分布：3 条全在 before 臂 —— 但**不写成断言**（真机数据会变），只作为观察打印
n_before = sum(1 for k in hit if k[0] == 'before')
print(u'      [观察] 命中里 before 臂 %d 条 / after 臂 %d 条'
      u'（第131轮报告 §3.4 记过：缺"我是谁"的那一臂更容易退回去念指令）'
      % (n_before, len(hit) - n_before))


# =============================================== B. 构造样本
head(u'B. 构造样本：5 条规则逐条有命中例 + 12 条易误伤的正常台词')

PER_RULE = [
    (u'我不该.{0,12}(开头|语气|问一句|留个)', u'我不该用亮起来的开头'),
    (u'我(该|应该|本该)先就着', u'我应该先就着那件事问一句'),
    (u'问一句[：:]', u'先就着那件事问一句："这么说"'),
    (u'留个[「"“]', u'再留个"我在"的意思'),
    (u'[（(]\\s*(这里说|这是说|以上是|注[：:])', u'（这里说的是你自己的事）'),
]
check(u'B0 分母闸：规则清单非空', len(PER_RULE) > 0, u'n=%d' % len(PER_RULE))
for pat_src, sample in PER_RULE:
    check(u'B 每条规则都有命中例 ← %s' % sample[:16],
          FN(sample) is True)

# 12 条正常台词：都**不该**被拦（每条都刻意踩着一个规则边角）
NORMAL = [
    u'我昨天不该说那些话的，对不起。',
    u'我该说谢谢才对。',
    u'你问我一句，我就答一句。',
    u'留个位置给你。',
    u'（这里有点暗，我看不太清。）',
    u'我不是不想给你建议，只是觉得你心里已经有数了。',
    u'我该先起来，还是再躺一会儿呢。',
    u'那句话我不该说得那么重。',
    u'你想问什么就问吧，我在。',
    u'（小声）其实我有点怕。',
    u'我本来该早点告诉你的。',
    u'这门后面留个记号，免得走错。',
]
check(u'B1 分母闸：正常台词清单非空', len(NORMAL) > 0, u'n=%d' % len(NORMAL))
bad = [s for s in NORMAL if FN(s)]
check(u'B2 12 条正常台词一条都不命中（易误伤样本）', not bad,
      u'' if not bad else u'误伤：%r' % (bad,))
check(u'B3 A/B 先断言：同一批输入里既有 True 也有 False',
      any(FN(s) for _p, s in PER_RULE) and not any(FN(s) for s in NORMAL))


# =============================================== C. 历史大池：300 条
head(u'C. 历史大池（第128轮 300 条真实回复）：0 命中')

FILES = ('base.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl',
         'pnew_bold.jsonl', 'pnew_relax.jsonl')
total = 0
hits = []
for fn in FILES:
    p = os.path.join(RAW128, fn)
    if not os.path.isfile(p):
        continue
    for line in io.open(p, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        total += 1
        if FN(rec.get('reply') or ''):
            hits.append((fn, (rec.get('reply') or '')[:60]))
check(u'C0 分母闸：负样本池够大（≥250 条）', total >= 250, u'n=%d' % total)
check(u'C1 这 300 条里 0 命中（口径：它们确实没在念规则）', not hits,
      u'' if not hits else u'%r' % (hits[:3],))


# =============================================== D. 接线（AST）
head(u'D. 接线：import 了 / 与另两道闸在同一个 if / 命中即 return None')

_main = ast.parse(_read(MAIN))
_imported = []
for node in ast.walk(_main):
    if isinstance(node, ast.ImportFrom) and node.module == 'modules.event_speech':
        _imported += [a.name for a in node.names]
check(u'D1 `main.py` 从 modules.event_speech 导入了 looks_like_meta_leak',
      'looks_like_meta_leak' in _imported, u'%r' % (_imported[-4:],))

_fn_cr = None
for node in ast.walk(_main):
    if isinstance(node, ast.FunctionDef) and node.name == '_clean_ai_reply':
        _fn_cr = node
check(u'D2 找到 `_clean_ai_reply`', _fn_cr is not None)

_same_if = []
_gate_ret = []
if _fn_cr is not None:
    for node in ast.walk(_fn_cr):
        if isinstance(node, ast.If):
            names = set(n.id for n in ast.walk(node.test) if isinstance(n, ast.Name))
            if 'looks_like_meta_leak' in names:
                _same_if.append((node.lineno, sorted(names)))
                # ★ 判据自纠：原来写 `b.value is None` —— 那是"AST 字段缺失"，
                #   而源码写的是 `return None`，AST 里是 `Return(value=Constant(None))`。
                #   判据自己报红，产品是对的。
                for b in node.body:
                    if not isinstance(b, ast.Return):
                        continue
                    v = b.value
                    if v is None or (isinstance(v, ast.Constant) and v.value is None):
                        _gate_ret.append(node.lineno)
check(u'D3 该闸与 out_of_character / assistant_speak 在**同一个 if** 里'
      u'（顺序即优先级：三道并列，不另起一支）',
      len(_same_if) == 1 and {'looks_out_of_character',
                              'looks_like_assistant_speak'} <= set(_same_if[0][1]),
      u'%r' % (_same_if,))
check(u'D4 命中后 `return None`（走既有的重采样路径，不是直接沉默）',
      bool(_gate_ret), u'行号=%r' % (_gate_ret,))


# =============================================== E. 自检
head(u'E. 自检（恒真判据 / 分母 / 零外部盘 / 模块依赖）')

_self = ast.parse(_read(os.path.abspath(__file__)))
_true_bad = []
for node in ast.walk(_self):
    if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'check' \
            and len(node.args) >= 2:
        a = node.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            _true_bad.append(node.lineno)
check(u'E1 没有 `check(..., True)` 这种恒真判据', not _true_bad, u'%r' % (_true_bad,))
check(u'E2 判据数 ≥ 20（分母非空）', _n['p'] + _n['f'] >= 20,
      u'实际 %d' % (_n['p'] + _n['f']))

_bad_drive = []
for _p in (os.path.abspath(__file__), ES):
    _s = _read(_p)
    for _ch in (68, 69):
        for _sep in (chr(58) + chr(92), chr(58) + chr(47)):
            if (chr(_ch) + _sep) in _s:
                _bad_drive.append((os.path.basename(_p), chr(_ch) + _sep))
check(u'E3 零外部盘：本文件与 event_speech.py 里没有盘符路径', not _bad_drive,
      u'' if not _bad_drive else u'%r' % (_bad_drive,))

# 模块契约：event_speech 不 import 任何项目内模块、不 import Qt（本闸在它里面，
# 一旦有人为了"拿人设"顺手 import main，这个模块就不再能被回归单独加载）
# ★ 判据自纠：第一版白名单只写了 {random, re} ⇒ 被 `import sys`（标准库）判红。
#   该守的是"**不碰项目内模块、不碰 Qt**"，不是"只能有两个标准库"。
_es = ast.parse(_read(ES))
_pkgs = []
for node in ast.walk(_es):
    if isinstance(node, ast.Import):
        _pkgs += [a.name.split('.')[0] for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        _pkgs.append(node.module.split('.')[0])
_pkgs = sorted(set(_pkgs))
_FORBIDDEN = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PyQt4',
              'main', 'modules', 'core', 'animation', 'npc_life'}
check(u'E4 `event_speech` 不 import 项目内模块、不 import Qt',
      not (set(_pkgs) & _FORBIDDEN), u'实际 import=%r' % (_pkgs,))

# 正控制：把闸门"打回不判"必须让 A2 那三条重新变干净（证明 A 段有鉴别力）
_orig = ESR._META_LEAK_RES
try:
    ESR._META_LEAK_RES = ()
    _muted = [k for k in LEAKS if not FN(dict(
        ((r['arm'], r['qid'], r['sample']), r['reply']) for r in rows)[k] or '')]
finally:
    ESR._META_LEAK_RES = _orig
check(u'E5 破坏性正控制：把规则表清空后，那 3 条**全部**不再命中',
      len(_muted) == 3, u'%d/3' % len(_muted))
check(u'E6 规则表已原样恢复（长度一致）', len(ESR._META_LEAK_RES) == len(_orig),
      u'%d → %d' % (len(_orig), len(ESR._META_LEAK_RES)))

print(u'')
print(u'=' * 78)
print(u'check132：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
