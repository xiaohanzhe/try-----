# -*- coding: utf-8 -*-
u"""第172轮 · `check172` 的变异测试：每条变异都必须被**指定判据**抓到。

规矩（前三轮踩出来的）：
  ① **临时区只在 D 盘**（`D:\_tmp\mut172\`），**绝不**把 `ralsei_pet` 整包拷进临时区
     —— 第171轮那么干被清理守卫拦下（1,714 个文件 rmtree > 50 阈值）；
     本轮只拷**一个** `_routes.json`（2.3 MB）。
  ② 判据不改一行：靠 `CQ_ROUTES172` 环境变量把 `check172` 指向变异副本。
  ③ 每条变异都记「期望哪几条判据红」；**实际红的不是它也不算通过**，
     要么改夹具、要么改期望值并写明为什么。
  ④ 先跑一次「零变异」对照（必须 33/0），否则红是环境问题不是变异。
  ⑤ `no-op` 也要显式过：有一条变异是"改了但语义不变"，它必须**保持全绿**
     —— 否则说明判据是靠"文件变了"报红，不是靠语义。

用法: python mutate172.py
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
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
CHECK = os.path.join(HERE, 'check172.py')
TMP = os.environ.get('CQ_MUT172_DIR') or os.path.join('D:' + os.sep, '_tmp', 'mut172')


def load(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def dump(obj, p):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2).replace(u'\n', u'\r\n'))


def _mine(R):
    return [r for r in R['routes'] if (r.get('_original') or {}).get('batch') == 172]


# ---------------------------------------------------------------- 变异体
def m1_del_edge(R):
    u"""删掉本轮第一条边（模拟"少落一条"）。"""
    R['routes'].remove(_mine(R)[0])


def m2_shift_x(R):
    u"""把一条的门 `door_x` 挪 1px（坐标与原作实例对不上）。"""
    _mine(R)[0]['_original']['door_x'] += 1


def m3_drop_axis(R):
    u"""抹掉一条 `axis: "y"`（同房同 x 的两扇就只能按 x 分，必然挑不中）。"""
    for r in _mine(R):
        if (r.get('_original') or {}).get('axis') == 'y':
            r['_original'].pop('axis')
            return
    raise AssertionError(u'没有 axis=y 的规则，夹具失效')


def m4_fake_to(R):
    u"""把一条的目标改成另一个**已登记**场景（造一条假边，且证据对不上）。"""
    r = _mine(R)[0]
    r['to'] = u'ch2.cyber_city.dw_city_mansion_front' \
        if r['to'] != u'ch2.cyber_city.dw_city_mansion_front' else u'ch2.hometown.town_school'


def m5_fake_precreate(R):
    u"""把一条的实例创建代码名改成别的房（`PreCreate` 里嵌的房名与源房对不上）。"""
    r = _mine(R)[0]
    o = r['_original']
    o['precreate'] = u'gml_RoomCC_room_not_this_room_9_PreCreate'


def m6_prio_collide(R):
    u"""把一条的 priority 改成 7299（越出本轮段 + 与历史段相邻）。"""
    _mine(R)[0]['priority'] = 7299


def m7_dup_pair(R):
    u"""落一条与既有 `(场景, 目标)` **真的**完全重复的边（弄脏重复组）。

    ★ 第一版是"把 `to` 随手改成一个固定场景"，可那个 `(场景, 目标)` 组合本来就
      不存在 ⇒ 造出来的是**假边**不是**重复边**，A5 的重复组数根本不涨
      （夹具不保真＝测了个假问题）。现在改成：从同一场景里另找一条**目标不同**的
      规则，把它的 `to` 抄过来 ⇒ 必然形成重复组。
    """
    by = {}
    for r in R['routes']:
        by.setdefault(r.get('when_scene'), []).append(r)
    for r in _mine(R):
        same = [q for q in by.get(r.get('when_scene'), [])
                if q is not r and q.get('to') != r.get('to')]
        if same:
            r['to'] = same[0]['to']
            return
    raise AssertionError(u'同场景里找不到目标不同的第二条规则，夹具失效')


def m8_del_loop(R):
    u"""删掉那条自环边（原作真实的"回自身"）。"""
    for r in _mine(R):
        if r.get('when_scene') == r.get('to'):
            R['routes'].remove(r)
            return
    raise AssertionError(u'没有自环边，夹具失效')


def m9_fake_src(R):
    u"""把一条的 `when_src` 改成别的门对象名（产品查不到它 ⇒ 落错房间）。"""
    _mine(R)[0]['when_src'] = u'obj_doorW'


def m10_drop_y(R):
    u"""抹掉一条的 `door_y`（双坐标消歧与轴判定都失去依据）。"""
    _mine(R)[0]['_original']['door_y'] = None


def m11_noop(R):
    u"""**无害变异**：把 reason 文案改一个字（语义不变，必须保持全绿）。"""
    _mine(R)[0]['reason'] = _mine(R)[0]['reason'] + u'（文案微调）'


#: (编号, 说明, 变异函数, 期望报红的判据前缀)
#: ★ 期望值是**照着实测改的**，不是照着我"以为"写的（第170轮教训：
#:   判据抓到 ≠ 我猜对是哪条）。每条后面的注写清"为什么是它"。
MUTS = [
    # 少一条边 ⇒ 分母/段位/集合/反回滚四道同时缩水。★ C1 抓不到：它只扫"表里还有的边"，
    #   边被删了就扫不到 ⇒ 删边归 B1/D2 管，分工不许混。
    ('M1', u'删掉一条本轮边', m1_del_edge, ['A0', 'A1', 'B1', 'D2']),
    # 坐标造假 ⇒ 与证据对不上。★ C1 抓不到（它拿规则自己的坐标去查，自洽）。
    ('M2', u'门坐标 +1px', m2_shift_x, ['B2']),
    # 抹掉 axis=y ⇒ 单轴退化。★ C1 恰好没红：那条规则的 priority 本来就是该房最小，
    #   退化成 priority 最小以后答案**没变** ⇒ 只有 B4 能看出"口径字段丢了"。
    ('M3', u'抹掉 axis=y', m3_drop_axis, ['B4']),
    # 目标造假 ⇒ 集合对不上 + 逐条对账对不上。
    ('M4', u'目标改成别的场景', m4_fake_to, ['B1', 'B2']),
    ('M5', u'实例创建代码名造假', m5_fake_precreate, ['B2']),
    # priority 挪出本轮段 ⇒ 连续性断。★ A2 不红是**对的**：7299 没有撞上任何人。
    ('M6', u'priority 越界撞号', m6_prio_collide, ['A1']),
    # 真造一条重复边 ⇒ 重复组数 5→6（A5）+ 集合多一条（B1）。
    # ★ D1 不红是对的：它守的是"**同门**重复"，而这条是**不同门同目标**（合法形态）。
    ('M7', u'落一条重复边', m7_dup_pair, ['A5', 'B1']),
    ('M8', u'删掉自环边', m8_del_loop, ['A0', 'B6', 'D2']),
    # 对象级定位丢了 ⇒ 这扇门查不到对象级规则。
    ('M9', u'when_src 改成别的门', m9_fake_src, ['C1']),
    # 缺 door_y ⇒ 逐条对账 + 必备字段亮红。★ B4 不红是对的：轴判定只看 door_x。
    ('M10', u'抹掉 door_y', m10_drop_y, ['B2', 'D5']),
    ('M11', u'（无害）只改 reason 文案', m11_noop, []),
]


def run_check(path):
    env = dict(os.environ)
    env['CQ_ROUTES172'] = path
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    pr = subprocess.run([sys.executable, CHECK], cwd=HERE, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    fails = [l[7:].strip() for l in out.split(u'\n') if l.startswith('[FAIL] ')]
    return pr.returncode, fails, out


def main():
    if not os.path.isdir(TMP):
        os.makedirs(TMP)
    base = os.path.join(TMP, '_routes.json')
    shutil.copyfile(ROUTES, base)

    # ---- 对照：零变异必须 33/0 ----
    rc, fails, _ = run_check(base)
    print(u'[对照] 零变异 exit=%d FAIL=%d' % (rc, len(fails)))
    if rc != 0 or fails:
        print(u'!! 对照就没过，后面所有结论都不可信：%r' % (fails[:5],))
        return 2

    ok_n = bad_n = 0
    for mid, desc, fn, want in MUTS:
        R = load(ROUTES)
        try:
            fn(R)
        except AssertionError as exc:
            print(u'%s %s —— 夹具失效：%s' % (mid, desc, exc))
            bad_n += 1
            continue
        dump(R, base)
        rc, fails, out = run_check(base)
        got = set()
        for f in fails:
            for w in want:
                if f.startswith(w):
                    got.add(w)
        if not want:
            # 无害变异：必须全绿
            ok = (rc == 0 and not fails)
            print(u'%s %s —— %s（FAIL=%d）' % (mid, desc,
                                              u'OK 保持全绿' if ok else u'!! 竟然红了',
                                              len(fails)))
            if ok:
                ok_n += 1
            else:
                bad_n += 1
                for f in fails[:4]:
                    print(u'     红：%s' % f)
        else:
            miss = [w for w in want if w not in got]
            ok = (rc != 0 and not miss)
            print(u'%s %s —— %s（红的判据 %d 条；期望 %r 缺 %r）'
                  % (mid, desc, u'OK 被抓到' if ok else u'!! 没按预期报红',
                     len(fails), want, miss))
            if ok:
                ok_n += 1
            else:
                bad_n += 1
                for f in fails[:4]:
                    print(u'     实红：%s' % f)
        # 每条都用**原表**重建，避免变异叠加
        shutil.copyfile(ROUTES, base)

    print(u'')
    print(u'合计：变异 %d 条 —— 符合预期 %d / 不符合 %d' % (len(MUTS), ok_n, bad_n))
    # 清理（只删自己建的临时目录）
    try:
        shutil.rmtree(TMP)
    except OSError:
        pass
    return 0 if bad_n == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
