# -*- coding: utf-8 -*-
"""第196轮探针：原作源文件里**每个角色到底有多少自己的动画帧**。

用户原话（本轮起点）：
    「每个角色在原作可是都有自己的动画的，为啥要用 ralsei 的啊」

上一轮我判断错了：拿「立绘只有站立帧」去推断「NPC 没有动画」。
本脚本只做一件事 = **数清楚盘上真有什么**，不做任何推断。

三个数据源
----------
1. `ralsei_pet/assets/sprites/dr/_npc_frames.json` —— 产品**当前**能画的帧（走路循环）
2. `项目文件夹/deltarune/**/*.png` —— 原作**解包**目录（逐角色 + 逐章节）
3. `ralsei_pet/assets/animations.json` —— Ralsei 自己那 115 组动画

输出：每个角色 × 每个情绪关键词的命中数，以及命中的样例文件名。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
GAME = os.path.abspath(os.path.join(REPO, '..', 'deltarune'))

MANIFEST = os.path.join(PET, 'assets', 'sprites', 'dr', '_npc_frames.json')
ANIM_JSON = os.path.join(PET, 'assets', 'animations.json')

#: 情绪关键词 → 正则。**只认"动作/表情"词**，不认走路方向词。
EMO = [
    ('laugh', r'laugh|giggl|haha'),
    ('cry', r'cry|crying|tear|sob'),
    ('sad', r'\bsad\b|_sad|depress|miserab'),
    ('surprised', r'surpris|shock|startl|astonish|_shock'),
    ('angry', r'angry|_mad\b|_mad_|rage|furious|annoy'),
    ('happy', r'happy|smile|joy|cheer'),
    ('hurt', r'hurt|pain|damage|wince'),
    ('sleep', r'sleep|snor|doze'),
]

#: 明确**不是**表情动画的（战斗/UI/特效）——先剔掉，免得把弹幕当表情
NOISE = re.compile(
    r'battle|bullet|_ui_|_icon|_item|_box|_bar|_text|_font|_bg_|_sfx|'
    r'soul|heart_|_heart|_hud|_menu|_cursor|_shadow|_hitbox|eff_|fx_',
    re.I)


def read_json(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('  [WARN] 读不出 %s: %s' % (path, e))
        return None


def manifest_chars():
    d = read_json(MANIFEST) or {}
    ch = d.get('characters') or {}
    out = {}
    for k, v in ch.items():
        fr = (v or {}).get('frames') or {}
        out[k] = {
            'dirs': sorted(fr.keys()),
            'n_frames': sum(len(x) for x in fr.values() if isinstance(x, list)),
            'kind': (v or {}).get('kind'),
        }
    return out, (d.get('no_art') or []), (d.get('not_a_person') or [])


def walk_pngs(root):
    """全树扫 png。返回 (相对路径, 文件名) 列表。"""
    out = []
    if not os.path.isdir(root):
        return out
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.png'):
                out.append((os.path.relpath(os.path.join(dp, f), root), f))
    return out


def main():
    print('=' * 72)
    print('第196轮探针 · 原作逐角色动画盘点')
    print('=' * 72)
    print('仓库根 : %s' % REPO)
    print('游戏根 : %s  (存在=%s)' % (GAME, os.path.isdir(GAME)))

    chars, no_art, not_person = manifest_chars()
    print('\n[npc_frames 清单] 有立绘 %d 人 / no_art %d / not_a_person %d'
          % (len(chars), len(no_art), len(not_person)))

    all_png = walk_pngs(GAME)
    print('[原作 png]  %d 张' % len(all_png))

    # Ralsei 自己的动画组
    aj = read_json(ANIM_JSON) or {}
    groups = aj.get('groups') or {}
    print('[Ralsei animations.json] groups = %d，组名样例 = %s'
          % (len(groups), ', '.join(list(groups)[:6])))

    # ---- 逐角色扫原作 ----
    print('\n' + '-' * 72)
    print('逐角色 × 情绪关键词：原作 PNG 命中数（已剔战斗/UI/特效噪声）')
    print('-' * 72)
    print('%-12s %-6s %-6s %s' % ('角色', '立绘帧', 'kind', '  '.join(k for k, _ in EMO)))
    rows = []
    for cid in sorted(chars):
        info = chars[cid]
        toks = [cid]
        # `susiedark` 这种复合 id 拆一下，否则文件名里永远不出现
        if cid.endswith('dark'):
            toks.append(cid[:-4])
        tok_re = re.compile(
            r'(?:%s)' % '|'.join(re.escape(t) for t in toks), re.I)
        hits = {k: [] for k, _ in EMO}
        for rel, fn in all_png:
            if not tok_re.search(fn):
                continue
            if NOISE.search(fn):
                continue
            for k, pat in EMO:
                if re.search(pat, fn, re.I):
                    hits[k].append(rel)
        row = {'id': cid, 'n': info['n_frames'], 'kind': info['kind'],
               'hits': {k: len(v) for k, v in hits.items()},
               'sample': {k: v[:2] for k, v in hits.items() if v}}
        rows.append(row)
        print('%-12s %-6d %-6s %s' % (
            cid, info['n_frames'], str(info['kind'])[:5],
            '  '.join('%s=%d' % (k, row['hits'][k]) for k, _ in EMO)))

    # ---- 汇总 ----
    print('\n' + '-' * 72)
    print('汇总')
    print('-' * 72)
    tot = sum(sum(r['hits'].values()) for r in rows)
    covered = sum(1 for r in rows if sum(r['hits'].values()) > 0)
    print('有情绪帧命中的角色：%d / %d' % (covered, len(rows)))
    print('情绪帧命中总数    ：%d' % tot)
    for k, _ in EMO:
        c = sum(1 for r in rows if r['hits'][k])
        n = sum(r['hits'][k] for r in rows)
        print('  %-10s 角色数=%-3d 帧数=%-4d' % (k, c, n))

    # ---- 落证据 ----
    ev = os.path.join(ROUND, '_evidence', 'anim_src_probe.json')
    try:
        with io.open(ev, 'w', encoding='utf-8') as f:
            f.write(json.dumps({
                'game_root': GAME,
                'game_png_total': len(all_png),
                'ralsei_anim_groups': len(groups),
                'rows': rows,
            }, ensure_ascii=False, indent=1))
        print('\n[证据] %s' % ev)
    except Exception as e:
        print('\n[WARN] 证据写不出: %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
