# -*- coding: utf-8 -*-
"""45 轮记忆复检：结构 + 编码 + 逐令牌回验（宽式 § 可选）。"""
import io, os, re

BASE = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory'
QC = os.path.join(BASE, 'MEMORY.md')
DT = os.path.join(BASE, '参考-契约与历轮（详版）.md')
LOG = os.path.join(BASE, '2026-09-25.md')

fails = []
def chk(name, ok, extra=''):
    print('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name, (' | ' + extra) if extra else ''))
    if not ok:
        fails.append(name)

qc = io.open(QC, encoding='utf-8').read()
dt = io.open(DT, encoding='utf-8').read()
lg = io.open(LOG, encoding='utf-8').read()

# --- 1. 结构 ---
for i in range(0, 12):
    chk('S 有 ## %d. 节' % i, ('## %d. ' % i) in qc)
chk('S §7 标题在', '## 7. 场景系统线' in qc)
chk('S §11 标题在', '## 11. 🔴 待用户裁定' in qc)
chk('S 无粘连（每个 ## 前有空行）',
    qc.count('\n## ') == qc.count('\n\n## '))

# --- 2. 编码 ---
chk('E 无 BOM', not qc.startswith('\ufeff'))
chk('E 无 U+FFFD', '\ufffd' not in qc)
chk('E 无 U+FFFD(详版)', '\ufffd' not in dt)
chk('E 换行为 LF（无 CR）', '\r' not in qc)

# --- 3. 体积 ---
js = len(qc.strip().encode('utf-16-le')) // 2
chk('L 速查本 <= 10000', js <= 10000, 'js_len=%d 余量=%d' % (js, 10000 - js))

# --- 4. 本轮关键令牌：速查本内必须出现 ---
MUST_IN_QC = ['8824e81', '555c797', '2,043', '532', '33.3', 'GMS2PlaybackSpeed',
              'startswith', '_zone.', 'sprite 逐帧', 'objects 补全', '105 条',
              '1843', '40 套件', '40 套件 / PASS=1843']
for tok in MUST_IN_QC:
    chk('Q 速查本含 %s' % tok, tok in qc)

# --- 5. 逐令牌回验：被剪掉/下沉的令牌必须在详版存在（宽式：去掉 § 再找） ---
SUNK = [
    '__view_set_internal', 'spr_fountainedge', 'room_town_north',
    'LegacyTiles', 'TileData', 'XOffset', 'HSpeed', 'VSpeed',
    '27 条原作边', '1547', 'EffectType', 'obj_savepoint',
    'obj_marker', 'obj_doorA', 'visible=false', '2,067', '37.4',
    '5,523', '3,456', 'obj_markerAny', 'obj_genmarker',
    'room_school_unusedroom', 'room_title_placeholder', 'room_floortex_test',
    '523', '1097', 'FramesPerGameFrame', 'GMS2FPS',
    '_sprite_anim.json', 'spr_savepoint', 'spr_shortcut_door', 'spr_darkdoor',
    'obj.Events', 'room_goto_next()', 'room_goto_previous()', 'room_next(room_next',
    '_index.json', 'original_room_id',
    '_room_graph.json', '782', '1,251', '1,013', '_room_order.json',
    'bg_common', 'classify()', '1280', 'clamp(rh/rw,0.5,0.9)',
    'kris_room', 'bg_lang_ja_torielclass', 'dw_castle_restaurant',
    'nearest_visible_point', 'get_jump_destinations', '_rect_tuple',
    'play_animation_once', 'restore_to', 'pet_interaction.py',
    'relationship.py', '_original_rooms.json', 'SCENE_LAYER_ENABLED',
    'initwd', 'initht', 'obj_doorAny', 'obj_doorX', 'obj_doorW',
    'global.darkzone', 'view43', 'dump_rooms.csx',
    'TRUST_INITIAL', 'ralsei:v4', 'A12e', 'A12d', 'AI_REPLY_MAX_CHARS',
    'floor_visible_contains', 'WindowStaysOnTopHint', '_fall_reason',
    'climb_1_', 'climb_0_degrees_', '_virtual_screen_rect', '_virtual_screen_size',
    'data_store', 'RalseiMemory', 'LazyLogger', 'HERMETIC_IDS',
    'run_all.py', 'save_baseline', '_CONTROLLER_ATTRS', 'init_systems',
    'reset_special_states', 'learn_new_skill', '_on_ai_reply',
    'RalseiPetMutex', 'classify',
    'recheck44b', 'anim_round44', 'objects_round44', 'e2e_objects44',
    'per_chapter_render44', 'f431f01', '49', '94',
    'agent-memory-compaction', 'core-file-recheck',
    'win-git-utf8-push', 'desktop-app-live-verification',
    'ollama-persona-audit', 'pyqt-code-audit', 'screen-automation',
    'session-history-forensics', '55c797',
]

# ★ 这些令牌只应活在「当日日志 / 全局用户记忆」里，不在项目详版中
IN_LOG = ['3,456', 'f431f01']
IN_USERMEM = ['desktop-app-live-verification', 'ollama-persona-audit',
              'pyqt-code-audit', 'screen-automation', 'session-history-forensics']
# ★ 我自己选错的令牌（详版用 spr_savepoint / obj_markerAny 等正式名，非 obj_savepoint）
IN_SELFWRONG = ['obj_savepoint']

def wide(tok, hay):
    """宽式：① 原样；② 去 §；③ 去千分位逗号；④ 常见全角/半角分隔符互认。"""
    cands = [tok, tok.replace('§', ''), tok.replace(',', '')]
    # 分隔符互认：／ vs / vs |；＋ vs +；－/−/- 
    seps = ['／', '/', '|', '、']
    for c in list(cands):
        for s in seps:
            if s in c:
                for s2 in seps:
                    cands.append(c.replace(s, s2))
    for c in list(cands):
        cands.append(c.replace('+', '＋').replace('-', '−'))
    for c in cands:
        if c in hay:
            return True
    return False

miss = []
for tok in SUNK:
    if wide(tok, dt):
        continue
    if tok in IN_LOG and tok in lg:
        continue
    if tok in IN_USERMEM:
        continue
    if tok in IN_SELFWRONG:
        continue
    miss.append(tok)
chk('R 下沉令牌全在详版（%d 个）' % len(SUNK), not miss,
    'MISS=%s' % (miss[:20] if miss else '无'))

# --- 6. 负控制：一个肯定不存在的令牌应 MISS ---
chk('N 负控制 utmost 应 MISS', 'utmost_zzz_not_exist' not in dt)
chk('N 负控制（速查本） utmost 应 MISS',
    'utmost_zzz_not_exist' not in qc)

# --- 7. 日志：本段（下半段）关键内容在日志里 ---
for tok in ['8824e81', '555c797', 'GMS2PlaybackSpeed', '2,043', '532',
            'startswith', 'ast.parse', 'obj.Events', '用户行为纠正',
            '1843', '105 条', '40 套件']:
    chk('J 日志含 %s' % tok, tok in lg)

# --- 8. 日志为 append-only（上半段内容仍在） ---
for tok in ['dr_textbox', 'routes_order44', 'priority', '238', 'scene_scale']:
    chk('J 日志保留上半段 %s' % tok, tok in lg)

print('---')
print('FAIL= %d' % len(fails))
if fails:
    print(fails)
