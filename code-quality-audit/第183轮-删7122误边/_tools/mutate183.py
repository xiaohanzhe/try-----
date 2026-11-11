# -*- coding: utf-8 -*-
u"""第183轮 · 变异测试：证明 `check183` 的每一条**真的能红**。

## 为什么需要它

`check183` 里最危险的两条是 B3 和 B4：
  · B3 说"把留档加回去再 match，结果不变" —— 如果留档那条本来就是个死条目，
    这条断言**永远为真**，等于什么都没证明；
  · B4 就是为了堵这个洞：抠掉 7121 后 7122 必须上位。
两者成对才构成"7122 被遮住、而非垃圾"的证明。M13 / M14 专门打这两条。

## 施工纪律（沿用第178/180/182轮的教训）

1. 每条变异都**从源文件重建**一份副本到临时区，不在原件上改；
2. 锚点按 **LF 归一** 后再匹配（源文件是 CRLF，按 `\\n` 写锚点会一条都命中不了）；
3. 三重断言：**期望的那几条必须红** + **红的条数 > 0** + **红的条数 < 总数**
   （防"整段崩掉、一条 `[FAIL]` 都不打"——第178轮 M3 / 第182轮 `once` 那次）；
4. 每条**连跑两遍**，红项集合必须相同（幂等，防"跑一次就坏掉"）。

## 跑法

    C:/Python311/python.exe code-quality-audit/第183轮-删7122误边/_tools/mutate183.py
"""
import io
import json
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
CHECK183 = os.path.join(HERE, 'check183.py')
ROUTES = os.path.join(PET, 'assets', 'scenes', '_routes.json')
EVID = os.path.join(ROUND, '_evidence', 'removed183.json')
CHECK181 = os.path.join(REPO, 'code-quality-audit', u'第181轮-补门型', '_tools', 'check181.py')
APPLY183 = os.path.join(HERE, 'apply183.py')

WORK = os.path.join('D:\\', '_tmp183', 'mut')
TOTAL_CHECKS = 26


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def rd_py(p):
    u"""读源码并把 EOL 归一成 LF（**只用于匹配锚点**，写回时再换回原 EOL）。"""
    s = rd(p)
    return s.replace('\r\n', '\n')


def wr_py(p, s, eol):
    wr(p, s.replace('\n', eol))


def dump_routes(d):
    return json.dumps(d, indent=2, ensure_ascii=False).replace('\n', '\r\n')


def run_check(mdir):
    env = dict(os.environ)
    env['CQ_ROUTES_183'] = os.path.join(mdir, '_routes.json')
    env['CQ_EVID_183'] = os.path.join(mdir, 'removed183.json')
    env['CQ_CHECK181_183'] = os.path.join(mdir, 'check181.py')
    env['CQ_APPLY183_183'] = os.path.join(mdir, 'apply183.py')
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, CHECK183], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.decode('utf-8', 'replace')
    red, npass = [], 0
    for ln in txt.split('\n'):
        if ln.startswith('[FAIL] '):
            red.append(ln[7:].split(' ', 1)[0])
        elif ln.startswith('[PASS] '):
            npass += 1
    return p.returncode, red, npass, txt


# ---------------------------------------------------------------------------
#  变异定义：每条 = (id, 说明, 目标文件, 施加函数, 期望红项集合)
# ---------------------------------------------------------------------------
def _m_routes_add_back(d):
    u"""把留档那条原样加回表里（模拟"没删過"）。"""
    ev = json.loads(rd(os.path.join(WORK, '_base_removed183.json')))
    d['routes'].append(ev['routes'][0])


def _m_routes_kill_7121_to_man(d):
    for r in d['routes']:
        if r.get('priority') == 7121:
            r['to'] = 'ch2.cyber_city.dw_city_man'


def _m_routes_prio_7121_high(d):
    for r in d['routes']:
        if r.get('priority') == 7121:
            r['priority'] = 9000


def _m_routes_7123_to_man(d):
    for r in d['routes']:
        if r.get('priority') == 7123:
            r['to'] = 'ch2.cyber_city.dw_city_man'


def _m_evid_drop_original(e):
    e['routes'][0].pop('_original', None)


