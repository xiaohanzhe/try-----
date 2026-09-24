# -*- coding: utf-8 -*-
"""第44轮续 · 把原作 sprite 播放参数蒸馏进仓库（`_sprite_anim.json`）。

为什么必须进仓库
----------------
记忆铁律：「回归套件不许依赖『用后即删』的临时区」。
`spranim44.json` 在 `E:\\Download\\_tmp\\drw\\` 下，随时可能被清。
本脚本把**只需要的部分**（我们用到的 25 个 sprite 的帧数与速度）
提炼成小文件落进 `ralsei_pet/assets/scenes/_sprite_anim.json`。

★ 数据来源与字段名的坑（务必保留）
--------------------------------
`UndertaleSprite` 的播放速度字段名是 **`GMS2PlaybackSpeed`** /
**`GMS2PlaybackSpeedType`**。我第一版写成 `Speed` / `PlaybackSpeed`（GML 里的
变量名），UTMT 里**不存在这两个属性** ⇒ 静默取到 null ⇒ 全表 `speed=0`。
那是一份**假数据**：会得出"原作所有 sprite 都不动"的错误结论。
发现方式 = 探查 `UndertaleSprite` 的属性名清单（`probespr44.csx`）。

★ 本脚本的锚点（不命中就退出，不写文件）
  ST1 输入文件存在且可解析
  ST2 预期 sprite 名字集合命中率 >= 90%（25 个里至少 23 个在源文件里）
  ST3 至少一个 sprite 的 frames > 1（否则"动画"这件事无从谈起）
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
OUT = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_sprite_anim.json')
SRC = r'E:\Download\_tmp\drw\chapter1_windows\spranim44.json'

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def ok(msg):
    print('  [OK]   %s' % msg)


def bad(msg):
    print('  [BAD]  %s' % msg)


def main():
    # ---- ST1 ----
    if not os.path.isfile(SRC):
        bad('ST1 输入不存在：%s' % SRC)
        return 1
    with io.open(SRC, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    ok('ST1 读入 %s（%d sprite）' % (os.path.basename(SRC),
                                     len(raw.get('sprites') or [])))

    # 我们用到的 sprite 名（从 objs/ 磁盘真值反推）
    # ★ 同时算出"哪些在磁盘上是多帧" —— 这才是本脚本真正关心的集合：
    #   单帧 sprite（spr_doorB~F / spr_marker*）不需要动画参数，源文件里
    #   也没有它们的行（spranim44.csx 只输出 nf>1 或 watch 名单）。若把
    #   单帧也算进命中率，会得到"44% 命中"的**假报红**（判据口径错）。
    want = set()
    multi_on_disk = set()
    disk_frames = {}
    for f in os.listdir(OBJS):
        if not f.lower().endswith('.png'):
            continue
        base = f[:-4]
        tail = base.rsplit('_', 1)[-1]
        if tail.isdigit():
            base = base[:-(len(tail) + 1)]
            disk_frames[base] = max(disk_frames.get(base, 0), int(tail) + 1)
        want.add(base)
    multi_on_disk = set(n for n, c in disk_frames.items() if c > 1)
    ok('objs/ 磁盘真值 %d 个 sprite（其中多帧 %d 个）'
       % (len(want), len(multi_on_disk)))

    by_name = {}
    for row in (raw.get('sprites') or []):
        nm = row.get('name')
        if isinstance(nm, str) and nm:
            by_name[nm] = row

    hit = sorted(want & set(by_name))
    miss = sorted(want - set(by_name))
    rate = (len(hit) / float(len(want))) if want else 0.0

    # ---- ST2（口径 = **多帧** sprite 的命中率）----
    m_hit = sorted(multi_on_disk & set(by_name))
    m_miss = sorted(multi_on_disk - set(by_name))
    m_rate = (len(m_hit) / float(len(multi_on_disk))) if multi_on_disk else 0.0
    if m_rate < 1.0:
        bad('ST2 多帧 sprite 命中率 %.1f%% < 100%%（缺 %s）'
            % (m_rate * 100, m_miss))
        return 1
    ok('ST2 多帧 sprite 全部命中（%d/%d）；单帧无需参数（整体命中 %d/%d = %.0f%%）'
       % (len(m_hit), len(multi_on_disk), len(hit), len(want), rate * 100))

    # ---- ST3 ----
    n_multi = sum(1 for n in hit if int(by_name[n].get('frames') or 1) > 1)
    if n_multi <= 0:
        bad('ST3 没有多帧 sprite ⇒ 源数据可疑')
        return 1
    ok('ST3 多帧 sprite = %d' % n_multi)

    # ---- 组装 ----
    out = {
        'schema_version': 1,
        '_comment': {
            'source': '第43轮 UTMT 导出 + 第44轮 spranim44.csx（字段名 GMS2PlaybackSpeed）',
            'fps': 30,
            'unit': 'speed 单位 = 帧/游戏帧（GMS2PlaybackSpeedType='
                    'FramesPerGameFrame）；单帧时长 ms = 1000 / (30 * speed)',
            'why': 'scene_render.plan_frame 按 (t * 30 * speed) % frames 取帧',
            'only_used': '只蒸馏 objs/ 里实际用到的 sprite，避免引入无用体量',
        },
        'fps': 30,
        'sprites': {},
    }
    for n in hit:
        row = by_name[n]
        frames = int(row.get('frames') or 1)
        try:
            speed = float(row.get('speed'))
        except (TypeError, ValueError):
            speed = 0.0
        stype = row.get('speed_type')
        if frames <= 1:
            continue
        out['sprites'][n] = {
            'frames': frames,
            'speed': speed,
            'speed_type': stype,
            # 单帧毫秒（四舍五入到 0.1）；speed<=0 → null（"不自走"，由调用方决定）
            'frame_ms': (round(1000.0 / (30.0 * speed), 1)
                         if speed and speed > 0 else None),
        }

    with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=2))
        fh.write('\n')
    ok('写出 %s（%d 个多帧 sprite，%d B）'
       % (os.path.relpath(OUT, ROOT), len(out['sprites']),
          os.path.getsize(OUT)))
    for n in sorted(out['sprites']):
        r = out['sprites'][n]
        print('     %-24s frames=%d speed=%s frame_ms=%s'
              % (n, r['frames'], r['speed'], r['frame_ms']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
