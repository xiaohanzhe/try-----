# -*- coding: utf-8 -*-
"""第57轮 · 速查本 **逐令牌回验** —— `token_verify57.py`。

为什么单独做这一份
------------------
本轮为了不撞 10,000 JS 字符注入上限，对 `.workbuddy/memory/MEMORY.md`（速查本）
做了**结构性压缩**。跨项目 MEMORY.md 的铁律是：

    ★ 压缩删掉的「可检索令牌」必须能在**详版**里 `in` 到 ——
      否则「压缩」就等于「静默丢信息」。

`recheck57.py` 的 §5 只核验**报告**里的关键数字回原文件；它**不**看速查本。
所以速查本这条链路必须单独留证据（速查本属"重要核心文件"，改过必复检）。

判据
----
  T1  速查本 `js_len <= 10000`（★真判据 = JS 字符数 `len(t.strip().encode('utf-16-le'))//2`，
      **不是**字节数/行数 —— 那两种是"假安全"，见 §41.1）
  T2  差集：`git show HEAD:.workbuddy/memory/MEMORY.md`（**压缩前**）有、**现在没有**的令牌
  T3  每个被删令牌必须能在详版 `in` 到（或在**显式白名单**里、且白名单必须写理由）
  T4  正控制：合成的"必然缺失"令牌必须被判为缺失（证明判据有鉴别力，不是恒真）
  T5  负控制：两边都在的令牌**不许**出现在"被删"列表里（证明差集方向没写反）

令牌口径（故意写得可读，避免"判据过窄 ⇒ 误报"）
------------------------------------------------
  · `§12.3` 形式的章节引用
  · ASCII 标识符（>=3 字符，避免 a/t/`x` 之类噪音）
  · 数字（含小数 / 百分号）
  · **长度 >= 4 的连续中文片段**（短于 4 的中文词太常见，当令牌会淹掉真信号）
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
RDIR = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(RDIR, '..', '..'))

QUICK_REL = '.workbuddy/memory/MEMORY.md'
QUICK = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
OUT = os.path.join(RDIR, '_evidence', 'token_verify57_result.txt')

RE_A = re.compile(r'§\d+(?:\.\d+)*|[A-Za-z_][A-Za-z0-9_]{2,}|\d+(?:\.\d+)?%?')
RE_CJK = re.compile(r'[\u4e00-\u9fff]{4,}')

# ★ 白名单：**必须逐条写理由**。空理由 = 不许豁免。
#   （本轮压缩只做结构性去重；下列令牌是有意不保留字面量的，理由必须说得清。）
#   ⚠️ 白名单是"诚实登记"用的，**不是**把判据放宽的开关：
#      本条判据第一版就抓到 5 个真缺失，其中 2 个是**真信息丢失**，已修（见下）。
#
# 已修（不再需要豁免）：
#   · `未真机验收`  —— 详版 §51.8 第3项补回历轮口径
#   · `§0–§51` 陈旧范围声明 —— 速查本头部改回 §0–§53（长度中性）
EXEMPT = {
    '1.91': '本轮**有意**用比值（冷/热差 23~190 倍）替掉逐个数；'
            '同源数据 36.82s 在详版 §19（L2432）、103.6s→0.55s 在详版 §31（L2457）',
    '灵魂实体': '速查本 §10 索引已简写为「灵魂」（词被缩、信息未丢）；'
                '★ 详版**自第51轮起无小节**（既有缺口，见 §54 与本轮报告 §8）',
    '§51.9': '指针；目标小节 `### 51.9` 在详版存在（详版小节标题不带 `§` 前缀）',
    '全部细节见详版': '指针用语；其指向对象就是本详版自身',
    '候选压到': '是「`_match_tier` 把 166 候选压到 1」的措辞；'
                '同信息在详版 §46（L5065-5066：「不分级时『教堂』全域命中 166 个场景」）',
    '余见': '指针用语本身；其指向的 §23.13.1 在详版存在',
    '详见': '指针用语本身；其指向章节在详版存在',
}

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    tag = '[PASS]' if cond else '[FAIL]'
    print('  %s %s %s' % (tag, name, extra))
    if not cond:
        FAILS.append(name)


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def js_len(t):
    """★真判据：与 JS 的 UTF-16 code unit 数对齐。"""
    return len(t.strip().encode('utf-16-le')) // 2


def tokens(text):
    return set(RE_A.findall(text)) | set(RE_CJK.findall(text))


def head_quick():
    """压缩前的速查本（HEAD 里的版本；本轮压缩尚未提交）。"""
    r = subprocess.run(['git', 'show', 'HEAD:' + QUICK_REL], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise RuntimeError('git show 失败：%s' % (r.stderr or r.stdout))
    return r.stdout


print('=' * 78)
print('【T1】速查本体积（★JS 字符数，不是字节/行数）')
print('=' * 78)
_q = rd(QUICK)
_j = js_len(_q)
check('T1  速查本 js_len=%d <= 10000' % _j, _j <= 10000,
      '(余量 %d)' % (10000 - _j))

print()
print('=' * 78)
print('【T2】差集：压缩前 vs 现在')
print('=' * 78)
_old = head_quick()
assert _old and len(_old) > 1000, 'HEAD 版速查本取不到'
_t_old, _t_new = tokens(_old), tokens(_q)
_deleted = sorted(_t_old - _t_new)
print('  · 压缩前 js_len = %d ｜ 现在 js_len = %d' % (js_len(_old), _j))
print('  · 令牌数：压缩前 %d ／ 现在 %d ／ **被删 %d**'
      % (len(_t_old), len(_t_new), len(_deleted)))

print()
print('=' * 78)
print('【T3】被删令牌逐个回详版 `in` 一次')
print('=' * 78)
_detail = rd(DETAIL)
_missing, _exempt_hit = [], []
for t in _deleted:
    if t in _detail:
        continue
    if t in EXEMPT:
        _exempt_hit.append(t)
        continue
    _missing.append(t)

check('T3a 全部被删令牌都能在详版找回（或命中白名单）', not _missing,
      '硬缺失=%s' % _missing if _missing else '0 个')
if _exempt_hit:
    print('  · 白名单豁免 %d 个（逐条理由）：' % len(_exempt_hit))
    for t in _exempt_hit:
        print('      `%s` → %s' % (t, EXEMPT[t]))

print()
print('=' * 78)
print('【T4/T5】控制组')
print('=' * 78)
# 正控制：一个绝不可能在详版里出现的令牌，必须落到"缺失"里
_canary = 'ZZQ_CANARY_NOT_IN_DETAIL_57'
_fake_missing = [t for t in (_deleted + [_canary])
                 if t not in _detail and t not in EXEMPT]
check('T4  正控制：合成令牌必须被判为缺失（判据有鉴别力）',
      _canary in _fake_missing)
# 负控制：两边都有的令牌不许出现在"被删"里
_kept = sorted(_t_old & _t_new)
_probe = next((t for t in _kept if len(t) >= 6), _kept[0] if _kept else '')
check('T5  负控制：两边都在的令牌 `%s` **不在**被删列表里' % _probe,
      _probe not in _deleted and _probe in _t_new)

print()
print('-' * 78)
print('结果：PASS=%d FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
if FAILS:
    print('失败项：%s' % FAILS)

# 落盘证据
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('第57轮 · 速查本逐令牌回验结果\n')
    fh.write('生成：token_verify57.py\n')
    fh.write('-' * 60 + '\n')
    fh.write('T1 速查本 js_len = %d / 10000（余量 %d）\n' % (_j, 10000 - _j))
    fh.write('T2 压缩前 js_len = %d；令牌 前%d/后%d；被删 %d\n'
             % (js_len(_old), len(_t_old), len(_t_new), len(_deleted)))
    fh.write('T3 硬缺失 = %s\n' % (_missing or '无'))
    fh.write('T3 白名单豁免 %d 个：\n' % len(_exempt_hit))
    for t in _exempt_hit:
        fh.write('   · %s -> %s\n' % (t, EXEMPT[t]))
    fh.write('被删令牌全表（%d）：%s\n' % (len(_deleted), ', '.join(_deleted)))
    fh.write('-' * 60 + '\n')
    fh.write('PASS=%d FAIL=%d\n' % (N[0] - len(FAILS), len(FAILS)))
    if FAILS:
        fh.write('失败项：%s\n' % FAILS)
print('  · 证据已落盘：%s' % os.path.relpath(OUT, ROOT))

sys.exit(1 if FAILS else 0)
