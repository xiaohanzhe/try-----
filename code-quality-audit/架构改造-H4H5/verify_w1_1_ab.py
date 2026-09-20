# -*- coding: utf-8 -*-
"""W1-1 A/B 校验：**父版本** vs **当前版本**，跑同一组场景，比对轨迹。

A/B 纪律（W1-4 报告第五节，真踩过）：
  1. **先断言 A ≠ B** —— 取"旧值"若恰好拿到已提交的当前版，A == B，
     探针就退化成"自己跟自己比"，结论必然"没差别"**且非常像真的**。
     本脚本**第一步**就比两份 main.py 的 md5，相同即 SystemExit。
  2. 取**父版本**源码：本项施工**尚未提交**时父版本 = `HEAD:...`；
     已提交则 = `HEAD~1:...`。用"哪份含这 4 个方法"来自动判定。
  3. 轨迹 = 一组**行为可观测量**的序列（不是源码文本），两版必须逐项一致。

与 unit 探针的分工：
  · unit  —— 静态：方法体逐字等价
  · e2e   —— 动态：当前版能跑
  · ab    —— 动态×2：**两版跑出同样的行为**（这才是"改造不改行为"的直接证据）
"""
import ast
import hashlib
import io
import os
import subprocess
import sys
import types

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
# ★ 当前版这 4 个方法**已经搬出 main.py**，落在这个新模块里。
#   早先的版本把两侧都从 main.py 取 → 当前侧恒为空（AB2b n=0），
#   于是 A/B 根本没跑起来。取源码必须**按方法实际所在文件**取。
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'spell_controller.py')
CTRL_REL = 'ralsei_pet/modules/spell_controller.py'
NAMES = ['_spell_interrupted_reason', '_tick_spell_flow',
         '_cast_spell_then', '_start_open_with_spell']

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


def git_show(path, rev):
    p = subprocess.run(['git', 'show', '%s:%s' % (rev, path)],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return p.stdout if p.returncode == 0 else None


def find_parent():
    """找"这 4 个方法还在 main.py 里"的那个版本 = W1-1 施工前的父版本。"""
    for rev in ('HEAD', 'HEAD~1', 'HEAD~2'):
        s = git_show('ralsei_pet/src/main.py', rev)
        if s and all(('    def %s' % n) in s for n in NAMES):
            return rev, s
    return None, None


print('=== A/B 前置：取父版本 + 断言 A != B ===')
cur_src = io.open(CTRL, encoding='utf-8').read()          # B：当前（控制器）
rev, old_src = find_parent()                              # A：父版本（main.py）
check('AB0 找到含这 4 个方法的父版本', old_src is not None,
      'rev=%s' % rev)
if old_src is None:
    sys.exit(1)

md5_old = hashlib.md5(old_src.encode('utf-8')).hexdigest()
md5_cur = hashlib.md5(cur_src.encode('utf-8')).hexdigest()
print('   父版本 %s md5 = %s' % (rev, md5_old))
print('   当前   md5 = %s' % md5_cur)
if md5_old == md5_cur:
    # 硬红线：A == B 时继续跑毫无意义，且会产出"非常像真的"的假结论
    print('  !! A == B —— 探针已退化，拒绝继续（这是 W1-4 踩过的坑）')
    sys.exit(3)
check('AB1 A != B（md5 不同，探针未退化）', md5_old != md5_cur)


# ---------------- 构建"旧版宿主"：用父版本源码 exec 出 RalseiPet ----------------
print()
print('=== AB2 用父版本源码构建旧版宿主 ===')


def build_old_host(src, tmp_path):
    """把父版本 main.py 落成临时模块并导入。

    注意：父版本里 4 个方法是 RalseiPet 的成员，控制器还不存在；
    本脚本只关心**行为轨迹**，所以用同一个 stub 宿主驱动两种实现。
    为了不拉起整个 GUI，这里**只提取 4 个方法体**，装进一个共享 stub，
    再分别用"父版方法体"和"当前控制器方法体"跑，比对轨迹。
    """
    return None


# 上面那种"整文件导入"的方案会拉起 GUI/init_systems，代价过高且不稳。
# 改用**方法体级** A/B：从两版源码里提取 4 个方法，编译进同一个 stub 类，
# 各跑一遍同样的场景序列，比对轨迹。这与 e2e 的分工互补：e2e 保证"当前版能跑"，
# 这里保证"两版跑出同样的行为"。
from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])


