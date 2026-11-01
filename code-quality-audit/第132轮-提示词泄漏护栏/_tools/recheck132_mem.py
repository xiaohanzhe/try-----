# -*- coding: utf-8 -*-
"""第132轮 · 记忆文件复检（只读）。

A 体积 / B 编码 / C 新增要点在位 / D 本轮删掉的令牌仍能在详版检索 / E 详版 §132 结构 / F 日志 append-only

★ 上一轮抓到过"以为详版有、其实从来没有"（`obj_doorD` 正负号），所以 D 段一条都不省。
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


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    for p in (MEM, DETAIL, LOG):
        ok(os.path.isfile(p), '文件存在：%s' % os.path.basename(p))
    if FAILED:
        return 1

    mem, det, log = read(MEM), read(DETAIL), read(LOG)
    raw = io.open(MEM, 'rb').read()

    js = len(mem.encode('utf-16-le')) // 2
    ok(js <= 10000, 'A1 速查本 UTF-16 码元数 <= 10000', 'js_len=%d 余 %d' % (js, 10000 - js))
    ok(not raw.startswith(b'\xef\xbb\xbf'), 'B1 无 BOM')
    ok('\ufffd' not in mem, 'B2 无 U+FFFD')
    n_crlf = raw.count(b'\r\n')
    n_lf = raw.count(b'\n') - n_crlf
    ok((n_crlf == 0) or (n_lf == 0), 'B3 EOL 不混用', 'CRLF=%d 裸LF=%d' % (n_crlf, n_lf))

    added = [('132 元话语泄漏', '132 的结论进 §5'),
             ('重合度判不了', '本轮最重要的负结论'),
             ('check132', '锁号含 check132'),
             ('132＝元话语泄漏闸', '近轮要点含 132'),
             # ★ 判据自纠：`main78` 原来被放进"删掉的令牌"里去详版查 —— 查不到就报红。
             #   但本轮只压掉了 `tier` 这个词，`main78/plain18` 仍在速查本里（事实没丢），
             #   所以它属于"在位"。
             ('main78/plain18', '档位分布仍在（本轮只压掉了 tier 一词）')]
    ok(len(added) > 0, 'C0 分母闸：新增要点非空集', 'n=%d' % len(added))
    for tok, desc in added:
        ok(tok in mem, 'C 新增在位：%s' % desc, tok)

    dropped = [('三连确认', 'Niko 家彩蛋的三连确认'),
               ('209', 'outertale 补 209 条门'),
               ('§108', '旧遗留池的下沉指针'),
               ('1,740', 'routes 条数')]
    ok(len(dropped) > 0, 'D0 分母闸：删除令牌清单非空集', 'n=%d' % len(dropped))
    for tok, desc in dropped:
        ok(tok in det, 'D 删后有据：%s' % desc, tok)

    secs = ['## §132.%d' % i for i in range(1, 8)]
    ok(len(secs) > 0, 'E0 分母闸：§132 小节清单非空集', 'n=%d' % len(secs))
    for s in secs:
        ok(s in det, 'E 详版小节在位：%s' % s)

    ok('## 第132轮' in log, 'F1 日志有第132轮整节')
    ok('## 第131轮' in log, 'F2 第131轮整节仍在')
    ok(log.index('## 第131轮') < log.index('## 第132轮'), 'F3 131 在 132 之前（append-only）')

    print('-' * 60)
    print('合计：%d 判据 / %d FAIL' % (TOTAL, FAILED))
    print('[PASS] recheck132_mem' if FAILED == 0 else '[FAIL] recheck132_mem')
    return 0 if FAILED == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
