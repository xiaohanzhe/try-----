# -*- coding: utf-8 -*-
"""谁占着 E:\\RalseiMemory 里的文件？

线索：
  · `logs\\ralsei_pet.log` 可读、**不可追加**（ro=False 属性正常）⇒ 疑似被独占打开
  · `logs\\` 里 13 个同尺寸 `ralsei_pet.log.old.<ts>` ⇒ 轮转改名反复发生
  · 产品自己日志初始化就失败（Errno 13）⇒ **不是产品自己在持有**
  · 产品 `os.replace` 到 config.json / memory.json 一律 WinError 5
⇒ 假设：另有进程长期持握这些文件。本脚本枚举进程与句柄做定位。
"""
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psutil

VAULT = 'ralseimemory'      # 小写比较
TARGETS = ['ralsei_pet.log', 'config.json', 'memory.json', 'jieba.cache']


def cmd_of(p):
    try:
        return ' '.join(p.info.get('cmdline') or [])
    except Exception:
        return '<无法读取>'


def main():
    me = os.getpid()
    print('本进程 pid =', me)
    print('\n=== 全部 python 进程 ===')
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
        try:
            nm = (p.info.get('name') or '').lower()
            ex = (p.info.get('exe') or '').lower()
            if 'python' in nm or 'python' in ex:
                procs.append(p)
        except Exception:
            continue
    print('共 %d 个' % len(procs))
    for p in sorted(procs, key=lambda q: q.info['create_time']):
        try:
            ct = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.info['create_time']))
        except Exception:
            ct = '?'
        age = time.time() - p.info['create_time']
        print('\n  pid=%-7s up=%-9s %s' % (p.info['pid'], '%.0fs' % age, ct))
        print('     exe=%s' % (p.info.get('exe') or ''))
        print('     cmd=%s' % cmd_of(p)[:220])
        try:
            ofs = p.open_files()
        except Exception as e:
            print('     open_files 不可用: %s' % type(e).__name__)
            ofs = []
        hit = [f.path for f in ofs if VAULT in f.path.lower()]
        if hit:
            print('     ★ 持有 vault 文件:')
            for h in hit:
                print('        ', h)
        else:
            print('     （未发现 vault 句柄；open_files 跨进程可能受限，仅供参考）')

    print('\n=== 全局：所有进程里扫 vault 句柄（可能较慢）===')
    found = []
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['pid'] == me:
            continue
        try:
            for f in p.open_files():
                if VAULT in f.path.lower():
                    found.append((p.info['pid'], p.info['name'], f.path))
        except Exception:
            continue
    if found:
        for f in found:
            print('   ★', f)
    else:
        print('   无（或受权限限制查不到）')

    print('\n=== 探测：这些文件能否独占打开 ===')
    for rel in TARGETS:
        fp = os.path.join(r'E:\RalseiMemory', rel)
        if 'logs' in rel:
            fp = os.path.join(r'E:\RalseiMemory\logs', rel)
        if not os.path.exists(fp):
            print('  %-22s 不存在' % rel); continue
        res = []
        for mode in ('r', 'a'):
            try:
                f = open(fp, mode, encoding='utf-8', errors='replace')
                f.close()
                res.append('%s:OK' % mode)
            except Exception as e:
                res.append('%s:%s' % (mode, type(e).__name__))
        print('  %-22s %s' % (rel, '  '.join(res)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
