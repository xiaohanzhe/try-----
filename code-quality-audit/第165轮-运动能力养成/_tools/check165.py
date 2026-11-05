# -*- coding: utf-8 -*-
u"""第165轮回归锁：**运动能力养成**（练出来的能力 / 每人档不同 / 倍率制零回归）。

## 用户口径（2026-11-06）

> 「那就给AI加装一个学习模块，让他能够像是练习一样练出来，
>   当然，针对不同NPC的特点，运动能力肯定也不同，所以初始和进步速度都不同哦」

四轮问答定下来的细节：
1. **练习怎么发生** → 日常动作即练习（真跳/真跑就记一笔，不新增行为）
2. **接到哪儿** → 桌宠 + NPC 两边都真读档案（不存"写了没人读"的死数据）
3. **初始值真源** → **全员按原作手写**
4. **没依据的人怎么办** → 每人落值 + 标依据等级（明证 / 推断 / 无据）

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | `modules/motion_profile.py` 纯函数：**默认档恒等**（零回归的根）/ 坏值不抛 / 越界钳制 / 只加不减 / 封顶 / 成长率真的影响涨幅 / 校验器该报的必须报、不该报的不许报 |
| B | 96 人数据：与 `_registry.json` 一一对应 / 全员过校验 / 三档都有 / **基准人必须 1.0** / **"无据"不许超过默认档** / 生成表与磁盘逐字一致 |
| C | 桌宠接线：未练 = 1.0、满级 > 1、陌生 id = 1.0、闸门/冲刺上限真按倍率变、记账权重、落盘 round-trip、坏档不抛 |
| D | 零回归的结构性保证：`max_speed` **没**参与倍率（走路手感不变）/ 基准人 id / 闸门那行确实乘了 |
| E | 自检：无 BOM / 只用一套 harness / 判据名不带计数标记 / 分母闸 |

## 为什么"A 段全是纯函数"就够撑起零回归

倍率制把"能力"与"手感常量"分开了：`1.0` 时 `x * 1.0 == x` **精确成立**（浮点下也是），
所以"加了这个模块"对旧存档、旧测试、旧行为是**零改动**。A1 是这条的核心断言，
A1b 是它的正控制（非 1.0 的档必须真的变），两条成对才说明 A1 不是恒真。
"""
import ast
import json
import os
import sys
import tempfile
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
# ★ 变异测试（`mutate165.py`）把 main.py / modules 的**副本**喂进来，绝不改产品文件：
#   `CQ_SRC_DIR` 指向副本 src 目录时 AST 与 import 都读那份副本；
#   `CQ_MOD_DIR` 指向副本项目根时 `modules` 包也读副本（5MB，整包复制才不漏模块）。
_SRC_DIR = os.environ.get('CQ_SRC_DIR') or os.path.join(PET, 'src')
_MOD_ROOT = os.environ.get('CQ_MOD_DIR') or ''
MAIN = os.path.join(_SRC_DIR, 'main.py')
PROFILE = os.path.join(PET, 'assets', 'npc', '_motion_profile.json')
REGISTRY = os.path.join(PET, 'assets', 'npc', '_registry.json')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ★ 顺序即优先级（前面先命中）：副本 → 本文件目录 → 真实 src/PET。
#   `ralsei_pet/modules` 自己也要在 path 上：`main.py` 里是 `import data_store`
#   这种**平铺**写法（不是 `from modules import data_store`），两条路都得通。
_PATHS = []
if _MOD_ROOT:
    _PATHS += [os.path.join(_MOD_ROOT, 'modules'), _MOD_ROOT]
_PATHS += [HERE, _SRC_DIR, PET, os.path.join(PET, 'src'), os.path.join(PET, 'modules')]
for _p in reversed(_PATHS):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

_p = _f = 0
_bad = []


def check(desc, cond, extra=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + extra) if extra else ''))
    else:
        _f += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + extra) if extra else ''))


def read_src(path):
    import io
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


try:
    from modules import motion_profile as MP
    _MP_ERR = ''
except Exception as _e:                              # noqa: BLE001
    MP = None
    _MP_ERR = '%s: %s' % (type(_e).__name__, _e)
    print('  (import motion_profile 失败：%s)' % _MP_ERR)

# ★ 不让 import 崩掉整个套件：变异把文件改出语法错时，抛异常会让本套件一行
#   [FAIL] 都打不出来 ⇒ 变异测试误判"全绿"（第164轮记过这条）。
try:
    import main as MAIN_MOD
    _IMPORT_ERR = ''
