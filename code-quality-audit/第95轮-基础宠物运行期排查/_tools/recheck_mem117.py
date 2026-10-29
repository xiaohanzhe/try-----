# -*- coding: utf-8 -*-
"""第117轮：MEMORY.md 压缩后的「逐令牌回验」。

判据（三条，缺一不可）：
  V1 旧版速查本里的**每个令牌**，必须在新速查本 或 详版 里 `in` 得到。
  V2 详版必须真的变大了（本轮下沉了多少字节，且新增 §117 章节在位）。
  V3 新速查本的体积真降下来了，且 EOL 不混用、无 BOM、无 U+FFFD。

★ 令牌定义故意宽（宁可多抽几个，也不要漏）：
  a) 反引号包起来的整段       b) `§\d+(\.\d+)?` 形式的章节号
  c) ASCII 标识符（≥3 字）    d) 带逗号/小数/百分号的数字
★ 报红时**不直接判死**：先看它是不是被等价改写（例如 `A2·A3` ⇒ `A2`/`A3`）。
  所以脚本把 miss 分两档：`MISS`（两处都没有）与 `SOFT`（新速查本没了、但详版有）。
"""
import io
import json
import os
import re
import subprocess
import sys

MEM = os.path.abspath('C:/Users/23002/Desktop/项目文件夹/try - 副本/.workbuddy/memory/MEMORY.md')
DET = os.path.abspath('C:/Users/23002/Desktop/项目文件夹/try - 副本/.workbuddy/memory/参考-契约与历轮（详版）.md')
REPO = 'C:/Users/23002/Desktop/项目文件夹/try - 副本'

n_pass = 0
n_fail = 0
failed = []


def check(desc, cond, detail=''):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        n_fail += 1
        failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


new_mem = read(MEM)
det = read(DET)

# ---------------- 旧版：从 git 取，别信本地（本地已经被我改了） ----------------
# ★ 第117轮教训：这脚本里 `V1c`（有令牌下沉）与 `V3c`（净减）**只对"压缩轮"成立**。
#   之后再加内容的轮次拿 HEAD 当基准 ⇒ 这两条必然假红（本轮就是）。
#   ⇒ 加 `--base <rev>` 显式指定基准；默认仍取 HEAD（保持历史行为）。
BASE = 'HEAD'
for _i, _a in enumerate(sys.argv):
    if _a == '--base' and _i + 1 < len(sys.argv):
        BASE = sys.argv[_i + 1]

old_mem = subprocess.check_output(
    ['git', '-c', 'core.quotepath=false', 'show', BASE + ':.workbuddy/memory/MEMORY.md'],
    cwd=REPO).decode('utf-8')

check('V0 取到旧版速查本（git %s）且与新文件不同' % BASE,
      old_mem.strip() != new_mem.strip(), 'old=%d new=%d' % (len(old_mem), len(new_mem)))


# ---------------- 令牌抽取 ----------------
RE_TICK = re.compile(r'`([^`\n]{2,80})`')
RE_SEC = re.compile(r'§\d{1,3}(?:\.\d{1,2})?')
RE_ID = re.compile(r'[A-Za-z_][A-Za-z0-9_.]{2,40}')
RE_NUM = re.compile(r'\d[\d,]*(?:\.\d+)?%?')


def tokens(text):
    out = set()
    for m in RE_TICK.finditer(text):
        out.add(m.group(1).strip())
    for m in RE_SEC.finditer(text):
        out.add(m.group(0))
    for m in RE_ID.finditer(text):
        out.add(m.group(0))
    for m in RE_NUM.finditer(text):
        out.add(m.group(0))
    # 明显是噪声的丢掉：纯 1~2 位数字、纯年份以外的都留着
    out = {t for t in out if t and (len(t) >= 3 or not t.isdigit())}
    return out


old_tok = tokens(old_mem)
new_tok = tokens(new_mem)
det_tok = tokens(det)

gone = sorted(old_tok - new_tok)          # 新速查本里没了
miss = [t for t in gone if t not in det_tok]
soft = [t for t in gone if t in det_tok]

