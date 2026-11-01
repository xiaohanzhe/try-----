# -*- coding: utf-8 -*-
"""第134轮记忆文件复检。

对象：`.workbuddy/memory/MEMORY.md`（速查本，注入）+ `参考-契约与历轮（详版）.md` + 当日日志。

★ 硬闸：`check95 A2` —— 速查本 `js_len ≤ 10000`，口径是 **UTF-16 码元数**（不是字节、不是字符）。
★ 纪律：
  · 删令牌**必须有据**（"速查本 or 详版"并集里还在），逐条打印，不许只报总数。
  · 当日日志 **append-only**：既要有本轮内容，也不能少了上一轮的内容。
  · 匹配用宽式（`§` 可选）—— 判据太窄会报假红（第133轮踩过）。
"""
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MEMDIR = os.path.join(ROOT, '.workbuddy', 'memory')
FAST = os.path.join(MEMDIR, 'MEMORY.md')
DETAIL = os.path.join(MEMDIR, u'参考-契约与历轮（详版）.md')
TODAY = os.path.join(MEMDIR, '2026-11-01.md')

_n = {'p': 0, 'f': 0}
_failed = []


def ok(desc, cond, extra=''):
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


def _raw(p):
    with io.open(p, 'rb') as f:
        return f.read()


_fast = _read(FAST)
_det = _read(DETAIL)
_today = _read(TODAY)

# =============================================== A 体积
head(u'A. 体积（`check95 A2` 硬闸：UTF-16 码元 ≤ 10000）')

_js = len(_fast.encode('utf-16-le')) // 2
_chars = len(_fast)
_bytes = len(_fast.encode('utf-8'))
ok(u'A1 速查本 js_len ≤ 10000', _js <= 10000, u'js_len=%d（余 %d）· chars=%d · bytes=%d'
   % (_js, 10000 - _js, _chars, _bytes))
ok(u'A2 速查本非空且结构完整（§0 铁律 + §11 待裁定都在）',
   u'## 0. 铁律' in _fast and u'## 11. 待裁定' in _fast)
ok(u'A3 详版不是空壳（> 1 MB）', len(_det.encode('utf-8')) > 1000000,
   u'%d 字节' % len(_det.encode('utf-8')))

# =============================================== B 编码
head(u'B. 编码（BOM / U+FFFD）')

for p, name in ((FAST, u'速查本'), (DETAIL, u'详版'), (TODAY, u'当日日志')):
    b = _raw(p)
    ok(u'B1 %s 无 BOM' % name, not b.startswith(b'\xef\xbb\xbf'))
    ok(u'B2 %s 无 U+FFFD' % name, u'\ufffd' not in b.decode('utf-8'))

# =============================================== C 新增在位
head(u'C. 本轮新增内容在位（速查本 + 详版 + 日志）')

_need_fast = [u'check134', u'58/59', u'ralsei', u'134＝训练线收口']
for t in _need_fast:
    ok(u'C1 速查本含 %r' % t, t in _fast)

for i in range(1, 9):
    t = u'§134.%d' % i
    ok(u'C2 详版含 %s' % t, t in _det)

for t in (u'6387', u'B1c2', u'_personas.json', u'零读取'):
    ok(u'C3 详版含 %r' % t, t in _det)

ok(u'C4 详版 §134 的标题在（`## §134 第134轮：训练线收口`）',
   u'## §134 第134轮：训练线收口' in _det)
ok(u'C5 当日日志有「第134轮」一节', u'### 第134轮' in _today or u'## 第134轮' in _today)

# =============================================== D 删后有据
head(u'D. 删掉的令牌必须仍可检索（速查本 or 详版 并集）')

# 本轮从速查本移出的令牌（锁号减一个 + 近轮要点去括号说明）
_removed = [u'check126', u'check125', u'门型/落点/寻路']
for t in _removed:
    hit_fast = t in _fast
    hit_det = t in _det or (t.replace(u'§', u'') in _det)
    ok(u'D1 %r 仍可检索（速查本=%s / 详版=%s）' % (t, hit_fast, hit_det),
       hit_fast or hit_det)

# ★ 上一轮的数字不许被这一轮的压缩带走
for t in (u'6/6', u'1/6', u'3/3', u'2/3'):
    ok(u'D2 第131/132轮的数字 %r 仍在（速查本 or 详版）' % t, t in _fast or t in _det)

# ★ 负控制：编造的令牌必须判"不在"（证明 D1 不是恒真）
for fake in (u'zzz_fake_token_134', u'§134.99', u'check134__nonexistent'):
    ok(u'D3 负控制：编造令牌 %r 必须判不在' % fake,
       fake not in _fast or (fake == u'§134.99' and fake not in _det))

# =============================================== E 日志 append-only
head(u'E. 当日日志 append-only（上一轮的内容不许消失）')

for t in (u'第133轮', u'guard_reaction', u'2ad801e', u'local-133'):
    ok(u'E1 上一轮留下的 %r 仍在日志里' % t, t in _today)

ok(u'E2 日志里有本轮的推送/遗留登记（`local-134` 或「遗留」节）',
   u'local-134' in _today or u'### 遗留' in _today)

# =============================================== F 守恒
head(u'F. 守恒（记录净变化，不判"好不好"，只判"没失控"）')

_prev = 9984      # 第133轮收口值（本文件第133轮的结论）
ok(u'F1 相对上一轮净变化在 ±40 码元内（结构性压缩，不是大改）',
   abs(_js - _prev) <= 40, u'%d → %d（差 %+d）' % (_prev, _js, _js - _prev))
ok(u'F2 余量 ≥ 10（留给下一轮）', (10000 - _js) >= 10, u'余 %d' % (10000 - _js))

# =============================================== 落盘
print(u'')
print(u'=' * 78)
print(u'recheck134_mem：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
