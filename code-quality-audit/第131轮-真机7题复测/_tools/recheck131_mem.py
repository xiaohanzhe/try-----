# -*- coding: utf-8 -*-
"""第131轮 · 记忆文件复检（只读，不改变被测状态）。

守六件事：
  A 体积：MEMORY.md 的 UTF-16 码元数 <= 10000（check95 A2 的硬闸口径）
  B 编码：无 BOM / 无 U+FFFD / EOL 不混用（这份文件历来 CRLF，不要求 LF）
  C 新增：131 的要点真的落进速查本（逐条 in）
  D 守恒：本轮为腾空间删掉的令牌，逐个回详版 in 一次
  E 结构：详版 §131.1~§131.8 全在
  F 日志：当日日志既有 130 又有 131，且 130 在前（append-only 的证据）

分母闸：C/D/E 每段先断言"应检条数 > 0"。
★ 上轮栽过三条"判据过窄"的假红，本轮一律查**稳定的语义片段**，不整句抄。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
LOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-11-01.md')

TOTAL = 0
FAILED = 0


def ok(cond, msg, extra=''):
    global TOTAL, FAILED
    TOTAL += 1
    if not cond:
        FAILED += 1
    print('%s %s%s' % ('[OK]  ' if cond else '[FAIL]', msg, ('  ' + extra) if extra else ''))


def read(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    for p in (MEM, DETAIL, LOG):
        ok(os.path.isfile(p), '文件存在：%s' % os.path.basename(p))
    if FAILED:
        print('合计：%d 判据 / %d FAIL' % (TOTAL, FAILED))
        return 1

    mem = read(MEM)
    det = read(DETAIL)
    log = read(LOG)
    raw = io.open(MEM, 'rb').read()

    js = len(mem.encode('utf-16-le')) // 2
    ok(js <= 10000, 'A1 速查本 UTF-16 码元数 <= 10000', 'js_len=%d 余 %d' % (js, 10000 - js))
    ok(len(mem) > 8000, 'A2 速查本没被压成空壳（codepoints > 8000）', 'cp=%d' % len(mem))

    ok(not raw.startswith(b'\xef\xbb\xbf'), 'B1 无 BOM')
    ok('\ufffd' not in mem, 'B2 无 U+FFFD 乱码')
    n_crlf = raw.count(b'\r\n')
    n_lf = raw.count(b'\n') - n_crlf
    ok((n_crlf == 0) or (n_lf == 0), 'B3 EOL 不混用', 'CRLF=%d 裸LF=%d' % (n_crlf, n_lf))

    added = [
        ('131 真机 n=3', '131 的结论进了 §5'),
        ('6/6→1/6', '那边引力的 before→after 数字'),
        ('3/3→2/3', '"记忆不许编"基本无效的数字'),
        ('check131', '锁号速查含 check131'),
        ('131＝真机7题复测', '近轮要点含 131'),
    ]
    ok(len(added) > 0, 'C0 分母闸：新增要点非空集', 'n=%d' % len(added))
    for tok, desc in added:
        ok(tok in mem, 'C 新增在位：%s' % desc, tok)

    dropped = [
        ('0/358', 'outertale 按名匹配为 0 的证据'),
        ('死路', '可读物正文走错路的留档'),
        ('正负号', '第125轮"证据不足"的取证冤案'),
        ('1,740', 'routes 条数'),
        ('98 条', 'W 门拒收时的证据条数'),
        ('非 UT', '另 20 间不是 UT 房的说明'),
    ]
    ok(len(dropped) > 0, 'D0 分母闸：删除令牌清单非空集', 'n=%d' % len(dropped))
    for tok, desc in dropped:
        ok(tok in det, 'D 删后有据：%s' % desc, tok)

    secs = ['## §131.%d' % i for i in range(1, 9)]
    ok(len(secs) > 0, 'E0 分母闸：§131 小节清单非空集', 'n=%d' % len(secs))
    for s in secs:
        ok(s in det, 'E 详版小节在位：%s' % s)

    ok('## 第131轮' in log, 'F1 当日日志有第131轮整节')
    ok('## 第130轮' in log, 'F2 第130轮整节仍在（append-only）')
    ok(log.index('## 第130轮') < log.index('## 第131轮'), 'F3 130 在 131 之前（确实是追加）')

    print('-' * 60)
    print('合计：%d 判据 / %d FAIL' % (TOTAL, FAILED))
    print('[PASS] recheck131_mem' if FAILED == 0 else '[FAIL] recheck131_mem')
    return 0 if FAILED == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
