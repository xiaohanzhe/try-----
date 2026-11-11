# -*- coding: utf-8 -*-
u"""第184轮 · 变异测试：把门控层的每一环逐个打断，看 `check184` 抓不抓得到。

三条铁律（第178/182/183轮踩出来的）
----------------------------------
① **期望红必须 > 0 且 < 总数** —— 防"整段崩掉、一条 `[FAIL]` 都不打"那种假抓到
   （第178轮 M3、第182轮坑 3 都栽过：rc=1 但红项为空）。
② **双跑幂等** —— 同一变异跑两遍，红集必须一模一样。
③ **只动这四个文件、每步都还原** —— 变异**原地**做（副本方案行不通：
   `scene_routing` 会 `import scene_system`，拷依赖链会一路扩散），
   但每个变异前后都从 `D:\\_tmp184\\orig` 的**快照**整文件还原，
   收尾再核四个文件的 sha1 == 开工前。

★ 为什么不能"拷一棵树到临时区"：第174轮把整个 `ralsei_pet` 拷进去时被**清理守卫**
  拦下（1714 个文件 rmtree > 50 阈值）。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')

WORK = os.path.join('D:\\', '_tmp184')
ORIG = os.path.join(WORK, 'orig')

#: 会被变异的**四个真文件**（其余模块一个不碰）。
TARGETS = {
    'routes': os.path.join(PET, 'assets', 'scenes', '_routes.json'),
    'main': os.path.join(PET, 'src', 'main.py'),
    'sr': os.path.join(PET, 'modules', 'scene_routing.py'),
    'ii': os.path.join(PET, 'modules', 'item_interact.py'),
}

CHECK = os.path.join(HERE, 'check184.py')
TOTAL_CHECKS = 34

BASELINE = {}


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr_raw(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sha(p):
    import hashlib
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def lf(s):
    u"""锚点一律在 LF 上写（源文件是 CRLF，直接拿 CRLF 文本当锚必然落空）。"""
    return s.replace('\r\n', '\n')


def snapshot():
    if os.path.isdir(ORIG):
        shutil.rmtree(ORIG, ignore_errors=True)
    os.makedirs(ORIG)
    for k, p in TARGETS.items():
        shutil.copyfile(p, os.path.join(ORIG, k + '.bak'))
        BASELINE[k] = sha(p)


def restore():
    u"""整文件还原（不信"上一步没改"，每次都拷一遍）。"""
    for k, p in TARGETS.items():
        shutil.copyfile(os.path.join(ORIG, k + '.bak'), p)


def run_check():
    p = subprocess.run([sys.executable, CHECK], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    green, red = [], []
    for line in out.splitlines():
        m = re.match(r'^\[(PASS|FAIL)\] (\S+)', line)
        if m:
            (green if m.group(1) == 'PASS' else red).append(m.group(2))
    return p.returncode, green, red, out


def patch(key, old, new):
    u"""在 LF 化的文本上做**一次性**替换（原文件的 CRLF 保持不动）。

    ★ 旧串必须**真的出现**（`assert`）—— 锚点落空是最常见的"变异没生效、
      看起来像判据不灵"（第182轮坑 2）。
    """
    p = TARGETS[key]
    s = lf(rd(p))
    assert old in s, u'锚点没命中：%s / %r' % (key, old[:60])
    wr_raw(p, s.replace(old, new, 1))


MUTS = []


def mut(name, expect):
    def deco(fn):
        MUTS.append((name, set(expect), fn))
        return fn
    return deco


# --------------------------------------------------------------- 数据侧
@mut(u'M1 把 `_gates` 整条删掉', ['A1', 'A2', 'A3', 'A4', 'A8', 'B1', 'B2', 'B6',
                                'B7', 'B8', 'B9', 'B10', 'D2'])
def _m1():
    p = TARGETS['routes']
    d = json.loads(rd(p))
    d.pop('_gates', None)
    wr_raw(p, json.dumps(d, indent=2, ensure_ascii=False).replace('\n', '\r\n'))


@mut(u'M2 `to_when_set` 改指 man（走回第183轮的死路）', ['A3', 'B6', 'B10', 'D2'])
def _m2():
    patch('routes', u'"to_when_set": "ch2.cyber_city.dw_city_moss"',
          u'"to_when_set": "ch2.cyber_city.dw_city_man"')


@mut(u'M3 记账点改成出发房（去了 traffic_3 就记账）', ['A4', 'B9'])
def _m3():
    patch('routes', u'"set_mark_when_arrive": "ch2.cyber_city.dw_city_dog_traffic"',
          u'"set_mark_when_arrive": "ch2.cyber_city.dw_city_traffic_3"')


@mut(u'M4 `mark` 改名（查的账与写的账不是同一笔）',
     ['A3', 'B6', 'B9', 'B10', 'D2'])
def _m4():
    patch('routes', u'"mark": "ch2.city.dog_traffic"',
          u'"mark": "ch2.city.dog_traffic_wrong"')


@mut(u'M5 `_original.cond_set` 抄错一个空格', ['A8'])
def _m5():
    patch('routes', u'&& !(man_room)', u'&&  !(man_room)')


@mut(u'M6 偷偷给一条 route 加门控键（违背"不碰 route 对象"）', ['A7'])
def _m6():
    p = TARGETS['routes']
    d = json.loads(rd(p))
    for r in d['routes']:
        if r.get('priority') == 7121:
            r['when_gate'] = 'ch2.city.dog_traffic'
            break
    wr_raw(p, json.dumps(d, indent=2, ensure_ascii=False).replace('\n', '\r\n'))


@mut(u'M7 门控挂错门字母（W → A）',
     ['A3', 'B2', 'B4', 'B6', 'B7', 'B8', 'B10', 'D2'])
def _m7():
    # ★ 第一版用文本替换，命中的是**第一条 route 的 `when_door`** 而不是 `_gates`
    #   里那条 —— 变异等于没做（实测 0 红）。改成整表改写、只动 `_gates[0]`。
    p = TARGETS['routes']
    d = json.loads(rd(p))
    d['_gates'][0]['when_door'] = 'A'
    wr_raw(p, json.dumps(d, indent=2, ensure_ascii=False).replace('\n', '\r\n'))


# --------------------------------------------------------------- 纯函数侧
@mut(u'M8 `gate_for` 缺门信息也套门控（放行派）', ['B5'])
def _m8():
    # ★ 第一版只把 `continue` 改成 `pass` —— 后面那句"字母不相等就 continue"照样
    #   把它拦下 ⇒ 行为一字未变、0 红。真正让"缺门也套用"的做法是把 door 补成
    #   门控要求的那个字母（模拟"放行派"实现）。
    patch('sr', u'''            if not (isinstance(door, str) and door):
                continue          # \u2605 \u7f3a\u95e8\u4fe1\u606f \u21d2 \u4e0d\u5957\u95e8\u63a7\uff08\u89c1 docstring\uff09''',
          u'''            if not (isinstance(door, str) and door):
                door = want_door''')


@mut(u'M9 `gate_target` 的 fail-open 翻成 fail-closed',
     ['B6', 'B7', 'B8', 'B10', 'D1'])
def _m9():
    patch('sr', u'_GATE_ASSUME_UNSET = False', u'_GATE_ASSUME_UNSET = True')


@mut(u'M16 `gate_marks_on_arrival` 不看目的地（到哪都记账）', ['B9'])
def _m16():
    patch('sr', u'''        if arrive != scene_id:
            continue
        if mark not in out:''', u'''        if mark not in out:''')


# --------------------------------------------------------------- 接线侧
@mut(u'M10 宿主漏传 `door_overrides=` 关键字', ['C4'])
def _m10():
    patch('main', u'                door_overrides=door_overrides,\n', u'')


@mut(u'M11 `build_props` 门分支不再应用覆盖表（结构还在、走不到）', ['D2'])
def _m11():
    patch('ii', u'''                _ov = door_overrides.get(letter)
                if isinstance(_ov, str) and _ov:
                    tgt = _ov''',
          u'''                _ov = door_overrides.get(letter)
                if False and isinstance(_ov, str) and _ov:
                    tgt = _ov''')


@mut(u'M12 记账改看"刚走过哪扇门"而不是当前场景', ['C6'])
def _m12():
    # ★ 第一版替换的是 main.py 里**第一处** `current_scene`（根本不在记账函数里）
    #   ⇒ 0 红。改成带上下面三行当锚，整块唯一。
    patch('main', u'''            sid = self.__dict__.get('current_scene')
            if not sid:
                return 0
            routes = self.__dict__.get('_scene_routes')''',
          u'''            sid = self.__dict__.get('_last_door_scene')
            if not sid:
                return 0
            routes = self.__dict__.get('_scene_routes')''')


@mut(u'M13 记账顺序倒过来（gate 在 hidden 之前）', ['C5'])
def _m13():
    a = u'''        try:
            self._commit_hidden_seen()
        except Exception:
            _log.exception('隐藏房记账入口异常（已忽略）')'''
    b = u'''        try:
            self._commit_gate_marks()
        except Exception:
            _log.exception('门控记账入口异常（已忽略）')'''
    # ★ 两个 try 块中间夹着注释行，不能"拼成一串"去找 ⇒ 分别打占位符再对调。
    src = lf(rd(TARGETS['main']))
    assert a in src and b in src
    src = src.replace(a, '@@HIDDEN@@', 1).replace(b, '@@GATE@@', 1)
    src = src.replace('@@HIDDEN@@', b, 1).replace('@@GATE@@', a, 1)
    wr_raw(TARGETS['main'], src)


@mut(u'M14 不再写账（`mark_plot_done` 调用删掉）', ['C7'])
def _m14():
    patch('main', u"                if self.mark_plot_done(m, note=u'第184轮门控：到过 %s' % sid):",
          u"                if False:")


@mut(u'M15 `item_interact` 破零依赖（import scene_routing）', ['C3'])
def _m15():
    patch('ii', u'import collections\n', u'import collections\nimport scene_routing\n')


def main():
    if '--restore' in sys.argv:
        if os.path.isfile(os.path.join(ORIG, 'routes.bak')):
            for k, p in TARGETS.items():
                shutil.copyfile(os.path.join(ORIG, k + '.bak'), p)
            print(u'[OK] 已按快照还原四个文件')
            return 0
        print(u'[FAIL] 没有快照可还原')
        return 2

    snapshot()
    guard = dict(BASELINE)

    rc, g, r, out = run_check()
    print(u'[基线] rc=%d 绿=%d 红=%d（期望 %d/0）' % (rc, len(g), len(r), TOTAL_CHECKS))
    if len(g) != TOTAL_CHECKS or r:
        print(out[-2500:])
        print(u'[FAIL] 未变异的真文件本身就不绿 ⇒ 后面的变异没有意义')
        restore()
        return 2

    ok = 0
    for i, (name, expect, fn) in enumerate(MUTS, 1):
        rc1 = rc2 = -1
        g1 = r1 = r2 = []
        try:
            restore()
            fn()
            rc1, g1, r1, out1 = run_check()
            restore()
            fn()
            rc2, g2, r2, out2 = run_check()
        except AssertionError as e:
            print(u'[DIFF] M%-2d %s\n        锚点没命中：%s' % (i, name, e))
            continue
        finally:
            restore()

        same = set(r1) == set(r2)
        hit = set(r1)
        good = (hit == expect) and same and 0 < len(hit) < TOTAL_CHECKS
        if good:
            ok += 1
        print(u'[%s] M%-2d %s' % (u'OK  ' if good else u'DIFF', i, name))
        print(u'        rc=%d/%d  红=%d 绿=%d  期望红=%r'
              % (rc1, rc2, len(r1), len(g1), sorted(expect)))
        print(u'        实际红=%r  双跑一致=%s' % (sorted(hit), same))
        if hit != expect:
            print(u'        差集：多 %r / 少 %r'
                  % (sorted(hit - expect), sorted(expect - hit)))

    restore()
    after = {k: sha(p) for k, p in TARGETS.items()}
    clean = after == guard
    print(u'\n四个文件已还原 == 开工前 = %s' % clean)
    if not clean:
        for k in TARGETS:
            if after[k] != guard[k]:
                print(u'  [FAIL] %s 与快照不同' % k)

    print(u'\n' + '=' * 70)
    print(u'变异 %d/%d 符合预期%s' % (ok, len(MUTS), u'' if clean else u'（但文件未还原！）'))
    print('=' * 70)
    return 0 if (ok == len(MUTS) and clean) else 1


if __name__ == '__main__':
    sys.exit(main())
