# -*- coding: utf-8 -*-
"""第71轮 · UTMT 定向导出的最小驱动（冒烟用）。

★ 铁律（第61轮实测）：UTMT CLI 的 stdout 必须是**文件**，PIPE 会崩/挂。
"""
import io
import os
import subprocess
import sys
import tempfile
import time

EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
HOME = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第71轮-电梯与跨作品贴图'
CSX = os.path.join(HOME, '_tools', 'dump_spr71.csx')


def run(data, names, outdir, listfile=None, tag='smoke'):
    os.makedirs(outdir, exist_ok=True)
    listfile = listfile or os.path.join(tempfile.gettempdir(), 'r71_list_%s.txt' % tag)
    with io.open(listfile, 'w', encoding='utf-8') as fh:
        fh.write(u'\n'.join(names) + u'\n')
    log = os.path.join(tempfile.gettempdir(), 'r71_%s.log' % tag)
    env = dict(os.environ)
    env['R71_LIST'] = listfile
    env['R71_OUT'] = outdir
    cmd = [EXE, 'load', data, '-s', CSX]
    print('>>> %s' % ' '.join(cmd))
    t0 = time.time()
    with io.open(log, 'wb') as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, env=env, timeout=1800)
    dt = time.time() - t0
    txt = io.open(log, 'rb').read().decode('utf-8', 'replace')
    print('rc=%s  %.1fs' % (p.returncode, dt))
    print(txt[-4000:])
    return p.returncode, txt


if __name__ == '__main__':
    DATA = r'E:\Download\_extract61\_data\undertale\game.droid'
    OUT = os.path.join(HOME, '_evidence', '_out71_ut')
    ELEV = ['spr_elevatorgem_l', 'spr_elevatorgem_r', 'spr_elevatorpanel',
            'spr_elevatordoor', 'spr_elevatordoorframe', 'spr_elevatordoor_vines',
            'spr_darkelevator_l', 'spr_darkelevator_r',
            'bg_elevtop', 'bg_elevarmR', 'bg_elevarmL', 'bg_elevleg',
            'bg_elevbelow', 'bg_elevunit', 'bg_elevbottom']
    run(DATA, ELEV, OUT, tag='elev')
