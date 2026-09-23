import subprocess, os, sys, shutil, hashlib, time, json

EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
GAME = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\DELTARUNE_183049\DELTARUNE'
OUTROOT = r'E:\Download\_tmp\dr_out'
WORK = r'E:\Download\_tmp\drw'
SCRIPT = r'E:\Download\_tmp\dump_rooms.csx'
LOG = r'E:\Download\_tmp\batch_all.log'

CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']

log = open(LOG, 'w', encoding='utf-8')


def w(s):
    print(s)
    log.write(s + '\n')
    log.flush()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(tag, args):
    t0 = time.time()
    p = subprocess.Popen([EXE] + args, cwd=CWD, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    n = 0
    for line in p.stdout:
        n += 1
        if n % 500 == 0:
            log.write('   [%s] %d lines...\n' % (tag, n))
            log.flush()
    p.wait()
    return p.returncode, time.time() - t0


results = {}
for ch in CHS:
    w('=' * 70)
    w('CHAPTER %s' % ch)
    src = os.path.join(GAME, ch, 'data.win')
    if not os.path.exists(src):
        w('  MISSING: %s' % src)
        continue
    before = sha(src)
    w('  orig size=%d sha=%s' % (os.path.getsize(src), before[:16]))

    outdir = os.path.join(OUTROOT, ch)
    os.makedirs(outdir, exist_ok=True)

    # 1) dump 纹理 + 精灵
    rc, el = run('dump', ['dump', src, '-t', '--sprites', '-o', outdir, '-v'])
    w('  [dump]  rc=%d %.1fs' % (rc, el))

    # 2) 房间结构（在副本上跑，绝不动原文件）
    wdir = os.path.join(WORK, ch)
    os.makedirs(wdir, exist_ok=True)
    dst = os.path.join(wdir, 'data.win')
    if (not os.path.exists(dst)) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copyfile(src, dst)
    sdir = os.path.join(wdir, 'scripts')
    os.makedirs(sdir, exist_ok=True)
    sdst = os.path.join(sdir, 'dump_rooms.csx')
    shutil.copyfile(SCRIPT, sdst)
    rc2, el2 = run('rooms', ['load', dst, '-s', sdst])
    w('  [rooms] rc=%d %.1fs' % (rc2, el2))

    after = sha(src)
    w('  orig sha unchanged: %s' % (before == after))

    rm = os.path.join(wdir, 'rooms_map.json')
    if os.path.exists(rm):
        shutil.copyfile(rm, os.path.join(outdir, 'rooms_map.json'))
        w('  rooms_map.json %d bytes' % os.path.getsize(rm))
        try:
            d = json.load(open(rm, encoding='utf-8'))
            w('  rooms in map: %d' % len(d.get('rooms', [])))
        except Exception as e:
            w('  rooms_map parse fail: %s' % e)

    n_spr = len(os.listdir(os.path.join(outdir, 'Sprites'))) if os.path.isdir(os.path.join(outdir, 'Sprites')) else 0
    n_tex = len(os.listdir(os.path.join(outdir, 'EmbeddedTextures'))) if os.path.isdir(os.path.join(outdir, 'EmbeddedTextures')) else 0
    w('  sprites=%d textures=%d' % (n_spr, n_tex))
    results[ch] = dict(rc_dump=rc, rc_rooms=rc2, sprites=n_spr, textures=n_tex,
                       orig_untouched=(before == after))

w('=' * 70)
w('SUMMARY')
w(json.dumps(results, indent=2, ensure_ascii=False))
log.close()
print('BATCH DONE ->', LOG)
