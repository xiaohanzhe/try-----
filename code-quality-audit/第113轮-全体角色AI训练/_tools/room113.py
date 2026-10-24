# -*- coding: utf-8 -*-
"""第113轮c · 房间专属回忆 + 主动开口（用户 2026-10-24 追加口径）

用户原话：「**在特定 room 有特殊回忆，主动提出对话**等，你也训练一下，
当然，**频次会递减**」。

## 三件事分开做
1. `--build`：**数据面**。把「NPC → 他的房间 → 房间的原作名 → 可读说法」拼出来，
   落 `assets/npc/_rooms/room_memories113.json`。**不调模型**，随时可跑。
2. `--train`：**生成面**。每个 NPC 在自己房间里主动开口说一句，**四档频次递减**
   （第 1 次最具体 → 第 4 次起闭口）。占模型，排在主训练之后。
3. `--report`：判据汇总。

## 素材从哪来（"一切根据原作"）
+ 房间名：`assets/scenes/_original_rooms.json` —— 从 Deltarune 反编译的
  `scr_roomname` / `scr_get_room_by_id` 抄录的**真实房间 id 与显示名**（不是我们编的）。
+ 归属于谁：`assets/npc/_placement.json` 的 `placement`（每条带 `room_id` / `room_raw` /
  `scene` / `evidence`），以及 `homes`（50 人有家，但**明细文件
  `第87轮-每人一个家/_evidence/homes87.json` 已在那 1017 个"已暂存删除"里**，
  所以这里只能退回用 `placement` 的站位 + scene 尾段）。
+ 中文别称：`assets/scenes/_aliases.json`（教堂→church、花店→flowershop…）。

★ 证据分级照抄现有规矩，**不假装**：
  `original`（查到原作房间名）/ `derived`（有 room_raw，用 scene 尾段推可读说法）/
  `authored`（只有 scene 路径，按命名规律给说法）—— 三档都要在产物里写清楚，
  并且**没有 room 归属的人一律不训练**（62 人 unplaced：跨作品角色、knight 等），
  不给他编一个"安身之所"。

## 频次递减怎么落地
`TIERS = (1, 2, 3, 4)`：第 1 次说最具体的（提到房间的**具体细节** + 回望），
第 2 次补充，第 3 次一句短的，**第 4 次起不说话**（返回空）。
判据里 `monotone` = 长度随档位递减，`silent_at_4` = 第 4 档为空/极短。

用法
----
    python room113.py --build              # 只出数据面（不占模型）
    python room113.py --train --limit 3    # 试跑 3 人
    python room113.py --train              # 全量（断点续跑）
    python room113.py --report
"""
import json
import os
import re
import sys
import time

import common113 as C
import dialogue113 as D

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, '_evidence')
PET = os.path.join(os.path.dirname(os.path.dirname(ROUND)), 'ralsei_pet')
ASSETS = os.path.join(PET, 'assets')
OUT_DIR = os.path.join(ASSETS, 'npc', '_rooms')
OUT_JSON = os.path.join(OUT_DIR, 'room_memories113.json')
RAW_ROOM = os.path.join(EVID, 'raw_room')
TR_ROOM = os.path.join(EVID, 'transcripts_room')

CTX = 12288
PREDICT = 150        # 主动开口比对话可以稍长一点点（第 1 档要容得下一句完整回忆）
MAX_RETRIES = 1
TIERS = (1, 2, 3, 4)
SILENT_TIER = 4      # 第 4 次起不说话

#: 房间尾段 → 可读说法的补充词表（只做"翻译"，不编内容）
TAIL_CN = {
    'kris': 'Kris 的房间', 'susie': 'Susie 的房间', 'ralsei': 'Ralsei 的房间',
    'noelle': 'Noelle 的房间', 'berdly': 'Berdly 的房间',
    'flowershop': '花店', 'church': '教堂', 'diner': '餐厅', 'library': '图书馆',
    'castle_town': '城堡镇', 'throne': '王座厅', 'prison': '牢房',
    'shop': '商店', 'cafe': '咖啡馆', 'inn': '旅店', 'school': '学校',
    'hospital': '医院', 'graveyard': '墓地', 'lake': '湖边', 'forest': '森林',
}


