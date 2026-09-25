# -*- coding: utf-8 -*-
"""第49轮 · 鉴别力体检：逐条**改盘上文件** → 跑套件 → 收 [FAIL] <id> → 还原 → 校验 hash。

一条判据如果改了对应实现却**不报红**，它就没有鉴别力（"看着在守其实没守"）。
本脚本对 12 组破坏逐条断言「命中的 FAIL id 集合 == 期望集合」。

用法: C:\\Python311\\python.exe disc_npc49.py
"""
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SUITE = os.path.join(ROUND, 'verify_npc49.py')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
NPCJSON = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
BUBBLE = os.path.join(ROOT, 'ralsei_pet', 'assets', 'bubble')
GML = os.path.join(ROUND, '_evidence', 'gml')

NS = os.path.join(MOD, 'npc_system.py')
BS = os.path.join(MOD, 'bubble_system.py')
REG = os.path.join(NPCJSON, '_registry.json')
DIA = os.path.join(NPCJSON, '_dialogue.json')
GACHA = os.path.join(GML, 'ch3.obj_tenna_board4_gacha_Draw_0.gml')

CASES = [
    # id, 文件, (old, new), 期望 FAIL id 集合, 说明
    ('P1', BS, ("DRAW_ORDER = (FRAME_BACK, FRAME_FRONT, FRAME_TOP)",
                "DRAW_ORDER = (FRAME_FULL, FRAME_FRONT, FRAME_TOP)"),
     {'H2'}, '把球的绘制序常量改掉（角色将不再被夹住）'),
    ('P2', BS, ("{'role': 'character', 'sprite': char_sprite, 'frame': char_frame,\n"
                "         'x': char_xy[0], 'y': char_xy[1], 'scale': CHAR_SCALE, "
                "'angle': 0.0, 'alpha': 1.0},\n        ", ''),
     {'F12', 'F13'}, '把角色从绘制序中间摘掉（只剩三层球）'),
    ('P3', BS, ("NEVER_EJECTABLE = ('lancer',)", "NEVER_EJECTABLE = ()"),
     {'F7'}, '★ 抽掉 "Lancer 不可脱" 的名字表 '
             '（注意：ejectable 末尾还有 ALWAYS_EJECTABLE 兜底 ⇒ 只有 must_stay_inside 会动）'),
    ('P4', NS, ("    if world == WORLD_LIGHT:\n"
                "        if carried and npc.escape_via_bubble:",
                "    if world == WORLD_LIGHT:\n"
                "        return GateResult(True, REASON_OK, 'hacked')\n"
                "        if carried and npc.escape_via_bubble:"),
     {'E1', 'E2', 'E6', 'E13'}, '★ 拆掉「不可脱离暗世界」这道门（光世界一律放行）'),
    ('P5', NS, ("    NpcTier.PLAIN: FollowPolicy.CONSENT,",
                "    NpcTier.PLAIN: FollowPolicy.AUTONOMOUS,"),
     {'D2', 'D3', 'D7', 'D8', 'D10'},
     '★ 让纯 NPC 也变成自主跟随（不再需要主角同意；D10 因状态不再是 pending 而连带报红）'),
    ('P6', BS, ("SPIN_STEP_DEG = 360.0 / SPIN_DIRECTIONS", "SPIN_STEP_DEG = 45.0"),
     {'G4', 'G6'}, '把「4 个方向」的步长从 90°（均分整圈）改回 45°（转不满一圈）'),
    ('P7', BS, ("    if d <= radius:\n        return (cx, cy, False, d)",
                "    if d <= radius * 1e9:\n        return (cx, cy, False, d)"),
     {'G1'}, '★ 拆掉「越界钳回球内」（穿模门失效）'),
    ('P8', DIA, ('"lines": {', '"lines": {\n  "zzz_probe": ["一", "二", "三"],'),
     {'C1', 'C2'}, '塞一组只有 3 句的内置对话（C2 越下限 + C1 组数不再等于纯 NPC 数）'),
    ('P9', REG, ('"tier": "plain"', '"tier": "main"'),
     {'B7', 'C1', 'C4'}, '把一条纯 NPC 改标成主线（分层/对话来源/needs_setting 三处对不上）'),
    ('P10', BUBBLE, None, {'H10', 'H12'}, '★ 删掉一个角色帧 PNG（资产计数立刻掉）'),
    ('P11', GACHA, ('spr_dw_tv_gachaball_transparent, 2',
                    'spr_dw_tv_gachaball_transparent, 0'),
     {'H1', 'H2', 'H3'}, '★ 改掉原作 GML 里的球帧序（判据必须读得到这个文件）'),
    ('P12', NS, ("SCHEMA_VERSION = 1", "SCHEMA_VERSION = 1  # noop-probe"),
     set(), '负控制：加一行无关注释 ⇒ **不许**报红（判据不许过宽）'),
]


def sha(p):
    h = hashlib.sha256()
    with io.open(p, 'rb') as fh:
        h.update(fh.read())
    return h.hexdigest()


def run_suite():
    p = subprocess.run([sys.executable, SUITE], cwd=ROOT, capture_output=True,
                       timeout=300)
    out = p.stdout.decode('utf-8', 'replace')
    return set(re.findall(r'^\[FAIL\]\s+(\S+)', out, re.M)), out


def read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(t)


def main():
    base = {p: sha(p) for p in (NS, BS, REG, DIA, GACHA)}
    base_files = sorted(os.listdir(BUBBLE))
    bad = []
    print('=== 鉴别力体检（第49轮）===')
    for cid, path, sub, expect, why in CASES:
        old = None if sub is None else read(path)
        moved = None
        if sub is None:            # 删除型
            victim = os.path.join(BUBBLE, sorted(
                f for f in base_files if f.startswith('spr_board_'))[0])
            moved = victim + '.hidden'
            os.rename(victim, moved)
        else:
            o, n = sub
            if o not in old:
                print('[SKIP] %s 找不到锚点 %r' % (cid, o[:40]))
                bad.append(cid)
                continue
            write(path, old.replace(o, n, 1))
        try:
            got, out = run_suite()
        finally:
            if sub is None:
                if moved and os.path.isfile(moved):
                    os.rename(moved, moved[:-len('.hidden')])
            else:
                write(path, old)
        ok = (got == expect)
        print('%s %-4s 期望 %-22s 实得 %-22s | %s'
              % ('[OK]  ' if ok else '[BAD] ', cid,
                 sorted(expect) or '{}', sorted(got) or '{}', why))
        if not ok:
            bad.append(cid)
            for line in out.splitlines():
                if line.startswith('[FAIL]'):
                    print('        ', line)

    print('-' * 72)
    drift = [p for p, h in base.items() if sha(p) != h]
    files_now = sorted(os.listdir(BUBBLE))
    print('还原校验: 内容漂移 %s / 资产清单一致 %s'
          % (drift or '无', files_now == base_files))
    print('体检结果: %d/%d 精确报红' % (len(CASES) - len(bad), len(CASES)))
    if bad or drift or files_now != base_files:
        print('问题:', bad, drift)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