except Exception as _e:                              # noqa: BLE001
    MAIN_MOD = None
    _IMPORT_ERR = '%s: %s' % (type(_e).__name__, _e)
    print('  (import main 失败：%s)' % _IMPORT_ERR)

_PET_CLS = getattr(MAIN_MOD, 'RalseiPet', None) if MAIN_MOD is not None else None
_SRC = read_src(MAIN)
_TREE = None
try:
    _TREE = ast.parse(_SRC)
except Exception:                                    # noqa: BLE001
    pass


def _raw(name):
    return getattr(_PET_CLS, name, None) if _PET_CLS is not None else None


def _mt(pet, fn):
    return types.MethodType(fn, pet) if fn is not None else None


# ============================================================ A · 纯函数
print('=' * 66)
print(u'A 段  motion_profile：倍率制纯函数（零 Qt、可脱离产品单测）')
print('=' * 66)

check(u'A0 `modules/motion_profile.py` 能导入（零依赖）', MP is not None, _MP_ERR)

if MP is None:
    check(u'A0b motion_profile 不可用 —— 后面 A 段全部无法执行', False)
else:
    # ---- A1 零回归的根：默认档 + 0 经验必须是恒等 ----
    _eff0 = MP.effective(MP.default_profile(), 0.0)
    check(u'A1 ★★★ 默认档 + 0 经验 ⇒ 三项倍率**全 1.0**（零回归的根）',
          all(abs(_eff0[k] - 1.0) < 1e-12 for k in MP.EFF_KEYS),
          u'实得 %s' % ({k: round(_eff0[k], 6) for k in MP.EFF_KEYS},))
    # ---- A1b 正控制：非 1.0 的档必须真的变（否则 A1 是恒真） ----
    _eff_big = MP.effective({'jump': 1.4, 'run': 1.4, 'accel': 1.4, 'growth': 1.0}, 0.0)
    check(u'A1b 正控制：1.4 的档必须算出 != 1.0（证明 A1 不是恒真判据）',
          abs(_eff_big['jump'] - 1.0) > 1e-6,
          u'jump=%.3f' % _eff_big['jump'])

    # ---- A2 坏值不抛 ----
    _junk = [None, 'abc', [], {}, {'jump': 'x'},
             {'jump': float('nan')}, {'jump': float('inf')},
             {'run': None, 'accel': -1}]
    _ok_all = True
    _detail = ''
    for _j in _junk:
        try:
            MP.from_dict(_j)
        except Exception as _e:                      # noqa: BLE001
            _ok_all = False
            _detail = '%r -> %s: %s' % (_j, type(_e).__name__, _e)
            break
    check(u'A2 坏值一律不抛（档案在启动路径上，抛一次就起不来）', _ok_all, _detail)

    # ---- A3 越界钳制 ----
    _hi = MP.from_dict({'jump': 99, 'run': -99, 'accel': 'x', 'growth': 0.01})
    check(u'A3 越界钳回区间（jump 99→2.0 / run -99→0.4 / accel 坏值→1.0 / growth 0.01→0.3）',
          abs(_hi['jump'] - MP.LIMITS['jump'][1]) < 1e-9
          and abs(_hi['run'] - MP.LIMITS['run'][0]) < 1e-9
          and abs(_hi['accel'] - 1.0) < 1e-9
          and abs(_hi['growth'] - MP.LIMITS['growth'][0]) < 1e-9,
          u'实得 %s' % ({k: round(_hi[k], 3) for k in ('jump', 'run', 'accel', 'growth')},))

    # ---- A4 等级边界 ----
    _lv = (MP.level_of(0), MP.level_of(MP.LEVEL_STEP - 1), MP.level_of(MP.LEVEL_STEP),
           MP.level_of(MP.MAX_EXP), MP.level_of(MP.MAX_EXP * 10))
    check(u'A4 等级边界（0 / 差 1 / 刚满 / 满头 / 溢出）',
          _lv == (0, 0, 1, MP.MAX_LEVEL, MP.MAX_LEVEL), u'实得 %s' % (_lv,))

    # ---- A5 只加不减 ----
    check(u'A5 ★ 经验只加不减（负数不给减 = "不练也不退步"）',
          abs(MP.apply_exp(100.0, -50.0) - 100.0) < 1e-9
          and abs(MP.apply_exp(100.0, 0.0) - 100.0) < 1e-9,
          u'100 + (-50) = %s' % MP.apply_exp(100.0, -50.0))

    # ---- A6 封顶 ----
    check(u'A6 经验封顶（不会练成超人）',
          abs(MP.apply_exp(MP.MAX_EXP - 10, 999) - MP.MAX_EXP) < 1e-9,
          u'实得 %s（上限 %s）' % (MP.apply_exp(MP.MAX_EXP - 10, 999), MP.MAX_EXP))

    # ---- A7 单调递增 ----
    _prof = MP.from_dict({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0})
    _seq = [MP.effective(_prof, e)['jump']
            for e in (0, 100, 240, 480, 720, 960, 1200, 5000)]
    check(u'A7 倍率随经验**单调不减**', all(b >= a - 1e-12 for a, b in zip(_seq, _seq[1:])),
          u'%s' % [round(x, 3) for x in _seq])

    # ---- A8 成长率真的影响涨幅（成对：先证 A≠B，再说方向） ----
    _slow = MP.effective({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 0.6}, MP.MAX_EXP)['jump']
    _mid = MP.effective({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0}, MP.MAX_EXP)['jump']
    _fast = MP.effective({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.6}, MP.MAX_EXP)['jump']
    check(u'A8 ★★ 同一份经验下 growth 大的涨得多（0.6 < 1.0 < 1.6，且先证三者不相等）',
          (_slow != _mid != _fast) and _slow < _mid < _fast,
          u'%.3f / %.3f / %.3f' % (_slow, _mid, _fast))

    # ---- A9 上限钳制 ----
    _max_eff = MP.effective({'jump': 2.0, 'run': 2.0, 'accel': 2.0, 'growth': 2.5}, MP.MAX_EXP)
    check(u'A9 天顶档也不越界（钳在 LIMITS 上限的 1.5 倍以内）',
          all(_max_eff[k] <= MP.LIMITS[k][1] * 1.5 + 1e-9 for k in MP.EFF_KEYS),
          u'%s' % ({k: round(_max_eff[k], 3) for k in MP.EFF_KEYS},))

    # ---- A10 进度 ----
    check(u'A10 等级内进度 ∈ [0,1] 且满级恒 1.0',
          all(0.0 <= MP.progress_of(e) <= 1.0 for e in (0, 1, 239.9, 240, 999))
          and abs(MP.progress_of(MP.MAX_EXP * 3) - 1.0) < 1e-12)

    # ---- A11~A13 校验器：该报的报、不该报的不报 ----
    _v1 = MP.validate_entry({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0,
                             'evidence': u'推断'}, 'x')
    check(u'A11 缺 why 必须报（"有值"不够，还得能说清值是哪来的）',
          any(u'why' in s for s in _v1), u'%d 条问题' % len(_v1))
    _v2 = MP.validate_entry({'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0,
                             'evidence': u'瞎写', 'why': u'凑数'}, 'x')
    check(u'A12 evidence 不在三档必须报',
          any('evidence' in s for s in _v2), u'实得 %s' % (_v2,))
    _v3 = MP.validate_entry({'jump': 1.2, 'run': 1.0, 'accel': 1.0, 'growth': 1.5,
                             'evidence': u'明证', 'why': u'原作里他跑得很快'}, 'x')
    check(u'A13 负控制：合格的条目**一条问题都不许报**',
          _v3 == [], u'实得 %s' % (_v3,))
    check(u'A14 effective_tuple 的顺序与 EFF_KEYS 一致',
          MP.effective_tuple(MP.default_profile(), 0.0) == (1.0, 1.0, 1.0)
          and len(MP.EFF_KEYS) == 3)

