# -*- coding: utf-8 -*-
"""第44轮：用 UTMT dump 子命令导出 ch1 的 GML 源码 / 精灵 PNG / 纹理页。只读，不改 data.win。"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
WIN = r'E:\Download\_tmp\drw\chapter1_windows\data.win'

CODE_NAMES = [
    'gml_GlobalScript_scr_dbox',
    'gml_GlobalScript_scr_textsetup',
    'gml_GlobalScript_scr_texttype',
    'gml_GlobalScript_scr_textsound',
    'gml_GlobalScript_scr_writetext',
    'gml_GlobalScript_scr_nextmsg',
    'gml_GlobalScript_scr_getmsgno',
    'gml_GlobalScript_scr_darkbox',
    'gml_GlobalScript_scr_darkbox_black',
    'gml_GlobalScript_draw_text_shadow',
    'gml_GlobalScript_scr_text',
    'gml_Object_obj_dialoguer_Create_0',
    'gml_Object_obj_dialoguer_Draw_0',
    'gml_Object_obj_dialoguer_Other_10',
]

mode = sys.argv[1] if len(sys.argv) > 1 else 'code'
if mode == 'codeloop':
    # -c 一次只吃一个 code 名 ⇒ 逐个跑
    OUT = r'E:\Download\_tmp\drw\ch1_code'
    os.makedirs(OUT, exist_ok=True)
    for cn in CODE_NAMES:
        a = [EXE, 'dump', WIN, '-o', OUT, '-c', cn]
        q = subprocess.run(a, cwd=CWD, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = q.stdout.decode('utf-8', 'replace')
        bad = 'does not contain' in out or q.returncode != 0
        print('[%s] rc=%d %s' % ('FAIL' if bad else 'ok', q.returncode,
                                 out.strip().splitlines()[-1][:100] if out.strip() else ''))
    print('--- 产物 ---')
    fs = sorted(os.listdir(OUT))
    for x in fs:
        print('   %-46s %d B' % (x, os.path.getsize(os.path.join(OUT, x))))
    sys.exit(0)
elif mode == 'code':
    OUT = r'E:\Download\_tmp\drw\ch1_code'
    args = [EXE, 'dump', WIN, '-o', OUT, '-c'] + CODE_NAMES
elif mode == 'codestr':
    # -c 只接受一个参数：把多个 code 名用空格拼成**单个** argv
    OUT = r'E:\Download\_tmp\drw\ch1_code'
    args = [EXE, 'dump', WIN, '-o', OUT, '-c', ' '.join(CODE_NAMES)]
elif mode == 'codeall':
    OUT = r'E:\Download\_tmp\drw\ch1_code_all'
    args = [EXE, 'dump', WIN, '-o', OUT, '-c', 'UMT_DUMP_ALL']
elif mode == 'sprites':
    OUT = r'E:\Download\_tmp\drw\ch1_sprites'
    args = [EXE, 'dump', WIN, '-o', OUT, '--sprites']
elif mode == 'textures':
    OUT = r'E:\Download\_tmp\drw\ch1_tex'
    args = [EXE, 'dump', WIN, '-o', OUT, '-t']
else:
    print('unknown mode')
    sys.exit(2)

os.makedirs(OUT, exist_ok=True)
p = subprocess.run(args, cwd=CWD, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print('rc=%d  mode=%s' % (p.returncode, mode))
print(p.stdout.decode('utf-8', 'replace')[:2500])
print('--- 产物 ---')
n = 0
sample = []
for r, d, f in os.walk(OUT):
    for x in f:
        n += 1
        if len(sample) < 60:
            sample.append(os.path.join(r, x).replace(OUT, '.'))
print('files=%d' % n)
for s in sorted(sample):
    print('  ', s)