def _m_evid_prio_as_7121(e):
    e['routes'][0]['priority'] = 7121


def _m_evid_prio_as_1000(e):
    e['routes'][0]['priority'] = 1000


def _m_evid_total_after(e):
    e['meta']['total_after'] = 2831


def _m_evid_dup(e):
    e['routes'].append(dict(e['routes'][0]))


def _m_evid_other_scene(e):
    e['routes'][0]['when_scene'] = 'ch1.hometown.schooldoor'


def _m_routes_note_back(d):
    u"""把说明改回"尚未删除"，但**保留** 1/50 表达式与锁文件名 —— 只隔离 C2，
    不让 C3 陪着红（夹具要打到那一条，不要顺手打到旁边那条）。"""
    for h in (d.get('_hidden_rooms') or []):
        if h.get('from_scene') == 'ch2.cyber_city.dw_city_traffic_3':
            h['note'] = (u'第182轮已启用：掷 `ceil(random(50)) == 50`，'
                         u'真站进去才写 `hidden_rooms_seen.json`。'
                         u'⚠️ 既有确定性边（priority 7122）**尚未删除**。')


def _m_routes_note_no_expr(d):
    for h in (d.get('_hidden_rooms') or []):
        if h.get('from_scene') == 'ch2.cyber_city.dw_city_traffic_3':
            h['note'] = (u'第183轮已删除那条确定性边，见 hidden_rooms_seen.json；'
                         u'概率另议。')


def _m_routes_disable_ch2(d):
    for h in (d.get('_hidden_rooms') or []):
        if h.get('from_scene') == 'ch2.cyber_city.dw_city_traffic_3':
            h['enabled'] = False


MUTS = [
    ('M1', u'把留档那条加回表里（模拟"没删过"）', 'routes', _m_routes_add_back,
     {'A1', 'A2', 'A7'}),
    ('M2', u'留档丢掉 `_original`（还原信息不全）', 'evid', _m_evid_drop_original,
     {'A4', 'A5'}),
    ('M3', u'留档 priority 改成 7121（留档的不是那条）', 'evid', _m_evid_prio_as_7121,
     {'A3', 'D1'}),
    ('M4', u'登记说明改回"尚未删除"', 'routes', _m_routes_note_back,
     {'C2'}),
    ('M5', u'登记说明删掉 1/50 表达式', 'routes', _m_routes_note_no_expr,
     {'C3'}),
    ('M6', u'ch2 隐藏房改成 `enabled: false`', 'routes', _m_routes_disable_ch2,
     {'C1', 'B6'}),
    ('M7', u'7121 也指向 man（同门两条去同一间）', 'routes', _m_routes_kill_7121_to_man,
     {'A6', 'B5'}),
    ('M8', u'7123 改指 man（moss 被顶掉）', 'routes', _m_routes_7123_to_man,
     {'A6'}),
    ('M9', u'7121 的 priority 抬到 9000（顺序变了）', 'routes', _m_routes_prio_7121_high,
     {'A6', 'B2'}),
    ('M10', u'留档的 `meta.total_after` 写错成 2831', 'evid', _m_evid_total_after,
     {'A2'}),
    ('M11', u'留档复制成两条（还原会造重复）', 'evid', _m_evid_dup,
     {'A3', 'D3'}),
    ('M12', u'留档 `when_scene` 改成别的场景', 'evid', _m_evid_other_scene,
     {'A5', 'B4'}),
    ('M13', u'留档 priority 改成 1000（加回去就抢赢 ⇒ B3 必须红）', 'evid',
     _m_evid_prio_as_1000, {'A3', 'B3', 'D1'}),
    ('M14', u'第181轮账本里把 7122 改成 7100', 'check181', 'LEDGER',
     {'D1'}),
    ('M15', u'第181轮 A1 改回裸数字（不再引账）', 'check181', 'A1_LITERAL',
     {'D2'}),
    ('M16', u'施工脚本里插一句 `assert False`（破坏幂等）', 'apply183', 'ASSERT',
     {'D4'}),
]


