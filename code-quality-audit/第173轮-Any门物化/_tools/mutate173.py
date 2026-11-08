# -*- coding: utf-8 -*-
u"""第173轮 · `check173.py` 的变异测试（证明每条判据**有鉴别力**，不是恒真）。

做法
----
一次只改**一处**数据 → 跑一遍 `check173.py` → 看**指定的那条判据是否报红**
→ `finally` 里从备份原样拷回 → 用 sha1 核对"真的恢复了"。

★ 备份落在 `D:\\_tmp\\mut173\\`，**不进工作区**：工作区里出现临时件会被
  `git add -A` 记成"删除/新增"，第75轮踩过（见记忆「临时/备份禁放工作区」）。
★ 一次只动 1 个文件（`shutil.copy2` 级），不碰 `ralsei_pet` 整树 ——
  第172轮实测整树拷贝会被清理守卫拦下（>50 文件 rmtree）。
★ 恢复靠 `try/finally` ＋ sha1 双保险：变异脚本崩了也不留脏数据。

用法
----
    python mutate173.py            # 全跑
    python mutate173.py M3         # 只跑一个（调试用）
"""
import hashlib
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
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
CHECK = os.path.join(HERE, 'check173.py')
BAK = os.path.join('D:' + os.sep, '_tmp', 'mut173')
PY = sys.executable
WANT = 'obj_doorAny'

RE_RED = re.compile(r'^  - ([A-E]\d+[-\w]*)', re.M)


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace',
                              newline='').read())


