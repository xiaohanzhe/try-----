# -*- coding: utf-8 -*-
u"""第174轮 · `check174.py` 的变异测试（证明每条判据**有鉴别力**，不是恒真）。

做法与第173轮 `mutate173.py` 完全一致：
一次只改**一处**数据 → 跑一遍 `check174.py` → 看**指定的那条判据是否报红**
→ `finally` 里从备份原样拷回 → 用 sha1 核对"真的恢复了"。

★ 备份落在 `D:\\_tmp\\mut174\\`，**不进工作区**（工作区里出现临时件会被
  `git add -A` 记成删除/新增，第75轮踩过）。
★ 先 `backup()` 再改 —— 顺序反了就是假安全（第173轮 M5/M6 栽过）。

用法
----
    python mutate174.py            # 全跑
    python mutate174.py M3         # 只跑一个（调试用）
"""
import hashlib
import io
import importlib.util
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
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
CHECK = os.path.join(HERE, 'check174.py')
BAK = os.path.join('D:' + os.sep, '_tmp', 'mut174')
PY = sys.executable
HORZ = 'obj_doorAnyHorz'
VERT = 'obj_doorAnyVert'
WANT = (HORZ, VERT)

RE_RED = re.compile(r'^  - ([A-E]\d+[-\w]*)', re.M)


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace',
                              newline='').read())