def extract_methods(src):
    """在整份源码里搜这 4 个方法，**不预设宿主类名**。

    父版本里它们是 `RalseiPet` 的成员，当前版本里是 `SpellFlowController`
    的成员 —— 写死类名会让一侧静默返回 {}（AB2b 已踩）。
    """
    t = ast.parse(src)
    found = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in NAMES:
                    found[fn.name] = fn
    return found


old_nodes = extract_methods(old_src)
cur_nodes = extract_methods(cur_src)
check('AB2a 父版本 4 个方法可提取', len(old_nodes) == 4, 'n=%d' % len(old_nodes))
check('AB2b 当前版本 4 个方法可提取', len(cur_nodes) == 4, 'n=%d' % len(cur_nodes))
print('   A = %s:ralsei_pet/src/main.py' % rev)
print('   B = 工作区 ralsei_pet/modules/spell_controller.py')
if len(old_nodes) != 4 or len(cur_nodes) != 4:
    # 提取不齐就没有 A/B 可言，硬退（不产"静默跳过"的假绿）
    sys.exit(3)

old_lines = old_src.split('\n')
cur_lines = cur_src.split('\n')


# ---------------- 构造 stub 宿主 ----------------
print()
print('=== AB3 构造共享 stub 宿主 ===')


def make_stub(logger_obj, log_sink):
    """一个最小宿主：字段与真机一致，方法只做可观测记录。"""
    class Loader:
        sprites = {'spell': [object()] * 11, 'spell_left': [object()] * 11}

        def note_animation_miss(self, *a, **k):
            log_sink.append(('anim_miss', a[0] if a else None))

    class Sound:
        def play_spell(self):
            log_sink.append(('sound', 'play_spell'))

    class Agent:
        def suspend(self):
            log_sink.append(('agent', 'suspend'))

        def resume(self):
            log_sink.append(('agent', 'resume'))

    class Stub:
        pass

    s = Stub()
    s.sprite_loader = Loader()
    s.sound_manager = Sound()
    s.autonomous_agent = Agent()

    # 状态
    s._spell_stage = None
    s._spell_target_direction = None
    s._spell_target_path = None
    s._spell_target_kind = None
    s._spell_target_screen_pos = None
    s._spell_finish_cb = None
    s._spell_frames_seen = 0
    s._spell_cast_start_frame = None
    s._spell_touched_flag = False
    s._spell_auto_suspended = False
    s._spell_seen_frame = -1
    s._spell_cast_start_time = None
    # 环境
    s._hide_stage = None
    s._hide_obstacles = []
    s._hide_folder_path = None
    s._is_being_dragged = False
    s.is_jumping = False
    s.is_falling = False
    s.is_moving = False
    s.current_speed_x = 0
    s.current_speed_y = 0
    s.current_animation = 'idle'
    s.current_frame = 0
    s.current_direction = 'right'
    s.previous_direction = 'right'
    s.target_pos = None
    s.last_animation_change = 0

    # 可观测回调
    def change_animation(anim, force=False, **kw):
        log_sink.append(('change_animation', anim))
        s.current_animation = anim
        return True

    def frameGeometry():
        from PyQt5.QtCore import QRect
        return QRect(100, 100, 10, 10)

    def width():
        return 100

    def height():
        return 100

    def _resolve_target_screen_anchor(path):
        log_sink.append(('resolve_anchor', path))
        return (500, 500)

    def _abort_hide_and_seek(reason='generic'):
        log_sink.append(('abort_hide_seek', reason))

    s.change_animation = change_animation
    s.frameGeometry = frameGeometry
    s.width = width
    s.height = height
    s._resolve_target_screen_anchor = _resolve_target_screen_anchor
    s._abort_hide_and_seek = _abort_hide_and_seek
    return s


