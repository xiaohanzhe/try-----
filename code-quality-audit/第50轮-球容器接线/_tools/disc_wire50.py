# -*- coding: utf-8 -*-
"""第50轮「鉴别力体检」——证明 `verify_wire50.py` 的判据**真能报红**。

纪律（记忆铁律 §4）：只写判据不做体检 = 不知道判据是"守住了"还是"恒真"。
本脚本逐例**真的改盘上产品文件**，跑套件，看**期望的那条判据 id 是否报红**，
然后立即还原并核对文件与原文一致（SHA-256）。

用例设计原则：
* 每例只动**一处**（单变量）；
* 期望 id 用「⊆ 实际报红集」判（有些改动会级联多条，不算失败）；
* 每例结束后立刻还原，最后再全量跑一次确认 76/76 恢复。

备份落 `E:\\Download\\_tmp\\wire50_bak\\`（临时区，用后即删；不污染工作区）。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys

PY = r'C:\Python311\python.exe'
HERE = os.path.dirname(os.path.abspath(__file__))
CQ = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(CQ, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
SUITE = os.path.join(CQ, 'verify_wire50.py')
BAK = r'E:\Download\_tmp\wire50_bak'

FILES = {
    'render': os.path.join(MODS, 'scene_render.py'),
    'canvas': os.path.join(MODS, 'scene_canvas.py'),
    'bubble': os.path.join(MODS, 'bubble_system.py'),
    'npc': os.path.join(MODS, 'npc_system.py'),
    'main': os.path.join(SRC, 'main.py'),
}


def sha(p):
    with io.open(p, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def wr(p, text):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def run_suite():
    """→ (退出码, 报红的判据 id 集合)。"""
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.run([PY, SUITE], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode('utf-8', 'replace')
    fails = set()
    for line in out.splitlines():
        if line.startswith('[FAIL]'):
            parts = line.split()
            if len(parts) >= 2:
                fails.add(parts[1])
    return proc.returncode, fails, out


# (用例名, 目标文件键, 原文片段, 替换成, 期望报红的 id 集合)
# ⚠️ 每条都必须是**真能改掉被测行为**的改动（记忆铁律：负控制输入必须真落进被测分支）。
#    踩过的坑：把 `setAttribute(..., True)` 改成 `False` —— 判据只看**标识符是否出现**，
#    改值不会摘掉标识符 ⇒ 常量 G16 不报红（假阴性体检）。正确做法 = 整行换成 `pass`。
CASES = [
    ('帧号 BACK 常量改错(2→1)', 'render',
     'BUBBLE_FRAME_BACK = 2', 'BUBBLE_FRAME_BACK = 1', {'A4', 'B4'}),
    ('球素材前缀改错', 'render',
     "BUBBLE_PREFIX = 'bubble:'", "BUBBLE_PREFIX = 'bub:'", {'A5'}),
    ('四层绘制序对调(back↔front)', 'render',
     "            ('ball', BUBBLE_ROLE_BACK, bubble_sprite_name(BUBBLE_FRAME_BACK)),\n"
     "            ('char', BUBBLE_ROLE_CHAR, b.get('char_sprite')),\n"
     "            ('ball', BUBBLE_ROLE_FRONT, bubble_sprite_name(BUBBLE_FRAME_FRONT)),",
     "            ('ball', BUBBLE_ROLE_FRONT, bubble_sprite_name(BUBBLE_FRAME_FRONT)),\n"
     "            ('char', BUBBLE_ROLE_CHAR, b.get('char_sprite')),\n"
     "            ('ball', BUBBLE_ROLE_BACK, bubble_sprite_name(BUBBLE_FRAME_BACK)),",
     {'B2'}),
    ('分流漏掉上罩 top', 'render',
     'BUBBLE_ROLE_TOP)):', ')):',   # 只在 split_bubble_layers 的分流元组里出现一次
     {'C2'}),
    ('塑料滤镜强度算错(1→0.5)', 'canvas',
     'cover = max(0.06, min(0.6, 1.0 - max(0.0, min(1.0, a))))',
     'cover = max(0.06, min(0.6, 0.5 - max(0.0, min(1.0, a))))', {'D4'}),
    ('overlay 摘掉鼠标穿透', 'canvas',
     'self.setAttribute(Qt.WA_TransparentForMouseEvents, True)',
     'pass  # 鼠标穿透被摘掉（体检）', {'G16'}),
    ('球被误赋跨暗世界能力', 'bubble',
     '    return False\n\n\ndef filter_params',
     '    return True\n\n\ndef filter_params', {'E1'}),
    # ⚠️ 首版把 lancer 塞进 ALWAYS_EJECTABLE —— **测不动**：ejectable 先判 NEVER_EJECTABLE
    #    （优先级更高）⇒ 仍返回 False。正确单变量 = 直接让 NEVER 分支返回 True。
    ('Lancer 变成可脱(NEVER 分支反了)', 'bubble',
     '    if char_id in NEVER_EJECTABLE:\n        return False',
     '    if char_id in NEVER_EJECTABLE:\n        return True', {'E2'}),
    ('光世界不再要求 Ralsei 靠球', 'npc',
     '        if not light_needs_bubble(npc):', '        if True:', {'F1'}),
    ('Ralsei 失去跨暗世界权', 'npc',
     '    return is_dark_only(npc)\n\n\ndef world_gate',
     '    return False\n\n\ndef world_gate', {'F4', 'F9'}),
    ('场景层总开关被关', 'main',
     '    SCENE_LAYER_ENABLED = True', '    SCENE_LAYER_ENABLED = False', {'G3'}),
    ('overlay 忘了 raise_', 'main',
     '                ov.raise_()   # 保证在 `sprite_label` 之上（否则球壳被角色盖住）',
     '                pass  # raise_ 被移除（体检）', {'G8'}),
]


def main():
    if os.path.isdir(BAK):
        shutil.rmtree(BAK)
    os.makedirs(BAK)
    # 备份 + 记录 hash
    orig = {}
    for k, p in FILES.items():
        shutil.copy2(p, os.path.join(BAK, os.path.basename(p)))
        orig[k] = rd(p)
    hashes = {k: sha(p) for k, p in FILES.items()}

    print('基线 hash:')
    for k in FILES:
        print('  %-7s %s' % (k, hashes[k][:16]))

    res = []
    try:
        for name, key, old, new, expect in CASES:
            if not expect:
                continue      # 占位用例跳过
            p = FILES[key]
            text = rd(p)
            if old not in text:
                print('[SKIP] %-28s 片段未命中：%r' % (name, old[:40]))
                res.append((name, False, 'old-not-found'))
                continue
            wr(p, text.replace(old, new, 1))
            try:
                rc, fails, out = run_suite()
            finally:
                wr(p, orig[key])          # 立即还原
            hit = expect <= fails
            res.append((name, hit, sorted(fails)))
            print('%s %-28s 期望%s 实得%s' %
                  ('[OK]  ' if hit else '[MISS]', name,
                   sorted(expect), sorted(fails)))
    finally:
        # 兜底还原 + 核验
        for k, p in FILES.items():
            if sha(p) != hashes[k]:
                wr(p, orig[k])

    print('-' * 72)
    ok = sum(1 for _, h, _ in res if h)
    print('鉴别力体检：%d/%d 例精确报红' % (ok, len(res)))
    for name, h, f in res:
        if not h:
            print('  未命中: %s  实得 %r' % (name, f))

    bad = [k for k, p in FILES.items() if sha(p) != hashes[k]]
    print('还原核验：%s' % ('全部一致' if not bad else '不一致 %r' % bad))
    rc, fails, _ = run_suite()
    print('还原后全量复跑：exit=%d FAIL=%d %s' % (rc, len(fails), sorted(fails)))
    sys.exit(0 if (ok == len(res) and not bad and not fails) else 1)


if __name__ == '__main__':
    main()
