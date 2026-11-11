# -*- coding: utf-8 -*-
u"""第183轮 · 删掉 ch2 `priority=7122` 那条（`traffic_3 → dw_city_man`）确定性边。

## 为什么要删

原作 `obj_doorw_musfade.Alarm_2`：

    man_room = scr_sideb_get_phase() == 0 && global.flag[917] < 2
               && global.flag[918] == 0 && ceil(random(50)) == 50;
    if (man_room) room_goto(room_dw_city_man);
    else          room_goto(room_dw_city_moss);

⇒ `man` 是 **1/50 的概率分支**，`moss` 才是 else。第169轮把同一扇 W 门的三个互斥分支
（`dog_traffic` / `man` / `moss`）都物化成**无条件边**，于是账本里多了一条
"确定性地去 man"——它既不符合原作，又会让人以为这条路一定能走通。

第182轮已经把概率机制接上（`_hidden_rooms[1]`，`enabled: true`，p=0.02），
所以这条确定性边必须让位。

## 为什么是"删"而不是"改指 moss"

`7123` 本来就已经指向 `dw_city_moss`。把 `7122` 也改指 moss 只会造出
**两条一模一样的 moss 边**（重复边是本项目明令不加的东西，见第170轮）。

## 为什么删它安全

`7121`（`dog_traffic`）的 priority 更小、`when_*` 完全相同 ⇒ `match()` **永远**返回 7121，
`7122` 从落地那天起**从未被消费**。删它不改任何运行行为，只改可达图与账本计数。

## 幂等（第180轮双跑教训）

第一次：留档 → 删 → 重写。
第二次起：检测到已删且留档可还原 ⇒ **空转并说清理由**，不 assert、不重复删。
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
EVID = os.path.join(ROUND, '_evidence', 'removed183.json')

PRIORITY = 7122
FROM_SCENE = u'ch2.cyber_city.dw_city_traffic_3'

#: 删完边之后，`_hidden_rooms[1].note` 里那句"7122 尚未删除"就成了假话。
#: 这条 note 是**给下一个人看的现况说明**，必须跟着改（否则下一轮又要重新推一遍）。
NEW_NOTE = (
    u'第182轮**已启用**：站在这间房出门时掷 1/50（`ceil(random(50)) == 50`），'
    u'命中且没发现过才改去本房；真站进来后写 `data_store/hidden_rooms_seen.json` **永久锁定**。'
    u'★ 第183轮已删掉与之冲突的确定性边 `dw_city_traffic_3 → dw_city_man`'
    u'（原 priority 7122，留档 `第183轮-删7122误边/_evidence/removed183.json`）：'
    u'原作那是 1/50 概率分支、不是确定性边，且 `7121`（dog_traffic）`when_*` 完全相同、'
    u'priority 更小 ⇒ 它从落地起**从未被 `match()` 消费**，删它不改变任何运行行为。'
)


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def dump_routes(d):
    """按第44轮定下的格式落盘：indent=2 / ensure_ascii=False / CRLF / 无尾换行。

    ★ 这个口径是**校验过的**：对改前文件做同样的 dumps 与磁盘逐字节相同
      （`len 2210868 == 2210868`），所以重写不会顺带改排版。
    """
    return json.dumps(d, indent=2, ensure_ascii=False).replace('\n', '\r\n')


def _sig(obj):
    """条目指纹：字段序无关的规范化 JSON。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def fix_note(data):
    u"""把 ch2 那条隐藏房登记的 `note` 更新成"边已删"的现况。返回改动条数。"""
    n = 0
    for e in (data.get('_hidden_rooms') or []):
        if not isinstance(e, dict):
            continue
        if e.get('from_scene') != FROM_SCENE:
            continue
        if e.get('note') == NEW_NOTE:
            continue
        e['note'] = NEW_NOTE
        n += 1
    return n


def load_evidence():
    if not os.path.isfile(EVID):
        return None
    try:
        d = json.loads(rd(EVID))
        if isinstance(d, dict) and isinstance(d.get('routes'), list):
            return d
    except Exception:                                  # noqa: BLE001
        pass
    return None


