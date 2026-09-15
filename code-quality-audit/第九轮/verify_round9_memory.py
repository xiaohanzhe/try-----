# -*- coding: utf-8 -*-
"""第九轮验证（四）：拟人记忆系统 + 存储位置迁移。

分组：
  S 存储位置（设备优先 / 桌面兜底 / 环境变量强制）
  M 迁移（先写成功再删源、留新不丢旧、清空桌面副本、只删空目录）
  F 选择性记忆（小片段 / 关键记忆 / 去重即复习 / 体量上限）
  R 召回与场景重构（倒排索引 + 联想扩散 + 复习强化 + 出口文案）
  G 遗忘（衰减 / 日摘要 / 保护期 / 关键记忆免疫 / 硬上限）
  P 持久化（schema 2 往返 / 坏文件兜底 / 旧文件继承 / 节流落盘）
  I 集成契约（dialogue_ui / main 的接线，tokenize 剥注释与字符串）

全程把 RALSEI_MEMORY_DIR / RALSEI_DESKTOP 指向临时目录 —— **绝不碰真机记忆**。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import tokenize
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
# 临时目录放系统 TEMP：既不污染仓库（_evidence 是入库目录），
# 也不会因上一轮的残留文件影响本次断言。
TMP = tempfile.mkdtemp(prefix='ralsei_mem9_')
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(TMP, 'dev')
for p in (MODS, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

import memory_store as ST          # noqa: E402
from memory_system import MemorySystem  # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name + ('' if cond else '   <<< ' + str(detail)))


def set_env(device_dir=None, device_off=False, desktop=None):
    if device_dir is None:
        os.environ.pop('RALSEI_MEMORY_DIR', None)
    else:
        os.environ['RALSEI_MEMORY_DIR'] = device_dir
    if device_off:
        os.environ['RALSEI_MEMORY_DEVICE'] = 'off'
    else:
        os.environ.pop('RALSEI_MEMORY_DEVICE', None)
    if desktop is None:
        os.environ.pop('RALSEI_DESKTOP', None)
    else:
        os.environ['RALSEI_DESKTOP'] = desktop


class FakeParent(object):
    """最小父对象：不提供 config_manager（add_memory 的隐私门就得能容忍缺失）。"""
    def __init__(self):
        self.api_enabled = False


def new_ms(dirname='ms'):
    """在临时目录里造一个干净的 MemorySystem（旧记忆路径也隔离）。"""
    d = os.path.join(TMP, dirname)
    os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_no_such_legacy.json')
    set_env(device_dir=d, desktop=os.path.join(TMP, 'Desktop'))
    ms = MemorySystem(FakeParent())
    return ms


def read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def code_only(src):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            out.append('\n' if tok.type in (tokenize.COMMENT, tokenize.STRING) else tok.string)
    except Exception:
        return src
    return ''.join(out)


def func_src(src, name):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ''
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ''
    return ''


# ================================================================== S 存储位置
def test_storage():
    print('\n[S] 存储位置')
    set_env(device_off=True, desktop=os.path.join(TMP, 'D1'))
    d, on_dev, _dev = ST.default_memory_dir()
    ok('S1 设备关闭 → 桌面兜底 <桌面>/memory', (not on_dev) and d == os.path.join(TMP, 'D1', 'memory'), d)

    set_env(device_dir=os.path.join(TMP, 'D2'), desktop=os.path.join(TMP, 'D1'))
    d2, on_dev2, dev2 = ST.default_memory_dir()
    ok('S2 设备存在 → 用设备目录', on_dev2 and d2 == os.path.join(TMP, 'D2'), (d2, on_dev2))
    ok('S3 记忆文件名为 memory.json', os.path.basename(ST.memory_file_in(d2)) == 'memory.json', None)

    set_env(device_off=True)
    ok('S4 关闭设备时 find_device_dir(create=False) → None', ST.find_device_dir(create=False) is None, None)
    set_env(device_dir=os.path.join(TMP, 'D2'))
    ok('S5 强制设备目录时 find_device_dir 原样返回', ST.find_device_dir(create=False) == os.path.join(TMP, 'D2'), None)


# ===================================================================== M 迁移
def test_migrate():
    print('\n[M] 桌面 → 设备的搬运')
    fb = os.path.join(TMP, 'DeskM', 'memory')
    dev = os.path.join(TMP, 'DevM')
    os.makedirs(fb, exist_ok=True)
    os.makedirs(dev, exist_ok=True)
    set_env(device_dir=dev, desktop=os.path.join(TMP, 'DeskM'))

    # M1：设备侧为空 → 直接搬过去，桌面文件与空目录都清掉
    with open(os.path.join(fb, 'memory.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 2, 'saved_at': 100.0,
                   'fragments': [{'text': '桌面上的旧记忆'}]}, fh, ensure_ascii=False)
    r = ST.migrate_from_fallback(dev)
    moved_ok = (r.get('moved') and
                os.path.exists(os.path.join(dev, 'memory.json')) and
                not os.path.exists(os.path.join(fb, 'memory.json')) and
                not os.path.isdir(fb))
    ok('M1 设备为空时搬入并清理桌面副本与空目录', moved_ok, r)

    # M2：两边都有内容、桌面更新 → 保留桌面的那份；旧的设备版留档
    fb2 = os.path.join(TMP, 'DeskM2', 'memory')
    dev2 = os.path.join(TMP, 'DevM2')
    os.makedirs(fb2, exist_ok=True)
    os.makedirs(dev2, exist_ok=True)
    set_env(device_dir=dev2, desktop=os.path.join(TMP, 'DeskM2'))
    with open(os.path.join(fb2, 'memory.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 2, 'saved_at': 200.0, 'level': 9,
                   'fragments': [{'text': '较新的桌面记忆'}]}, fh, ensure_ascii=False)
    with open(os.path.join(dev2, 'memory.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 2, 'saved_at': 100.0, 'level': 3,
                   'fragments': [{'text': '较旧的设备记忆'}]}, fh, ensure_ascii=False)
    r2 = ST.migrate_from_fallback(dev2)
    tgt = json.loads(read(os.path.join(dev2, 'memory.json')))
    old = json.loads(read(os.path.join(dev2, 'memory.old.json')))
    ok('M2 桌面更新 → 用桌面的，旧的设备版留档不丢',
       r2.get('kept') == 'fallback' and tgt.get('level') == 9 and old.get('level') == 3,
       (r2.get('kept'), tgt.get('level'), old.get('level')))
    ok('M3 搬运后桌面副本被清掉', not os.path.exists(os.path.join(fb2, 'memory.json')), None)

    # M4：设备侧更新 → 保留设备版，桌面那份留档
    fb3 = os.path.join(TMP, 'DeskM3', 'memory')
    dev3 = os.path.join(TMP, 'DevM3')
    os.makedirs(fb3, exist_ok=True)
    os.makedirs(dev3, exist_ok=True)
    set_env(device_dir=dev3, desktop=os.path.join(TMP, 'DeskM3'))
    with open(os.path.join(fb3, 'memory.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 2, 'saved_at': 100.0, 'level': 2}, fh, ensure_ascii=False)
    with open(os.path.join(dev3, 'memory.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 2, 'saved_at': 300.0, 'level': 7}, fh, ensure_ascii=False)
    r3 = ST.migrate_from_fallback(dev3)
    tgt3 = json.loads(read(os.path.join(dev3, 'memory.json')))
    old3 = json.loads(read(os.path.join(dev3, 'memory.old.json')))
    ok('M4 设备更新 → 保留设备版，桌面那份留档',
       r3.get('kept') == 'target' and tgt3.get('level') == 7 and old3.get('level') == 2,
       (r3.get('kept'), tgt3.get('level'), old3.get('level')))

    # M5：桌面没有文件 → 明确返回没搬
    dev4 = os.path.join(TMP, 'DevM4')
    os.makedirs(dev4, exist_ok=True)
    set_env(device_dir=dev4, desktop=os.path.join(TMP, 'DeskM4'))
    r4 = ST.migrate_from_fallback(dev4)
    ok('M5 桌面无记忆 → moved=False 且不报错', (not r4.get('moved')) and '没有' in str(r4.get('reason')), r4)

    # M6：目标就是兜底目录 → 拒绝自我搬运
    set_env(device_off=True, desktop=os.path.join(TMP, 'DeskM5'))
    same = ST.fallback_dir()
    os.makedirs(same, exist_ok=True)
    r5 = ST.migrate_from_fallback(same)
    ok('M6 目标即兜底目录 → 不搬（防自我删除）', not r5.get('moved'), r5)


# ========================================================= F 选择性记忆
def test_fragments():
    print('\n[F] 选择性记忆（小片段 / 关键记忆）')
    ms = new_ms('msF')
    f1 = ms.add_fragment('我今天玩了很久的塞尔达，剧情特别感人', who='user')
    ok('F1 正常写入片段（含 id/日/keywords/强度）',
       isinstance(f1, dict) and f1.get('id') and f1.get('day') and f1.get('kw')
       and 0 < float(f1.get('strength', 0)) <= 1, f1)
    ok('F2 太短（<2 字）不算片段', ms.add_fragment('嗯', who='user') is None, None)

    long_text = '这是一句很长的台词。' * 40
    f2 = ms.add_fragment(long_text, who='ralsei')
    ok('F3 超长片段被截断到上限',
       len(str(f2.get('text'))) <= ms.FRAGMENT_TEXT_MAX, len(str(f2.get('text'))))

    # 去重 = 复习
    n0 = len(ms.fragments)
    s_before = float(f1.get('strength'))
    f1b = ms.add_fragment('我今天玩了很久的塞尔达，剧情特别感人', who='user')
    ok('F4 2 小时内重复同句 → 不新增，只当作复习',
       len(ms.fragments) == n0 and f1b is not None
       and int(f1b.get('rehearsals', 0)) >= 2
       and float(f1b.get('strength')) >= s_before, (len(ms.fragments), f1b.get('rehearsals')))

    # 显著性：主人说的 > 自己说的（用不同措辞，避免被"重复即复习"合并）
    fa = ms.add_fragment('我想聊聊量子物理的波函数坍缩', who='user')
    fb = ms.add_fragment('我在想量子物理的波函数坍缩挺难懂的', who='ralsei')
    ok('F5 主人说的话显著性更高', float(fa.get('salience')) > float(fb.get('salience')),
       (fa.get('salience'), fb.get('salience')))

    # 关键记忆去重
    ms.remember_key('achievement_unlocked', '解锁成就：第一次陪主人看完一整部电影')
    k2 = ms.remember_key('achievement_unlocked', '解锁成就：第一次陪主人看完一整部电影')
    ok('F6 同一条关键记忆不去重堆积（只累计次数）',
       len([k for k in ms.keys if k.get('kind') == 'achievement_unlocked']) == 1
       and int(k2.get('count', 0)) >= 2, k2.get('count'))

    # 体量上限
    big = new_ms('msF2')
    for i in range(big.MAX_FRAGMENTS + 40):
        big.add_fragment('编号%d 我们在聊一个很长很长的第%d个话题内容' % (i, i), who='user',
                         importance=0.4, now=time.time() - (i + 1) * 90000)
    ok('F7 片段数受上限约束', len(big.fragments) <= big.MAX_FRAGMENTS, len(big.fragments))


# ================================================== R 召回与场景重构
def test_recall():
    print('\n[R] 召回 / 联想扩散 / 场景重构')
    ms = new_ms('msR')
    # f1/f2 之间靠"塞尔达"共现；f2/f3 之间靠"游戏"共现 → cue 只有"塞尔达"时，
    # 人也能顺着联想把"手柄/主机"那件事想起来。
    ms.add_fragment('我最近在玩塞尔达这个游戏，剧情特别感人', who='user')
    ms.add_fragment('塞尔达这个游戏的配乐也很好听，我很喜欢', who='user')
    ms.add_fragment('不过那个游戏的主机版手柄手感更好', who='user')
    ms.add_fragment('我下午去公园散步了，天气很好', who='user')

    hits = ms.recall('塞尔达的剧情怎么样', limit=4)
    top = hits[0] if hits else {}
    ok('R1 直接命中并排第一', '塞尔达' in str(top.get('text')), top)

    # 联想扩散：cue 只有"塞尔达"，但"游戏"把第三条（手柄/主机）带出来
    ok('R2 联想扩散：共现词把相邻话题也带出来',
       any('手柄' in str(h.get('text')) for h in hits), [h.get('text') for h in hits])

    # 复习强化
    frag = [f for f in ms.fragments if '塞尔达' in str(f.get('text'))][0]
    s_before = float(frag.get('strength'))
    ms.recall('再聊聊塞尔达', limit=3)
    ok('R3 被想起 → 可回忆度提升（复习效应）',
       float(frag.get('strength')) > s_before, (s_before, frag.get('strength')))

    # 出口文案
    txt = ms.recall_text('塞尔达')
    ok('R4 recall_text 有命中 → 含"零星的回忆"与原文',
       ('零星的回忆' in txt) and ('塞尔达' in txt), txt[:120])
    ok('R5 recall_text 完全无关 → 返回空串（不硬编）',
       ms.recall_text('涡轮增压直喷发动机的压缩比') == '', None)

    # 关键记忆优先
    ms.remember_key('important_dates', '主人的生日是 3 月 14 日', importance=1.0)
    hits2 = ms.recall('主人的生日是哪天', limit=3)
    ok('R6 关键记忆优先出现在召回结果里',
       any(h.get('is_key') for h in hits2), [h.get('text') for h in hits2])

    # 场景重构
    ms2 = new_ms('msR2')
    ms2.add_fragment('那天我们聊到塞尔达的剧情，你说最喜欢里面的音乐', who='user')
    ms2.add_fragment('然后你还说了你小时候也玩过类似的游戏', who='user')
    scene = ms2.reconstruct_scene('塞尔达')
    ok('R7 场景重构能拼出叙述', ('我记得' in scene or '我们正聊着' in scene), scene)

    # 索引生效（不走全表扫描）
    ok('R8 倒排索引已建立', ms.get_memory_stats().get('index_keys', 0) > 0,
       ms.get_memory_stats())

    # 同一条不重复出现
    ids = [str(h.get('text')) for h in hits]
    ok('R9 召回结果不重复', len(ids) == len(set(ids)), ids)


# ============================================================== G 遗忘
def test_forget():
    print('\n[G] 遗忘 / 日摘要 / 保护期')
    ms = new_ms('msG')
    now = time.time()
    old = now - 6 * 86400.0

    f_weak = ms.add_fragment('这是一句几乎没人会再提起的碎碎念内容',
                             who='ralsei', importance=0.06, now=old)
    f_weak['strength'] = 0.01
    f_recent = ms.add_fragment('刚刚才说过的很重要的新鲜事内容', who='user',
                               importance=0.1, now=now - 600)
    f_recent['strength'] = 0.01
    f_old_keep = ms.add_fragment('很久以前但很显著的一段重要回忆内容', who='user',
                                 importance=0.95, now=old)
    ms.remember_key('achievement_unlocked', '关键记忆不该被遗忘', importance=1.0)

    s_before = float(f_old_keep.get('strength'))
    stats = ms.forget_cycle(now=now)
    ok('G1 又弱又老又无关的片段被忘掉',
       stats.get('forgotten', 0) >= 1
       and '碎碎念' not in ' '.join(str(f.get('text')) for f in ms.fragments), stats)
    ok('G2 最近 24 小时内的内容受保护（强度再低也不删）',
       any('新鲜事' in str(f.get('text')) for f in ms.fragments), None)
    ok('G3 关键记忆免疫遗忘', len(ms.keys) == 1, len(ms.keys))
    ok('G4 遗忘周期会衰减强度',
       float(f_old_keep.get('strength')) < s_before, (s_before, f_old_keep.get('strength')))
    ok('G5 超过 2 天的日子会生成"日摘要"',
       len(ms.digests) >= 1, list(ms.digests.keys())[:3])
    _dg = ' '.join(str(v) for v in ms.digests.values())
    ok('G6 日摘要留下那天的"印象"（关键词或原话）',
       any(k in _dg for k in ('碎碎念', '重要回忆', '几乎', '很久')), _dg[:120])

    # 硬上限
    ms2 = new_ms('msG2')
    t0 = time.time()
    for i in range(ms2.MAX_FRAGMENTS + 80):
        f = ms2.add_fragment('压测片段第%d条，内容刻意有点长度便于建索引' % i,
                             who='user', importance=0.3, now=t0 - (i + 1) * 7200)
        f['strength'] = 0.3
    ms2.forget_cycle(now=t0)
    ok('G7 硬上限兜底后片段数不超上限', len(ms2.fragments) <= ms2.MAX_FRAGMENTS, len(ms2.fragments))
    ok('G8 遗忘后索引与片段数一致（无脏下标）',
       all(0 <= i < len(ms2.fragments) for v in ms2._index.values() for i in v),
       len(ms2._index))


# ============================================================= P 持久化
def test_persist():
    print('\n[P] 持久化')
    ms = new_ms('msP')
    ms.add_fragment('持久化测试：我喜欢在晚上听爵士乐', who='user')
    ms.remember_key('user_preferences', '主人喜欢爵士乐', importance=0.9)
    ms.digests['2026-08-01'] = '那天聊过爵士乐'
    ms.forget_cycle()
    ms.save_memory()

    raw = json.loads(read(ms.memory_file))
    ok('P1 落盘含 schema=2 与存储类型', raw.get('schema') == 2 and raw.get('storage_kind') in ('device', 'desktop'), raw.get('storage_kind'))
    ok('P2 落盘包含新记忆层四个键',
       all(k in raw for k in ('fragments', 'keys', 'digests', 'assoc')), list(raw.keys())[:12])

    ms2 = new_ms('msP')          # 同一目录 → 读到刚才写的文件
    ms2._legacy_file = os.path.join(TMP, '_no_such_legacy.json')
    ok('P3 重新加载后片段/关键记忆/日摘要一致',
       len(ms2.fragments) == len(ms.fragments)
       and len(ms2.keys) == len(ms.keys)
       and ms2.digests == ms.digests, (len(ms2.fragments), len(ms2.keys)))
    ok('P4 重新加载后倒排索引可用',
       any('爵士乐' in str(f.get('text')) for f in ms2.fragments)
       and len(ms2._index) > 0, len(ms2._index))

    # 坏文件
    bad = os.path.join(TMP, 'msBad')
    os.makedirs(bad, exist_ok=True)
    with open(os.path.join(bad, 'memory.json'), 'w', encoding='utf-8') as fh:
        fh.write('{ this is not json')
    set_env(device_dir=bad, desktop=os.path.join(TMP, 'Desktop'))
    ms3 = MemorySystem(FakeParent())
    ms3._legacy_file = os.path.join(TMP, '_no_such_legacy.json')
    ok('P5 坏文件不崩且退化为空记忆（长期记忆键齐全）',
       ms3.fragments == [] and 'skill_levels' in ms3.long_term_memory
       and ms3.level == 1, list(ms3.long_term_memory.keys())[:4])

    # 旧位置继承
    ms4 = new_ms('msP2')
    legacy = os.path.join(TMP, 'legacy_memory.json')
    with open(legacy, 'w', encoding='utf-8') as fh:
        json.dump({'schema': 1, 'experience': 555, 'level': 4,
                   'long_term_memory': {'user_preferences': {'user_name': '测试主人'}}},
                  fh, ensure_ascii=False)
    ms4.memory_file = os.path.join(TMP, 'msP2', 'not_there.json')
    ms4._legacy_file = legacy
    ms4.load_memory()
    ok('P6 新位置无文件时从旧版 memory.json 继承（升级不失忆）',
       ms4.experience == 555 and ms4.level == 4
       and ms4.long_term_memory.get('user_preferences', {}).get('user_name') == '测试主人',
       (ms4.experience, ms4.level))

    # 节流落盘
    ms5 = new_ms('msP3')
    ms5.add_fragment('节流测试用的一句话内容', who='user')
    ms5.save_memory()
    m1 = os.path.getmtime(ms5.memory_file)
    wrote = ms5.autosave(force=False)     # 刚存过 → 应被节流
    m2 = os.path.getmtime(ms5.memory_file)
    ok('P7 autosave 节流：刚存过不再写盘', (wrote is False) and m1 == m2, (wrote, m1, m2))
    ok('P8 autosave(force=True) 必定写盘', ms5.autosave(force=True) is True, None)

    # reset_all
    ms5.reset_all()
    ok('P9 reset_all 清空记忆文件与内存态',
       (not os.path.exists(ms5.memory_file)) and ms5.fragments == [] and ms5.keys == [],
       None)


# =========================================================== I 集成契约
def test_integration():
    print('\n[I] 集成契约（源码级）')
    du = read(os.path.join(MODS, 'dialogue_ui.py'))
    mn = read(os.path.join(SRC, 'main.py'))
    mss = read(os.path.join(MODS, 'memory_system.py'))

    ad = code_only(func_src(du, 'add_dialogue'))
    ok('I1 add_dialogue 每轮登记记忆片段', '_note_memory' in ad, None)
    nm = code_only(func_src(du, '_note_memory'))
    ok('I2 _note_memory 调 memory_system.add_fragment', 'add_fragment' in nm, None)

    cw = code_only(func_src(mn, 'chat_with_ai'))
    ok('I3 chat_with_ai 注入"零星回忆"', 'recall_text' in cw, None)

    up = code_only(func_src(mss, 'update'))
    ok('I4 update 触发遗忘周期与存储迁移',
       ('forget_cycle' in up) and ('maybe_relocate_storage' in up), None)

    ok('I5 save_memory 落盘 schema 与记忆层',
       "'schema': self.SCHEMA" in func_src(mss, 'save_memory'), None)
    ok('I6 memory_store 在 import 期不做磁盘操作',
       ('makedirs' not in code_only(read(os.path.join(MODS, 'memory_store.py')).split('def ', 1)[0])), None)

    ms = new_ms('msI')
    st = ms.get_memory_stats()
    ok('I7 get_memory_stats 反映位置与体量',
       st.get('on_device') is True and st.get('file', '').endswith('memory.json'), st)


if __name__ == '__main__':
    print('python =', sys.executable)
    try:
        test_storage()
        test_migrate()
        test_fragments()
        test_recall()
        test_forget()
        test_persist()
        test_integration()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print('\n' + '=' * 60)
    print('PASS = %d   FAIL = %d' % (len(PASS), len(FAIL)))
    for n in FAIL:
        print('  - ' + n)
    sys.exit(1 if FAIL else 0)