def _chapter_of(scene):
    m = re.match(r'(ch\d+)\.', scene or '')
    return m.group(1) if m else ''


def _tail_of(scene):
    """`ch2.my_castle_town.dw_castle_rooms_kris` → `dw_castle_rooms_kris`"""
    parts = [p for p in (scene or '').split('.') if p]
    return parts[-1] if parts else ''


def _humanize(tail):
    """把 scene 尾段翻成一句可读的房间说法（**只翻译命名，不编剧情**）。"""
    if not tail:
        return ''
    for k, cn in TAIL_CN.items():
        if k in tail:
            return cn
    return ''


def build():
    """数据面：NPC → 房间 → **可读说法**。

    ★★ 房间名的来源有三层，按可靠性从高到低用（第一版只用 `_original_rooms.json`，
    original 只有 3 人 —— 因为那张表只有三章 95 间，而实际场景几百个）：
      1. `_index.json` 的三级索引（章节 → 区域 → 场景），每个 scene 带 `name`
         和 `original_room_id` —— **这是全量可用的**；
      2. `_original_rooms.json` 的原作显示名（"Kris's Room"、"Castle Town"），
         要按 chapter + room_id 同时命中才算数；
      3. `_zone.*.json` 的 `area_name`（中文区域名，如"拉尔赛的城堡"）。
    """
    rooms = C.load_json(os.path.join(ASSETS, 'scenes', '_original_rooms.json'), {}) or {}
    index = C.load_json(os.path.join(ASSETS, 'scenes', '_index.json'), {}) or {}
    placement = C.load_json(os.path.join(ASSETS, 'npc', '_placement.json'), {}) or {}
    alias = C.load_json(os.path.join(ASSETS, 'scenes', '_aliases.json'), {}) or {}
    alias_entries = alias.get('entries') or {}

    # 1) 原作房间表： (chapter, id) -> 显示名
    by_id = {}
    for ch, info in (rooms.get('chapters') or {}).items():
        for r in (info.get('rooms') or []):
            by_id[(ch, r.get('id'))] = (r.get('name') or '').strip()

    # 2) 总索引：scene_id -> {chapter, area, scene_name, original_room_id}
    scenes = {}
    for ch, chv in (index.get('chapters') or {}).items():
        ch_name = chv.get('name') or ch
        for area, av in (chv.get('areas') or {}).items():
            area_name = av.get('name') or area
            for sid, sv in (av.get('scenes') or {}).items():
                scenes[sid] = {'chapter': ch, 'chapter_name': ch_name,
                               'area': area, 'area_name': area_name,
                               'scene_name': sv.get('name') or '',
                               'original_room_id': sv.get('original_room_id')}

    plist = placement.get('placement') or []
    out = {'schema_version': 1,
           'note': ('房间专属回忆的数据面：NPC → 房间 → 可读说法（含区域中文名）。'
                    '三级证据 original/derived/authored 与站位表同口径，'
                    '没房间的人不训练、不编安身之所。'),
           'source': {
               'index': 'assets/scenes/_index.json（章节/区域/场景三级，含 name 与 original_room_id）',
               'rooms': 'assets/scenes/_original_rooms.json（原作反编译 scr_roomname）',
               'placement': 'assets/npc/_placement.json 的 placement[]',
               'aliases': 'assets/scenes/_aliases.json',
               'missing': ('第87轮-每人一个家/_evidence/homes87.json 已在"已暂存删除"里，'
                           '故退回用 placement 的站位 + 场景索引'),
           },
           'npcs': {}}

    stat = {'original': 0, 'derived': 0, 'authored': 0, 'no_room': 0}
    for p in plist:
        nid = p.get('id')
        if not nid:
            continue
        scene = p.get('scene') or ''
        ch = _chapter_of(scene) or (scenes.get(scene, {}) or {}).get('chapter', '')
        rid = p.get('room_id')
        meta = scenes.get(scene) or {}
        tail = _tail_of(scene)

        room_name = by_id.get((ch, rid), '') if (ch and rid is not None) else ''
        if room_name in ('---', '??????'):
            room_name = ''
        area_name = meta.get('area_name') or ''
        scene_name = meta.get('scene_name') or ''
        human = _humanize(tail)

        if room_name:
            src = 'original'
            label = '%s·%s' % (area_name, room_name) if area_name else room_name
        elif scene_name:
            src = 'derived'
            label = scene_name
        elif area_name or human:
            src = 'derived' if area_name else 'authored'
            label = area_name or human
        elif tail:
            src = 'authored'
            label = tail
        else:
            stat['no_room'] += 1
            continue
        stat[src] += 1

        # 中文别称（别名表是 中文→英文关键词，这里反向找）
        hay = (tail + ' ' + room_name + ' ' + (meta.get('area') or '')).lower()
        cn_alias = [cn for cn, kws in alias_entries.items()
                    if any(k and k.lower() in hay for k in kws)]

        out['npcs'][nid] = {
            'room_id': rid, 'chapter': ch, 'room_raw': p.get('room_raw') or '',
            'scene': scene, 'area_name': area_name, 'scene_name': scene_name,
            'room_name': room_name, 'label': label, 'cn_alias': cn_alias[:4],
            'source': src, 'evidence': (p.get('evidence') or '')[:160],
        }

    out['stats'] = stat
    out['counts'] = {'placed': len(plist), 'with_room': len(out['npcs']),
                     'unplaced': len(placement.get('unplaced') or {})}
    os.makedirs(OUT_DIR, exist_ok=True)
    C.write_text(OUT_JSON, json.dumps(out, ensure_ascii=False, indent=1) + '\n')

    print('房间数据面已落盘：%s' % OUT_JSON)
    print('  placement %d 条 ⇒ 有房间说法 %d 人' % (len(plist), len(out['npcs'])))
    print('  证据分级：original %d / derived %d / authored %d / 无 %d'
          % (stat['original'], stat['derived'], stat['authored'], stat['no_room']))
    print('  无站位（不训练）：%d 人' % len(placement.get('unplaced') or {}))
    for nid, v in list(out['npcs'].items())[:8]:
        print('   %-12s [%-8s] %-30s alias=%s'
              % (nid, v['source'], v['label'][:30], v['cn_alias']))
    return 0


