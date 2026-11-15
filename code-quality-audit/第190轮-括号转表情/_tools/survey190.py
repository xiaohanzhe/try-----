# -*- coding: utf-8 -*-
u"""第190轮 · 表情素材普查 v2（以**游戏包的 sprite 名单**为准，只读）。

v1 的错：把整个 `face/ch3` 目录算给每个 Deltarune 角色（于是人人 800 张）。
v2 改成**按名字匹配**：先用 `utmt190.py` 把各包的 Sprite 名单导出成 tsv（权威），
再按"角色关键词"筛 face / portrait / talk 三类，逐个角色出数。

口径
----
* `portrait` = 对话肖像（UTY 的 `spr_portrait_<角色>_<情绪>`，最理想，**带情绪名**）
* `face`     = 脸部贴图（UT/OT 的 `spr_*face*`、Deltarune 的 `spr_face_*`）
* `talk`     = 只有口型帧（`_talk_0/1`），**不算表情**，单列出来供参考

用法
----
    python survey190.py            # 打印 + 写 _evidence/faces_survey.json
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
TSV = os.path.join(ROUND, '_evidence', 'sprites')
OUT = os.path.join(ROUND, '_evidence', 'faces_survey.json')

#: 作品 → 用哪些包的名单
WORK_TSV = {
    'Undertale Yellow': ['hy'],
    'Undertale': ['ut'],
    'Outertale': ['ot'],
    'Deltarune': ['dr2', 'dr3'],
    'OneShot': [],          # 没有 GM 包，用项目内已抽的 dialog_*/contacts_*
}

#: id → 名字关键词（**手工**，宁缺不猜；只在对应作品的名单里找）
KEYS = {
    # ---- Deltarune ----
    'ralsei': ['face_r_nohat', 'face_r_dark'],
    'susie': ['face_susie', 'face_s'],
    'noelle': ['face_n_matome', 'face_n0', 'face_n1', 'face_n'],
    'berdly': ['face_berdly'],
    'asgore': ['face_asgore'],
    'toriel': ['face_toriel'],
    'king': ['face_king'],
    'queen': ['face_queen', 'ja_face_queen'],
    'lancer': ['face_l0', 'face_lancer'],
    'rouxls': ['rouxls_facehands', 'face_rurus'],
    'tenna': ['tenna'],
    'spamton': ['spamton'],
    'kris': ['kris'],
    'gerson': ['gerson'],
    'mike': ['mike'],
    'flowery': ['flowery'],
    # ---- Undertale ----
    'ut_sans': ['sans'],
    'ut_papyrus': ['papyrus'],
    'ut_toriel': ['toriel'],
    'ut_undyne': ['undyne'],
    'ut_alphys': ['alphys'],
    'ut_asgore': ['asgore'],
    'ut_mettaton': ['mett'],
    'ut_muffet': ['muffet'],
    'ut_napstablook': ['napstablook', 'blook'],
    'ut_monster_kid': ['mkid', 'monsterkid', 'monster_kid'],
    'ut_flowey': ['flowey'],
    'ut_frisk': ['frisk'],
    'ut_chara': ['chara'],
    'ut_gaster': ['gaster'],
    # ---- UTY ----
    'hy_ace': ['portrait_ace'],
    'hy_axis': ['portrait_axis', 'axis_face'],
    'hy_bowll': ['bowll'],
    'hy_ceroba_ketsukane': ['portrait_ceroba'],
    'hy_chujin_ketsukane': ['portrait_chujin'],
    'hy_clover': ['clover'],
    'hy_dalv': ['dalv'],
    'hy_ed': ['portrait_ed'],
    'hy_flowey': ['flowey'],
    'hy_guardener': ['guardener'],
    'hy_martlet': ['martlet'],
    'hy_mooch': ['portrait_mooch'],
    'hy_moray': ['portrait_moray'],
    'hy_sousborg': ['sousborg'],
    'hy_starlo': ['portrait_starlo'],
    # ---- OuterTale ----
    'ot_sans': ['sans'],
    'ot_papyrus': ['papyrus'],
    'ot_toriel': ['toriel'],
    'ot_undyne': ['undyne'],
    'ot_alphys': ['alphys'],
    'ot_asgore': ['asgore'],
    'ot_mettaton': ['mett'],
    'ot_muffet': ['muffet'],
    'ot_napstablook': ['napstablook', 'blook'],
    'ot_kidd': ['kidd'],
    'ot_asriel_twinkly': ['asriel', 'twinkly'],
}

_CACHE = {}


def load(tag):
    if tag in _CACHE:
        return _CACHE[tag]
    names = []
    p = os.path.join(TSV, tag + '.tsv')
    if os.path.isfile(p):
        for line in io.open(p, encoding='utf-8', errors='replace'):
            if line.startswith('#'):
                continue
            f = line.rstrip('\n').split('\t')
            if f and f[0]:
                names.append(f[0])
    _CACHE[tag] = names
    return names


def classify(names, keys):
    u"""返回 (portrait, face, talk) 三组名字。"""
    port, face, talk = [], [], []
    for n in names:
        low = n.lower()
        if not any(k in low for k in keys):
            continue
        if 'portrait' in low:
            port.append(n)
        elif re.search(r'face', low):
            face.append(n)
        elif re.search(r'_talk(_\d+)?$|talk_', low):
            talk.append(n)
    return sorted(port), sorted(face), sorted(talk)


def os_inventory():
    u"""OneShot：项目里已抽的 dialog_*/contacts_*。"""
    d = os.path.join(PET, 'assets', 'sprites', 'os')
    out = {}
    if not os.path.isdir(d):
        return out
    for f in os.listdir(d):
        if f.startswith('dialog_'):
            out.setdefault('os_niko', []).append(f)
        elif f.startswith('contacts_'):
            out.setdefault('os_' + f[len('contacts_'):-4], []).append(f)
    return out


def main():
    idx = json.load(io.open(os.path.join(PET, 'assets', 'npc', '_personas.json'),
                            encoding='utf-8'))
    ps = idx.get('personas') or []
    os_inv = os_inventory()

    rows = []
    for p in ps:
        nid = p.get('id')
        work = p.get('work')
        keys = KEYS.get(nid) or [nid.split('_', 1)[-1]]
        port, face, talk = [], [], []
        for tag in WORK_TSV.get(work, []):
            a, b, c = classify(load(tag), keys)
            port += a
            face += b
            talk += c
        osf = os_inv.get(nid) or []
        # OneShot 的 dialog_* 是**真表情**（normal/happy/sad/crying…）；
        # contacts_* 只是通讯录小头像，算"有脸但只有 1 张"
        os_face = [f for f in osf if f.startswith('dialog_')]
        os_icon = [f for f in osf if f.startswith('contacts_')]
        rows.append({
            'id': nid, 'work': work, 'name': p.get('name'),
            'portrait': port, 'face': face, 'talk': talk,
            'os_dialog': os_face, 'os_icon': os_icon,
            'n_emotion': len(set(port) | set(face) | set(os_face)),
            'grade': ('A' if port else
                      'B' if (face or os_face) else
                      'C' if (talk or os_icon) else 'D'),
        })

    print('=' * 96)
    print('表情素材普查 v2（按游戏包 sprite 名单匹配；A=有带情绪名的肖像，B=有脸，C=只有口型/通讯录小图，D=无）')
    print('=' * 96)
    for w in ('Deltarune', 'Undertale', 'Undertale Yellow', 'OneShot', 'Outertale'):
        got = [r for r in rows if r['work'] == w]
        cnt = collections.Counter(r['grade'] for r in got)
        print('\n--- %s：%d 人  A%d B%d C%d D%d ---'
              % (w, len(got), cnt['A'], cnt['B'], cnt['C'], cnt['D']))
        for r in got:
            mark = {'A': '肖像', 'B': '脸部', 'C': '口型', 'D': '—  '}[r['grade']]
            src = ''
            if r['portrait']:
                src = ' | '.join(n.split('portrait_')[-1] for n in r['portrait'][:3])
            elif r['face']:
                src = ', '.join(r['face'][:3])
            elif r['os_dialog']:
                src = 'dialog_* ×%d' % len(r['os_dialog'])
            elif r['talk']:
                src = 'talk ×%d' % len(r['talk'])
            elif r['os_icon']:
                src = r['os_icon'][0]
            print('  %-22s %s %4d  %s' % (r['id'], mark, r['n_emotion'], src))

    tot = collections.Counter(r['grade'] for r in rows)
    print('\n合计：A%d / B%d / C%d / D%d  （共 %d）'
          % (tot['A'], tot['B'], tot['C'], tot['D'], len(rows)))

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'rows': rows, 'summary': dict(tot)}, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('→ %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