def install_code(stub, whole_src, names, log_sink):
    """把 whole_src 里 names 指定的方法**全部**编译绑到 stub 上。

    whole_src = "含这些方法的整份源码"（父版 main.py / 当前版控制器）。
    ★ 必须一次装齐 NAMES 里的 4 个：`_tick_spell_flow` 会调
      `self._spell_interrupted_reason()`；只装"被直接驱动的那个方法"会让
      两侧**同时**抛 AttributeError → 轨迹相同 → 假 PASS（本探针已踩）。
    """
    t = ast.parse(whole_src)
    lines = whole_src.split('\n')
    bodies = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in names:
                    bodies[fn.name] = '\n'.join(lines[fn.lineno - 1:fn.end_lineno])

    ns = {'__name__': '_ab_probe', 'time': __import__('time'), 'os': os}
    from PyQt5.QtCore import QPoint
    ns['QPoint'] = QPoint
    import logging
    ns['_log'] = logging.getLogger('ab_probe')

    mod_src = 'class _Holder(object):\n'
    for nm in names:
        if nm not in bodies:
            continue
        for line in bodies[nm].split('\n'):
            mod_src += ('    ' + line if line.strip() else '') + '\n'
        mod_src += '\n'
    mod_src += '\n'.join(
        '    ' + l if l.strip() else '' for l in '''

    def _log_(self):
        import logging
        return logging.getLogger('ab_probe')
'''.split('\n'))

    exec(compile(mod_src, '<ab>', 'exec'), ns)
    H = ns['_Holder']
    ok = []
    # ★ `_log_` 不在 NAMES 里，必须**单独**绑 —— 只遍历 names 会漏掉它，
    #   于是中断路径触发 `self._log_()` 时抛 AttributeError（已踩，AB7 抓到）。
    for nm in list(names) + ['_log_']:
        if hasattr(H, nm):
            setattr(stub, nm, types.MethodType(getattr(H, nm), stub))
            if nm in names:
                ok.append(nm)
    return ok


# ---------------- 场景定义 ----------------
print()
print('=== AB4 场景 1：_cast_spell_then 纯施法（left / right）===')


