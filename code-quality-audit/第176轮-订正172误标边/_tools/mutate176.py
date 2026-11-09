# -*- coding: utf-8 -*-
u"""第176轮变异：证明 `check176.py` 的每条判据不是摆设。

规矩（与 173/174/175 轮同）
--------------------------
  ① **先备份再改**（"先改再备份"等于没恢复，sha1 还是绿的 = 假安全）；
  ② 每个变异跑完**立即**恢复并按 sha1 + 全文核对字节还原；
  ③ 「红在哪几条」按**实测**记 —— 判据抓到 ≠ 我猜对是哪条，
     但**必须**抓到本变异针对的那一条（`want`），否则等于"抓错了人"；
  ④ 备份落 `D:\\_tmp\\mut176\\`（不在工作区，免得 `git add -A` 把它记成删除）。

★ 本轮只动两个文件：`_routes.json`（产品表）与 `removed176.json`（留档）。
  `_routes.json` 用与 `apply176.py` 完全相同的**规范化写法**（indent=2 + CRLF）落盘，
  这样 E2（无损往返）在变异里也仍然成立 —— 变异要**只**命中目标判据，不制造噪声。

用法：python mutate176.py
"""
import hashlib
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
EV = os.path.join(ROUND, '_evidence')
CHECK = os.path.join(HERE, 'check176.py')
ROUTES_P = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
RM_P = os.path.join(EV, 'removed176.json')
BAK = 'D:\\_tmp\\mut176'


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()


def dump_routes(d):
    return json.dumps(d, ensure_ascii=False, indent=2).replace(u'\n', u'\r\n')


