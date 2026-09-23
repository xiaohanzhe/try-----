# -*- coding: utf-8 -*-
"""第37轮遗留收尾：用修正版 dump_rooms.csx 重跑 chapter1 的 rooms_map.json。

只读动作：
  - 在**副本** E:\Download\_tmp\drw\chapter1_windows\data.win 上跑 load（不带 -o ⇒ 不落盘）
  - 原始游戏目录的 data.win 完全不碰
  - 跑完把新 rooms_map.json 拷回 _evidence 同级产物目录
自检：跑前/跑后都对副本做 sha256，必须一致。
"""
import subprocess, os, shutil, time, json, io, hashlib, sys

EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
W = r'E:\Download\_tmp\drw\chapter1_windows'
SCRIPT = r'E:\Download\_tmp\dump_rooms.csx'
OUT = r'E:\Download\_tmp\dr_out\chapter1_windows\rooms_map.json'
RESULT = r'E:\Download\_tmp\rerun_ch1_rooms.txt'

lines = []


def w(s):
    lines.append(str(s))
    print(s)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def stats(path):
    d = json.load(io.open(path, encoding='utf-8'))
    rooms = d.get('rooms', [])
    tot = bad = 0
    for r in rooms:
        for l in (r.get('layers') or []):
            v = l.get('bg_sprite')
            if v:
                tot += 1
                if v == 'UndertaleSprite':
                    bad += 1
    names = sorted(set(l.get('bg_sprite') for r in rooms
                       for l in (r.get('layers') or []) if l.get('bg_sprite')))
    return len(rooms), tot, bad, names


try:
    wm = os.path.join(W, 'data.win')
    rm = os.path.join(W, 'rooms_map.json')
    w('work copy = %s' % wm)
    w('exists: win=%s rooms_map=%s' % (os.path.exists(wm), os.path.exists(rm)))
    if not os.path.exists(rm):
        w('!! no pre-existing rooms_map.json to compare; abort')
        raise SystemExit(1)

    n0, t0, b0, nm0 = stats(rm)
    w('BEFORE  rooms=%d  bg_sprite_layers=%d  bad(UndertaleSprite)=%d' % (n0, t0, b0))
    w('BEFORE  sample names = %s' % nm0[:12])

    before = sha(wm)

    sdir = os.path.join(W, 'scripts')
    os.makedirs(sdir, exist_ok=True)
    sdst = os.path.join(sdir, 'dump_rooms.csx')
    shutil.copyfile(SCRIPT, sdst)
    w('csx copied, has ResolveName fix = %s' % ('ResolveName' in io.open(sdst, encoding='utf-8').read()))

    t = time.time()
    p = subprocess.Popen([EXE, 'load', wm, '-s', sdst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    nline = 0
    for _ in p.stdout:
        nline += 1
    p.wait()
    w('[rooms] rc=%d  %.1fs  stdout_lines=%d' % (p.returncode, time.time() - t, nline))

    after = sha(wm)
    w('work copy sha unchanged: %s' % (before == after))

    n1, t1, b1, nm1 = stats(rm)
    w('AFTER   rooms=%d  bg_sprite_layers=%d  bad(UndertaleSprite)=%d' % (n1, t1, b1))
    w('AFTER   distinct names = %d' % len(nm1))
    w('AFTER   names = %s' % nm1)

    verdict = (b1 == 0 and t1 > 0 and n1 == n0)
    w('VERDICT bug_fixed=%s  (bad 0->%d, layers %d->%d, rooms %d->%d)'
      % (verdict, b1, t0, t1, n0, n1))

    if os.path.exists(OUT):
        shutil.copyfile(OUT, OUT + '.bak_before_rerun')
        w('backed up old evidence -> %s.bak_before_rerun' % OUT)
    shutil.copyfile(rm, OUT)
    w('copied -> %s (%d bytes)' % (OUT, os.path.getsize(OUT)))
except Exception:
    import traceback
    w('EXCEPTION:\n' + traceback.format_exc())
finally:
    io.open(RESULT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('LOG ->', RESULT)
