# -*- coding: utf-8 -*-
"""第193轮：E 盘记忆目录只读探测（不写 E 盘、不删任何东西）。

只做四件事：
  1) 逐层 os.walk，把**每一层**的读取异常单独记下来（E 盘坏点会让 listdir 抛 OSError）
  2) 对每个文件：读全部字节 → 记长度 / sha1 / 头 4 字节 / 是否合法 JSON
  3) 判定 USBC 污染（头 4 字节 == b'USBC'）与读失败（OSError）
  4) 产物写 D:\_tmp\，不动 E 盘

用法：C:\Python311\python.exe D:\_tmp\probe_e193.py
"""
import hashlib
import io
import json
import os
import sys

SRC = r'E:\RalseiMemory'
OUT = r'D:\_tmp\e193_probe.txt'

lines = []


def say(s=''):
    lines.append(str(s))
    print(s)


def walk(root):
    """自己递归，逐层兜异常（shutil/os.walk 默认会把错误吞掉或整体抛）。"""
    stack = [(root, '')]
    dirs_err = []
    files = []
    while stack:
        absd, reld = stack.pop()
        try:
            names = os.listdir(absd)
        except OSError as e:
            dirs_err.append((reld or '.', repr(e)))
            continue
        for n in names:
            ap = os.path.join(absd, n)
            rp = os.path.join(reld, n) if reld else n
            try:
                isdir = os.path.isdir(ap)
            except OSError as e:
                dirs_err.append((rp, repr(e)))
                continue
            if isdir:
                stack.append((ap, rp))
            else:
                files.append((ap, rp))
    return files, dirs_err


def probe(ap):
    try:
        with io.open(ap, 'rb') as fh:
            data = fh.read()
    except OSError as e:
        return {'read': False, 'err': repr(e)}
    info = {
        'read': True,
        'bytes': len(data),
        'sha1': hashlib.sha1(data).hexdigest()[:12],
        'head': data[:4].hex(),
        'usbc': data[:4] == b'USBC',
        'json': None,
    }
    if ap.lower().endswith('.json') and data:
        try:
            json.loads(data.decode('utf-8', 'replace'))
            info['json'] = True
        except Exception:                                             # noqa: BLE001
            info['json'] = False
    return info


def main():
    if not os.path.isdir(SRC):
        say('!! 源目录不存在：%s' % SRC)
        return 2
    say('=== E 盘记忆目录只读探测 ===')
    say('源 = %s' % SRC)
    try:
        top = os.listdir(SRC)
        say('根目录 listdir 成功，条目数 = %d' % len(top))
    except OSError as e:
        say('!! 根目录 listdir 失败：%r' % (e,))
        top = []

    files, dirs_err = walk(SRC)
    say('')
    say('--- 目录读取失败 %d 处 ---' % len(dirs_err))
    for rp, e in dirs_err:
        say('  [DIRERR] %s  %s' % (rp, e))

    say('')
    say('--- 文件明细 %d 个 ---' % len(files))
    stat = {'ok': 0, 'usbc': 0, 'fail': 0, 'json_bad': 0}
    total = 0
    rows = []
    for ap, rp in sorted(files, key=lambda x: x[1]):
        inf = probe(ap)
        if not inf.get('read'):
            stat['fail'] += 1
            rows.append('  [READFAIL] %-52s %s' % (rp, inf.get('err')))
            continue
        total += inf['bytes']
        if inf['usbc']:
            stat['usbc'] += 1
            tag = 'USBC-污染'
        else:
            stat['ok'] += 1
            tag = '正常'
        if inf['json'] is False:
            stat['json_bad'] += 1
            tag += '/JSON坏'
        rows.append('  [%-10s] %-52s %8d B  %s  head=%s'
                    % (tag, rp, inf['bytes'], inf['sha1'], inf['head']))
    for r in rows:
        say(r)

    say('')
    say('--- 汇总 ---')
    say('可读且未污染 = %d' % stat['ok'])
    say('USBC 污染     = %d' % stat['usbc'])
    say('读失败        = %d' % stat['fail'])
    say('JSON 解析失败 = %d' % stat['json_bad'])
    say('可读总字节    = %d' % total)
    say('目录失败      = %d' % len(dirs_err))
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(lines) + '\n')
        say('')
        say('报告已写：%s' % OUT)
    except Exception as e:                                            # noqa: BLE001
        say('!! 报告落盘失败：%r' % (e,))
    return 0 if (stat['fail'] == 0 and not dirs_err) else 1


if __name__ == '__main__':
    sys.exit(main())