check('V1a 分母闸：旧版令牌数 > 500（不是空集自证）',
      len(old_tok) > 500, '旧版令牌 %d 个' % len(old_tok))
check('V1b ★★★ 旧版令牌里**没有一个**在两处都找不到（真丢失）',
      not miss, 'MISS=%d 例：%s' % (len(miss), miss[:12]))
check('V1c 下沉有效：确有令牌从速查本移出、且都能在详版 `in` 到',
      len(soft) > 30, '下沉令牌 %d 个' % len(soft))

# ---------------- 详版侧 ----------------
check('V2a 详版里有 §117 章节标题', '## §117' in det)
for sub in ('§117.5', '§117.6', '§117.7'):
    check('V2b 详版里有子节 %s' % sub, sub in det)

# 旧版里那三段被压的原句，必须**逐字**躺在详版里
VERBATIM = [
    u'131 条切成 38 个碎块',
    u'38 个互不相连的碎块（最大 14 间）',
    u'`conn_inferred115.json`＝**候选边**（ut 563/outertale 588）',
    u'无解 2,057＝一门房摆 4 个 doorA',
    u'2560×1600：2133×1600/6.666',
    u'`_ui_base`+`_i(key)=int(round(base[key]*s))`',
    u'`check99`(36)+`verify_scene_fit99`(106)',
    u'`spr_darkdoor` 44×56',
    u'`QScreen.grabWindow(0)`',
]
bad = [v for v in VERBATIM if v not in det]
check('V2c ★★★ 抽 %d 段被压原句，逐字都在详版（不是"大意还在"）' % len(VERBATIM),
      not bad, '缺：%s' % (bad or '无'))

# ---------------- 新速查本自身 ----------------
b = open(MEM, 'rb').read()
js = len(new_mem.encode('utf-16-le')) // 2
check('V3a ★★★ `js_len ≤ 10000`（与 `check95 A2` 同口径：UTF-16 码元数）',
      js <= 10000, 'js_len=%d 余量=%d' % (js, 10000 - js))
check('V3b 余量 ≥ 300（给下一轮留位置，别贴着上限）',
      10000 - js >= 300, '余量=%d' % (10000 - js))
check('V3c 净减：新 < 旧（本轮的改动是压缩，不是借机加内容）',
      len(new_mem) < len(old_mem),
      'old=%d new=%d 减=%d' % (len(old_mem), len(new_mem), len(old_mem) - len(new_mem)))
check('V3d 无 BOM', b[:3] != b'\xef\xbb\xbf')
check('V3e 无 U+FFFD（编码没坏）', u'\ufffd' not in new_mem)
crlf, lf = b.count(b'\r\n'), b.count(b'\n')
check('V3f EOL 不混用（不是"必须 LF"——该文件历史就是 CRLF）',
      crlf == lf, 'CRLF=%d LF=%d' % (crlf, lf))

# 标题完整性：14 个 `## ` 章节 + 1 个 `# ` 主标题。
# ★ 判据自己也栽过一次：第一版写 `len(heads) == 15`（把 H1 数进来了）⇒ 假红。
N_H2 = 14
heads = [l for l in new_mem.splitlines() if l.startswith('## ')]
check('V3g %d 个 `## ` 章节标题都在（压缩没把某一节整段吃掉）' % N_H2,
      len(heads) == N_H2, '实际 %d 个' % len(heads))
check('V3g2 且 `# ` 主标题仍在（只有 1 个 H1）',
      len([l for l in new_mem.splitlines() if l.startswith('# ')]) == 1)
check('V3h 标题无重复', len(set(heads)) == len(heads),
      '重复：%s' % [h for h in set(heads) if heads.count(h) > 1])
_at_line_start = len(re.findall(r'(?m)^## ', new_mem))
check('V3i 没有标题粘在上一行行尾（`## ` 必须真的在行首）',
      _at_line_start == len(heads),
      '行首 %d / 共 %d' % (_at_line_start, len(heads)))

print()
print('=' * 70)
print('合计 PASS=%d FAIL=%d' % (n_pass, n_fail))
if failed:
    print('失败项：')
    for d in failed:
        print('  - %s' % d)
print('=' * 70)
sys.exit(0 if n_fail == 0 else 1)
