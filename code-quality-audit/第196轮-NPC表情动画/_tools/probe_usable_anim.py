# -*- coding: utf-8 -*-
"""第196轮探针 3：**可用**情绪帧筛选（尺寸族 + 单人帧），逐角色结算。

为什么需要这一层
----------------
原始命中数不能直接用（`susie surprised=112` 里混着
`spr_susie_kris_run_right_shocked_0.png(62x38)` —— 一张图里画了两个人，
拿来当 Susie 的惊讶动作会把 Kris 一起画到屏幕上）。

判据只用两条，都是**几何**的（不猜语义）：
  ① **同尺寸族**：该帧高度与「这个人走路帧的高度」差 ≤2px，宽度落在
     `[0.5×, 2.5×]` 走路帧宽度内。
     ⇒ 原作里同一个人的 overworld 立绘画布高度基本是常量，高度差 2px 以上
       说明是另一种呈现（立绘特写/躺倒/合体帧），混进小窗一定跳。
  ② **单人帧**：文件名里不出现**其他**已登记角色的 token。
     ⇒ 双人帧是给 cutscene 用的整图，不能挂在一个人身上。

不做像素解码，只读 PNG 头。
"""
import io
import json
import os
import re
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
GAME = os.path.abspath(os.path.join(REPO, '..', 'deltarune'))
MANIFEST = os.path.join(PET, 'assets', 'sprites', 'dr', '_npc_frames.json')
DR = os.path.join(PET, 'assets', 'sprites', 'dr')

#: 情绪 → 正则。★ `(?<!un)happy` 是**必须**的：`walk_down_unhappy` 是"不高兴"，
#: 归到 happy 里就等于把丧气当开心。
EMO = [
    ('happy', r'(?<!un)happy|laugh|smile|giggl'),
    ('surprised', r'surpris|shock|startl'),
    ('sad', r'(?<!un)sad\b|(?<!un)sad_|_sad|depress'),
    ('angry', r'angry|_mad\b|_mad_|annoy|rage'),
    ('cry', r'cry(?!stal)|tear|sob'),
    ('hurt', r'hurt|pain|wince'),
]

#: 明确不是"表情动作"的：战斗/弹幕/UI/特效/影子/按钮
NOISE = re.compile(
    r'battle|bullet|_ui_|_icon|_item_|_box_|_bar_|_text_|_font|_bg_|_sfx_|'
    r'soul|_heart|_hud_|_menu_|_cursor|_shadow|eff_|_fx_|_btn|_button|'
    r'_mask|_layer|_overlay', re.I)

#: 同一个人的"动作"帧可能存在多个方向变体；小窗只播**正面**，其余会让本体
#: 突然转身（朝向是 AI 状态机管的，不能被表情抢走）。
DOWN_TOKENS = re.compile(r'(?:^|_)(?:down|dw|d)(?:_|$)|^spr_[a-z0-9]+_(?!.*(?:up|left|right|_l_|_r_|_u_))',
                         re.I)
#: 明确是别的朝向的
OTHER_DIR = re.compile(r'(?:^|_)(?:up|left|right|ul|ur|dl|dr)(?:_|$)', re.I)