def tier_prompt(npc, info, tier):
    """第 tier 次进入房间时，要他主动开口。★ 用**舞台指示**当输入，不是玩家提问。"""
    place = info.get('label') or ''
    alias = '（也叫%s）' % '、'.join(info['cn_alias']) if info.get('cn_alias') else ''
    if tier == SILENT_TIER:
        return ('（你又一次走进%s%s。这次你什么也没说。）' % (place, alias))
    if tier == 1:
        return ('（你今天第一次走进%s%s。这里有些东西让你想起了以前。）' % (place, alias))
    if tier == 2:
        return ('（你今天第二次走进%s%s。刚才那句话之后，你又多想起了一点。）' % (place, alias))
    return ('（你今天第三次走进%s%s。这次只是经过。）' % (place, alias))


def room_system(card, info, patch=''):
    """system **全程固定**（只说明"你在哪"），四档的差别一律放进 user 的舞台指示。

    ★ 为什么（实测）：第一版把"第几次进入"写进 system ⇒ 四档四份 system ⇒
      每档都要重付一次冷 prefill（实测 154s / 4 档）。合成一段对话后
      只需一次冷 prefill，34 人从约 1.4 小时降到约 0.6 小时。

    ★★ 2026-10-24 修：这里原来写死 `D.system_for(card, '')` —— 把 `_index.json`
      里该角色的**纠正句整条丢掉**了。后果不是"少一句提示"，而是**已经修掉的毛病
      在房间轮重新长出来**（susie/rouxls 的"括号写动作"就是这么被修掉的）。
      训练器把纠正句当资产存着，另一条入口却不用，等于白修。
    """
    base = D.system_for(card, patch)
    extra = ['', '【你现在的处境】', '你正站在%s。' % (info.get('label') or '一个房间')]
    if info.get('cn_alias'):
        extra.append('这一带也常被叫作%s。' % '、'.join(info['cn_alias']))
    extra.append('你知道这里的一草一木 —— 想说话的时候是**主动开口**，不是等别人问。')
    return base + '\n'.join(extra)


