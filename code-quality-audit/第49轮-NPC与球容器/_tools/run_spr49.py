# -*- coding: utf-8 -*-
"""第49轮 · 跑 export_spr49.csx：导出「扭蛋球 + 四个可进球角色」的精灵帧。

用法: C:\\Python311\\python.exe run_spr49.py
产出: E:\\Download\\_tmp\\drw\\chapter3_windows\\spr49\\*.png
      _evidence/spr49_log.txt（帧数/尺寸/原点 蒸馏进仓库）
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
DRW = r'E:\Download\_tmp\drw'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(HERE, 'export_spr49.csx')

# ★ 球的 4 帧分层（原作 obj_tenna_board4_gacha_Draw_0 用的就是 1/2/3，0 帧备用）
BALL = [
    'spr_dw_tv_gachaball_transparent',
    'spr_dw_tv_gachaball',
    'spr_dw_tv_gachaball_colorless',
    'spr_dw_tv_gachaball_dark',
    'spr_dw_gachaballhalves_horizontal',
]
# 四个可进球角色的四向行走（ch3 board world 命名，与产品 deltarune_ralsei/ 一致）
CHARS = []
for who in ('kris', 'susie', 'ralsei'):
    for d in ('down', 'left', 'right', 'up'):
        CHARS.append('spr_board_%s_walk_%s' % (who, d))
CHARS += ['spr_board_lancer_down', 'spr_board_lancer_left',
          'spr_board_lancer_right', 'spr_board_lancer_up']

NAMES = BALL + CHARS


def safe_write(path, text, tries=6):
    for _ in range(tries):
        try:
            with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            return True
        except OSError:
            time.sleep(0.6)
    return False


def main(ch='chapter3_windows'):
    W = os.path.join(DRW, ch)
    dw = os.path.join(W, 'data.win')
    if not os.path.isfile(dw):
        print('缺 data.win: %s' % W)
        return 1
    safe_write(os.path.join(ROUND, '_evidence', 'spr_names49.txt'),
               '\n'.join(NAMES) + '\n')
    safe_write(os.path.join(W, 'spr_names49.txt'), '\n'.join(NAMES) + '\n')
    sdir = os.path.join(W, 'scripts')
    if not os.path.isdir(sdir):
        os.makedirs(sdir)
    dst = os.path.join(sdir, 'export_spr49.csx')
    need = True
    if os.path.isfile(dst):
        try:
            with io.open(dst, 'rb') as a, io.open(SRC, 'rb') as b:
                need = a.read() != b.read()
        except OSError:
            need = True
    if need:
        try:
            shutil.copyfile(SRC, dst)
        except PermissionError:
            print('⚠️ csx 复制被拒；沿用旧副本')
    t0 = time.time()
    p = subprocess.Popen([EXE, 'load', dw, '-s', dst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    print('rc=%d %.1fs | %s' % (p.returncode, time.time() - t0,
                                out.strip().splitlines()[-1] if out.strip() else ''))
    lg = os.path.join(W, 'spr_log49.txt')
    if os.path.isfile(lg):
        t = io.open(lg, encoding='utf-8').read()
        safe_write(os.path.join(ROUND, '_evidence', 'spr49_log.txt'),
                   '# chapter3_windows 精灵导出日志\n' + t)
        for l in t.splitlines()[:40]:
            print('   ', l)
    return 0


if __name__ == '__main__':
    sys.exit(main(*(sys.argv[1:] or [])))
