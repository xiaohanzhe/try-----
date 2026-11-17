# -*- coding: utf-8 -*-
r"""第193轮：E:\RalseiMemory → D:\RalseiMemory 只增不删迁移。

安全约定（逐条对应项目铁律）：
  · **不删源**：E 盘一个文件都不动、不删、不改名。
  · **不覆盖好的**：目标已存在且内容一致 ⇒ 跳过（幂等，同一条命令跑两次结果相同）。
  · **坏件不搬家**：头 4 字节 == b'USBC' 的一律进 `_corrupt_archive\<原相对路径>`，
    保持原样留档，绝不混进正常目录。
  · **逐文件 sha1 读回校验**：写完必须重新读一遍比对，不靠"copy 返回成功"。
  · **主记忆单独裁决**：E 盘 memory.json 已污染 ⇒ 用桌面兜底那份（sha1 6e6c25146e87）
    覆盖为新的 memory.json，污染件进归档。
  · 不改环境变量（那是单独一步，便于回退）。

用法：C:\Python311\python.exe D:\_tmp\migrate193.py
"""
import hashlib
import io
import json
import os
import shutil
import sys

SRC = r'E:\RalseiMemory'
DST = r'D:\RalseiMemory'
ARCH = os.path.join(DST, '_corrupt_archive')
FALLBACK = r'C:\Users\23002\Desktop\memory\memory.json'
MAIN_SHA1 = '6e6c25146e87'
OUT_JSON = r'D:\_tmp\e193_migrate.json'
OUT_TXT = r'D:\_tmp\e193_migrate.txt'

log = []
report = {'copied': [], 'same': [], 'archived': [], 'failed': [],
          'main_memory': None, 'bytes': 0}


def say(s=''):
    log.append(str(s))
    print(s)


def sha(b):
    return hashlib.sha1(b).hexdigest()


def read_bytes(p):
    try:
        with io.open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def write_bytes(p, data):
    """写 + 读回校验；返回读回的 sha1。"""
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(p, 'wb') as fh:
        fh.write(data)
    back = read_bytes(p)
    return sha(back) if back is not None else None


def walk(root):
    stack = [(root, '')]
    files, errs = [], []
    while stack:
        absd, reld = stack.pop()
        try:
            names = os.listdir(absd)
        except OSError as e:
            errs.append((reld or '.', repr(e)))
            continue
        for n in names:
            ap = os.path.join(absd, n)
            rp = os.path.join(reld, n) if reld else n
            try:
                if os.path.isdir(ap):
                    stack.append((ap, rp))
                else:
                    files.append((ap, rp))
            except OSError as e:
                errs.append((rp, repr(e)))
    return files, errs


def put(target, data, rel, bucket, tag):
    """写入 target；目标已一致 ⇒ same（幂等）。"""
    cur = read_bytes(target) if os.path.exists(target) else None
    if cur is not None and sha(cur) == sha(data):
        report['same'].append(rel)
        return 'same'
    if cur is not None:
        # 目标有不同内容：先把旧件留档，不静默覆盖
        prev = target + '.prev-' + sha(cur)[:8]
        if not os.path.exists(prev):
            os.makedirs(os.path.dirname(prev), exist_ok=True)
            shutil.copy2(target, prev)
        say('    [覆盖] %s 旧件留档 %s' % (rel, os.path.basename(prev)))
    got = write_bytes(target, data)
    if got != sha(data):
        report['failed'].append(rel + ' (读回 sha1 不符: %s)' % got)
        say('    [!!] %s 读回校验失败' % rel)
        return 'fail'
    report[bucket].append(rel)
    report['bytes'] += len(data)
    say('    [%s] %-44s %8d B  %s' % (tag, rel, len(data), sha(data)[:12]))
    return 'ok'


def main():
    say('=== 迁 D 盘（只增不删）===')
    say('源 = %s' % SRC)
    say('目标 = %s' % DST)
    if not os.path.isdir(SRC):
        say('!! 源不存在，终止')
        return 2
    os.makedirs(DST, exist_ok=True)
    os.makedirs(ARCH, exist_ok=True)

    files, errs = walk(SRC)
    say('枚举到 %d 个文件，目录异常 %d 处' % (len(files), len(errs)))
    for rp, e in errs:
        say('  [DIRERR] %s %s' % (rp, e))

    say('')
    say('--- 逐文件处理 ---')
    for ap, rp in sorted(files, key=lambda x: x[1]):
        data = read_bytes(ap)
        if data is None:
            report['failed'].append(rp + ' (读源失败)')
            say('    [READFAIL] %s' % rp)
            continue
        if data[:4] == b'USBC':
            put(os.path.join(ARCH, rp), data, rp, 'archived', '归档污染')
        else:
            put(os.path.join(DST, rp), data, rp, 'copied', '复制')

    # ---- 主记忆：E 盘那份已污染，改用桌面兜底 ----
    say('')
    say('--- 主记忆裁决 ---')
    fb = read_bytes(FALLBACK)
    if fb is None:
        say('!! 桌面兜底读不到 ⇒ 不写 memory.json（保留现状，等人定）')
        report['main_memory'] = {'ok': False, 'why': '兜底读不到'}
    else:
        h = sha(fb)
        if h[:12] != MAIN_SHA1:
            say('!! 桌面兜底 sha1=%s，与预期 %s 不符 ⇒ 不写' % (h[:12], MAIN_SHA1))
            report['main_memory'] = {'ok': False, 'why': 'sha1 不符', 'sha1': h[:12]}
        else:
            try:
                j = json.loads(fb.decode('utf-8', 'replace'))
                info = {'ok': True, 'src': FALLBACK, 'sha1': h[:12],
                        'bytes': len(fb), 'saved_at': j.get('saved_at'),
                        'fragments': len(j.get('fragments') or []),
                        'assoc': len(j.get('assoc') or [])}
            except Exception as e:                                    # noqa: BLE001
                info = {'ok': False, 'why': 'JSON %r' % (e,)}
            say('    兜底 JSON 校验：%s' % ('通过' if info.get('ok') else '失败'))
            if info.get('ok'):
                say('    saved_at=%s fragments=%s assoc=%s'
                    % (info.get('saved_at'), info.get('fragments'),
                       info.get('assoc')))
                put(os.path.join(DST, 'memory.json'), fb, 'memory.json',
                    'copied', '主记忆')
                report['main_memory'] = info

    # ---- 汇总 ----
    say('')
    say('--- 汇总 ---')
    say('复制成功 = %d' % len(report['copied']))
    say('已一致跳过 = %d' % len(report['same']))
    say('污染归档 = %d' % len(report['archived']))
    say('失败 = %d' % len(report['failed']))
    say('本轮写入字节 = %d' % report['bytes'])
    for f in report['failed']:
        say('  [FAIL] %s' % f)
    ok_empty = (not report['failed']) and (not errs)
    say('')
    say('=== 判定 = %s ===' % ('OK' if ok_empty else 'HAS_PROBLEM'))

    try:
        with io.open(OUT_JSON, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=2))
        with io.open(OUT_TXT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(log) + '\n')
        say('清单：%s' % OUT_JSON)
    except Exception as e:                                            # noqa: BLE001
        say('!! 清单落盘失败 %r' % (e,))
    return 0 if ok_empty else 1


if __name__ == '__main__':
    sys.exit(main())
