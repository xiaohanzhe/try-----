# -*- coding: utf-8 -*-
"""第97轮：MEMORY.md 压缩后的逐令牌回验。
对每个被我删除/下沉的令牌，去详版里 `in` 一次；缺失即报告。
"""
import os
import sys

BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    '.workbuddy', 'memory')
MEM = os.path.join(BASE, 'MEMORY.md')
DET = os.path.join(BASE, '参考-契约与历轮（详版）.md')

def read_lossless(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()

mem = read_lossless(MEM)
try:
    det = read_lossless(DET)
except FileNotFoundError:
    print('[FATAL] 详版不存在:', DET)
    sys.exit(2)

# (令牌, 期望落在详版? , 说明)
TOKENS = [
    ('14,658,588', True, 'ch1 data.win 字节数'),
    ('undertale.apk', True, 'UT 黄魂包名'),
    ('UndertaleModCli.exe', True, 'UTMT CLI'),
    ('load <data> -s <script.csx>', True, 'UTMT 调用形式'),
    ('-45/45/135', True, '方向分档速度角'),
    ('abs(dx)>abs(dy)', True, '方向分档判据'),
    ('L7270', True, '斜向抽搐注释行'),
    ('_spell_stage', True, '_spell_stage 门控'),
    ('L11800', True, 'change_animation 行号'),
    ('L9192', True, '兜底覆盖行号'),
    ('L10780', True, '兜底覆盖行号'),
    ('L9402', True, '兜底覆盖行号'),
    ('REC97_INJECT_FALL', True, '第97轮注入开关'),
    ('jump_duration', True, '活变量'),
    ('trigger_surprise', True, '唯一写点'),
    ('9276', True, 'trigger_surprise 行号'),
    ('PrintWindow', True, 'PrintWindow 抓屏'),
    ('PW_RENDERFULLCONTENT', True, 'PrintWindow 标志'),
    ('grabWindow', True, 'QScreen.grabWindow'),
    ('18..90', True, '形状判据宽高'),
    ('deltarune_ralsei', True, '精灵真源目录'),
    ('20410ms', True, 'QPixmap.save 耗时'),
    ('current_speed_x/y', True, '朝向权威量'),
    ('14.31%', True, '回测假阳率'),
    ('_subpixel', True, '亚像素结转'),
    ('102.3 px/s', True, '位移修复后速率'),
    ('desktop_floor', True, '桌面层'),
    ('get_all_floors', True, '楼层枚举'),
    ('ast.unparse', True, '剥注释正解'),
    ('skip_desktop', True, '第97轮 A3 令牌'),
    ('str.count', True, '第97轮 C2 令牌'),
    ('fall_back_rub', True, '揉眼动画名'),
    ('35 角色', False, '已简写，速查本内可检索'),
    ('Deltarune', False, '速查本标题含'),
    ('录屏不入库', True, '工作习惯'),
]

fails = []
loose = []

def norm(s):
    """归一化：剥空白。允许 `abs(dx)>abs(dy)` 与 `abs(dx) > abs(dy)` 等价。"""
    return ''.join(s.split())

det_n = norm(det)
mem_n = norm(mem)

print('=== 详版回验 ===')
for tok, must_in_det, desc in TOKENS:
    in_det = tok in det
    in_mem = tok in mem
    # 宽松兜底：剥空白后再判（避免"判据过窄"误报）
    in_det_loose = (not in_det) and (norm(tok) in det_n)
    in_mem_loose = (not in_mem) and (norm(tok) in mem_n)
    in_det = in_det or in_det_loose
    in_mem = in_mem or in_mem_loose
    ok = in_det or in_mem
    flag = 'OK ' if ok else 'MISS'
    tag = ''
    if in_det_loose or in_mem_loose:
        tag = ' <-宽松匹配'
        loose.append(tok)
    if not ok:
        fails.append(tok)
    print('  [%s] %-32s det=%-5s mem=%-5s%s  # %s' % (flag, tok, in_det, in_mem, tag, desc))

print()
print('=== 结论 ===')
if loose:
    print('[INFO] 以下令牌靠"剥空白"方匹配上（判据过窄预警）: %s' % loose)
if fails:
    print('[FAIL] 丢失令牌 %d 个: %s' % (len(fails), fails))
    sys.exit(1)
print('[PASS] 全部 %d 个令牌均可检索（详版或速查本）' % len(TOKENS))
