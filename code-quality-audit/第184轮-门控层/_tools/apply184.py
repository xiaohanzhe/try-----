# -*- coding: utf-8 -*-
u"""第184轮 · 施工：给 `_routes.json` 加顶层 `_gates`（**只加一条**，不碰任何 route 对象）。

为什么只加顶层
--------------
塞进 route 对象（给 7121/7123 各加一个 `when_gate`）会动两条规则，而 `check169`
的 `_original` 指纹、`check176` 的规范化 sha1 都对 route **逐字段**敏感 ⇒ 会撞一排
与本轮无关的老锁。放顶层只影响"统计文件字节/CRLF 数"的纯回显套件。

幂等
----
第二遍跑：`_gates` 已存在且**逐字段等于**本脚本要写的那条 ⇒ 空转 `rc=0`。
`_gates` 存在但内容不同 ⇒ **不覆盖**，打 `[FAIL]` 退 `rc=2`（让人来看，
而不是"跑到第二遍就把别人的手改冲掉"）。

自证（两条都必须**能失败**）
--------------------------
① 改前整表 `dump()` 与磁盘**逐字节相同**（无损往返）—— 失败说明这个 json 不是
   用 `indent=2 + ensure_ascii=False + CRLF` 存的，直接重写会污染全表格式；
② 加完之后 `routes` 仍是 2830 条、且**逐条与改前相同**（用多重集合比，
   **不用**"过滤掉谁再比"那种会放过"多改了一条"的写法 —— 第169轮踩过）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, u'..', u'..', u'..')
ROUTES = os.path.join(ROOT, u'ralsei_pet', u'assets', u'scenes', u'_routes.json')

EXPECT_ROUTES = 2830

#: 唯一要加的那条门控。**字段顺序即书写顺序**（人要读它）。
GATE = {
    u'when_scene': u'ch2.cyber_city.dw_city_traffic_3',
    u'when_door': u'W',
    u'mark': u'ch2.city.dog_traffic',
    u'set_mark_when_arrive': u'ch2.cyber_city.dw_city_dog_traffic',
    u'to_when_unset': u'ch2.cyber_city.dw_city_dog_traffic',
    u'to_when_set': u'ch2.cyber_city.dw_city_moss',
    u'_original': {
        u'chapter': u'ch2',
        u'object': u'obj_doorw_musfade',
        u'event': u'Alarm_2',
        u'cond_unset': u'global.flag[917] == 0 && scr_sideb_get_phase() == 0',
        u'cond_set': (u'!(global.flag[917] == 0 && scr_sideb_get_phase() == 0)'
                      u' && !(man_room)'),
        u'cond_man': (u'!(global.flag[917] == 0 && scr_sideb_get_phase() == 0)'
                      u' && man_room'),
        u'evidence': (u'code-quality-audit/第170轮-门实例级落点/_evidence/'
                      u'applied170.json（prio 7121 / 7122 / 7123 的 cond 原文）'),
        u'note': (u'`dog_traffic` 与 `moss` 是同一扇门的**确定性两支**，区别只在剧情'
                  u'状态；`man` 那支是 1/50 概率，第182轮已由 `_hidden_rooms[1]` '
                  u'承担，与门控无关。★★ `flag[917]` 在原件里是**次数**'
                  u'（`< 2` 才会继续掷 man），本产品只代理"去过 / 没去过"这层布尔'
                  u'（第184轮口径）⇒ `to_when_set` 之后永久去 moss。'),
    },
}


def dump(d):
    u"""与磁盘同一套序列化口径（第183轮验证过：逐字节相同）。"""
    return json.dumps(d, indent=2, ensure_ascii=False).replace(u'\n', u'\r\n')


def read_bytes(path):
    with io.open(path, 'rb') as f:
        return f.read()


def write_bytes(path, data):
    u"""临时文件 + `os.replace` 原子替换（写一半断电不会留半个 JSON）。"""
    tmp = path + u'.tmp'
    with io.open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def sig(route):
    u"""一条规则的**内容**指纹（不含书写位置）。用于"其余逐条未变"。"""
    return json.dumps(route, ensure_ascii=False, sort_keys=True)


def main():
    raw = read_bytes(ROUTES)
    text = raw.decode(u'utf-8')
    data = json.loads(text)

    # ① 无损往返（**能失败的**自证：格式若不符，这里就红）
    same = dump(data).encode(u'utf-8') == raw
    print(u'[1] 改前无损往返 = %s（若 False 则本脚本的重写会污染格式，已中止）' % same)
    if not same:
        return 2

    routes = data.get(u'routes')
    if not isinstance(routes, list) or len(routes) != EXPECT_ROUTES:
        print(u'[FAIL] routes 期望 %d 条，实际 %r ⇒ 表已被别的东西改过，拒绝施工'
              % (EXPECT_ROUTES, len(routes) if isinstance(routes, list) else routes))
        return 2

    existing = data.get(u'_gates')
    if existing is not None:
        if existing == [GATE]:
            print(u'[2] `_gates` 已存在且逐字段等于目标 ⇒ 空转（幂等）')
            print(u'[OK] 无事可做')
            return 0
        print(u'[FAIL] `_gates` 已存在但内容不同 ⇒ **不覆盖**，请人工判断')
        print(u'      现有 = %s' % json.dumps(existing, ensure_ascii=False)[:300])
        return 2

    before_sigs = [sig(r) for r in routes]
    before_count = {}
    for s in before_sigs:
        before_count[s] = before_count.get(s, 0) + 1

    # ② 追加顶层键（插在 `_hidden_rooms` 之后；不存在就放末尾）
    out = {}
    placed = False
    for k, v in data.items():
        out[k] = v
        if k == u'_hidden_rooms':
            out[u'_gates'] = [GATE]
            placed = True
    if not placed:
        out[u'_gates'] = [GATE]

    # ③ 加完之后：条数不变、逐条不变（多重集合比，不用"过滤谁再比"）
    routes_after = out.get(u'routes')
    ok_n = isinstance(routes_after, list) and len(routes_after) == EXPECT_ROUTES
    after_count = {}
    for r in (routes_after or []):
        s = sig(r)
        after_count[s] = after_count.get(s, 0) + 1
    ok_same = after_count == before_count

    print(u'[3] 加完后 routes 条数 = %s（期望 %d）' % (len(routes_after or []), EXPECT_ROUTES))
    print(u'[4] 除新增顶层键外**逐条未变** = %s' % ok_same)
    print(u'[5] 顶层键序 = %s' % list(out.keys()))
    if not (ok_n and ok_same):
        print(u'[FAIL] 自证未过，**不落盘**')
        return 2

    write_bytes(ROUTES, dump(out).encode(u'utf-8'))
    print(u'[6] 已写入：顶层新增 `_gates`（1 条），routes 仍 %d 条' % EXPECT_ROUTES)

    # ④ 落盘后回读再确一次（防"写进去的不是我以为的"）
    back = json.loads(read_bytes(ROUTES).decode(u'utf-8'))
    ok_back = back.get(u'_gates') == [GATE] \
        and len(back.get(u'routes') or []) == EXPECT_ROUTES
    print(u'[7] 回读核对 = %s' % ok_back)
    if not ok_back:
        return 2
    print(u'[OK] 只加了 `_gates` 一条，routes 一条没动')
    return 0


if __name__ == '__main__':
    sys.exit(main())