# ============================================================ B · 96 人数据
print('')
print('=' * 66)
print(u'B 段  96 人档案：名单对齐 / 全员过校验 / 依据三档 / 基准人与"无据"的纪律')
print('=' * 66)

_DATA = None
try:
    import io
    with io.open(PROFILE, 'r', encoding='utf-8') as _fh:
        _DATA = json.load(_fh)
except Exception as _e:                              # noqa: BLE001
    print('  (读档案失败：%s)' % _e)

check(u'B1 档案文件存在且是对象', isinstance(_DATA, dict))
if isinstance(_DATA, dict) and MP is not None:
    _ids = [k for k in _DATA if k != '_meta']
    _reg = json.load(io.open(REGISTRY, 'r', encoding='utf-8'))
    _reg_ids = [x['id'] for x in _reg['npcs']]
    check(u'B2 与 `_registry.json` 一一对应（一个不多一个不少）',
          sorted(_ids) == sorted(_reg_ids),
          u'档案 %d / 注册表 %d；多=%s 少=%s'
          % (len(_ids), len(_reg_ids),
             sorted(set(_ids) - set(_reg_ids)), sorted(set(_reg_ids) - set(_ids))))
    _all_prob = []
    for _nid in _ids:
        _all_prob.extend(MP.validate_entry(_DATA[_nid], _nid))
    check(u'B3 全员过校验（why 必填 / evidence 三档 / 数值有限且在区间内）',
          not _all_prob, u'%d 条问题：%s' % (len(_all_prob), _all_prob[:4]))
    _levels = {}
    for _nid in _ids:
        _ev = _DATA[_nid].get('evidence')
        _levels[_ev] = _levels.get(_ev, 0) + 1
    check(u'B4 三档依据都有条目（明证 / 推断 / 无据）',
          all(_levels.get(k, 0) > 0 for k in MP.EVIDENCE_LEVELS),
          u'%s' % (_levels,))
    # ---- B5 基准人：不许顺手把手感改掉 ----
    _r = _DATA.get('ralsei') or {}
    check(u'B5 ★★★ 基准人 ralsei 的三项**必须都是 1.0**（全局常量就是照他的手感定的）',
          all(abs(float(_r.get(k, 0)) - 1.0) < 1e-9 for k in MP.EFF_KEYS),
          u'实得 %s' % ({k: _r.get(k) for k in MP.EFF_KEYS},))
    # ---- B6 "无据"不许超过默认档 ----
    _over = [(k, _DATA[k]['jump'], _DATA[k]['run'], _DATA[k]['accel'])
             for k in _ids
             if _DATA[k].get('evidence') == u'无据'
             and max(float(_DATA[k]['jump']), float(_DATA[k]['run']),
                     float(_DATA[k]['accel'])) > 1.0 + 1e-9]
    check(u'B6 ★★★ "无据"的人不许超过默认档（不许把猜测写成数据）',
          not _over, u'越线 %d 个：%s' % (len(_over), _over[:3]))
    # ---- B7 生成表与磁盘逐字一致 ----
    _gen_ok = True
    _gen_msg = ''
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            'gen165', os.path.join(HERE, 'gen165_profiles.py'))
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _gen_ids = sorted(_mod.TABLE.keys())
        if _gen_ids != sorted(_ids):
            _gen_ok = False
            _gen_msg = u'表 %d 人 vs 档案 %d 人' % (len(_gen_ids), len(_ids))
        else:
            for _nid in _ids:
                _row = _mod.TABLE[_nid]
                _d = _DATA[_nid]
                for _i, _k in enumerate(('jump', 'run', 'accel', 'growth')):
                    if abs(float(_row[_i]) - float(_d[_k])) > 1e-9:
                        _gen_ok = False
                        _gen_msg = u'%s.%s 表=%s 档案=%s' % (_nid, _k, _row[_i], _d[_k])
                        break
                if not _gen_ok:
                    break
    except Exception as _e:                          # noqa: BLE001
        _gen_ok = False
        _gen_msg = '%s: %s' % (type(_e).__name__, _e)
    check(u'B7 生成表与磁盘档案逐字一致（改了表没重生成 ⇒ 这里报）', _gen_ok, _gen_msg)