def dump(p, data):
    """★ 用生成器同一套 `dump()`，保住 indent / EOL / `pos` 塌缩格式。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'gen44_for_mut', os.path.join(REPO, 'code-quality-audit',
                                      u'第44轮-原作对话框复刻', '_tools',
                                      'gen_objects44.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DRY_RUN = False
    mod.dump(p, data)


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


def first_scene_with_any():
    """找一个**含 Any 的分片场景**，返回 (文件路径, 场景键)。"""
    for name in sorted(os.listdir(SCENES)):
        if not (name.startswith('_zone.') and name.endswith('.json')):
            continue
        p = os.path.join(SCENES, name)
        d = jl(p)
        for sid, sc in (d.get('scenes') or {}).items():
            if not isinstance(sc, dict):
                continue
            for o in (sc.get('objects') or []):
                if isinstance(o, dict) and o.get('src') == WANT:
                    return p, sid
    raise SystemExit('找不到含 Any 的分片场景')


def first_noroom_xy():
    """从普查里找一个**未登记房间**的 Any 坐标（用于 M3 硬塞）。"""
    sys.path.insert(0, PKG)
    idx = jl(os.path.join(SCENES, '_index.json'))
    reg = set()
    for ch, blk in ((idx.get('chapters')) or {}).items():
        for _a, ablk in ((blk.get('areas')) or {}).items():
            for _s, e in ((ablk.get('scenes')) or {}).items():
                if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
                    reg.add((ch, e['original_room_id']))
    e42 = os.path.join(REPO, 'code-quality-audit', u'第42轮-原作拓扑取证', '_evidence')
    files = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json',
             'ch3': 'ch3_inst42.json', 'ch4': 'ch4_inst42.json',
             'ch5': 'ch5_inst42.json'}
    for ch, fn in files.items():
        p = os.path.join(e42, fn)
        if not os.path.isfile(p):
            continue
        for rec in ((jl(p).get('rooms')) or []):
            rid = rec.get('index')
            if not isinstance(rid, int) or (ch, rid) in reg:
                continue
            for it in (rec.get('insts') or []):
                if it.get('obj') == WANT and isinstance(it.get('x'), int):
                    return it['x'], it['y']
    raise SystemExit('找不到未登记房间的 Any 坐标')


# ===========================================================================
# 变异体：`(编号, 说明, 期望报红的判据前缀, 施加函数)`
# ★ 施加函数**收路径参数**：必须先 `backup()` 再改，否则备份下来的是改后的文件
#   （第一版就是"先改再备份"，恢复等于没恢复，且 sha1 校验会绿 —— 假安全）。
# ===========================================================================
def _scene_of(d):
    """`(场景键, 场景dict)` —— 第一个含 Any 的场景。

    ★ 参数是**已解析的 dict**，不是路径。第一版传路径、函数内部又读了一次，
      于是返回的 `sc` 属于**另一份**新读出来的 dict ⇒ 改它等于改了个寂寞
      （实测"变更? False"，5 个变异体全部漏抓）。这是"两处各自读盘 ⇒ 改的不是同一个对象"
      的老坑（第130轮同款）。
    """
    for sid, sc in (d.get('scenes') or {}).items():
        if not isinstance(sc, dict):
            continue
        for o in (sc.get('objects') or []):
            if isinstance(o, dict) and o.get('src') == WANT:
                return sid, sc
    raise SystemExit('目标文件里没有 Any')


def mut_delete_one(p):
    d = jl(p)
    _sid, sc = _scene_of(d)
    for i, o in enumerate(sc['objects']):
        if isinstance(o, dict) and o.get('src') == WANT:
            del sc['objects'][i]
            break
    dump(p, d)


def mut_add_sprite(p):
    d = jl(p)
    _sid, sc = _scene_of(d)
    for o in sc['objects']:
        if isinstance(o, dict) and o.get('src') == WANT:
            o['sprite'] = 'spr_doorA_0.png'
            break
    dump(p, d)


def mut_noroom(p):
    """把**未登记房间**的一条 Any 硬塞进 `desktop.json`（桌面不在房间登记集里）。

    ★ 这个变异体改过三版，值得留档：
      ① 塞进一个**已登记**的分片场景 ⇒ 只让 B0 红、B3 照样绿，等于没测到 B3；
      ② 塞进 ut 分片 ⇒ `_index.json` **也登记了 ut 的房间**，`(ut, rid)` 在登记集里，
         仍然不算"未登记"；
      ③ 塞进 `desktop.json` ⇒ 它没有 `original_room_id`、`scene_id` 也不在 index
         ⇒ 键天然不在登记集里，B3 才真的被走到。
      「负控制输入必须真落进被测分支」——两次都栽在这一条上，不是剧本写错。
    """
    x, y = first_noroom_xy()
    d = jl(p)
    d.setdefault('objects', []).append({'pos': [x, y], 'src': WANT})
    dump(p, d)


def mut_move_pos(p):
    d = jl(p)
    _sid, sc = _scene_of(d)
    for o in sc['objects']:
        if isinstance(o, dict) and o.get('src') == WANT:
            o['pos'] = [o['pos'][0] + 1, o['pos'][1] + 1]
            break
    dump(p, d)


def mut_duplicate(p):
    d = jl(p)
    _sid, sc = _scene_of(d)
    for o in list(sc['objects']):
        if isinstance(o, dict) and o.get('src') == WANT:
            sc['objects'].append(dict(o))
            break
    dump(p, d)


def mut_wipe_shard(p):
    d = jl(p)
    n = 0
    for sc in (d.get('scenes') or {}).values():
        if not isinstance(sc, dict):
            continue
        keep = [o for o in (sc.get('objects') or [])
                if not (isinstance(o, dict) and o.get('src') == WANT)]
        n += len(sc.get('objects') or []) - len(keep)
        sc['objects'] = keep
    dump(p, d)
    print('     （清掉 %d 条 Any）' % n)


def mut_routes_edge(p):
    d = jl(p)
    rs = d.get('routes') if isinstance(d, dict) else d
    rs.append({'to': 'ch1.kris_room.kris_s_room', 'priority': 999999,
               'reason': 'MUT173 编造边', 'when_scene': 'desktop',
               'when_door': None, 'when_src': WANT})
    if isinstance(d, dict):
        d['routes'] = rs
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)


MUTS = [
    ('M1', u'删掉某场景的一条 Any', 'B0', mut_delete_one),
    ('M2', u'给一条 Any 硬加 sprite', 'B2', mut_add_sprite),
    ('M3', u'把未登记房间的门硬塞进某场景', 'B3', mut_noroom),
    ('M4', u'把一条 Any 的坐标挪 1px', 'B0', mut_move_pos),
    ('M5', u'复制一条造成同坐标重复', 'B1', mut_duplicate),
    ('M6', u'清空一个分片里的全部 Any', 'A4', mut_wipe_shard),
    ('M7', u'往 `_routes.json` 编造一条 Any 边', 'D0', mut_routes_edge),
]


def locate(mid):
    """变异落在哪个文件上（**改之前就要知道**，才能先备份）。"""
    if mid == 'M7':
        return os.path.join(SCENES, '_routes.json')
    if mid == 'M3':
        return os.path.join(SCENES, 'desktop.json')
    return first_scene_with_any()[0]


def main():
    only = [a for a in sys.argv[1:] if a.startswith('M')]
    print('=' * 70)
    print(u'check173 变异测试：%d 个变异体' % len(MUTS))
    print('=' * 70)

    print('')
    print(u'[基线] 不改任何数据，先确认全部绿')
    rc, txt, reds = run_check()
    base_ok = (rc == 0 and not reds)
    print(u'   exit=%d 红项=%r  ⇒ %s' % (rc, reds, u'OK' if base_ok else u'不绿！'))
    if not base_ok:
        print(u'基线就不绿，变异测试无意义 ⇒ 先修 check173')
        return 1

    caught = 0
    total = 0
    for mid, desc, want, fn in MUTS:
        if only and mid not in only:
            continue
        total += 1
        print('')
        print(u'[%s] %s（期望报红：%s）' % (mid, desc, want))
        rec = None
        try:
            p = locate(mid)
            rec = backup([p])          # ★ 先备份，再改（顺序反了就是假安全）
            fn(p)
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