def dump_scene(p, data):
    """★ 用生成器同一套 `dump()`，保住 indent / EOL / `pos` 塌缩格式。"""
    spec = importlib.util.spec_from_file_location(
        'gen44_for_mut174', os.path.join(REPO, 'code-quality-audit',
                                         u'第44轮-原作对话框复刻', '_tools',
                                         'gen_objects44.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DRY_RUN = False
    mod.dump(p, data)


def dump_routes(p, data):
    """路由表用 `indent=2` + CRLF（与 `apply174.py` 的落盘口径一致）。"""
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n'))


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(65536), b''):
            h.update(b)
    return h.hexdigest()


def backup(paths):
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    rec = {}
    for i, p in enumerate(paths):
        dst = os.path.join(BAK, '%d_%s' % (i, os.path.basename(p)))
        shutil.copy2(p, dst)
        rec[p] = (dst, sha1(p))
    return rec


def restore(rec):
    bad = []
    for p, (dst, want) in rec.items():
        shutil.copy2(dst, p)
        if sha1(p) != want:
            bad.append(p)
    return bad


def run_check():
    r = subprocess.run([PY, CHECK], cwd=REPO, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    txt = r.stdout.decode('utf-8', 'replace')
    return r.returncode, txt, RE_RED.findall(txt)


def first_scene_with_var():
    """找一个**含变体物件**的载体，返回 (文件路径, 场景键或 None)。"""
    for name in sorted(os.listdir(SCENES)):
        if not name.endswith('.json'):
            continue
        if name.startswith('_') and not name.startswith('_zone.'):
            continue
        p = os.path.join(SCENES, name)
        d = jl(p)
        if not isinstance(d, dict):
            continue
        inner = d.get('scenes')
        if isinstance(inner, dict):
            for sid, sc in inner.items():
                if not isinstance(sc, dict):
                    continue
                for o in (sc.get('objects') or []):
                    if isinstance(o, dict) and o.get('src') in WANT:
                        return p, sid
        elif 'objects' in d or 'scene_id' in d:
            for o in (d.get('objects') or []):
                if isinstance(o, dict) and o.get('src') in WANT:
                    return p, None
    raise SystemExit(u'找不到含变体物件的场景')


def _scene_of(d, sid):
    """`(场景dict)` —— ★ 收**已解析的 dict**，不许在这里再读一次盘。

    第173轮在同一个地方栽过：函数内部又 `jl(p)` 读一遍 ⇒ 改的是**另一份**对象
    ⇒ 落盘内容没变 ⇒ 变异体全部漏抓（"两处各自读盘"的老坑）。
    """
    inner = d.get('scenes')
    if isinstance(inner, dict):
        sc = inner.get(sid)
        if isinstance(sc, dict):
            return sc
        raise SystemExit(u'场景键 %r 不存在' % (sid,))
    return d


def first_var_edge():
    """`_routes.json` 里第一条变体边的下标。"""
    d = jl(ROUTES)
    rs = d.get('routes') if isinstance(d, dict) else d
    for i, q in enumerate(rs):
        if isinstance(q, dict) and q.get('when_src') in WANT:
            return i
    raise SystemExit(u'路由表里没有变体边')


# ===========================================================================
# 变异体
# ===========================================================================
def mut_del_edge(p):
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    del rs[first_var_edge()]
    dump_routes(p, d)


def mut_edit_door_x(p):
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    q = rs[first_var_edge()]
    o = q['_original']
    o['door_x'] = o['door_x'] + 1 if isinstance(o.get('door_x'), int) else 12345
    dump_routes(p, d)


def mut_relabel_src(p):
    """把一条变体边的 `when_src` 改成 `obj_doorAny`（模拟"标签说假话"）。"""
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    q = rs[first_var_edge()]
    q['when_src'] = 'obj_doorAny'
    q['_original']['via'] = 'obj_doorAny'
    dump_routes(p, d)


def mut_bad_priority(p):
    """把一条边的 priority 挪到段外 ⇒ 段里出现空洞。"""
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    rs[first_var_edge()]['priority'] = 999999
    dump_routes(p, d)


def mut_break_via(p):
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    rs[first_var_edge()]['_original']['via'] = 'obj_doorAnyFAKE'
    dump_routes(p, d)


def mut_del_obj(p, sid):
    d = jl(p)
    sc = _scene_of(d, sid)
    for i, o in enumerate(sc.get('objects') or []):
        if isinstance(o, dict) and o.get('src') in WANT:
            del sc['objects'][i]
            break
    dump_scene(p, d)


def mut_add_sprite(p, sid):
    d = jl(p)
    sc = _scene_of(d, sid)
    for o in (sc.get('objects') or []):
        if isinstance(o, dict) and o.get('src') in WANT:
            o['sprite'] = 'spr_doorA_0.png'
            break
    dump_scene(p, d)


def mut_noroom(p, sid):
    """往 `desktop.json` 塞一个变体物件（它没有 room/chapter ⇒ 键不在登记集里）。"""
    d = jl(p)
    d.setdefault('objects', []).append({'pos': [7, 7], 'src': HORZ})
    dump_scene(p, d)


MUTS = [
    ('M1', u'删掉一条变体边', 'B0', 'routes'),
    ('M2', u'把一条边的 `door_x` 挪 1px', 'B1', 'routes'),
    ('M3', u'把一条变体边改标成 `obj_doorAny`', 'B6', 'routes'),
    ('M4', u'把一条边的 priority 挪到段外', 'B3', 'routes'),
    ('M5', u'把一条边的 `_original.via` 改成假名', 'B4', 'routes'),
    ('M6', u'删掉某场景的一个变体物件', 'C1', 'scene'),
    ('M7', u'给一个变体物件硬加 sprite', 'D2', 'scene'),
    ('M8', u'把变体物件硬塞进 `desktop.json`', 'D4', 'desktop'),
]


def locate(kind):
    if kind == 'routes':
        return ROUTES, None
    if kind == 'desktop':
        return os.path.join(SCENES, 'desktop.json'), None
    return first_scene_with_var()


def apply_mut(kind, p, sid):
    if kind == 'routes':
        fn = {'M1': mut_del_edge, 'M2': mut_edit_door_x, 'M3': mut_relabel_src,
              'M4': mut_bad_priority, 'M5': mut_break_via}[_CUR]
        fn(p)
    elif kind == 'desktop':
        mut_noroom(p, sid)
    else:
        {'M6': mut_del_obj, 'M7': mut_add_sprite}[_CUR](p, sid)


_CUR = ''


def main():
    global _CUR
    only = [a for a in sys.argv[1:] if a.startswith('M')]
    print('=' * 70)
    print(u'check174 变异测试：%d 个变异体' % len(MUTS))
    print('=' * 70)

    print('')
    print(u'[基线] 不改任何数据，先确认全部绿')
    rc, txt, reds = run_check()
    base_ok = (rc == 0 and not reds)
    print(u'   exit=%d 红项=%r  ⇒ %s' % (rc, reds, u'OK' if base_ok else u'不绿！'))
    if not base_ok:
        print(u'基线就不绿，变异测试无意义 ⇒ 先修 check174')
        return 1

    caught = total = 0
    for mid, desc, want, kind in MUTS:
        if only and mid not in only:
            continue
        total += 1
        _CUR = mid
        print('')
        print(u'[%s] %s（期望报红：%s）' % (mid, desc, want))
        rec = None
        try:
            p, sid = locate(kind)
            rec = backup([p])
            apply_mut(kind, p, sid)
            rc, txt, reds = run_check()
            hit = want in reds
            if hit:
                caught += 1
            print(u'   exit=%d 红项=%r' % (rc, reds))
            print(u'   ⇒ %s' % (u'抓到了' if hit else u'★没抓到（判据有洞）'))
            if rc and not reds:
                print(u'   ★ 没解析出红项但退出码非 0 ⇒ 检查是否崩了，末 15 行：')
                for _ln in txt.strip().splitlines()[-15:]:
                    print(u'      | ' + _ln)
        finally:
            if rec:
                bad = restore(rec)
                print(u'   已恢复 %d 个文件%s'
                      % (len(rec), u'' if not bad else u'；★恢复失败 %r' % (bad,)))
                if bad:
                    return 2

    print('')
    print('=' * 70)
    print(u'变异测试：%d/%d 被抓到' % (caught, total))
    print('=' * 70)
    return 0 if caught == total else 1


if __name__ == '__main__':
    sys.exit(main())