# ============================================================ C · 桌宠接线
print('')
print('=' * 66)
print(u'C 段  桌宠接线：未练恒等 / 满级变强 / 闸门与冲刺真按倍率走 / 记账与落盘')
print('=' * 66)

_MOTION_EFF = _raw('_motion_eff')
_PROF_TABLE = _raw('_motion_profile_table')
_PROF_OF = _raw('_motion_profile_of')
_NOTE = _raw('_motion_note_practice')
_PROG_FILE = _raw('_motion_progress_file')
_PROG_LOAD = _raw('_motion_progress_load')
_PROG_SAVE = _raw('_motion_progress_save')
_PROG_ENSURE = _raw('_motion_progress_ensure')


class _Pet(object):
    u"""假 self：只放产品方法真正读到的字段，方法本身用产品那一份。"""

    def __init__(self, exp=0.0):
        self._motion_exp = float(exp)
        self._motion_eff_cache = None
        self._motion_profile_cache = None
        self._motion_dirty = False
        self._motion_exp_map = {}
        self._motion_progress_path = None
        self._motion_progress_loaded = True      # 不真去读盘
        self._motion_saved_at = 0.0
        self.max_speed = 15.0
        self.speed = 5.0
        self._last_move_dt = 0.0
        self._runup_ready = False
        self._last_move_speed_px_s = 0.0
        self._runup_best_px_s = 0.0
        self.JUMP_SPEED_MAX = 700.0
        self.jump_duration = 1.0
        self.gravity = 500.0
        self._jump_reject = None
        self.jump_start_pos = None
        self.jump_target_pos = None
        self._motion_note_practice = None


