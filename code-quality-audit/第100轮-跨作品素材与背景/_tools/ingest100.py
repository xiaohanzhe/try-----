# -*- coding: utf-8 -*-
u"""ingest100.py —— 第100轮：把用户补发的 OneShot 素材**按内容核实后**入库。

用户口径（逐字）
----------------
「oneshot 有部分音效和素材缺失，这些是补齐的，对了，**里面可能有些素材名称被改了**」
「**以后记住，任何素材都从这里找**」

因此本脚本做三件**不可省**的事：
 1. **按内容识别**（不信文件名）——结论取自 `_evidence/identify100.json`。
 2. **跳过重复项**：`niko.png` 与仓库 `assets/sprites/os/niko.png` **逐像素相同**，
    直接跳过（不覆盖、不重复入库），并在清单里记明。
 3. **留下改名映射**：`foodstep_grass.wav` -> WME `sfx/step_grass.wav` 这类改写必须可查。

★ 安全：源目录 `C:\\Users\\23002\\Desktop\\项目文件夹\\assets` 里混着用户的工作文件
  （`config.json` 含**明文 API key**、`save_key.py`、`desktop.ini`）⇒ 一律排除，
  且**绝不把 key 的内容写进任何产物**。

用法：
    C:\\Python311\\python.exe -X utf8 ingest100.py            # 演练（只打印，不写）
    C:\\Python311\\python.exe -X utf8 ingest100.py --apply     # 真入库
"""
import hashlib
import io
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))          # 仓库根
PET = os.path.join(REPO, 'ralsei_pet')
SUP = r'C:\Users\23002\Desktop\项目文件夹\assets'
EVID = os.path.join(ROUND, '_evidence', 'identify100.json')

SPR_OUT = os.path.join(PET, 'assets', 'sprites', 'os')
SND_OUT = os.path.join(PET, 'assets', 'sounds', 'os')
NOT_ASSETS = {'config.json', 'save_key.py', 'desktop.ini'}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def pixkey(p):
    """★ 重复判据用**像素**而非字节：`niko.png` 与仓库现有的是同一张画，
    但 PNG 编码器不同（7009 vs 2235 字节）⇒ 字节哈希判"不同"会误入库一份重复。
    （第100轮实测：这个误判真发生过，护栏当场拦住了。）"""
    im = Image.open(p).convert('RGBA')
    return hashlib.sha256(b'%dx%d|' % (im.width, im.height)
                          + im.tobytes()).hexdigest()


