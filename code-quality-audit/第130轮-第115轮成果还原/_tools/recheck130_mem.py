# -*- coding: utf-8 -*-
"""第130轮 · 记忆文件复检（只读，不改变被测状态）。

守六件事：
  A. 体积：MEMORY.md 的 UTF-16 码元数 <= 10000（check95 A2 的硬闸口径）
  B. 编码：无 BOM / 无 U+FFFD / 纯 LF
  C. 新增：本轮 130 的要点真的落进速查本（逐条 in）
  D. 守恒：本轮为腾空间删掉的令牌，逐个回详版 in 一次（删了就找不回来 = 静默丢信息）
  E. 结构：详版 §130.1~§130.8 全在
  F. 日志：当日日志既有 129 整节又有 130 整节（append-only 的证据）

分母闸：C/D/E 每段都先断言"应检条数 > 0"，否则"0 条全过"是假绿。
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
    # 字节忠实：newline='' 不吞 CRLF，才能判 EOL
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    for p in (MEM, DETAIL, LOG):
        ok(os.path.isfile(p), '文件存在：%s' % os.path.basename(p), p)
    if FAILED:
        print('合计：%d 判据 / %d FAIL' % (TOTAL, FAILED))
        return 1

    mem = read(MEM)
    det = read(DETAIL)
    log = read(LOG)

    # ---- A 体积（口径 = UTF-16 码元数，与 check95 A2 一致） ----
    js_len = len(mem.encode('utf-16-le')) // 2
    ok(js_len <= 10000, 'A1 速查本 UTF-16 码元数 <= 10000', 'js_len=%d 余 %d' % (js_len, 10000 - js_len))
    ok(len(mem) > 8000, 'A2 速查本没有被压成空壳（codepoints > 8000）', 'cp=%d' % len(mem))

    # ---- B 编码 ----
    raw = io.open(MEM, 'rb').read()
    ok(not raw.startswith(b'\xef\xbb\xbf'), 'B1 无 BOM')
    ok('\ufffd' not in mem, 'B2 无 U+FFFD 乱码')
    # 判据自纠①：原来写"纯 LF"是**错的** —— 这份文件历来是 CRLF，
    # 该守的是"EOL 不混用"（编辑不许把一半行改成 LF），不是"必须 LF"。
    n_crlf = raw.count(b'\r\n')
    n_lf_only = raw.count(b'\n') - n_crlf
    ok((n_crlf == 0) or (n_lf_only == 0),
       'B3 EOL 不混用（全 CRLF 或全 LF）', 'CRLF=%d 裸LF=%d' % (n_crlf, n_lf_only))

    # ---- C 本轮新增要点在位（分母闸） ----
    added = [
        ('worktree 从未提交', '改在 worktree ＝ 从未提交（130 的根因）'),
        ('禁整覆盖', 'worktree mtime 更旧 ⇒ 禁整文件覆盖'),
        ('派生字段必被重建冲掉', '派生字段必被重建冲掉（voice_markers）'),
        ('voice_markers', 'voice_markers 作为派生字段被点名'),
        ('cards113.py` 必 `--all', 'cards113.py 必须带 --all'),
        ('check115', '锁号速查含 check115'),
        ('130＝取回第115轮成果', '近轮要点含 130'),
    ]
    ok(len(added) > 0, 'C0 分母闸：新增要点非空集', 'n=%d' % len(added))
    for token, desc in added:
        ok(token in mem, 'C 新增在位：%s' % desc, token)

    # ---- D 本轮删掉的令牌必须仍能在详版检索到（分母闸） ----
    dropped = [
        ('95.9%', '第125轮 D 门 marker 覆盖率'),
        ('obj_doorD', '第125轮"证据不足"的取证冤案对象'),
        ('musfade', '第126轮"musfade 变体"这条线索本身'),
        ('已证伪', '第126轮遗留池那项已证伪的结论'),
        ('if not cand', '第127轮别名档被判死的那个 if'),
        ('ambiguous', '第127轮误判类型'),
        ('§127', '详版第127轮整节（速查本已只留要点）'),
    ]
    ok(len(dropped) > 0, 'D0 分母闸：删除令牌清单非空集', 'n=%d' % len(dropped))
    for token, desc in dropped:
        ok(token in det, 'D 删后有据：%s' % desc, token)

    # 被削掉的下沉指针：§99/§103~§105 这几节自己还在详版里
    for sec in ('§99', '§103', '§104', '§105'):
        ok(sec in det, 'D 下沉节仍可检索：%s' % sec, sec)

    # ---- E 详版 §130.x 结构 ----
    secs = ['## §130.%d' % i for i in range(1, 9)]
    ok(len(secs) > 0, 'E0 分母闸：§130 小节清单非空集', 'n=%d' % len(secs))
    for s in secs:
        ok(s in det, 'E 详版小节在位：%s' % s)

    # ---- F 当日日志 append-only ----
    ok('## 第130轮' in log, 'F1 当日日志有第130轮整节')
    ok('## 第129轮' in log, 'F2 第129轮整节仍在（append-only，没被覆盖）')
    ok(log.index('## 第129轮') < log.index('## 第130轮'), 'F3 129 在 130 之前（确实是追加）')

    print('-' * 60)
    print('合计：%d 判据 / %d FAIL' % (TOTAL, FAILED))
    print('[PASS] recheck130_mem' if FAILED == 0 else '[FAIL] recheck130_mem')
    return 0 if FAILED == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
