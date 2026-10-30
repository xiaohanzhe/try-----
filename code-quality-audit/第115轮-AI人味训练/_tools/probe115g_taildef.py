# -*- coding: utf-8 -*-
"""
第115轮 · 钉死索引哈希口径（只读）

probe115f 的发现（这是**不能靠猜**的地方）：
  · 76 份尾部块逐字节相同，其 raw sha256 = `ad1269d1…`；
  · 但索引顶层 `tail_sha256` = `fd46fd7d…` —— **两者不等**！
  ⇒ 说明顶层那个哈希**不是**"从 .txt 里切出来那段的哈希"。

本项目栽过太多次"哈希口径搞错 ⇒ 静默错账"，所以这里**逐个口径试**，
把 `tail_text` / `tail_sha256` / 每记录的 `chars`/`bytes`/`sha256`/`sha256_lf`
分别对到**唯一命中**的那一个定义上。只读。
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
INDEX = os.path.join(NPC, '_personas.json')

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def h(b):
    return hashlib.sha256(b).hexdigest()


def main():
    idx = json.loads(io.open(INDEX, 'rb').read().decode('utf-8'))
    top = idx.get('tail_sha256')
    tt = idx.get('tail_text')

    say('顶层 tail_sha256 = %s' % top)
    say('顶层 tail_text   = %r' % (tt,))
    say('tail_text 长度   = %d 字符' % (len(tt) if tt else -1))

    say('\n=== A. tail_sha256 到底对什么取哈希 ===')
    cands = {
        'tail_text 原样 utf-8': tt.encode('utf-8'),
        'tail_text LF→CRLF': tt.replace('\n', '\r\n').encode('utf-8'),
        'tail_text CRLF→LF': tt.replace('\r\n', '\n').encode('utf-8'),
        'tail_text + "\\n"': (tt + '\n').encode('utf-8'),
        'tail_text + "\\r\\n"': (tt + '\r\n').encode('utf-8'),
        'tail_text 去尾空白': tt.strip().encode('utf-8'),
    }
    hit = None
    for k, b in cands.items():
        ok = h(b) == top
        say('  %-24s %s %s' % (k, h(b)[:16], '<== 命中' if ok else ''))
        if ok:
            hit = k
    say('  ⇒ 定义 = %s' % (hit or '**未命中任何候选（要继续查）**'))

    say('\n=== B. 每记录的 chars/bytes/sha256/sha256_lf 口径 ===')
    recs = idx.get('personas') or []
    r0 = recs[0]
    # ★ 索引里的 `file` 是**相对 npc/ 的路径**（形如 `persona/asgore.txt`）
    p = os.path.join(NPC, r0['file']) if r0.get('file') else os.path.join(PDIR, r0['id'] + '.txt')
    raw = io.open(p, 'rb').read()
    txt = raw.decode('utf-8')
    say('  样本 = %s' % os.path.basename(p))
    say('  记录: chars=%s bytes=%s sha256=%s sha256_lf=%s'
        % (r0.get('chars'), r0.get('bytes'), str(r0.get('sha256'))[:16],
           str(r0.get('sha256_lf'))[:16]))
    say('  实测: 磁盘字节=%d  字符=%d  sha(raw)=%s  sha(LF)=%s'
        % (len(raw), len(txt), h(raw)[:16], h(raw.replace(b'\r\n', b'\n'))[:16]))
    say('  ⇒ bytes 口径命中 raw 字节? %s' % (r0.get('bytes') == len(raw)))
    say('  ⇒ chars 口径命中 len(text)? %s' % (r0.get('chars') == len(txt)))
    say('  ⇒ sha256 命中 raw? %s' % (r0.get('sha256') == h(raw)))
    say('  ⇒ sha256_lf 命中 LF 归一? %s'
        % (r0.get('sha256_lf') == h(raw.replace(b'\r\n', b'\n'))))

    say('\n=== C. 尾块在文件里的**实际切片**与 tail_text 的关系 ===')
    MARK = u'【本项目补充'
    i = txt.find(MARK)
    tail_slice = txt[i:]
    say('  文件内切片起点 index = %d' % i)
    say('  切片字符数 = %d ｜ tail_text 字符数 = %d' % (len(tail_slice), len(tt)))
    say('  切片 == tail_text ? %s' % (tail_slice == tt))
    say('  ★ 切片里有 CR 吗（\\r in slice）= %s' % ('\r' in tail_slice))
    say('  ★ 切片前的正文里有 CR 吗 = %s' % ('\r' in txt[:i]))
    say('  切片.strip() == tail_text.strip() ? %s'
        % (tail_slice.strip() == tt.strip()))
    say('  切片尾部 6 字符 repr = %r' % tail_slice[-6:])
    say('  文件尾部 6 字符 repr = %r' % txt[-6:])
    say('  ⇒ 切片 - 尾换行 == tail_text ? %s'
        % (tail_slice[:-1] == tt if tail_slice.endswith('\n') else False))

    say('\n=== D. 尾块在文件中的终止位置（后面还有没有内容）===')
    say('  切片结尾到 EOF：%s（若为 True ⇒ 尾块一直到底，直接 append 新行即可）'
        % (tail_slice.rstrip() == txt[i:].rstrip()))
    say('  文件是否以换行结尾 = %s' % txt.endswith('\n'))

    say('\n=== E. tail_text 逐字（这是要改的**单一真源**）===')
    say(repr(tt))

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
            with io.open(os.path.join(ev, 'probe115g_taildef_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