def _bind(p):
    for _name, _fn in (('_motion_profile_table', _PROF_TABLE),
                       ('_motion_profile_of', _PROF_OF),
                       ('_motion_eff', _MOTION_EFF),
                       ('_motion_note_practice', _NOTE),
                       ('_motion_progress_file', _PROG_FILE),
                       ('_motion_progress_load', _PROG_LOAD),
                       ('_motion_progress_save', _PROG_SAVE),
                       ('_motion_progress_ensure', _PROG_ENSURE),
                       ('_nominal_move_dt', _raw('_nominal_move_dt')),
                       ('_max_run_px_s', _raw('_max_run_px_s')),
                       ('_jump_reach_ok', _raw('_jump_reach_ok'))):
        if _fn is not None:
            setattr(p, _name, _mt(p, _fn))
    return p


if _MOTION_EFF is None:
    check(u'C0 产品有 `_motion_eff`（缺它整套接线都不存在）', False)
else:
    p = _bind(_Pet(0.0))
    _e0 = p._motion_eff()
    check(u'C1 ★★★ 没练过 ⇒ 三项全 1.0（与"没有这个模块"逐值相同）',
          all(abs(_e0[k] - 1.0) < 1e-12 for k in ('jump', 'run', 'accel')),
          u'%s' % (_e0,))

    p2 = _bind(_Pet(MP.MAX_EXP if MP else 1200.0))
    _e1 = p2._motion_eff()
    check(u'C2 练满 ⇒ 三项都 > 1（真能练出来）',
          all(_e1[k] > 1.0 for k in ('jump', 'run', 'accel')),
          u'jump=%.3f run=%.3f' % (_e1['jump'], _e1['run']))

    p3 = _bind(_Pet(0.0))
    _e_unknown = p3._motion_eff('nobody_at_all_xyz')
    check(u'C3 陌生 id ⇒ 1.0（没档案不许编一个）',
          all(abs(_e_unknown[k] - 1.0) < 1e-12 for k in ('jump', 'run', 'accel')))

    _e_susie = p3._motion_eff('susie')
    check(u'C3b 真读到了别人的档（susie 三项都 > 1）',
          all(_e_susie[k] > 1.0 for k in ('jump', 'run', 'accel')),
          u'%s' % ({k: round(_e_susie[k], 3) for k in ('jump', 'run', 'accel')},))

    # ---- C4 闸门：同一跳，跳力倍率决定放不放 ----
    # ★ `QPoint` 是纯值类型，**不需要** QApplication。早先这里写成"没 QApplication
    #   就判 FAIL"，而沙箱里 `import main` 并不建 app ⇒ 这条恒 FAIL，且失败原因
    #   跟被测逻辑一点关系没有（第138轮口径：判据自己制造的红也是红，得改判据）。
    try:
        from PyQt5.QtCore import QPoint
        _QP_ERR = ''
    except Exception as _e:                          # noqa: BLE001
        QPoint = None
        _QP_ERR = '%s: %s' % (type(_e).__name__, _e)

    def _gate(eff_jump):
        q = _bind(_Pet(0.0))
        q._motion_eff = lambda npc_id=None, _j=eff_jump: {'jump': _j, 'run': 1.0, 'accel': 1.0}
        q.jump_start_pos = QPoint(500, 900)
        q.jump_target_pos = QPoint(500, 300)          # dy=-600, T=1, g=500 ⇒ vy0=-850
        return q._jump_reach_ok(), q._jump_reject

    if QPoint is None:
        check(u'C4 起跳闸门按跳力倍率放行（需要 QPoint）', False, _QP_ERR)
    else:
        _ok1, _rj1 = _gate(1.0)
        _ok2, _rj2 = _gate(1.4)
        check(u'C4 ★★ 同一跳：1.0 倍率必须拒（too_high），1.4 倍率必须放（倍率真接线）',
              (_ok1 is False) and (_ok2 is True),
              u'1.0 → %s %s / 1.4 → %s %s'
              % (_ok1, ((_rj1 or (u'-',))[0]), _ok2, ((_rj2 or (u'-',))[0])))
        check(u'C4b 拒绝原因确实是 too_high（不是别的分支）',
              (_rj1 or (None,))[0] == 'too_high', u'%s' % ((_rj1 or ())[0],))
        # 负控制：闸门不能"永远拒绝"（那样 C4 也会绿）
        _ok_lo, _ = _gate(1.0)
        _ok_mid, _rj_mid = _gate(1.25)                # 700×1.25 = 875 > 850 ⇒ 该放
        check(u'C4c 正控制：1.25 倍率（875 > 850）必须放 —— 证明 C4 的"拒"不是恒拒',
              _ok_mid is True and _ok_lo is False,
              u'1.0 → %s / 1.25 → %s' % (_ok_lo, _ok_mid))

    # ---- C5 冲刺上限按 run 变，走路速度不变 ----
    # ★★ 夹具的 `max_speed` 必须取 5.0（产品文档里"走路 5px/帧 ⇒ 151px/s"那个实测值），
    #    不能沿用 15.0：上限是 `max(_base, min(_cap, _meas))`，15px/帧 ⇒ _base≈454px/s
    #    已经高过 RUNUP_SPEED_MAX(320) ⇒ 倍率把 _cap 抬到 448 也**看不见**
    #    （被 _base 压住）⇒ C5b 会变成一个永远涨不上去的空转判据。
    #    这是"夹具不保真就会报假问题"的又一例（第164轮记过）。
    _dt = _bind(_Pet(0.0))._nominal_move_dt()

    def _run_cap(run_mult, ready=True, walk=5.0, best=400.0):
        q = _bind(_Pet(0.0))
        q._motion_eff = lambda npc_id=None, _r=run_mult: {'jump': 1.0, 'run': _r, 'accel': 1.0}
        q.max_speed = walk
        q._runup_ready = ready
        q._runup_best_px_s = best
        return q._max_run_px_s()

    _base_walk = 5.0 / _dt
    _cap_walk = _run_cap(1.4, ready=False)
    check(u'C5 ★ 走路速度**不**吃倍率（runup_ready=False 时只看 max_speed）',
          abs(_cap_walk - _base_walk) < 1e-6, u'%.1f px/s（基准 %.1f）' % (_cap_walk, _base_walk))
    # best 给足 ⇒ 上限完全由 `RUNUP_SPEED_MAX × run` 决定，能逐值对齐
    _cap_lo = _run_cap(1.0, best=9999.0)
    _cap_hi = _run_cap(1.4, best=9999.0)
    check(u'C5b ★★ 助跑时冲刺上限 = RUNUP_SPEED_MAX × run（320 → 448，逐值对齐）',
          abs(_cap_lo - 320.0) < 1e-6 and abs(_cap_hi - 448.0) < 1e-6,
          u'1.0 → %.1f / 1.4 → %.1f' % (_cap_lo, _cap_hi))
    # 实测速度小于上限时，取实测（"真跑那么快才放行"这条不能被倍率放水掉）
    _cap_meas = _run_cap(1.4, best=400.0)
    check(u'C5c 倍率只抬上限、**不**伪造实测速度（实测 400 ⇒ 仍取 400）',
          abs(_cap_meas - 400.0) < 1e-6, u'实得 %.1f' % _cap_meas)

    # ---- C6 记账权重 ----
    _tmpf = os.path.join(tempfile.gettempdir(), 'p165_check165_progress.json')
    q = _bind(_Pet(0.0))
    q._motion_progress_file = lambda: _tmpf
    for _ in range(10):
        q._motion_note_practice('jump_ok')
    check(u'C6 成功起跳一次记 12 点（10 次 = 120）',
          abs(q._motion_exp - 120.0) < 1e-6, u'实得 %.1f' % q._motion_exp)
    q._motion_note_practice('jump_fail')
    check(u'C6b 失败也给（+3），且**少于**成功（12:3，撞墙不该比跳成功更划算）',
          abs(q._motion_exp - 123.0) < 1e-6, u'实得 %.1f' % q._motion_exp)
    q._motion_note_practice('errand', npc_id='susie')
    check(u'C6c NPC 的经验记在各自的账上（不混进桌宠那条）',
          abs(float(q._motion_exp_map.get('susie', 0.0)) - 8.0) < 1e-6
          and abs(q._motion_exp - 123.0) < 1e-6,
          u'susie=%.1f self=%.1f' % (q._motion_exp_map.get('susie', 0.0), q._motion_exp))

    # ---- C6d 练到升级 ⇒ 缓存必须失效 ----
    # ★ 这条守的是本模块最容易出的**哑巴 bug**：`_motion_eff()` 有缓存，
    #   练完不失效的话"经验涨了、倍率照旧"，界面上一切正常，就是练了白练。
    q5 = _bind(_Pet(0.0))
    q5._motion_progress_file = lambda: _tmpf
    _j0 = q5._motion_eff()['jump']
    for _ in range(20):                          # 20 × 12 = 240 = 恰好 1 级
        q5._motion_note_practice('jump_ok')
    _j1 = q5._motion_eff()['jump']
    check(u'C6d ★★ 练到升级之后 `_motion_eff` 必须**当场**变（缓存不失效 = 练了白练）',
          abs(_j0 - 1.0) < 1e-12 and _j1 > _j0 + 1e-6,
          u'练前 %.3f → 练后 %.3f（经验 %.0f）' % (_j0, _j1, q5._motion_exp))

    # ---- C7 落盘 round-trip ----
    try:
        os.remove(_tmpf)
    except OSError:
        pass
    _saved = q._motion_progress_save(force=True)
    q2 = _bind(_Pet(0.0))
    # ★★ 必须连 `_motion_progress_file` 一起打桩：`_motion_progress_load()` 里
    #    路径是**它自己算**的（`path = self._motion_progress_file()` 再回写
    #    `_motion_progress_path`）⇒ 只设 `_motion_progress_path` 会被当场覆盖成
    #    真实 vault 路径，于是这条判据读的是用户的真档、跟 `_tmpf` 无关。
    q2._motion_progress_file = lambda: _tmpf
    q2._motion_progress_path = _tmpf
    q2._motion_progress_loaded = False
    q2._motion_progress_load()
    check(u'C7 落盘 → 读回，经验与 NPC 表都一致',
          _saved and abs(q2._motion_exp - 123.0) < 1e-6
          and abs(float(q2._motion_exp_map.get('susie', 0.0)) - 8.0) < 1e-6,
          u'self=%.1f npcs=%s' % (q2._motion_exp, q2._motion_exp_map))
    try:
        os.remove(_tmpf)
    except OSError:
        pass

    # ---- C8 坏档 / 缺档不抛 ----
    _badpath = os.path.join(tempfile.gettempdir(), 'p165_check165_bad.json')
    try:
        with open(_badpath, 'w', encoding='utf-8') as _fh:
            _fh.write('{"self": "abc", "npcs": {"x": "y", "z": 5}}')
        q3 = _bind(_Pet(0.0))
        q3._motion_progress_file = lambda: _badpath
        q3._motion_progress_path = _badpath
        q3._motion_progress_loaded = False
        _threw = False
        try:
            q3._motion_progress_load()
        except Exception:                            # noqa: BLE001
            _threw = True
        check(u'C8 坏档不抛，且坏的那条被丢掉、好的那条留下（z=5）',
              (not _threw) and ('z' in q3._motion_exp_map)
              and ('x' not in q3._motion_exp_map),
              u'map=%s' % (q3._motion_exp_map,))
    finally:
        try:
            os.remove(_badpath)
        except OSError:
            pass
    q4 = _bind(_Pet(0.0))
    _missing = os.path.join(tempfile.gettempdir(), 'p165_no_such_file.json')
    try:
        os.remove(_missing)
    except OSError:
        pass
    q4._motion_progress_file = lambda: _missing
    q4._motion_progress_path = _missing
    q4._motion_progress_loaded = False
    _threw2 = False
    try:
        q4._motion_progress_load()
    except Exception:                                # noqa: BLE001
        _threw2 = True
    check(u'C9 缺档（老存档）不抛、当 0（这是**正常态**，不是错误）',
          (not _threw2) and abs(q4._motion_exp) < 1e-9)