_PATCH_CACHE = {}


def patch_of(nid):
    """取该角色的纠正句（`_training/_index.json` 的 `patches`）。"""
    if not _PATCH_CACHE:
        idx = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
        _PATCH_CACHE.update(idx.get('patches') or {})
    return _PATCH_CACHE.get(nid, '') or ''


#: 舞台指示（user 侧）。四档差别全在这里。
#: ★★ 每条都要把**要求本身**写出来，不能只说"想主动说一句" —— 实测那样会退化成
#:   应景寒暄（"这地方我挺习惯的"），既没有回望、也不递减。系统的固定段只负责
#:   "你在哪、你可以主动开口"，**强度**必须留在每一档的指示里。
def tier_prompt(npc, info, tier):
    place = info.get('label') or ''
    if tier == SILENT_TIER:
        return ('（你又走进%s。这一趟你什么也没打算说 —— **只输出空字符串**，不要解释、'
                '不要写"（沉默）"之类的占位。）' % place)
    if tier == 1:
        return ('（你今天第一次走进%s。这里有些东西让你想起了以前 —— 主动说一句**往事**：'
                '用回忆的语气（那时候 / 当时 / 记得），不要写成正在发生的事；'
                '要具体，提到这个地方的细节。）' % place)
    if tier == 2:
        return ('（你今天第二次走进%s。再主动补一句，**必须比刚才那句短**，'
                '并且不要重复刚才说过的话；补的是另一个细节。）' % place)
    return ('（你今天第三次走进%s。只是路过，**只说一句很短的话（十字以内）**，'
            '别再多说。）' % place)


def run_one(card, nid, info, verbose=False, patch=''):
    """一段对话里连做四档：只付一次冷 prefill。"""
    turns = []
    t0 = time.time()
    system = room_system(card, info, patch)
    msgs = [{'role': 'system', 'content': system}]
    prev = []
    for tier in TIERS:
        user = tier_prompt(card, info, tier)
        msgs.append({'role': 'user', 'content': user})
        attempts, final = [], None
        for attempt in range(MAX_RETRIES + 1):
            D.wait_for_memory()
            try:
                text, st = C.chat(msgs, seed=C.stable_seed(nid, 'room', tier, attempt),
                                  num_ctx=CTX, num_predict=PREDICT,
                                  temperature=C.TEMPERATURE + 0.15 * attempt)
            except Exception as e:
                attempts.append({'attempt': attempt, 'error': repr(e)[:160], 'text': ''})
                continue
            bad, soft = C.gate_reply(text, user, prev,
                                     card['name'], card.get('_persona_text') or '')
            rec = {'attempt': attempt, 'text': text, 'violations': [list(x) for x in bad],
                   'stats': st}
            attempts.append(rec)
            final = rec
            if not bad:
                break
        text = (final or {}).get('text', '') or ''
        msgs.append({'role': 'assistant', 'content': text})
        prev.append(text)
        turns.append({'tier': tier, 'user': user, 'text': text,
                      'violations': (final or {}).get('violations') or [],
                      'chars': len(text.strip()),
                      'attempts': attempts})
        if verbose:
            print('    T%d [%d字] %s' % (tier, len(text.strip()), text.strip()[:50]), flush=True)
    return {'schema_version': 1, 'id': nid, 'name': card['name'],
            'room': info, 'turns': turns,
            'cost_s': round(time.time() - t0, 1),
            'metrics': room_metrics(turns, info)}


#: 房间里常见的东西 —— 判"他是不是真的在说这个地方"的**弱信号**。
#: ★ 为什么要这个（实测）：第一版只查房间名，susie 说「我记得就是这扇门了」被判
#:   房间命中 0/4 —— 可是**人在自己屋里本来就不会念门牌号**。
#:   判据要么能识别"具体到这个地方的细节"，要么就别装作能判。
ROOM_PROPS = ('门', '窗', '床', '桌', '椅', '墙', '地板', '走廊', '楼梯', '角落',
              '灯', '屋顶', '台阶', '柜子', '画', '钟', '床头', '门槛', '院子', '街道',
              # ★ 第113轮c 补：实测 ralsei 说「喷泉边打水仗」「台阶上聊天」、
              #   susie 说「躲在这棵老橡树下」「阳光特别刺眼」—— 都是真·房间细节，
              #   但第一版词表里没有「树/阳光/喷泉」，被判成命中 0。
              '树', '橡树', '草', '花', '石头', '水池', '喷泉', '长椅', '栏杆',
              '地毯', '书架', '照片', '窗帘', '桥', '井', '阳光', '阴影', '灰尘',
              '吱呀', '锈', '裂缝')


