# -*- coding: utf-8 -*-
"""第113轮i · 把「本地化人设」正式落进产品，并同步两层登记（索引）。

背景
----
`probe_lang113i.py` 的 A/B 实测已经定性（`hy_guardener`）：

    A 原版（人设 30% 拉丁、示例段 49% 拉丁）  中文占比 **0.00**
    B 译版（人设 7% 拉丁、示例段 3% 拉丁）   中文占比 **0.79**
    ⇒ 根因 = **语料语言**，不是接线、不是措辞、不是纠正机制。

本脚本负责把「取证产物」变成「产品文件」。它自己不做翻译，只做三件事：

  ① **结构守门**：只许改正文里的行内容，不许改行数、不许碰尾部
     「【本项目补充 —— 桌宠运行口径】」块（那是我们加的运行规则，不是角色设定）、
     不许改 EOL、不许引入 BOM。**任何一条不满足就拒绝写盘**。
  ② **原子写盘** + 回读逐字节比对（`os.replace`，失败不留半截文件）。
  ③ **同步 `_personas.json`**：重算 `chars`/`bytes`/`sha256`/`sha256_lf`/`sections`。
     ★★★ 为什么不能直接跑 `personas113.py --write`：它是**生成器**，会从
     `SRC`（用户提供的原始 txt）重算正文并覆盖 —— 手改的中文化会被它一把抹掉。
     ⇒ 索引只能**定点改这 4 个字段**，正文一个字节都不许它动。

用法
----
    python apply_loc113i.py --id hy_guardener --src <译版.txt>          # dry
    python apply_loc113i.py --id hy_guardener --src <译版.txt> --write  # 落盘
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
IDX = os.path.join(NPC, '_personas.json')

#: 尾部「本项目补充」块的分隔锚点。它是运行口径而不是角色设定，**译版不许动它**。
TAIL_ANCHOR = '【本项目补充'

#: 段落标题的识别式（与 `personas113.py` 的 `sections` 口径一致：【xxx】行）。
import re                                                    # noqa: E402
SEC_RE = re.compile(r'^【(.+?)】\s*$', re.M)


def read_disk(path):
    """按**字节忠实**方式读（`newline=''` ⇒ 不替我们归一化 CRLF）。"""
    return io.open(path, encoding='utf-8', newline='').read()


def latin_ratio(t):
    body = [c for c in t if not c.isspace()]
    if not body:
        return 0.0
    return sum(1 for c in body if c.isascii() and c.isalpha()) / len(body)


def sha_calc(raw):
    """与索引口径完全一致：`sha256` 用 CRLF 磁盘文本，`sha256_lf` 用 LF 归一化。"""
    return {
        'chars': len(raw),
        'bytes': len(raw.encode('utf-8')),
        'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
        'sha256_lf': hashlib.sha256(raw.replace('\r\n', '\n').encode('utf-8')).hexdigest(),
    }


def split_tail(raw):
    """拆成 (正文, 尾部块)。锚点必须**恰好出现一次**，否则说明结构已经不对了。"""
    n = raw.count(TAIL_ANCHOR)
    if n != 1:
        return None, None, n
    i = raw.index(TAIL_ANCHOR)
    # 往前退到该行行首（尾部块前通常有 "\r\n\r\n" 或 "\n\n" 分隔）
    j = max(raw.rfind('\n', 0, i) + 1, 0)
    return raw[:j], raw[j:], n


def main(argv):
    do_write = '--write' in argv
    nid = src = None
    for k, a in enumerate(argv):
        if a == '--id' and k + 1 < len(argv):
            nid = argv[k + 1]
        elif a == '--src' and k + 1 < len(argv):
            src = argv[k + 1]
    if not nid or not src:
        print('用法：apply_loc113i.py --id <npc_id> --src <译版.txt> [--write]')
        return 2

    idx = json.loads(read_disk(IDX))
    rec = next((r for r in idx['personas'] if r['id'] == nid), None)
    if rec is None:
        print('FAIL: 索引里没有 %s' % nid)
        return 3
    dst = os.path.join(NPC, rec['file'])
    src = os.path.abspath(src)
    for p in (dst, src):
        if not os.path.isfile(p):
            print('FAIL: 文件不存在 —— %s' % p)
            return 3

    old = read_disk(dst)
    new = read_disk(src)

    print('=== 结构守门（任何一条不过就拒绝写盘）===')
    ok = True

    # ① 行数必须一致：译版是「整行替换」，不许增删行（增删会让段落结构漂移）
    n_old, n_new = len(old.splitlines()), len(new.splitlines())
    c1 = (n_old == n_new)
    ok &= c1
    print('  ① 行数 %d → %d  %s' % (n_old, n_new, 'OK' if c1 else 'FAIL'))

    # ② 尾部「本项目补充」块逐字不变
    ot, tt_old, cnt_old = split_tail(old)
    nt, tt_new, cnt_new = split_tail(new)
    c2 = (cnt_old == 1 and cnt_new == 1 and tt_old == tt_new)
    ok &= c2
    print('  ② 尾部运行口径块逐字不变  %s（锚点出现 %d/%d 次，尾块 %d 字）'
          % ('OK' if c2 else 'FAIL', cnt_old, cnt_new, len(tt_new or '')))

    # ③ EOL 分布必须**一模一样**。
    #   ★★★ 第一版写的是 `(old_crlf > 0) == (new_crlf > 0)` —— 只判"有没有 CRLF"。
    #   这些人设是**混合 EOL**（`hy_guardener` 112 行里 94 个 CRLF、18 行纯 LF，
    #   `hy_axis` 121 行里 112 个），只判 >0 等于没判：后面我用编辑器改一个字，
    #   工具把整份文件的 CRLF 抹成了 LF，这条判据**照样绿**。
    #   真判据是"个数相等"：译版是整行替换、行数不变 ⇒ CRLF 个数必须一个不差。
    old_crlf = old.count('\r\n')
    new_crlf = new.count('\r\n')
    c3 = (old_crlf == new_crlf)
    ok &= c3
    print('  ③ CRLF 个数一致（原文 %d ／ 译版 %d）  %s'
          % (old_crlf, new_crlf, 'OK' if c3 else 'FAIL'))

    # ④ 无 BOM、无 U+FFFD（替换字符 = 中间某步编码坏了）
    c4 = (not new.startswith('\ufeff')) and ('\ufffd' not in new)
    ok &= c4
    print('  ④ 无 BOM / 无 U+FFFD  %s' % ('OK' if c4 else 'FAIL'))

    # ⑤ 语言指标必须真的变好（否则这次落地没有意义）
    lr_old, lr_new = latin_ratio(old), latin_ratio(new)
    c5 = (lr_new < lr_old - 0.05)
    ok &= c5
    print('  ⑤ 拉丁占比 %.0f%% → %.0f%%（要求至少降 5 个百分点）  %s'
          % (lr_old * 100, lr_new * 100, 'OK' if c5 else 'FAIL'))

    # ⑥ 【示例反应】段拉丁必须降到 10% 以下 —— 实测这一段是主要污染源
    def _sec(txt, head):
        i = txt.find(head)
        if i < 0:
            return None
        j = txt.find('\n---', i)
        return txt[i:j if j > 0 else len(txt)]

    so, sn = _sec(old, '【示例反应】'), _sec(new, '【示例反应】')
    if so is None or sn is None:
        print('  ⑥ 【示例反应】段找不到  FAIL')
        ok = False
    else:
        lo_, ln_ = latin_ratio(so), latin_ratio(sn)
        c6 = (ln_ < 0.10)
        ok &= c6
        print('  ⑥ 示例段 %d 字(拉丁 %.0f%%) → %d 字(拉丁 %.0f%%)  %s'
              % (len(so), lo_ * 100, len(sn), ln_ * 100, 'OK' if c6 else 'FAIL'))

    if not ok:
        print('\nFAIL: 结构守门未通过，未写盘。')
        return 3

    print()
    print('=== 写盘 ===')
    if not do_write:
        print('（dry：未写盘。加 --write 执行）')
        return 0

    tmp = dst + '.tmp'
    with io.open(tmp, 'wb') as fh:
        fh.write(new.encode('utf-8'))
    os.replace(tmp, dst)
    back = read_disk(dst)
    if back != new:
        print('FAIL: 回读与写入内容不一致')
        return 3
    print('  ✓ 已写入并回读校验：%s' % os.path.relpath(dst, ROOT))
    print('    %d 字 / %d B（原 %d 字 / %d B）'
          % (len(new), len(new.encode('utf-8')), len(old), len(old.encode('utf-8'))))

    # ---- 索引同步（只改这一条记录的 5 个字段）----
    print()
    print('=== 同步索引 `_personas.json` ===')
    got = sha_calc(back)
    old_rec = dict(rec)
    rec.update(got)
    # ★★★ 口径必须与 `personas113.py` 一致：`sections` 只数**正文**里的【xxx】，
    #   不含尾部「【本项目补充 —— 桌宠运行口径】」块（那是我们加的运行规则，不是角色设定段）。
    #   第一版我扫了全文 ⇒ 把 `hy_guardener` 的 sections 从 9 段"重算"成 10 段，
    #   等于借落地顺手改了索引口径。靠"另外 74 份 idx 全等于 body 段数"这个对照才读出来。
    _body_only = back.split(TAIL_ANCHOR)[0]
    rec['sections'] = [m.group(1).strip() for m in SEC_RE.finditer(_body_only)]
    changed = [k for k in ('chars', 'bytes', 'sha256', 'sha256_lf', 'sections')
               if old_rec.get(k) != rec.get(k)]
    print('  变更字段：%r' % (changed,))
    if not changed:
        print('  （无变化，跳过写盘）')
        return 0

    payload = json.dumps(idx, ensure_ascii=False, indent=1)
    # 原文件整份是 CRLF ⇒ 写回也必须 CRLF，否则整份文件会显示成"全部改动"
    if '\r\n' in read_disk(IDX):
        payload = payload.replace('\n', '\r\n')
    tmp2 = IDX + '.tmp'
    with io.open(tmp2, 'wb') as fh:
        fh.write(payload.encode('utf-8'))
    os.replace(tmp2, IDX)
    # 回读：必须是合法 JSON，且该记录的新值真的在
    chk = json.loads(read_disk(IDX))
    got2 = next(r for r in chk['personas'] if r['id'] == nid)
    same = all(got2.get(k) == rec.get(k) for k in ('chars', 'bytes', 'sha256', 'sha256_lf'))
    print('  ✓ 索引已写回，回读一致 = %s' % same)
    print('    chars %d ／ bytes %d ／ sections %d 段'
          % (got2['chars'], got2['bytes'], len(got2['sections'])))
    return 0 if same else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