def main():
    apply_ = '--apply' in sys.argv
    ident = json.load(io.open(EVID, encoding='utf-8'))
    names = sorted(n for n in os.listdir(SUP)
                   if n not in NOT_ASSETS and not n.endswith('.jpg'))
    pngs = [n for n in names if n.lower().endswith('.png')]
    wavs = [n for n in names if n.lower().endswith('.wav')]

    sprite_meta, sound_meta, skipped, rename = {}, {}, {}, {}
    plan = []                                            # (src, dst, kind, name)

    for n in pngs:
        src = os.path.join(SUP, n)
        dst = os.path.join(SPR_OUT, n)
        h = sha(src)
        if os.path.isfile(dst):
            if sha(dst) == h:
                skipped[n] = '与仓库现有 %s 逐字节相同（重复项，跳过）' % n
                continue
            if pixkey(dst) == pixkey(src):
                skipped[n] = ('与仓库现有 %s **逐像素相同**（PNG 编码不同：%d vs %d 字节，'
                              '内容重复，跳过）' % (n, os.path.getsize(dst), os.path.getsize(src)))
                continue
            raise SystemExit('★ 目标已存在且**像素不同**，拒绝覆盖：%s' % dst)
        im = Image.open(src)
        near = (ident.get('pics_near') or {}).get(n) or {}
        cp = ident['pics'].get(n)
        sprite_meta[n] = {
            'bytes': os.path.getsize(src), 'sha256': h, 'w': im.width, 'h': im.height,
            'counterpart': cp if isinstance(cp, str) else None,
            'structural_match': (near.get('ref') if near.get('r', 0) >= 0.9 else None),
            'match_r': near.get('r'), 'match_base': near.get('base_avg'),
        }
        if sprite_meta[n]['counterpart'] or sprite_meta[n]['structural_match']:
            rename[n] = (sprite_meta[n]['counterpart']
                         or sprite_meta[n]['structural_match'])
        plan.append((src, dst, 'sprite', n))

    for n in wavs:
        src = os.path.join(SUP, n)
        dst = os.path.join(SND_OUT, n)
        h = sha(src)
        if os.path.isfile(dst) and sha(dst) == h:
            skipped[n] = '已在库且内容相同（跳过）'
            continue
        if os.path.isfile(dst):
            raise SystemExit('★ 目标已存在且内容不同，拒绝覆盖：%s' % dst)
        wi = (ident.get('wavs_info') or {}).get(n) or {}
        hit = ident['wavs'].get(n)
        hit = [x.replace('\\', '/') for x in hit] if hit else hit
        sound_meta[n] = {'bytes': os.path.getsize(src), 'sha256': h,
                         'fmt': wi.get('fmt'), 'hit_tier': wi.get('tier'),
                         'counterpart': (hit[0] if hit else None)}
        if hit:
            rename[n] = hit[0]
        plan.append((src, dst, 'sound', n))

    print('待入库：贴图 %d / 音效 %d ；跳过 %d %s'
          % (len(sprite_meta), len(sound_meta), len(skipped), list(skipped)))
    print('改名映射 %d 条：' % len(rename))
    for k in sorted(rename):
        print('    %-22s -> %s' % (k, rename[k]))
    if not apply_:
        print('\n（演练模式，未写盘。加 --apply 真入库）')
        return 0

    os.makedirs(SPR_OUT, exist_ok=True)
    os.makedirs(SND_OUT, exist_ok=True)
    for src, dst, kind, n in plan:
        shutil.copy2(src, dst)

    # ---- 回读校验（写盘后重新算，别信"我写过了"）
    bad = []
    for n, m in list(sprite_meta.items()) + list(sound_meta.items()):
        d = os.path.join(SPR_OUT if n in sprite_meta else SND_OUT, n)
        if not os.path.isfile(d) or sha(d) != m['sha256']:
            bad.append(n)
    print('\n回读校验：%d 个文件，不一致 %d %s'
          % (len(sprite_meta) + len(sound_meta), len(bad), bad))
    if bad:
        raise SystemExit('★ 入库校验失败')

    manifest = {
        'round': 100,
        'date': '2026-10-10',
        'why': ('用户补发 OneShot 缺失素材。原话：「oneshot 有部分音效和素材缺失，这些是补齐的，'
                '对了，里面可能有些素材名称被改了」。'
                '★ 因此本清单的 `rename_map` 是**结论性证据**，不是备注。'),
        'source_dir': SUP,
        'identified_by': 'code-quality-audit/第100轮-跨作品素材与背景/_tools/identify100.py',
        'identify_evidence': '_evidence/identify100.json',
        'excluded': sorted(NOT_ASSETS) + ['1653f04433b09df48a87ef6e5725cd92.jpg'],
        'excluded_reason': ('源目录是用户的下载/工作目录，混有非素材文件。'
                            '★ 其中 config.json 含**明文 API key**：已排除，且本清单'
                            '**不记录其任何内容**。'),
        'skipped_duplicates': skipped,
        'rename_map': rename,
        'sprites': sprite_meta,
        'sounds': sound_meta,
        'naming': {
            'sprites': 'assets/sprites/os/<原名>.png（沿用 ut/hy/ot 的"按作品分子目录 + 保留原名"约定）',
            'sounds': 'assets/sounds/os/<原名>.wav（SoundManager._resolve_path 非递归，'
                      '调用时传 "os/xxx.wav" 即可命中）',
        },
    }
    mp = os.path.join(SPR_OUT, '_source100.json')
    with io.open(mp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=False)
    print('清单已写 ->', mp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
