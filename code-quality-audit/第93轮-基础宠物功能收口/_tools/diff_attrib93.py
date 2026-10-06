# -*- coding: utf-8 -*-
"""机器核证：`regress/_out/*.diff.txt` 的差异是否**纯数字漂移**。

判据（记忆 §4「机器核证纯数字漂移」，第93轮加固）：
  把 diff **按 @@ hunk 分组**，在**每个 hunk 内部**把 `-` 行与 `+` 行按序配对；
  两侧数字全抹成 `#`（含 `0x`/`0b` 前缀与 `\d` 序列），**非数字内容必须逐字相同**。
  任一对配不上 ⇒ 打印出来 ⇒ 不是纯漂移。

★ 为什么按 hunk 分组（而不是全文件按序号）：
  全文件序号配对在「多 hunk 且各 hunk 内 -/+ 行数不等」时会**跨 hunk 错配**，
  可能出现「真差异被抹平后相等」的**假绿**。hunk 内配对把错配面收窄到单个 hunk。
  hunk 内两侧行数不等 ⇒ 直接判 [NOT-PURE] 并列出，不猜。

★ 反向自检（判据不许恒真）：脚本对每个 hunk 都会统计 `-`/`+` 行数；
  「0 对差异」的套件也会打印 `[IDENTICAL]`，不会静默报绿。

用法（cwd = 仓库根）：
  C:\\Python311\\python.exe code-quality-audit/<轮次>/_tools/diff_attrib93.py [suite ...]
不带参数 = 扫 `_out/` 下**全部** `.diff.txt`（含陈旧残留，用 mtime 自己甄别）。
"""
import io
import os
import re
import sys

OUT = os.path.join('code-quality-audit', 'regress', '_out')
NUM = re.compile(r'\d+')


def blank(s):
    """把数字序列抹成 `#`。先抹 `0x..` 整个词，再抹裸数字。"""
    s = re.sub(r'0[xX][0-9a-fA-F]+', '#', s)
    return NUM.sub('#', s)


def hunks(path):
    """返回 [[(minus_line, plus_line), ...], ...]，每个元素是一个 hunk 的配对。"""
    buf = []
    cur = None            # 当前 hunk：[minus[], plus[]]
    with io.open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        text = f.read()
    for ln in text.split('\n'):
        if ln.startswith('@@'):
            if cur is not None:
                buf.append(cur)
            cur = ([], [])
            continue
        if ln.startswith('---') or ln.startswith('+++'):
            continue
        if cur is None:
            cur = ([], [])          # 容错：文件头之外出现的裸行
        if ln.startswith('-'):
            cur[0].append(ln[1:])
        elif ln.startswith('+'):
            cur[1].append(ln[1:])
    if cur is not None:
        buf.append(cur)
    return buf


def main(names):
    bad_total = 0
    for name in names:
        p = os.path.join(OUT, name + '.diff.txt')
        if not os.path.exists(p):
            print('%-22s [SKIP] 无 diff 文件' % name)
            continue
        hs = hunks(p)
        n_minus = sum(len(a) for a, _ in hs)
        n_plus = sum(len(b) for _, b in hs)
        if n_minus == 0 and n_plus == 0:
            print('%-22s [IDENTICAL] 0 差异行' % name)
            continue
        bad = []
        shape_bad = []
        n_pairs = 0
        for idx, (mi, pl) in enumerate(hs):
            if len(mi) != len(pl):
                shape_bad.append((idx, len(mi), len(pl)))
                continue
            for a, b in zip(mi, pl):
                n_pairs += 1
                if blank(a) != blank(b):
                    bad.append((a, b))
        if shape_bad:
            bad_total += 1
            print('%-22s [NOT-PURE] %d 个 hunk 两侧行数不等：' % (name, len(shape_bad)))
            for idx, a, b in shape_bad[:8]:
                print('        hunk#%d  -%d / +%d' % (idx, a, b))
        if bad:
            bad_total += 1
            print('%-22s [NOT-PURE] %d/%d 对非纯数字差异：' % (name, len(bad), n_pairs))
            for a, b in bad[:12]:
                print('        - %s' % a)
                print('        + %s' % b)
        if not bad and not shape_bad:
            print('%-22s [纯数字漂移] %d 对，抹掉数字后逐字相同（- %d / + %d 行）'
                  % (name, n_pairs, n_minus, n_plus))
    print('-' * 64)
    print('非纯数字漂移的套件数 =', bad_total)
    return 1 if bad_total else 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = sorted(f[:-9] for f in os.listdir(OUT) if f.endswith('.diff.txt'))
    sys.exit(main(args))