def run_check():
    r = subprocess.run([sys.executable, CHECK], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    codes = []
    for ln in out.splitlines():
        if ln.startswith('[FAIL]'):
            codes.append(ln.split('] ', 1)[1].split(u'    ')[0].strip()
                         .split(u' ')[0])
    return r.returncode, codes


# ---------------------------------------------------------------------------
# 夹具：动手之前先断言"我确实改到了"，改不到就直接抛（不许静默 no-op）
# ---------------------------------------------------------------------------
def _rm_load():
    return json.loads(rd(RM_P))


def m1_add_back():
    u"""把留档里的一条**加回**产品表（模拟"没删"）。"""
    d = json.loads(rd(ROUTES_P))
    r0 = _rm_load()['items'][0]
    assert r0['priority'] not in set(x.get('priority') for x in d['routes'])
    d['routes'].append(r0)
    return ROUTES_P, dump_routes(d)


def m2_rm_drop_one():
    u"""留档少一条（模拟"只删了 41 条"，count 仍写 42）。"""
    o = _rm_load()
    n0 = len(o['items'])
    o['items'] = o['items'][1:]
    assert len(o['items']) == n0 - 1
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


def m3_rm_prio():
    u"""留档里一条 priority 改错（换成一个区间内、但**没被占**的值）。

    ★ 第一版把 7950 写死，结果 `assert` 直接炸 —— 那个号本来就在留档里。
      "看着像空号"不算数，**从账上算出来**才算。
    """
    o = _rm_load()
    used = set(x['priority'] for x in o['items'])
    old = o['items'][0]['priority']
    free = [v for v in range(7300, 7300 + 798) if v not in used]
    assert free, u'区间里没有空号（说明留档不是 42 条）'
    o['items'][0]['priority'] = free[0]
    assert o['items'][0]['priority'] != old
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


def m4_edit_live():
    u"""改一条**现存**（非留档）边的目标 —— 其余 2,768 条不该被动的意思就是它。"""
    d = json.loads(rd(ROUTES_P))
    prios = set(x['priority'] for x in _rm_load()['items'])
    tgt = [x for x in d['routes']
           if (x.get('_original') or {}).get('batch') == 172
           and x.get('priority') not in prios]
    assert tgt, u'找不到可改的 172 段边'
    tgt[0]['to'] = u'ch1.card_castle.card_castle_1f'
    assert tgt[0]['to'] != u'__nope__'
    return ROUTES_P, dump_routes(d)


def m5_drop_variant():
    u"""删一条第174轮的变体边，而且**专挑**承载留档某个 `(场景,目标)` 对的那条。

    ★ 第一版随手删"第一条 Horz"，结果 C4（可达图逐对不变）**没红** —— 因为那条边
      的 `(场景,目标)` 有兄弟边顶着，对集合没变。C4 判的是**对**、不是**边**，
      它不红是对的。夹具要打到 C4，就得删"独苗承接者"。
    """
    d = json.loads(rd(ROUTES_P))
    rm_pairs = set((x.get('when_scene'), x.get('to')) for x in _rm_load()['items'])
    cnt = {}
    for x in d['routes']:
        k = (x.get('when_scene'), x.get('to'))
        cnt[k] = cnt.get(k, 0) + 1
    n0 = len(d['routes'])
    idx = [k for k, x in enumerate(d['routes'])
           if x.get('when_src') in ('obj_doorAnyHorz', 'obj_doorAnyVert')
           and (x.get('when_scene'), x.get('to')) in rm_pairs
           and cnt[(x.get('when_scene'), x.get('to'))] == 1]
    assert idx, u'找不到"独苗承接"的变体边'
    d['routes'].pop(idx[0])
    assert len(d['routes']) == n0 - 1
    return ROUTES_P, dump_routes(d)


def m6_rm_via():
    u"""留档里一条的 `_original.via` 改成变体名（"改标签"而非删除的痕迹）。"""
    o = _rm_load()
    o['items'][0]['_original']['via'] = 'obj_doorAnyHorz'
    assert o['items'][0]['_original']['via'] != 'obj_doorAny'
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


def m7_rm_precreate():
    u"""留档里一条 `precreate` 改成不存在的代码名 ⇒ 探针反查查不到。"""
    o = _rm_load()
    o['items'][0]['_original']['precreate'] = u'gml_RoomCC_nope_1_PreCreate'
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


def m8_rm_meta():
    u"""留档的 `note` 清空 + `count` 改成 41（"说明书自己先坏了"）。"""
    o = _rm_load()
    o['note'] = u''
    o['count'] = 41
    assert o['count'] != len(o['items'])
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


def m9_rm_doorx():
    u"""留档里一条门坐标漂移 1px（内容对不上原作那扇门）。"""
    o = _rm_load()
    old = o['items'][0]['_original']['door_x']
    o['items'][0]['_original']['door_x'] = old + 1
    assert o['items'][0]['_original']['door_x'] != old
    return RM_P, json.dumps(o, ensure_ascii=False, indent=1)


CASES = [
    (u'M1 把一条留档边加回产品表', m1_add_back, (u'B1', u'B2', u'B3')),
    (u'M2 留档少一条（count 仍 42）', m2_rm_drop_one, (u'A0', u'B2')),
    (u'M3 留档一条 priority 改错', m3_rm_prio, (u'B1', u'B2')),
    (u'M4 改一条现存边的目标', m4_edit_live, (u'B5', u'C1')),
    (u'M5 删掉留档某对的独苗承接边', m5_drop_variant, (u'B4', u'C4')),
    (u'M6 留档一条 via 改成变体名', m6_rm_via, (u'A3',)),
    (u'M7 留档一条 precreate 编造', m7_rm_precreate, (u'A5',)),
    (u'M8 留档 note 清空 + count 错', m8_rm_meta, (u'A0',)),
    #: ★ 坐标漂移由**内容级**判据抓（B7 按四元组查），不是 C5 ——
    #:   实测如此：C5 只对"同-src 组候选 >=2"的门才有鉴别力（见 check176 C5b），
    #:   而 items[0] 那扇恰好不在这 9 扇里。**按实测记，不按我期望记。**
    (u'M9 留档一条门坐标漂移 1px', m9_rm_doorx, (u'B7',)),
]


def main():
    os.makedirs(BAK, exist_ok=True)
    os.system('')
    rc, base = run_check()
    print(u'基线：rc=%d 红项=%r' % (rc, base))
    if rc != 0:
        print(u'★ 基线不绿，先修判据再跑变异。')
        return 2

    hit = 0
    for name, fn, want in CASES:
        p, new = fn()
        before = rd(p)
        h0 = sha(p)
        b = os.path.join(BAK, os.path.basename(p) + '.bak')
        shutil.copy2(p, b)
        try:
            wr(p, new)
            rc, reds = run_check()
            ok = rc != 0 and set(want) <= set(reds)
            hit += 1 if ok else 0
            print(u'%-30s rc=%d 红=%r  期望含%r %s'
                  % (name, rc, reds, list(want), u'✔' if ok else u'✘'))
        finally:
            shutil.copy2(b, p)
        h1 = sha(p)
        assert h1 == h0, u'%s 恢复失败 %s != %s' % (p, h1, h0)
        assert rd(p) == before, u'%s 字节没还原' % p

    print('')
    print('=' * 70)
    print(u'变异：%d/%d 被抓（且抓的是**针对的那一条**）' % (hit, len(CASES)))
    rc, again = run_check()
    print(u'还原后复跑：rc=%d 红项=%r' % (rc, again))
    print('=' * 70)
    return 0 if hit == len(CASES) and rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