def _room_kw(info):
    """房间相关词：中文地名块 + 别名 + （兜底）英文 id。"""
    kws = set()
    for f in ('area_name', 'label', 'room_name', 'scene_name'):
        for w in re.findall(r'[\u4e00-\u9fff]{2,4}', (info.get(f) or '')):
            kws.add(w)
    for w in re.findall(r'[A-Za-z]{4,}', (info.get('room_raw') or '')):
        kws.add(w.lower())
    kws.update(info.get('cn_alias') or [])
    return [k for k in kws if k]


def room_metrics(turns, info):
    import train30 as T
    kws = _room_kw(info)
    per = []
    for t in turns:
        txt = t['text'] or ''
        low = txt.lower()
        place = [k for k in kws if k and (k.lower() in low)]
        props = [w for w in ROOM_PROPS if w in txt]
        r = T.retro_of(txt)
        per.append({'tier': t['tier'], 'chars': t['chars'],
                    'place_hit': place, 'prop_hit': props,
                    'room_hit': bool(place or props),
                    'retro': r['state'],
                    'violations': [c for c, _ in t['violations']]})
    lens = [p['chars'] for p in per]
    # 递减：前三档不增（允许相等），第 4 档必须近乎沉默
    mono = (lens[0] >= lens[1] >= lens[2] >= 0) if len(lens) >= 3 else False
    return {'per_tier': per, 'monotone': mono,
            'silent_at_4': lens[3] <= 4 if len(lens) >= 4 else False,
            'room_hit_tiers': sum(1 for p in per if p['room_hit']),
            'place_hit_tiers': sum(1 for p in per if p['place_hit']),
            'prop_hit_tiers': sum(1 for p in per if p['prop_hit']),
            'lookback_tiers': sum(1 for p in per if p['retro'] == 'lookback'),
            'violation_tiers': sum(1 for p in per if p['violations'])}


def train(argv):
    data = C.load_json(OUT_JSON, {}) or {}
    npcs = data.get('npcs') or {}
    if not npcs:
        print('!! 先跑 --build')
        return 2
    only = [x.strip() for x in argv[argv.index('--only') + 1].split(',')] if '--only' in argv else None
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else None
    verbose = '--verbose' in argv
    force = '--force' in argv

    os.makedirs(RAW_ROOM, exist_ok=True)
    os.makedirs(TR_ROOM, exist_ok=True)
    roster, _ = C.load_roster()
    by_id = {r['id']: r for r in roster}

    done = {f[:-6] for f in os.listdir(RAW_ROOM) if f.endswith('.jsonl')} if not force else set()
    todo = [n for n in npcs if n in by_id and n not in done]
    if only:
        todo = [x for x in todo if x in only]
    if limit:
        todo = todo[:limit]

    print('房间主动对话：待跑 %d 人（有房间且有训练卡），每人 %d 档 ⇒ %d 次生成'
          % (len(todo), len(TIERS), len(todo) * len(TIERS)))
    if not todo:
        return 0
    if not C.model_loaded():
        print('预热中…')
        print('  =>', C.warmup())

    t_all = time.time()
    for i, nid in enumerate(todo, 1):
        card = D.load_card(nid, by_id)
        if card is None:
            print('[跳过] %s：训练卡缺失' % nid)
            continue
        print('[%d/%d] %s（%s）' % (i, len(todo), nid, npcs[nid]['label'][:20]), end='', flush=True)
        rec = run_one(card, nid, npcs[nid], verbose=verbose, patch=patch_of(nid))
        C.append_jsonl(os.path.join(RAW_ROOM, nid + '.jsonl'), rec)
        m = rec['metrics']
        print('  房间命中 %d/4 · 回望 %d · 递减 %s · 沉默 %s · %.0fs'
              % (m['room_hit_tiers'], m['lookback_tiers'],
                 'Y' if m['monotone'] else 'N', 'Y' if m['silent_at_4'] else 'N',
                 rec['cost_s']), flush=True)
        time.sleep(3)
    print('完成 %d 人，用时 %.1f 分钟' % (len(todo), (time.time() - t_all) / 60))
    return 0