# ============================================================ D · 零回归结构
print('')
print('=' * 66)
print(u'D 段  零回归的**结构性**保证（不是靠"这次跑绿了"）')
print('=' * 66)

check(u'D1 基准人 id 是 ralsei', getattr(MAIN_MOD, 'MOTION_PROFILE_ID', None) == 'ralsei',
      u'实得 %r' % (getattr(MAIN_MOD, 'MOTION_PROFILE_ID', None),))
check(u'D2 经验文件名单个、走 data_store（不自己拼绝对路径）',
      getattr(MAIN_MOD, 'MOTION_PROGRESS_FILE', None) == 'motion_progress.json')

_METHODS = {}
if _TREE is not None:
    for _n in ast.walk(_TREE):
        if isinstance(_n, ast.ClassDef) and _n.name == 'RalseiPet':
            for _m in _n.body:
                if isinstance(_m, ast.FunctionDef):
                    _METHODS[_m.name] = _m


def _line_of(fn_name, needle):
    """在某方法里找含 `needle` 的那一行（返回去空白后的字符串）。"""
    _node = _METHODS.get(fn_name)
    if _node is None or _TREE is None:
        return ''
    _seg = ast.get_source_segment(_SRC, _node) or ''
    for _ln in _seg.replace('\r\n', '\n').split('\n'):
        if needle in _ln:
            return _ln.strip()
    return ''