def apply_text(kind, src):
    u"""源码类变异的三种写法。返回改后的文本（LF 归一）。"""
    if kind == 'LEDGER':
        old = u'    183: ([7122], u'
        new = u'    183: ([7100], u'
    elif kind == 'A1_LITERAL':
        old = (u'      len(ROUTES) >= _BASE_TOTAL - _N_REMOVED, '
               u'u\'实测 %d\' % len(ROUTES))')
        new = u'      len(ROUTES) >= 2830, u\'实测 %d\' % len(ROUTES))'
    elif kind == 'ASSERT':
        old = u'PRIORITY = 7122'
        new = u'PRIORITY = 7122\nassert False, u\'mutated\''
    else:
        raise AssertionError(kind)
    if old not in src:
        raise AssertionError(u'锚点没命中：%s / %r' % (kind, old[:60]))
    return src.replace(old, new, 1)


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    base_routes = rd(ROUTES)
    base_evid = rd(EVID)
    base_181 = rd(CHECK181)
    base_apply = rd(APPLY183)
    wr(os.path.join(WORK, '_base_removed183.json'), base_evid)

    eol181 = u'\r\n' if u'\r\n' in base_181 else u'\n'
    eol_apply = u'\r\n' if u'\r\n' in base_apply else u'\n'

    ok_n = 0
    bad = []
    for mid, what, target, fn, expect in MUTS:
        mdir = os.path.join(WORK, mid)
        if os.path.isdir(mdir):
            shutil.rmtree(mdir, ignore_errors=True)
        os.makedirs(mdir, exist_ok=True)

        # ---- 重建四份副本 ----
        routes_s, evid_s = base_routes, base_evid
        c181_s, apply_s = base_181, base_apply

        if target == 'routes':
            d = json.loads(base_routes)
            fn(d)
            routes_s = dump_routes(d)
        elif target == 'evid':
            e = json.loads(base_evid)
            fn(e)
            evid_s = json.dumps(e, indent=2, ensure_ascii=False)
        elif target == 'check181':
            c181_s = apply_text(fn, rd_py(CHECK181)).replace('\n', eol181)
        elif target == 'apply183':
            apply_s = apply_text(fn, rd_py(APPLY183)).replace('\n', eol_apply)
        else:
            raise AssertionError(target)

        wr(os.path.join(mdir, '_routes.json'), routes_s)
        wr(os.path.join(mdir, 'removed183.json'), evid_s)
        wr(os.path.join(mdir, 'check181.py'), c181_s)
        wr(os.path.join(mdir, 'apply183.py'), apply_s)

        # ---- 跑两遍 ----
        rc1, red1, np1, txt1 = run_check(mdir)
        rc2, red2, np2, txt2 = run_check(mdir)

        s1, s2 = set(red1), set(red2)
        miss = sorted(expect - s1)
        extra_ok = (0 < len(s1) < TOTAL_CHECKS)
        idem = (s1 == s2)
        good = (not miss) and extra_ok and idem

        print('%s %s' % ('[OK  ]' if good else '[BAD ]', mid) + u'  ' + what)
        print(u'        rc=%d/%d  红=%d 绿=%d  期望红=%r  实际红=%r'
              % (rc1, rc2, len(s1), np1, sorted(expect), sorted(s1)))
        if miss:
            print(u'       ✗ 期望红但没红：%r' % (miss,))
        if not extra_ok:
            print(u'       ✗ 红项条数异常（%d/%d）—— 可能整段崩掉、一条 FAIL 都没打'
                  % (len(s1), TOTAL_CHECKS))
        if not idem:
            print(u'       ✗ 双跑不一致：%r vs %r' % (sorted(s1), sorted(s2)))
        if not good:
            # 崩掉时把尾部贴出来，否则只看到"红 0 条"没法定位
            tail = [l for l in txt1.strip().split('\n')][-6:]
            print(u'       --- 尾部 ---')
            for l in tail:
                print(u'       ' + l[:160])
            bad.append(mid)
        else:
            ok_n += 1

    print('')
    print('=' * 70)
    print(u'变异 %d/%d 符合预期' % (ok_n, len(MUTS)))
    if bad:
        print(u'不符合：%r' % (bad,))
    print('=' * 70)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
