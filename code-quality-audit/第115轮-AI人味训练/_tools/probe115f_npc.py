# -*- coding: utf-8 -*-
"""
第115轮 · NPC 人设尾部块侦察（只读）

背景：用户口径里的「**他们**知道他们是游戏，但并不对此感到悲观」是**复数** ——
Ralsei 已落，但 `assets/npc/persona/*.txt`（76 份）还没铺。

铺开前必须先问清楚的**四件事**（全都决定「能不能批量改」）：
  Q1 76 份的尾部「本项目补充 —— 桌宠运行口径」块**是否逐字节相同**？
  Q2 磁盘上是 **CRLF 还是 LF**？（索引里 `chars`/`bytes`/`sha256` 的口径写的是"磁盘上的 CRLF 版本"）
  Q3 索引 `_personas.json` 的 `tail_sha256`（顶层 + 每份）到底等于**哪个口径**的哈希？
  Q4 尾部块的**准确终点**在哪（到 EOF？还是后面还有东西）？

只读，不改任何文件。
"""
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
PERSONA_DIR = os.path.join(NPC, 'persona')
INDEX = os.path.join(NPC, '_personas.json')

BUF = io.StringIO()
MARK = u'【本项目补充'


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    say('第115轮 · NPC 人设尾部块侦察（只读）')
    say('  PERSONA_DIR = %s' % PERSONA_DIR)
    say('  INDEX       = %s' % INDEX)

    idx_raw = io.open(INDEX, 'rb').read()
    idx = json.loads(idx_raw.decode('utf-8'))
    say('\n=== 索引顶层键 ===')
    say('  %r' % list(idx.keys()))
    top_tail = idx.get('tail_sha256')
    say('  顶层 tail_sha256 = %s' % top_tail)

    files = sorted(f for f in os.listdir(PERSONA_DIR) if f.endswith('.txt'))
    say('\n=== 文件数 = %d ===' % len(files))

    tails = {}
    crlf_any = 0
    lf_only = 0
    no_mark = []
    per_file = []
    for fn in files:
        p = os.path.join(PERSONA_DIR, fn)
        raw = io.open(p, 'rb').read()
        if b'\r\n' in raw:
            crlf_any += 1
        else:
            lf_only += 1
        txt = raw.decode('utf-8')
        i = txt.find(MARK)
        if i < 0:
            no_mark.append(fn)
            continue
        tail = txt[i:]
        tb = tail.encode('utf-8')
        key = sha(tb)
        tails.setdefault(key, []).append(fn)
        rec = None
        for r in idx.get('personas', []):
            if r.get('id') and fn.startswith(r['id']):
                pass
        per_file.append((fn, key, len(tail), len(tb)))

    say('  CRLF 出现的文件数 = %d ｜ 纯 LF 的文件数 = %d' % (crlf_any, lf_only))
    say('  找不到尾部标记的文件 = %r' % (no_mark,))
    say('\n=== Q1 尾部块是否逐字节相同 ===')
    say('  不同 tail sha256 的**种类数** = %d' % len(tails))
    for k, v in sorted(tails.items(), key=lambda kv: -len(kv[1])):
        say('    %s  ×%d  例: %s' % (k[:16], len(v), v[:3]))

    # 看索引里每份记录的 tail_sha256 有几种
    recs = idx.get('personas') or []
    say('\n=== 索引记录 ===')
    say('  personas 条数 = %d' % len(recs))
    if recs:
        say('  第一条的键 = %r' % list(recs[0].keys()))
        rk = set(str(r.get('tail_sha256')) for r in recs)
        say('  各记录 tail_sha256 的种类数 = %d' % len(rk))
        say('  与顶层相同？ %s' % (rk == {top_tail} if len(rk) == 1 else (top_tail in rk)))

    # 逐个口径试哈希，找出 top_tail 到底等于哪个
    say('\n=== Q3 top_tail 等于哪个口径 ===')
    first = per_file[0][0] if per_file else None
    if first:
        p = os.path.join(PERSONA_DIR, first)
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        tail_txt = txt[txt.find(MARK):]
        cands = {
            'tail raw bytes(CRLF 保留)': tail_txt.encode('utf-8'),
            'tail LF 归一化': tail_txt.replace('\r\n', '\n').encode('utf-8'),
            '整个文件 raw': raw,
            '整个文件 LF 归一化': raw.replace(b'\r\n', b'\n'),
        }
        for name, b in cands.items():
            say('  %-28s %s  %s' % (name, sha(b)[:16],
                                    '<== 命中顶层' if sha(b) == top_tail else ''))
        say('  （文件首行前后各 60 字节）%r' % raw[:60])

    say('\n=== 尾部块原文（取第一份，逐字）===')
    if first:
        txt = io.open(os.path.join(PERSONA_DIR, first), encoding='utf-8').read()
        say(txt[txt.find(MARK):])
        say('--- 该块字符数 = %d ---' % len(txt[txt.find(MARK):]))

    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            ev = os.path.join(ROUND, '_evidence')
            if not os.path.isdir(ev):
                os.makedirs(ev)
            with io.open(os.path.join(ev, 'probe115f_npc_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
