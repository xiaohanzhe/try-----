# -*- coding: utf-8 -*-
"""第49轮回归锁：NPC 分层 / 跟随策略 / 世界门控 / 光世界球容器。

用法:
    C:\\Python311\\python.exe verify_npc49.py            # 跑（cwd 建议=仓库根）
    C:\\Python311\\python.exe verify_npc49.py --update   # 合并模式重建基线（由 run_all.py 调用）

判据纪律（沿用本项目既有教训）
* ✅ 能上 AST 就上 AST；断言**结构/行为**，不断赋值。
* ✅ 需要「不能报红」的地方必须有**正/负控制成对**。
* ✅ 锚定原作常量时，**直接读 `_evidence/gml/` 的逐字产物**，不复制粘贴到判据里自证。
* ⛔ 不写 `check(cid, True, ...)` 这种"看着在守其实没守"的恒真判据。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
EVID = os.path.join(HERE, '_evidence')
GML = os.path.join(EVID, 'gml')
NPCJSON = os.path.join(PET, 'assets', 'npc')
BUBBLE = os.path.join(PET, 'assets', 'bubble')

sys.path.insert(0, MOD)

FAILS = []
PASSES = []


def check(cid, ok, msg):
    tag = '[PASS]' if ok else '[FAIL]'
    print('%s %-5s %s' % (tag, cid, msg))
    (PASSES if ok else FAILS).append(cid)


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


# ================================================================ A 零依赖契约
ALLOWED_TOP = {'collections', 'json', 'logging', 'math', 'os', 'logger_utils'}
TARGETS = ['npc_system.py', 'bubble_system.py']


def _imports(path):
    """→ (顶层模块名集合, 函数内 import 列表)

    ⚠️ 判据坑（本轮首跑踩到）：本项目通用的模块级降级写法是

        try:
            from logger_utils import get_logger
        except ImportError:
            ...

    它是**顶层** import，但 AST 上的父节点是 `Try` 而不是 `Module`。
    首版判据只看 `Module` 的直接子节点 ⇒ 把这种写法误判成"函数内 import"。
    ⇒ 正确判据 = **按"是否位于函数体内"来分**，而不是"是否是 Module 直接子节点"。
    """
    tree = ast.parse(rd(path))
    tops = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            tops.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            tops.add((node.module or '').split('.')[0])
        elif isinstance(node, ast.Try):   # 模块级 try/except 的降级 import 算顶层
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    tops.update(a.name.split('.')[0] for a in sub.names)
                elif isinstance(sub, ast.ImportFrom):
                    tops.add((sub.module or '').split('.')[0])
    inner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Import):
                    inner[sub.lineno] = [a.name.split('.')[0] for a in sub.names]
                elif isinstance(sub, ast.ImportFrom):
                    inner[sub.lineno] = [(sub.module or '').split('.')[0]]
    return tops, sorted(inner.items())


for _f in TARGETS:
    _p = os.path.join(MOD, _f)
    _tops, _inner = _imports(_p)
    check('A1', os.path.isfile(_p) and not _inner,
          '%s 无函数内 import（实得 %r）' % (_f, _inner))
    _bad = sorted(_tops - ALLOWED_TOP)
    check('A2', not _bad, '%s 顶层 import 全在白名单内（越界 %r）' % (_f, _bad))

# 负控制：白名单本身不是空的、且真的会拦住东西（否则 A2 是恒真）
check('A3', _imports(os.path.join(MOD, 'bubble_system.py'))[0] >= {'math', 'collections'},
      'A 段白名单判据有鉴别力（顶层确实扫到了 math/collections）')


# ================================================================ B 注册表
import npc_system as NS          # noqa: E402
import bubble_system as BS       # noqa: E402

REG = NS.load_registry(PET)
check('B1', len(REG) >= 30, '注册表加载到 %d 条 NPC' % len(REG))
check('B2', len(REG.main_npcs()) >= 12, '主线 NPC %d 条' % len(REG.main_npcs()))
check('B3', len(REG.plain_npcs()) >= 15, '纯 NPC %d 条' % len(REG.plain_npcs()))
check('B4', all(n.objects for n in REG.all()), '每条 NPC 都有原作物件名')
check('B5', all(n.chapters for n in REG.all()), '每条 NPC 都登记了章节')
for _nid in ('toriel', 'asgore', 'lancer', 'tenna', 'ralsei'):
    _n = REG.get(_nid)
    check('B6', _n is not None and _n.tier == NS.NpcTier.MAIN,
          '%s 在主线层（实得 %s）' % (_nid, _n.tier if _n else 'MISSING'))
check('B7', all(n.needs_setting for n in REG.main_npcs()),
      '主线 NPC 全部标 needs_setting=True（等用户给设定）')

# 注册表与磁盘 JSON 一致（不靠内存自证）
_raw = json.loads(rd(os.path.join(NPCJSON, '_registry.json')))
check('B8', _raw.get('schema_version') == NS.SCHEMA_VERSION
      and len(_raw['npcs']) == len(REG),
      '注册表 schema_version=%r 且条数与磁盘一致(%d)' % (_raw.get('schema_version'), len(REG)))

# ================================================================ C 纯 NPC 内置对话
_LINES = json.loads(rd(os.path.join(NPCJSON, '_dialogue.json')))['lines']
check('C1', len(_LINES) == len(REG.plain_npcs()),
      '内置对话组数 %d == 纯 NPC 数 %d' % (len(_LINES), len(REG.plain_npcs())))
_bad = [k for k, v in _LINES.items() if not (NS.PLAIN_LINES_MIN <= len(v) <= NS.PLAIN_LINES_MAX)]
check('C2', not _bad, '所有内置对话都在 4~10 句内（越界 %r）' % (_bad,))
check('C3', all(REG.lines_of(n.id) for n in REG.plain_npcs()),
      '每个纯 NPC 都能从注册表取到对话')
check('C4', all(not REG.lines_of(n.id) for n in REG.main_npcs()),
      '主线 NPC 不走内置对话（取到空表）')


# ================================================================ D 跟随策略
_MAIN = REG.main_npcs()[0]
_PLAIN = REG.plain_npcs()[0]
check('D1', NS.follow_policy(_MAIN) == NS.FollowPolicy.AUTONOMOUS,
      '主线 NPC 策略=AUTONOMOUS（自主跟随）')
check('D2', NS.follow_policy(_PLAIN) == NS.FollowPolicy.CONSENT,
      '纯 NPC 策略=CONSENT（需主角同意）')
check('D3', NS.needs_consent(_PLAIN) and not NS.needs_consent(_MAIN),
      'needs_consent 与策略一致（正/负成对）')
check('D4', NS.can_follow(_MAIN) and NS.can_follow(_PLAIN),
      '**两类都能跟**主角团（差别只在谁发起）')
check('D5', NS.dialogue_source(_MAIN) == 'llm' and NS.dialogue_source(_PLAIN) == 'builtin',
      '对话来源：主线=llm / 纯=builtin')

# 状态机
_B = NS.FollowerBoard(REG)
check('D6', _B.request(_MAIN.id) == NS.FOLLOW_ACTIVE,
      '主线 request 直接 active（实得 %s）' % _B.state_of(_MAIN.id))
check('D7', _B.request(_PLAIN.id) == NS.FOLLOW_PENDING,
      '纯 NPC request 变 pending（实得 %s）' % _B.state_of(_PLAIN.id))
check('D8', _B.respond(_PLAIN.id, False) and _B.state_of(_PLAIN.id) == NS.FOLLOW_DENIED,
      '主角拒绝 ⇒ denied')
check('D9', _B.respond(_PLAIN.id, True) is False,
      '非 pending 的重复表态被拒（不会把 denied 翻成 active）')
_B2 = NS.FollowerBoard(REG)
_B2.request(_PLAIN.id)
check('D10', _B2.respond(_PLAIN.id, True) and _B2.state_of(_PLAIN.id) == NS.FOLLOW_ACTIVE,
      '主角同意 ⇒ active')
check('D11', _B.stop(_MAIN.id) and _B.state_of(_MAIN.id) == NS.FOLLOW_IDLE,
      'stop() 回到 idle')
check('D12', _B.request('no_such_npc_xyz') == NS.FOLLOW_IDLE,
      '未知 id 不抛异常、返回 idle')

# ================================================================ E 世界门控
_T = REG.get('toriel')
_L = REG.get('lancer')
_R = REG.get('ralsei')
check('E1', not NS.world_gate(_L, NS.WORLD_LIGHT).ok,
      'NPC 不可脱离暗世界（%s）' % NS.world_gate(_L, NS.WORLD_LIGHT).reason)
check('E2', NS.world_gate(_L, NS.WORLD_LIGHT).reason == NS.REASON_LEAVE_DARK,
      '拒绝原因码 = leave_dark_world（可与"异世界"区分）')
check('E3', NS.world_gate(_L, NS.WORLD_DARK, 'ch1.field.field_great_door').ok,
      '回到自己的暗世界（ch1）⇒ 允许')
check('E4', not NS.world_gate(_L, NS.WORLD_DARK, 'ch5.garden.garden_shrine').ok,
      '进入**不属于他**的暗世界（ch5）⇒ 拒绝')
check('E5', NS.world_gate(_L, NS.WORLD_DARK, 'ch5.garden.garden_shrine').reason
      == NS.REASON_FOREIGN_DARK, '原因码 = foreign_dark_world')
check('E6', not NS.world_gate(_R, NS.WORLD_LIGHT).ok, 'Ralsei 默认也不能脱离暗世界')
check('E7', NS.world_gate(_R, NS.WORLD_LIGHT, carried=True).ok,
      '★ Ralsei **被装进球里** ⇒ 允许进光世界（唯一豁免）')
check('E8', not NS.world_gate(_L, NS.WORLD_LIGHT, carried=True).ok
      or not _L.escape_via_bubble,
      '★ 别的 NPC 就算 carried 也不认这条豁免（escape_via_bubble=False）')
check('E9', NS.world_gate(_T, NS.WORLD_DARK, 'ch1.home.home').ok,
      '光世界出身者（Toriel）在其登记章节的暗世界也放行')
check('E10', not NS.world_gate(_T, NS.WORLD_DARK, 'ch9.zzz.zzz').ok,
      '不在登记章节 ⇒ 拒绝（章节门是真在跑）')
check('E11', NS.world_gate(_L, NS.WORLD_DARK, None).ok,
      'scene_id 缺失时不做章节硬判（不猜）')
check('E12', not _B.may_enter('no_such_npc_xyz', NS.WORLD_DARK).ok,
      'FollowerBoard.may_enter 对未知 id 拒绝')
_B3 = NS.FollowerBoard(REG)
_B3.request(_L.id)
_kicked = _B3.tick(NS.WORLD_LIGHT)
check('E13', _kicked == [_L.id] and _B3.state_of(_L.id) == NS.FOLLOW_IDLE,
      'tick 在光世界把不可进入的跟随者踢出（实得 %r）' % (_kicked,))

# ================================================================ F 球容器
_F = BS.BubbleField()
check('F1', _F.equip('ralsei', by='kris') is not None, 'Kris 可以给 Ralsei 套球')
check('F2', _F.equip('nobody_xyz', by='kris') is None, '非 CONTAINABLE 的不能进球')
check('F3', _F.equip('ralsei', by='nobody_xyz') is None, '非主角团不能给人套球')
check('F4', _F.unequip('ralsei', world='light') is False,
      '★ Ralsei 在光世界**不可脱下**（脱了就脱离暗世界）')
check('F5', _F.unequip('ralsei', world='dark') is True,
      'Ralsei 在暗世界可脱（本来不需要球）')
_F2 = BS.BubbleField()
_F2.equip('lancer', by='kris', world='light')
check('F6', _F2.unequip('lancer', world='dark') is False,
      '★ Lancer **永远脱不下来**（暗世界也不许）')
check('F7', BS.must_stay_inside('lancer', 'dark') is True, 'Lancer 必须留在球里')
check('F8', BS.must_stay_inside('ralsei', 'light') is True,
      'Ralsei 在光世界必须留在球里（不穿模）')
check('F9', BS.must_stay_inside('susie', 'light') is False,
      'Susie 不必一直在球里（可随时脱）')
_F3 = BS.BubbleField()
_F3.equip('susie', by='kris', world='light')
check('F10', _F3.unequip('susie', world='light') is True, 'Susie 光世界可随时脱下')
check('F11', BS.ejectable('kris', 'light') and BS.ejectable('susie', 'light'),
      'ALWAYS_EJECTABLE 里两位都可脱（正控制）')

# 绘制序 = 原作
_pl = BS.draw_plan(100.0, 100.0, (100.0, 100.0), char_sprite='spr_board_ralsei_walk_down')
check('F12', [p['role'] for p in _pl] == ['ball_back', 'character', 'ball_front', 'ball_top'],
      '绘制序 = 后层→角色→前层→上罩（实得 %r）' % [p['role'] for p in _pl])
check('F13', [p['frame'] for p in _pl] == [BS.FRAME_BACK, 0, BS.FRAME_FRONT, BS.FRAME_TOP],
      '帧号 = 2(后) / 角色 / 3(前) / 1(上罩)')

# 世界切换
_F4 = BS.BubbleField()
_F4.equip('susie', by='kris', world='light')
_drop = _F4.transfer_world('dark')
check('F14', _drop == ['susie'] and 'susie' not in _F4,
      '★ 回暗世界自动脱球（实得 dropped=%r）' % (_drop,))
_F5 = BS.BubbleField()
_F5.equip('lancer', by='kris', world='light')
check('F15', _F5.transfer_world('dark') == [] and 'lancer' in _F5,
      'Lancer 回暗世界也脱不掉（负控制，与 F14 成对）')

# ================================================================ G 几何 / 旋转 / 滤镜
_x, _y, _moved, _d = BS.clamp_inside(300.0, 100.0, 100.0, 100.0, 40.0)
check('G1', _moved and abs(_x - 140.0) < 1e-6 and abs(_y - 100.0) < 1e-6,
      '越界角色被钳回球边界（实得 %.1f,%.1f）' % (_x, _y))
_x2, _y2, _m2, _ = BS.clamp_inside(110.0, 105.0, 100.0, 100.0, 40.0)
check('G2', not _m2 and (_x2, _y2) == (110.0, 105.0), '球内不被动（负控制）')
_b = BS.Bubble('ralsei', world='light')
_r = BS.ball_radius(_b.scale)
check('G3', abs(_r - BS.SPRITE_W * BS.SCALE_DEFAULT / 2.0) < 1e-9,
      '球半径由原作精灵尺寸×缩放推出（%.2f）' % _r)
_angs = [BS.angle_for_direction(i) for i in range(BS.SPIN_DIRECTIONS)]
_diffs = [round(_angs[i + 1] - _angs[i], 3) for i in range(len(_angs) - 1)]
# ⚠️ 判据坑（本轮鉴别力体检抓到两次）：
#   ① 首版写成 `_diffs == [BS.SPIN_STEP_DEG]*3` —— 右边取自被测常量 ⇒ **恒真**；
#   ② 改版又写成 `angle_for_direction(4) - _angs[0] == 360` —— 而该函数**取模**，
#      永远回不到 +360 ⇒ 恒假（干净状态下也报红）。
#   ⇒ 最终判据：4 个朝向互不相同、相邻步长 **字面 90°**、且最后一步再加 90° 正好补满整圈。
check('G4', (BS.SPIN_DIRECTIONS == 4
             and len(set(_angs)) == BS.SPIN_DIRECTIONS
             and _diffs == [90.0, 90.0, 90.0]
             and abs((_angs[-1] + 90.0) - _angs[0]) == 360.0),
      '★「4 个方向」均分整圈 %r（相邻 90°，补满 360°）' % (_angs,))
check('G5', BS.angle_for_direction(0) == BS.ANGLE_DEFAULT,
      '方向 0 = 原作 target_angle -150')
_b.spin_to(2)
check('G6', abs(_b.spin_to(2) - 30.0) < 1e-9 and _b.dir_index == 2,
      'spin_to(2) = 基准 -150 + 2×90 = 30.0（实得 %.1f）' % _b.spin_to(2))
_b2 = BS.Bubble('ralsei')
_b2.alpha = 0.0
_b2.tick(1)
check('G7', 0.0 < _b2.alpha < 1.0, 'alpha 逐帧 lerp 上升（%.2f）' % _b2.alpha)
_fp = BS.filter_params('ralsei')
check('G8', set(_fp) == {'tint', 'alpha', 'rim', 'saturate'} and 0.0 < _fp['alpha'] < 1.0,
      '塑料滤镜参数齐全且半透（alpha=%.2f）' % _fp['alpha'])
check('G9', BS.scale_for('susie') != BS.scale_for('kris'),
      'Susie 特例倍率生效（2.02 vs 1.55）')

# ================================================================ H 原作证据锚定
_draw = rd(os.path.join(GML, 'ch3.obj_tenna_board4_gacha_Draw_0.gml'))
import re  # noqa: E402
_seq = [int(m.group(1)) for m in
        re.finditer(r'spr_dw_tv_gachaball_transparent,\s*(\d+)', _draw)]
check('H1', _seq == [2, 3, 1],
      '★ 原作 GML 里的球帧序逐字 = [2,3,1]（实得 %r）' % (_seq,))
check('H2', list(BS.DRAW_ORDER) == _seq, '模块常量 DRAW_ORDER 与原作逐字一致')
_idx_char = _draw.find('draw_sprite_ext(actor_sprite')
_idx_back = _draw.find('spr_dw_tv_gachaball_transparent, 2')
_idx_front = _draw.find('spr_dw_tv_gachaball_transparent, 3')
check('H3', 0 <= _idx_back < _idx_char < _idx_front,
      '★ 角色确实被夹在 后层(2) 与 前层(3) 之间 ⇒ "遮住/透出"由分层实现')
_w = BS.SPRITE_W
_log = rd(os.path.join(EVID, 'spr49_log.txt'))
check('H4', ('spr_dw_tv_gachaball_transparent' in _log) and ('w=62' in _log),
      '精灵导出日志确认主球存在且 62×62')
check('H5', 'frames=4' in _log.split('spr_dw_tv_gachaball_transparent')[1][:60],
      '主球 4 帧（0=整球/1=上罩/2=下后/3=下前）')
_geo = rd(os.path.join(EVID, '取证与设计49.md'))
for _tok, _cid in (('1.55', 'H6'), ('-100', 'H7'), ('2.02', 'H8')):
    check(_cid, _tok in _geo, '取证文档记有原作常量 %s' % _tok)
check('H9', 'obj_ch3_ballcon' in _geo and '不是球' in _geo,
      '文档明确排除了误认候选 obj_ch3_ballcon（对话气泡框）')

# 资产盘点（查磁盘，不靠"我写了 N 个"）
# ⚠️ 判据坑（鉴别力体检 P10 抓到）：首版直接 `len(os.listdir())` —— 把文件改名成
#    `xxx.png.hidden` 后目录条目数不变、且前缀仍是 `spr_board_` ⇒ 判据**看不到破坏**。
#    ⇒ 只数**真 PNG**（后缀 .png），文件名被动手脚立刻掉数。
_all = sorted(os.listdir(BUBBLE)) if os.path.isdir(BUBBLE) else []
_files = [f for f in _all if f.lower().endswith('.png')]
check('H10', len(_files) == 43 and len(_all) == len(_files),
      'assets/bubble 下落盘 %d 个真 PNG / 目录共 %d 条（非 PNG 杂物 %d）'
      % (len(_files), len(_all), len(_all) - len(_files)))
_ballf = [f for f in _files if f.startswith('spr_dw_tv_gachaball_transparent_')]
check('H11', len(_ballf) == 4, '主球帧文件 %d 个' % len(_ballf))
_chars = [f for f in _files if f.startswith('spr_board_')]
# 3 个角色（kris/susie/ralsei）× 4 向 × 2 帧 = 24，+ Lancer 4 向 × 1 帧 = 4 ⇒ 28
check('H12', len(_chars) == 28, '四个角色四向帧文件 %d 个（应为 28）' % len(_chars))


# ================================================================ 汇总
print('-' * 72)
print('第49轮 回归锁：PASS=%d FAIL=%d' % (len(PASSES), len(FAILS)))
if FAILS:
    print('FAIL 列表: %s' % (FAILS,))
sys.exit(1 if FAILS else 0)