def main():
    raw = rd(ROUTES)
    data = json.loads(raw)
    routes = data.get('routes') or []

    hit = [r for r in routes if isinstance(r, dict) and r.get('priority') == PRIORITY]
    ev = load_evidence()
    n_note = fix_note(data)

    if not hit:
        # ---------- 幂等分支：已经删过了 ----------
        if ev is None:
            print('[FAIL] 表里没有 priority=%d，但也没有留档 ⇒ 无法证明它曾经是什么' % PRIORITY)
            return 2
        keep = ev['routes']
        want = (ev.get('meta') or {}).get('total_after')
        sig = _sig
        # ★ 自证要能**失败**（第125轮：恒真判据比不写更危险）。
        #   两条都非平凡：①当前条数 == 留档记的删后条数；②留档那条**确实不在**表里。
        n_ok = (isinstance(want, int) and len(routes) == want)
        gone = not any(sig(r) == sig(k) for r in routes for k in keep)
        if n_note:
            wr(ROUTES, dump_routes(data))
            print('[NOTE] 登记说明已更新（%d 条）' % n_note)
        print('[OK] 已处理过（空转）：priority=%d 不在表里；留档 %d 条可整段加回' 
              % (PRIORITY, len(keep)))
        print('     当前条数 = %d（留档记 %s）一致=%s ；留档条目确实已不在表里=%s'
              % (len(routes), want, n_ok, gone))
        return 0 if (n_ok and gone) else 2

    if len(hit) != 1:
        print('[FAIL] priority=%d 命中 %d 条（期望恰好 1 条）' % (PRIORITY, len(hit)))
        return 2

    route = hit[0]
    print('[1] 待删：%s -> %s（when_scene=%s / when_door=%s）'
          % (PRIORITY, route.get('to'), route.get('when_scene'), route.get('when_door')))

    # ---------- 留档 ----------
    payload = {
        'meta': {
            'round': 183,
            'why': u'原作是 1/50 概率分支（ceil(random(50)) == 50），不是确定性边；'
                   u'第182轮已把概率机制接上（_hidden_rooms[1] enabled），本边让位。',
            'why_not_repoint': u'7123 已指向 dw_city_moss，改指会造出重复边。',
            'why_safe': u'7121 priority 更小且 when_* 相同 ⇒ match() 永远返回 7121，'
                        u'本条从未被消费。',
            'restore': u'把 routes 里的对象按原 priority 顺序插回 routes 数组即可（逐字段未改）。',
            'removed_count': 1,
            'total_before': len(routes),
            'total_after': len(routes) - 1,
        },
        'routes': [route],
    }
    wr(EVID, json.dumps(payload, indent=2, ensure_ascii=False).replace('\n', '\r\n'))
    print('[2] 留档 ⇒ %s' % EVID)

    # ---------- 删 ----------
    data['routes'] = [r for r in routes if not (isinstance(r, dict)
                                                and r.get('priority') == PRIORITY)]
    wr(ROUTES, dump_routes(data))
    print('[3] 已重写路由表：%d → %d 条' % (len(routes), len(data['routes'])))

    # ---------- 自证：往返无损 + 其余一条未变 ----------
    now_raw = rd(ROUTES)
    now = json.loads(now_raw)
    same_fmt = (dump_routes(now) == now_raw)

    # 「其余未变」用**多重集合**比，别用"过滤掉待删那条"（第169轮踩过：
    # 过滤法在有条目与待删条目逐字段相同时会误判）。
    def _count(items):
        c = {}
        for it in items:
            k = _sig(it)
            c[k] = c.get(k, 0) + 1
        return c

    before_c = _count(routes)
    after_c = _count(now['routes'])
    k_del = _sig(route)
    before_c[k_del] -= 1
    if before_c[k_del] == 0:
        del before_c[k_del]
    only_del = (before_c == after_c)

    print('[4] 格式无损往返 = %s ；剩余 %d 条 ；除待删那条外逐条未变 = %s'
          % (same_fmt, len(now['routes']), only_del))
    if not same_fmt:
        print('[FAIL] 重写改变了排版（会撞第176轮 E2）')
        return 2
    if not only_del:
        print('[FAIL] 删除时顺手动了别的条目')
        return 2
    print('[OK] 只删了这一条，其余逐条未变')
    return 0


if __name__ == '__main__':
    sys.exit(main())