def scenario_cast(whole_src, direction):
    sink = []
    stub = make_stub(None, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    try:
        stub._cast_spell_then(lambda p, k: sink.append(('cb', p, k)),
                              direction=direction)
        err = None
    except Exception as e:
        err = type(e).__name__
    snap = {
        'stage': stub._spell_stage,
        'dir': stub._spell_target_direction,
        'kind': stub._spell_target_kind,
        'anim': stub.current_animation,
        'frame': stub.current_frame,
        'frames_seen': stub._spell_frames_seen,
        'seen_frame': stub._spell_seen_frame,
        'auto_susp': stub._spell_auto_suspended,
        'err': err,
    }
    return sink, snap


for d in ('left', 'right'):
    so, ao = scenario_cast(old_src, d)
    sn, an = scenario_cast(cur_src, d)
    check('AB4.%s %s _cast_spell_then 事件序列一致' % (d, '父'),
          so == sn, 'old=%s new=%s' % (so, sn))
    check('AB4.%s %s _cast_spell_then 末态一致' % (d, '父'),
          ao == an, 'old=%s new=%s' % (ao, an))

print()
print('=== AB5 场景 2：_start_open_with_spell（walking 入口）===')


def scenario_open(whole_src, path, kind):
    sink = []
    stub = make_stub(None, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    try:
        stub._start_open_with_spell(path, kind, lambda p, k: None)
        err = None
    except Exception as e:
        err = type(e).__name__
    snap = {
        'stage': stub._spell_stage,
        'kind': stub._spell_target_kind,
        'path': stub._spell_target_path,
        'pos': stub._spell_target_screen_pos,
        'dir': stub._spell_target_direction,
        'auto_susp': stub._spell_auto_suspended,
        'err': err,
    }
    return sink, snap


for pth, kd in ((r'C:\a\b.txt', 'file'), (r'C:\a', 'folder')):
    so, ao = scenario_open(old_src, pth, kd)
    sn, an = scenario_open(cur_src, pth, kd)
    check('AB5 %s/%s 事件序列一致' % (kd, pth), so == sn,
          'old=%s new=%s' % (so, sn))
    check('AB5 %s/%s 末态一致' % (kd, pth), ao == an,
          'old=%s new=%s' % (ao, an))

print()
print('=== AB6 场景 3：_spell_interrupted_reason 全分支 ===')


def scenario_reason(whole_src, mutate):
    sink = []
    stub = make_stub(None, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    mutate(stub)
    try:
        r = stub._spell_interrupted_reason()
        err = None
    except Exception as e:
        r = None
        err = type(e).__name__
    return r, err


def m_none(s):
    s._spell_stage = None


def m_drag(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'spell'
    s._is_being_dragged = True


def m_touch(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'spell'
    s._spell_touched_flag = True


def m_jump(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'spell'
    s.is_jumping = True


def m_fall(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'spell'
    s.is_falling = True


def m_mismatch(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'idle'


def m_ok(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s.current_animation = 'spell'
    s.current_direction = 'right'


def m_dir_sync(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'left'
    s.current_animation = 'spell_left'
    s.current_direction = 'right'   # 动画对、方向不对 → 应同步不中断


for nm, mut in (('None', m_none), ('drag', m_drag), ('touch', m_touch),
                ('jump', m_jump), ('fall', m_fall), ('mismatch', m_mismatch),
                ('ok', m_ok), ('dir_sync', m_dir_sync)):
    ro, eo = scenario_reason(old_src, mut)
    rn, en = scenario_reason(cur_src, mut)
    check('AB6 %-9s 返回值一致' % nm, (ro, eo) == (rn, en),
          'old=%r/%r new=%r/%r' % (ro, eo, rn, en))
    # ★ 硬哨兵：两侧同为 None/无异常，也可能是"双双没跑起来"。
    #   本组里只有 None/ok/dir_sync 三种情况**合法地**返回 None 且不抛。
    if nm in ('drag', 'touch', 'jump', 'fall', 'mismatch'):
        check('AB6 %-9s 确实产出了原因（非空跑）' % nm,
              ro is not None and eo is None, 'r=%r err=%r' % (ro, eo))

print()
print('=== AB7 场景 4：_tick_spell_flow 中断分支（本项 P0 所在）===')
# 这一组正是实锤 P0 的地方：父版本用模块级 _log（能解析），
# 当前版本若写裸 _log_() 会 NameError —— A/B 必须**一致**才算过。
# 注：本脚本给当前版注入了 self._log_，故修复后应当一致。


def scenario_tick(whole_src, mutate, ticks=3):
    sink = []
    stub = make_stub(None, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    mutate(stub)
    err = None
    try:
        for i in range(ticks):
            stub._tick_spell_flow()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage': stub._spell_stage,
        'dir': stub._spell_target_direction,
        'cb': stub._spell_finish_cb,
        'frames_seen': stub._spell_frames_seen,
        'seen_frame': stub._spell_seen_frame,
        'touched': stub._spell_touched_flag,
        'auto_susp': stub._spell_auto_suspended,
        'anim': stub.current_animation,
        'err': err,
    }
    return sink, snap


def t_cast(s):
    s._spell_stage = 'casting'
    s._spell_target_direction = 'right'
    s._spell_target_kind = 'file'
    s._spell_target_path = r'C:\x.txt'
    s._spell_finish_cb = None
    s._spell_frames_seen = 0
    s._spell_seen_frame = -1
    s._spell_cast_start_time = None
    s.current_animation = 'spell'


def t_interrupt_drag(s):
    t_cast(s)
    s._is_being_dragged = True


def t_walking(s):
    s._spell_stage = 'walking'
    s._spell_target_screen_pos = (10000, 10000)
    s._spell_target_direction = 'right'
    s._spell_target_kind = 'folder'
    s._spell_target_path = r'C:\a'
    s._spell_finish_cb = None
    s._spell_frames_seen = 0
    s._spell_seen_frame = -1
    s._spell_auto_suspended = False
    s.current_animation = 'walk_right'


# 本组要求：两侧**都不许抛异常**。早先版本两侧同抛 AttributeError 仍判 PASS，
# 是典型"假绿"（轨迹相同恰恰因为代码根本没跑到）。故加硬哨兵。
for nm, mut in (('casting x3', t_cast),
                ('interrupt(drag)', t_interrupt_drag),
                ('walking x3', t_walking)):
    so, ao = scenario_tick(old_src, mut)
    sn, an = scenario_tick(cur_src, mut)
    check('AB7 %-16s 两侧均无异常' % nm,
          ao['err'] is None and an['err'] is None,
          'old_err=%r new_err=%r' % (ao['err'], an['err']))
    check('AB7 %-16s 事件序列一致' % nm, so == sn,
          'old=%s new=%s' % (so, sn))
    check('AB7 %-16s 末态一致' % nm, ao == an,
          'old=%s new=%s' % (ao, an))

print()
n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print('=' * 60)
print('W1-1 A/B：共 %d 项，通过 %d，失败 %d' % (len(results), n_pass, n_fail))
print('父版本 rev = %s (md5 %s)' % (rev, md5_old[:12]))
print('当前   md5 = %s' % md5_cur[:12])
sys.exit(0 if n_fail == 0 else 1)