# ---- D3 闸门那行确实乘了，且乘的是 jump ----
_g_line = _line_of('_jump_reach_ok', '_limit *=') or _line_of('_jump_reach_ok', '_limit =')
check(u'D3 `_jump_reach_ok` 的 `_limit` 那行真的乘了 `_motion_eff()`（AST 定位，不纯文本扫）',
      '_motion_eff' in _g_line and 'jump' in _g_line, u'实得 %r' % (_g_line[:100],))

# ---- D4 冲刺上限乘了 run，但 _base 那行**没有**乘（走路手感不变） ----
_cap_line = _line_of('_max_run_px_s', 'RUNUP_SPEED_MAX *')
_base_line = _line_of('_max_run_px_s', '_base =')
check(u'D4 ★ 冲刺上限那行乘了 run', '_motion_eff' in _cap_line and 'run' in _cap_line,
      u'实得 %r' % (_cap_line[:100],))
check(u'D4b ★★★ `_base`（走路速度）那行**没有**乘倍率 —— 走路手感不随练习变',
      bool(_base_line) and '_motion_eff' not in _base_line,
      u'实得 %r' % (_base_line[:100],))

# ---- D5 助跑距离用的是乘过 accel 的加速度 ----
_acc_line = _line_of('_try_runup', 'RUNUP_ACCEL *')
check(u'D5 助跑的加速度乘了 accel（L=v²/(2a) 里 a 变了，助跑距离才会变）',
      '_motion_eff' in _acc_line and 'accel' in _acc_line, u'实得 %r' % (_acc_line[:100],))