def report():
    if not os.path.isdir(RAW_ROOM):
        print('还没有房间对话记录')
        return 1
    rows = []
    for f in sorted(os.listdir(RAW_ROOM)):
        if f.endswith('.jsonl'):
            recs = C.read_jsonl(os.path.join(RAW_ROOM, f))
            if recs:
                rows.append(recs[-1])
    if not rows:
        print('空')
        return 1
    # ★★ 用**当前判据**重算，不读 jsonl 里存着的旧 metrics ——
    #   判据改过（比如补了"树/阳光/喷泉"这些房间细节词）之后，
    #   读旧 metrics 等于拿旧尺子量新数据。原始对话在 `turns` 里，随时能重算。
    for r in rows:
        r['metrics'] = room_metrics(r['turns'], r['room'])
    n = len(rows)
    hit = sum(r['metrics']['room_hit_tiers'] for r in rows)
    lb = sum(r['metrics']['lookback_tiers'] for r in rows)
    mono = sum(1 for r in rows if r['metrics']['monotone'])
    sil = sum(1 for r in rows if r['metrics']['silent_at_4'])
    vio = sum(r['metrics']['violation_tiers'] for r in rows)
    L = ['# 第113轮c · 房间专属回忆 + 主动开口（频次递减）', '',
         '> 用户 2026-10-24 口径：「在特定 room 有特殊回忆，主动提出对话等，你也训练一下，'
         '当然，频次会递减」。', '',
         '## 总体', '', '| 项 | 值 |', '|---|---|',
         '| 已训练角色 | **%d 人**（有房间归属且有训练卡） |' % n,
         '| 房间命中 | %d/%d 档（提到该房间的具体东西）|' % (hit, n * 4),
         '| 回望视角 | %d/%d 档 |' % (lb, n * 4),
         '| 长度递减（档1≥2≥3）| **%d/%d 人** |' % (mono, n),
         '| 第 4 档闭嘴 | **%d/%d 人** |' % (sil, n),
         '| 硬违规 | %d 档 |' % vio, '',
         '## 逐角色', '', '| 角色 | 房间（证据）| 房间命中 | 回望 | 递减 | 沉默 |',
         '|---|---|---|---|---|---|']
    for r in sorted(rows, key=lambda r: -r['metrics']['room_hit_tiers']):
        info = r['room']
        L.append('| `%s` %s | %s（%s）| %d/4 | %d/4 | %s | %s |' % (
            r['id'], r['name'], info.get('label', '')[:24], info.get('source', ''),
            r['metrics']['room_hit_tiers'], r['metrics']['lookback_tiers'],
            '✓' if r['metrics']['monotone'] else '✗',
            '✓' if r['metrics']['silent_at_4'] else '✗'))
    L += ['', '## 一个完整样本（看四档是不是真的递减）', '']
    if rows:
        r = rows[0]
        L.append('`%s` @ %s' % (r['id'], r['room'].get('label')))
        L.append('')
        for t in r['turns']:
            L.append('**第 %d 次进入 → %d 字**' % (t['tier'], t['chars']))
            L.append('')
            L.append('> %s' % (t['text'].strip() or '（沉默）'))
            L.append('')
    C.write_text(os.path.join(EVID, 'report_room113.md'), '\n'.join(L) + '\n')
    print('已写：%s' % os.path.join(EVID, 'report_room113.md'))
    print('命中 %d/%d · 回望 %d/%d · 递减 %d/%d · 沉默 %d/%d'
          % (hit, n * 4, lb, n * 4, mono, n, sil, n))
    return 0


def main(argv):
    if '--build' in argv:
        return build()
    if '--train' in argv:
        return train(argv)
    if '--report' in argv:
        return report()
    print(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
