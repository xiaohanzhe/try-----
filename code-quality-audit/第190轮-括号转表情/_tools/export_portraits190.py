# -*- coding: utf-8 -*-
u"""第190轮 · 导出 UTY 的**对话肖像**（spr_portrait_*），复用第71轮已验证的抽图脚本。

为什么只导这批
--------------
`survey190.py` 从游戏包名单里查出：黄魂（UTY）有 **124 条 `spr_portrait_<角色>_<情绪>`**，
覆盖 12 个角色（ceroba 28 / starlo 22 / kanako 11 / asgore 10 / axis 9 / mooch 8 /
chujin 8 / moray 6 / ace 6 / ed 4 ...）。**名字里直接带情绪词**，这是全场最好用的一批素材。
而 E 盘的解包料里**没有**它们（`/e/Download/_tmp/r71_work/hy` 只有 164 张 overworld 帧）。

复用 `第71轮-电梯与跨作品贴图/_tools/dump_spr71.csx`（`TextureWorker.ExportAsPNG`），
**不新写导出逻辑** —— 那段已经过"提取正确"复核，重写只会多一个失败面。

用法
----
    python export_portraits190.py --tag hy --prefix spr_portrait_
    python export_portraits190.py --tag hy --prefix spr_portrait_ --dry   # 只列清单
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
TSV = os.path.join(EV, 'sprites')
import utmtpath190
EXE = utmtpath190.require()  # 优先 D 盘副本，E 盘坏点会 FailFast
CSX = os.path.join(REPO, 'code-quality-audit', u'第71轮-电梯与跨作品贴图', '_tools',
                   'dump_spr71.csx')
PKG = {
    'hy': u'D:/_wb_tmp/dw_ut/uty/game.droid',
    'ot': u'D:/_wb_tmp/dw_ut/outertale/game.droid',
    'ut': u'D:/_wb_tmp/dw_ut/ut/game.droid',
}
WORK = u'D:/_tmp190'


def main():
    argv = sys.argv[1:]
    tag = argv[argv.index('--tag') + 1] if '--tag' in argv else 'hy'
    prefix = argv[argv.index('--prefix') + 1] if '--prefix' in argv else 'spr_portrait_'
    dry = '--dry' in argv

    tsv = os.path.join(TSV, tag + '.tsv')
    if not os.path.isfile(tsv):
        print('[停手] 缺名单：%s（先跑 utmt190.py）' % tsv)
        return 2
    names = []
    for line in io.open(tsv, encoding='utf-8', errors='replace'):
        if line.startswith('#'):
            continue
        p = line.rstrip('\n').split('\t')
        if p and p[0].startswith(prefix):
            names.append(p[0])
    print('[清单] %s 里 %s* 共 %d 条' % (os.path.basename(tsv), prefix, len(names)))
    for n in names[:5]:
        print('   ', n)
    if dry or not names:
        return 0 if names else 3

    outdir = os.path.join(WORK, tag + '_portraits')
    if os.path.isdir(outdir):
        shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    lst = os.path.join(WORK, tag + '_portraits.txt')
    with io.open(lst, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(names) + '\n')

    env = dict(os.environ)
    env['R71_LIST'] = lst
    env['R71_OUT'] = outdir.replace('/', '\\')
    # ★★ csx 必须放在**纯 ASCII 路径**下：直接把仓库里的中文路径交给 UTMT 会当场
    #    FailFast 崩掉（rc=3221225478 = 0xC0000602），而且不打印任何理由。
    csx_work = os.path.join(WORK, 'dump_spr71.csx')
    shutil.copyfile(CSX, csx_work)
    log = os.path.join(WORK, '%s_export.log' % tag)
    cmd = [EXE, 'load', PKG[tag], '-s', csx_work]
    print('[run] %s' % ' '.join(cmd))
    with io.open(log, 'wb') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=env)
        rc = p.wait()
    print('[rc] %s' % rc)
    txt = io.open(log, 'r', encoding='utf-8', errors='replace').read()
    tail = [l for l in txt.splitlines() if 'dump71' in l or 'ERROR' in l]
    print('\n'.join(tail[-6:]))

    pngs = sorted(f for f in os.listdir(outdir) if f.endswith('.png'))
    print('[产物] %d 张 png → %s' % (len(pngs), outdir))
    man = os.path.join(outdir, 'r71_sprites.json')
    if os.path.isfile(man):
        dst = os.path.join(EV, 'portraits_%s.json' % tag)
        shutil.copyfile(man, dst)
        print('[清单] → %s' % dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
