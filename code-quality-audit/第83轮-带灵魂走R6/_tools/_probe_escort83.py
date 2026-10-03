# -*- coding: utf-8 -*-
"""第83轮 R6 独立行为探针 —— 在接线前先证明 EscortState 逻辑正确。

★ 纪律：本探针**只读模块 + 跑纯函数**，不碰 Qt、不碰项目内其它模块。
★ A/B 锚点：sampling 下标必须**先验证**(lag=12 时取 trace[-13])，
   否则"照抄原作 12 帧"这句话无法自证。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')          # 仓库根
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import escort  # noqa: E402

PASS = [0]
FAIL = [0]


def check(name, cond, extra=''):
    if cond:
        PASS[0] += 1
        print('[PASS] %s' % name)
    else:
        FAIL[0] += 1
        print('[FAIL] %s %s' % (name, extra))


print('=' * 66)
print('一、★ A/B 锚点：轨迹采样下标必须先自证')
print('=' * 66)
st = escort.EscortState('kris', lag=12)
# 塞 25 个可区分的点：(0,0) (1,1) ... (24,24)
for i in range(25):
    st.push_trace(i, i)
# trace[-1] = (24,24) = 当前；12 帧前 = trace[-13] = (12,12)
pt = st.sample_at(12)
check('sampling: lag=12 ⇒ trace[-13] = (12,12)', pt == (12.0, 12.0), 'got %r' % (pt,))
pt0 = st.sample_at(1)
check('sampling: lag=1 ⇒ trace[-2] = (23,23)', pt0 == (23.0, 23.0), 'got %r' % (pt0,))
check('sampling: lag=0 ⇒ None（不许当"当前帧"用）', st.sample_at(0) is None)
check('sampling: lag=999 ⇒ None（历史不够，不猜）', st.sample_at(999) is None)

print()
print('=' * 66)
print('二、照抄值自证（与 companion 同一个原作表）')
print('=' * 66)
check('TRACE_LEN == 25（原作 remx[25]）', escort.TRACE_LEN == 25)
check('FOLLOW_LAG == 12（原作 12 + slot*12，slot=0）', escort.FOLLOW_LAG == 12)
check('FRAME_HZ == 30（原作 GMS2FPS）', escort.FRAME_HZ == 30)

print()
print('=' * 66)
print('三、状态机：直接带路 / 征求同意 / 拒绝')
print('=' * 66)
s1 = escort.EscortState('kris')
check('direct: request ⇒ LEADING', s1.request('kris', kind='direct') == escort.ESCORT_LEADING)
check('direct: is_leading True', s1.is_leading is True)

s2 = escort.EscortState('os_niko')
check('consent: 未问过 ⇒ ASKING', s2.request('os_niko', kind='consent') == escort.ESCORT_ASKING)
check('consent: is_asking True', s2.is_asking is True)
check('consent: grant ⇒ LEADING', s2.grant() == escort.ESCORT_LEADING)

s3 = escort.EscortState('os_niko')
s3.request('os_niko', kind='consent')
check('consent: refuse ⇒ REFUSED', s3.refuse() == escort.ESCORT_REFUSED)
check('consent: 拒绝后 mode 不是 LEADING', s3.mode != escort.ESCORT_LEADING)
check('consent: 拒绝后再 request ⇒ REFUSED（不静默放行）',
      s3.request('os_niko', kind='consent') == escort.ESCORT_REFUSED)

s4 = escort.EscortState('kris')
check('forbidden ⇒ REFUSED', s4.request('sans', kind='forbidden') == escort.ESCORT_REFUSED)
check('非法 id ⇒ REFUSED', s4.request(None, kind='direct') == escort.ESCORT_REFUSED)
check('非法 id 不改原状态', s4.mode == escort.ESCORT_NONE)

s5 = escort.EscortState('kris')
s5.request('kris', kind='direct')
check('跨场景 ⇒ REFUSED',
      s5.request('kris', kind='direct', scene='a', leader_scene='b') == escort.ESCORT_REFUSED)
s6 = escort.EscortState('kris')
check('一侧场景为 None ⇒ 不校验（不拿未知当不同）',
      s6.request('kris', kind='direct', scene='a', leader_scene=None) == escort.ESCORT_LEADING)

print()
print('=' * 66)
print('四、★ 行为：直接置位（用户裁定"完全照原作"）')
print('=' * 66)
s7 = escort.EscortState('kris', lag=12)
s7.request('kris', kind='direct')
s7.reset_trace(100.0, 200.0)
check('reset_trace 填满 25 个点', len(s7._trace) == 25)
# 带路者从 (100,200) 往右走 1 px/帧
pos = None
for i in range(1, 16):
    pos = s7.step(100.0 + i, 200.0)
# 第 15 帧时：trace[-1]=(115,200)，12 帧前 = trace[-13]=(103,200)
check('step: 直接置位到 12 帧前那一点',
      pos == (103.0, 200.0), 'got %r' % (pos,))
check('step: follower 坐标同步', (s7.follower_x, s7.follower_y) == (103.0, 200.0))

s8 = escort.EscortState('kris')
s8.request('kris', kind='direct')
check('未 reset / 历史不足 ⇒ step 返回 None（不猜）', s8.step(5.0, 5.0) is None)

s9 = escort.EscortState('kris')
check('未带路 ⇒ step 返回 None（★核心行为判据）', s9.step(1.0, 1.0) is None)
check('未带路 ⇒ needs_step False', s9.needs_step() is False)

print()
print('=' * 66)
print('五、幂等 / 停 / 叠')
print('=' * 66)
s10 = escort.EscortState('kris')
s10.request('kris', kind='direct')
check('stop ⇒ NONE', s10.stop() == escort.ESCORT_NONE)
check('stop 幂等', s10.stop() == escort.ESCORT_NONE)
check('stop 后 leader 清空', s10.leader_id is None)
s11 = escort.EscortState('kris')
s11.request('kris', kind='direct')
r = s11.request('ut_frisk', kind='direct')
check('二次 request 不叠加（后者胜）', r == escort.ESCORT_LEADING and s11.leader_id == 'ut_frisk',
      'leader=%r' % s11.leader_id)

print()
print('=' * 66)
print('六、归一 / 非法输入不抛')
print('=' * 66)
check('id 归一：  "  KRIS  " ⇒ kris', escort._norm_id('  KRIS  ') == 'kris')
check('id 归一： 全角空格', escort._norm_id('\u3000kris\u3000') == 'kris')
check('id 归一：空串 ⇒ None', escort._norm_id('') is None)
check('id 归一：非串 ⇒ None', escort._norm_id(123) is None)
s12 = escort.EscortState('kris')
check('push_trace 非法不抛且返回 False', s12.push_trace('x', None) is False)
check('push_trace nan 拒绝', s12.push_trace(float('nan'), 0.0) is False)
check('reset_trace 非法不抛', s12.reset_trace(None, None) is False)
check('consent 非法 id 不抛', s12.consent.grant('') is False)

print()
print('=' * 66)
print('七、★ 本模块自带 _MiniConsent 与 R5 ConsentState 必须语义等价')
print('=' * 66)
pos_path = os.path.join(MOD, 'possession.py')
psrc = io.open(pos_path, encoding='utf-8').read()
ptree = ast.parse(psrc)
# 把 possession.py 里 ConsentState 的源码抠出来单独 exec（不 import 它，
# 因为 possession 顶层 import 也是零依赖，可以安全 exec）
seg = None
for n in ptree.body:
    if isinstance(n, ast.ClassDef) and n.name == 'ConsentState':
        seg = ast.get_source_segment(psrc, n)
check('能从 possession.py 抠出 ConsentState 源码', bool(seg))
if seg:
    # ★ 抠出来的类**依赖模块级 SCHEMA_VERSION** ⇒ 必须一起喂进 exec 命名空间。
    #   （首版漏了它 ⇒ NameError ⇒ 这是**探针的错**，不是被测代码的错。
    #     本项目纪律：判据报红先怀疑判据。）
    ns = {'SCHEMA_VERSION': 1}
    exec(compile(seg, '<consent>', 'exec'), ns)
    RealConsent = ns['ConsentState']
    # A/B：同一组操作，两边状态逐值相等
    ops = [('grant', 'kris'), ('refuse', 'niko'), ('grant', 'niko'),
           ('grant', ''), ('reset', 'kris')]
    a, b = RealConsent(), escort._MiniConsent()
    for meth, arg in ops:
        ra = getattr(a, meth)(arg)
        rb = getattr(b, meth)(arg)
        check('  A/B %s(%r) 返回值相等' % (meth, arg), ra == rb, 'real=%r mini=%r' % (ra, rb))
    check('A/B as_dict 逐值相等（两实现同形状）', a.as_dict() == b.as_dict(),
          'real=%r mini=%r' % (a.as_dict(), b.as_dict()))
    check('A/B 三态语义：未问/同意/拒绝可区分',
          (a.get('zzz'), a.get('niko'), a.get('kris')) == (None, True, None),
          'real=%r' % (a.get('niko'),))

print()
print('=' * 66)
print('八、序列化')
print('=' * 66)
s13 = escort.EscortState('kris')
s13.consent.grant('os_niko')
d = s13.as_dict()
check('as_dict 形状', set(d.keys()) == {'schema_version', 'mode', 'leader',
                                       'follower', 'lag', 'consent'})
s14 = escort.EscortState('kris')
check('load_dict 只恢复 consent', s14.load_dict(d) is True and s14.consent.get('os_niko') is True)
check('load_dict 非法 ⇒ False', s14.load_dict('x') is False)
check('带路本身不跨会话（load 后 mode 仍 NONE）', s14.mode == escort.ESCORT_NONE)

print()
print('=' * 66)
print('九、describe_mode 覆盖全部状态码')
print('=' * 66)
for m in (escort.ESCORT_NONE, escort.ESCORT_ASKING, escort.ESCORT_LEADING,
          escort.ESCORT_REFUSED):
    check('describe_mode(%s) 非空' % m, bool(escort.describe_mode(m)))
check('未知状态码原样返回', escort.describe_mode('???') == '???')

print()
print('=' * 66)
print('PASS=%d FAIL=%d' % (PASS[0], FAIL[0]))
print('=' * 66)
sys.exit(1 if FAIL[0] else 0)