def png_hw(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
        if len(head) < 26 or head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        w, h = struct.unpack('>II', head[16:24])
        return int(w), int(h)
    except Exception:
        return None


def walk_pngs(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.png'):
                out.append(os.path.join(dp, f))
    return out


def main():
    print('=' * 84)
    print('第196轮探针 3 · 可用情绪帧（尺寸族 + 单人帧 + 正面朝向）')
    print('=' * 84)

    with io.open(MANIFEST, 'r', encoding='utf-8') as f:
        man = json.load(f)
    chars = man.get('characters') or {}
    all_ids = sorted(chars.keys())

    # ---- 走路帧几何基线 ----
    base = {}
    for cid in all_ids:
        fr = (chars[cid].get('frames') or {})
        d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        if not d:
            base[cid] = None
            continue
        s = png_hw(os.path.join(DR, cid, fr[d][0]['f']))
        if not s:
            base[cid] = None
            continue
        # 该方向所有帧的高度是否有波动
        hs = set()
        for it in fr[d]:
            q = png_hw(os.path.join(DR, cid, it['f']))
            if q:
                hs.add(q[1])
        base[cid] = {'w': s[0], 'h': s[1], 'dir': d, 'hs': sorted(hs)}

    print('\n[A] 走路帧几何基线（`kind=stand` 的人是单帧原地）')
    for cid in all_ids:
        b = base.get(cid)
        if not b:
            print('  %-12s 无基线' % cid)
            continue
        print('  %-12s %-6s %sx%s  高度波动=%s  %s'
              % (cid, (chars[cid].get('kind') or '')[:6], b['w'], b['h'],
                 b['hs'], '' if len(b['hs']) <= 1 else '★多高度'))

    all_png = walk_pngs(GAME)
    print('\n[原作 png] %d 张' % len(all_png))

    # ---- 逐角色筛 ----
    print('\n' + '-' * 84)
    print('[B] 筛选后可用帧（同高度±2 / 宽度0.5~2.5× / 单人 / 正面）')
    print('-' * 84)
    result = {}
    for cid in all_ids:
        b = base.get(cid)
        if not b:
            result[cid] = {'usable': {}, 'raw': {}}
            continue
        me = re.compile(r'(?<![a-z])%s(?![a-z])' % re.escape(cid), re.I)
        others = [o for o in all_ids if o != cid]
        others_re = re.compile(
            r'(?<![a-z])(?:%s)(?![a-z])'
            % '|'.join(re.escape(o) for o in others), re.I) if others else None
        usable = defaultdict(list)
        raw = defaultdict(int)
        for p in all_png:
            fn = os.path.basename(p)
            if not me.search(fn):
                continue
            if NOISE.search(fn):
                continue
            for emo, pat in EMO:
                if not re.search(pat, fn, re.I):
                    continue
                raw[emo] += 1
                if others_re is not None and others_re.search(fn):
                    continue                       # 双人帧
                if OTHER_DIR.search(fn):
                    continue                       # 别的朝向
                s = png_hw(p)
                if not s:
                    continue
                w, h = s
                if abs(h - b['h']) > 2:
                    continue                       # 不在同一画布高度族
                if not (0.5 * b['w'] <= w <= 2.5 * b['w']):
                    continue                       # 宽度离谱（躺倒/特写/合体）
                usable[emo].append((fn, '%dx%d' % (w, h)))
        result[cid] = {
            'base': b,
            'raw': dict(raw),
            'usable': {k: [{'f': a, 'size': b2} for a, b2 in v]
                       for k, v in usable.items()},
        }
        if not raw:
            print('  %-12s —— 原作无匹配情绪词' % cid)
            continue
        print('  %-12s %s' % (cid, '  '.join(
            '%s=%d/%d' % (e, len(usable.get(e, [])), raw.get(e, 0))
            for e, _ in EMO if raw.get(e))))
        for e, _ in EMO:
            v = usable.get(e) or []
            if v:
                print('      %-10s %s' % (e, ' | '.join(
                    '%s(%s)' % (n.replace('.png', ''), s) for n, s in v[:3])))

    # ---- 汇总 ----
    print('\n' + '-' * 84)
    print('[C] 汇总：有几个角色**每个情绪**都有可用帧')
    print('-' * 84)
    print('%-12s %s' % ('角色', '  '.join('%-11s' % e for e, _ in EMO)))
    full = 0
    for cid in all_ids:
        r = result[cid]
        cells = []
        for e, _ in EMO:
            n = len((r['usable'] or {}).get(e) or [])
            cells.append('%-11s' % (('%d帧' % n) if n else '—'))
        ok = all((r['usable'] or {}).get(e) for e, _ in EMO)
        full += 1 if ok else 0
        print('%-12s %s %s' % (cid, '  '.join(cells), '★齐全' if ok else ''))
    print('\n六情绪齐全的角色：%d / %d' % (full, len(all_ids)))

    ev = os.path.join(ROUND, '_evidence', 'anim_usable_probe.json')
    try:
        with io.open(ev, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'chars': result}, ensure_ascii=False, indent=1))
        print('[证据] %s' % ev)
    except Exception as e:
        print('[WARN] 证据写不出: %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
