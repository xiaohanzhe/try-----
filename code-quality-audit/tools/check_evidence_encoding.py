# -*- coding: utf-8 -*-
"""证据文件编码校验器 —— 防止"报告链接过去的证据打开是乱码"。

为什么需要它（第十三轮的真实翻车）
----------------------------------
我用 PowerShell 的 `*>` / `Out-File` 去捕获 Python 脚本的 stdout 存成证据文件，
结果中文全部变成 `閲忕翰鑷` 这类"不是字"的东西，还被提交推送进了仓库。

根因：**PowerShell 捕获原生程序的 stdout 时，会把字节按控制台代码页（本机 GBK）解码，
再把解码后的字符串按 UTF-8 重写** —— 于是 UTF-8 字节被二次编码。这不是"显示问题"，
文件内容本身已经坏了。也就是说：

    ✅ Python 自己 `open(path, 'w', encoding='utf-8')` 写出来的文件是干净的  ← 唯一正确姿势
    ❌ `& python x.py *> out.txt` / `... | Out-File -Encoding utf8` 捕获的是坏的
    ✅ `Copy-Item` 是逐字节复制，不经编码转换，可以安全搬运上面那种干净文件

四种坏法，分两级报（本脚本都检）：
  **确定性损坏（→ 退出码非 0，必须修）**
  1. **不是合法 UTF-8** —— 直接解不出来（含 UTF-16 被误存成 .txt 的情形）；
  2. **含替换字符 U+FFFD** —— 解码时丢过字节。
  **告警（→ 只提示，需人看一眼）**
  3. **带 BOM** —— 必须在 UTF-8 解码前判，否则 BOM 会被当成内容（`git log` 里显示成 `锘`）；
  4. **中文疑似乱码**（本次翻车的那种）—— 用**特征字绊线**识别，**会误报**，见 MOJIBAKE_MARKERS。
     为什么不用"精确判据"：PowerShell 那次 GBK 解码是**有损**的，GBK 编不回原字节，
     于是经典的 `text.encode('gbk').decode('utf-8')` 往返判据对真实样本**直接抛异常 → 永不触发**
     （本脚本第一版就栽在这，扫真实坏文件报"全部干净"）。绊线的立场是：零误报地圈出可疑，
     由**重跑生成源**来定性修复 —— 绝不靠猜字符去还原（那等于伪造证据）。

用法：
    python check_evidence_encoding.py                     # 扫 code-quality-audit/ 下全部文件
    python check_evidence_encoding.py <路径> [路径…]        # 扫指定文件/目录
    python check_evidence_encoding.py --out report.txt     # 报告交给 Python 自己写（正确姿势）
退出码：0 = 无确定性损坏；1 = 有确定性损坏（--strict 时，告警也算失败）。
"""
import argparse
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUDIT_ROOT = os.path.abspath(os.path.join(HERE, '..'))

BOM_UTF8 = b'\xef\xbb\xbf'
# 只检查这些后缀，避免去读二进制素材（png/zip/db 等）
TEXT_EXT = {'.txt', '.md', '.py', '.json', '.log', '.diff', '.csv', '.tsv', '.yaml', '.yml'}
SKIP_DIRS = {'__pycache__', '_recon', '.git'}

# "UTF-8 中文被按 GBK 解码"必然会吐出的一批字。它们在正常中文里几乎不出现，
# 却是这类乱码的高频组成（例：量纲自检 → 閲忕翰鑷、回归基线 → 鍥炲綊鍩虹嚎、
# 第九轮 → 绗節杞、显示 → 鏄剧ず）。出现 **≥2 个不同**的字即判乱码。
#
# ⚠ 这是**绊线，不是证明**。为什么不能做精确判定：PowerShell 那次解码是**有损**的
# （GBK 编不回原字节），所以经典的 "encode('gbk').decode('utf-8') 往返判据" 对它**失效**
# （本脚本第一版就写了往返判据，实测对真实样本直接抛 UnicodeDecodeError → 永不触发）。
# 绊线的价值在于零误报 + 覆盖真实故障；精确修复必须靠"重跑生成源"，不靠猜。
MOJIBAKE_MARKERS = set('锛銆鈥閲鑷鏌ワ紙鍥绗鏄剧ず鑳芥鍙屓鎴鍚鐢鏂鏈')
MOJIBAKE_MIN_HITS = 2

# 本工具自己产出的报告一律用 `_out_` 前缀命名（见 iter_files 说明），扫描时跳过。
TOOL_OUT_PREFIX = '_out_'
# main() 会把 `--out` 的绝对路径塞进来，确保那次运行不回扫自己的报告。
EXTRA_SKIP = set()


def _is_tool_out(path):
    return os.path.basename(path).startswith(TOOL_OUT_PREFIX)


def count_mojibake_markers(text):
    """数出绊线特征字的 {字: 次数}。

    刻意**不用** "encode('gbk').decode('utf-8')" 往返判据 —— 实测对真实样本失效
    （PowerShell 那次解码是有损的，GBK 编不回原字节，往返直接抛异常 → 永不触发）。
    绊线只报"疑似 + 命中数"，由人判断；真正的判定靠重跑生成源，不靠猜。
    """
    hits = {}
    for ch in text:
        if ch in MOJIBAKE_MARKERS:
            hits[ch] = hits.get(ch, 0) + 1
    return hits


