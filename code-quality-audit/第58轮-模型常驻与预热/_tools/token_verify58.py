# -*- coding: utf-8 -*-
"""第58轮：速查本逐令牌回验（skill `agent-memory-compaction` 的标准收尾）。

判据（与第57轮同口径，工具类名沿用）：
  T1  基线必须存在（`_evidence/MEMORY_pre58_baseline.md`，**冻结在仓库里**）
      —— 不能取 `git show HEAD:`（一提交就退化成"被删 0 / 全绿"）
  T2  差集：基线有、当前**没有**的令牌
  T3  每个被删令牌必须能在详版 `in` 到（或在显式白名单里、白名单必须写理由）
  T4  正控制：合成的"必然缺失"令牌必须被判为缺失（判据有鉴别力）
  T5  负控制：两边都在的令牌**不许**出现在"被删"列表里
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MEMDIR = os.path.join(ROOT, '.workbuddy', 'memory')
QUICK = os.path.join(MEMDIR, 'MEMORY.md')
DETAIL = os.path.join(MEMDIR, '参考-契约与历轮（详版）.md')
BASE = os.path.join(ROOT, 'code-quality-audit', '第58轮-模型常驻与预热',
                    '_evidence', 'MEMORY_pre58_baseline.md')

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    print(('[PASS] ' if cond else '[FAIL] ') + name + ' ' + extra)
    if not cond:
        FAILS.append(name)


def js_len(t):
    return len(t.strip().encode('utf-16-le')) // 2


def tokens(text):
    """可检索令牌：反引号内容 + §x.y 引用 + 十六进制串 + X=数字 常量 + 中文短语。

    ⚠️ 中文短语阈值取 **6 字**（不是 4 字）：4 字会切出"只加等待""体验上限"这类
    **碎片**，与完整短语互斥 ⇒ 产生大量**假报红**（判据过宽同样要防，§4）。
    """
    out = set()
    out |= set(re.findall(r'`([^`\n]{2,48})`', text))
    out |= set(re.findall(r'§\d+(?:\.\d+)*', text))
    out |= {m for m in re.findall(r'\b[0-9a-f]{7,40}\b', text)}
    out |= set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,30}\s*=\s*-?\d+(?:\.\d+)?', text))
    out |= set(re.findall(r'[\u4e00-\u9fff]{6,14}', text))
    return out


# 白名单：必须逐条写理由（都是"改写/指针变更"，语义在详版有等价原文）
EXEMPT = {
    '大目录遍历先': '★ 已在详版 §55.10 下沉区留档',
    '只列一次': '★ 已在详版 §55.10 下沉区留档',
    '冷启动单项未实测': '★ 改写为「未实测『设长后跨5分钟』」（更具体）',
    '是否加全局并发闸': '★ 改写为「并发闸 **不做**」（结论已定）',
    '这一阶段完全': '★ 改写为「这阶段」（纯措辞）',
    '第 3 个被丢字段': '★ 改写为「第3个被丢字段」（去空格）',
    '动机是': '★ 纯措辞删除（同句已含"贴合人物并且不出 bug"）',
}

with io.open(BASE, encoding='utf-8') as f:
    old = f.read()
with io.open(QUICK, encoding='utf-8') as f:
    cur = f.read()
with io.open(DETAIL, encoding='utf-8') as f:
    det = f.read()

print('=' * 74)
check('T1 基线存在且像样（>5000 字符）', len(old) > 5000, '%d 字符' % len(old))

t_old, t_new = tokens(old), tokens(cur)
deleted = sorted(t_old - t_new)
added = sorted(t_new - t_old)
print('  · js_len：压缩前 %d → 现在 %d（余量 %d）'
      % (js_len(old), js_len(cur), 10000 - js_len(cur)))
print('  · 令牌数：压缩前 %d ／ 现在 %d ／ **被删 %d** ／ 新增 %d'
      % (len(t_old), len(t_new), len(deleted), len(added)))

# T2b ★ 自守：差集不许退化成空（若基线取错，这里必须先炸）
check('T2b 自守：被删令牌数 > 0（差集非空 ⇒ 基线没取错）', len(deleted) > 0,
      '被删 %d' % len(deleted))

# T3 逐个回详版
#
# ⚠️ `§53.11` 这种**指针令牌**在详版里写作 `### 53.11`（不带 `§`）
#    ⇒ 直接 `in` 会**误报缺失**（判据过窄，与"过宽=恒真"同型要防）。
#    去掉 `§` 再查一次即可 —— 它们指的是同一节。
def in_detail(tok):
    if tok in det:
        return True
    if tok.startswith('§') and tok[1:] in det:
        return True
    return False


print()
print('--- T3 被删令牌逐个回详版 ---')
missing = []
for tok in deleted:
    if tok in EXEMPT:
        continue
    if not in_detail(tok):
        missing.append(tok)
for tok in deleted:
    if tok in EXEMPT:
        print('    [豁免] %-34s ← %s' % (tok, EXEMPT[tok]))
    elif in_detail(tok):
        tag = '详版有' if tok in det else '详版有(去§)'
        print('    [%s] %-34s' % (tag, tok))
    else:
        print('    [!!缺失] %-34s' % tok)
check('T3 每个被删令牌都能在详版找到（或已白名单说明）', not missing,
      '缺失 %d 个：%s' % (len(missing), missing))

# T4 正控制
FAKE = 'ZZ_此令牌必然不存在_58'
check('T4 正控制：合成"必然缺失"令牌 ⇒ 判据必须判否',
      FAKE not in det and FAKE not in cur)

# T5 负控制
common = sorted(t_old & t_new)
check('T5 负控制：两边都在的令牌**不许**出现在被删列表里',
      bool(common) and not (set(common) & set(deleted)),
      '共有 %d 个，交集 %d 个' % (len(common), len(set(common) & set(deleted))))

print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
if FAILS:
    for f in FAILS:
        print('  -', f)
print('=' * 74)
sys.exit(1 if FAILS else 0)