# ---- D6 记账点真的接在起跳成功/失败与差事办完上 ----
_start_line_ok = _line_of('_start_floor_jump', "jump_ok")
_start_line_fail = _line_of('_start_floor_jump', "jump_fail")
check(u'D6 `_start_floor_jump` 成功与失败**两条**都记账（失败不计就是"撞墙不进步"）',
      bool(_start_line_ok) and bool(_start_line_fail))
_errand_line = _line_of('_npc_errand_commit', "'errand'")
check(u'D6b 差事办完也记账（NPC 侧的运动能力来源）', bool(_errand_line),
      u'实得 %r' % (_errand_line[:80],))

# ============================================================ E · 自检
print('')
print('=' * 66)
print(u'E 段  自检')
print('=' * 66)

_self_path = os.path.abspath(__file__)
_self_raw = open(_self_path, 'rb').read()
check(u'E1 本套件无 BOM', not _self_raw.startswith(b'\xef\xbb\xbf'))
_self_txt = _self_raw.decode('utf-8', 'replace')
check(u'E2 本套件行尾统一（纯 LF 或纯 CRLF，不混合）',
      not (_self_raw.count(b'\r\n') > 0
           and (_self_raw.count(b'\n') - _self_raw.count(b'\r\n')) > 0))

# ★★ 自检必须扫**本文件**这棵树，不能借 D 段那棵 `_TREE`（那是 main.py 的）。
#    早先就写错成后者：`_names` 恒空 ⇒ E5「实得 0 条」恒 FAIL、
#    E4「无坏名」恒 PASS —— 一条恒假配一条恒真，正好互相掩护（第134/136轮同族）。
_SELF_TREE = ast.parse(_self_txt)
_SELF_FUNCS = [n.name for n in _SELF_TREE.body if isinstance(n, ast.FunctionDef)]
# ★★★ E3 也不能用 `'def ok(' in 文本`：判据自己那一行就含这串字，
#    扫描器把自己的字符串当证据 ⇒ 自己把自己打红（第96b轮同型坑）。
check(u'E3 本套件只用 `check()` 一套 harness（AST 取顶层函数名，不扫文本）',
      ('check' in _SELF_FUNCS) and ('ok' not in _SELF_FUNCS),
      u'顶层函数 %s' % (_SELF_FUNCS,))
# ---- E4 判据名不带计数标记（改条数时不用改名字） ----
_names = []
for _n in ast.walk(_SELF_TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'check' and _n.args:
        _a = _n.args[0]
        if isinstance(_a, ast.Constant) and isinstance(_a.value, str):
            _names.append(_a.value)
_badnames = [s for s in _names
             if any(t in s for t in (u'共', u'共 %', u'(N=', u'条判据'))]
check(u'E4 判据名里不带计数标记（走 AST 取 desc，不纯文本扫）', not _badnames,
      u'命中 %s' % (_badnames[:3],))
# ★ 这条自己的 desc 不许含 `条判据`（否则会被 E4 当成坏名 —— 又一次自指）
check(u'E5 分母闸：判据条数 ≥ 30（防"判据被意外删空还全绿"）',
      len(_names) >= 30, u'实得 %d 条' % len(_names))

print('')
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print(u'失败项：')
    for _x in _bad:
        print(u'  - %s' % _x)
    sys.exit(1)
print(u'[PASS] 第165轮运动能力养成回归锁全部通过')