def inspect(path):
    """返回 (fails, warns) 两个列表。

    fails = **确定性损坏**：不是合法 UTF-8 / 含 U+FFFD（丢过字节）。→ 让退出码非 0。
    warns = **需要人看一眼**：带 BOM（违反本项目"无 BOM"约定，但内容可读）；
            疑似乱码（绊线判据 —— **会误报**，见下）。
    """
    fails, warns = [], []
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except Exception as e:
        return ['读不出来: %s' % e], []

    if raw.startswith(BOM_UTF8):
        warns.append('带 UTF-8 BOM（内容可读，但不合本项目约定；`git log` 里会显示成 `锘`）')

    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        fails.append('不是合法 UTF-8（%s）' % e)
        return fails, warns

    if '\ufffd' in text:
        fails.append('含替换字符 U+FFFD（解码时丢过字节）')

    # 剥掉 BOM 再扫绊线（BOM 不在特征字集合里，剥掉只是更干净）。
    probe = text.lstrip('\ufeff')
    hits = count_mojibake_markers(probe)
    if len(hits) >= MOJIBAKE_MIN_HITS:
        total = sum(hits.values())
        warns.append('中文疑似乱码（绊线判据，需人工确认）：命中 %d 个不同特征字 / 共 %d 处'
                     % (len(hits), total))
    return fails, warns


def _printable(s):
    """把不可打印字符换成 '·'。

    必要性：UTF-16 文件被按 UTF-8 + errors='replace' 读出来时，行内会夹着 U+0000
    （NUL）。把这个预览原样写进报告，报告自己就变成"含 NUL 的二进制文件"，
    连查看器都会拒读（本脚本实测踩过）。
    """
    return ''.join(ch if ch >= ' ' or ch == '\t' else '·' for ch in s)


def iter_files(roots):
    # 跳过脚本自己：它的源码里必然含有 MOJIBAKE_MARKERS 和乱码示例（否则判据没法写），
    # 扫自己必定命中。这不是漏检，是自指。
    #
    # 同理跳过本工具自己的输出（`_out_*`）：报告里会引用乱码样本当例子，被自己重扫必然误报。
    # 这类"引用了坏样本的干净文件"是本判据的固有误报面，用约定前缀把它挡掉。
    self_path = os.path.abspath(__file__)
    skip_abs = {self_path} | EXTRA_SKIP
    for root in roots:
        if os.path.isfile(root):
            if os.path.abspath(root) not in skip_abs and not _is_tool_out(root):
                yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in sorted(filenames):
                if os.path.splitext(name)[1].lower() not in TEXT_EXT:
                    continue
                path = os.path.join(dirpath, name)
                if os.path.abspath(path) in skip_abs or _is_tool_out(path):
                    continue
                yield path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='*', help='要检查的文件/目录（默认 code-quality-audit/）')
    ap.add_argument('--out', metavar='FILE',
                    help='把报告写成 UTF-8 文件（**有这个选项是因为**：用 PowerShell 的 `>` 捕获本脚本'
                         'stdout 会把中文同样搞成乱码 —— 本工具自己就得示范正确姿势）')
    ap.add_argument('--strict', action='store_true',
                    help='把告警（BOM / 疑似乱码）也算失败，退出码非 0')
    ap.add_argument('--quiet', action='store_true', help='不往 stdout 打印，只写 --out')
    args = ap.parse_args()
    roots = args.paths or [AUDIT_ROOT]
    if args.out:
        # 别让本次报告被本次扫描读到（报告里含乱码样本预览，会自我误报）。
        EXTRA_SKIP.add(os.path.abspath(args.out))

    checked, failed, warned = 0, [], []
    for path in iter_files(roots):
        checked += 1
        fails, warns = inspect(path)
        if fails:
            failed.append((path, fails))
        if warns:
            warned.append((path, warns))

    lines = ['=' * 68,
             '证据编码校验：检查 %d 个文本文件｜确定性损坏 %d 个｜告警 %d 个'
             % (checked, len(failed), len(warned)),
             '=' * 68]

    def dump(title, items, mark):
        if not items:
            return
        lines.append('')
        lines.append('【%s】' % title)
        for path, problems in items:
            lines.append('%s %s' % (mark, os.path.relpath(path, os.path.dirname(AUDIT_ROOT))))
            for p in problems:
                lines.append('    - %s' % p)
            try:
                with open(path, encoding='utf-8', errors='replace') as fh:
                    first = fh.readline().rstrip('\n')
                lines.append('    首行: %s' % _printable(first)[:70])
            except Exception:
                pass

    if not failed and not warned:
        lines.append('全部干净。')
    else:
        dump('确定性损坏（必须修）', failed, '✗')
        dump('告警（需人工看一眼；绊线判据会有误报 —— 例如文件本身在引用乱码示例）',
             warned, '!')
        lines.append('')
        lines.append('修法：证据文件一律让 **Python 自己** `open(path,"w",encoding="utf-8")` 写；')
        lines.append('      不要用 PowerShell 的 `*>` / `Out-File` 去捕获原生程序 stdout。')

    text = '\n'.join(lines) + '\n'
    if args.out:
        with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    if not args.quiet:
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except Exception:
            pass
    if failed:
        return 1
    if args.strict and warned:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
