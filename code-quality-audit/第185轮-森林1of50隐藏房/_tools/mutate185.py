# -*- coding: utf-8 -*-
u"""第185轮 · 变异：证明 `check185` 的 39 条**有鉴别力**（不是写完就绿的摆设）。

做法：**原地变异 + 快照还原 + 收尾核 sha1**。
★ 为什么不在副本上变异（第184轮的教训）：`scene_routing` 会 `import` 兄弟模块、
  判据按目录拼文件名，拷到临时区就 `ModuleNotFoundError`；而且第174轮被清理守卫
  拦过一次（临时/备份禁放工作区）。所以就地改、改完立刻还原。

三重断言（每条变异都要同时成立）
--------------------------------
1. **期望红**：至少 1 条 `[FAIL]`，且**命中**它该打红的那条判据（按编号前缀比）。
2. **确定性**：同一条变异跑两遍，`[FAIL]` 集合**完全相同**（否则是随机/顺序相关的假红）。
3. **不越界**：红数 `0 < n < 39`（全红说明判据互相耦合到没有鉴别力）。

收尾：四个被改文件逐个核 sha1 == 快照；全绿复跑一次（还原是否干净）。

用法（仓库根）：python code-quality-audit/第185轮-森林1of50隐藏房/_tools/mutate185.py
"""
import hashlib
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
SC = os.path.join(PET, 'assets', 'scenes')

CHECK = os.path.join(HERE, 'check185.py')
TOTAL = 41

F = {
    'routes': os.path.join(SC, '_routes.json'),
    'zone': os.path.join(SC, '_zone.ch1.forest.json'),
    'index': os.path.join(SC, '_index.json'),
    'main': os.path.join(PET, 'src', 'main.py'),
    'sr': os.path.join(PET, 'modules', 'scene_routing.py'),
    'ii': os.path.join(PET, 'modules', 'item_interact.py'),
}


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def lf(s):
    return s.replace('\r\n', '\n')


def dumps_inline(obj, indent=1, level=0):
    pad = ' ' * (indent * level)
    pad2 = ' ' * (indent * (level + 1))
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        return '{\n' + ',\n'.join(
            '%s%s: %s' % (pad2, json.dumps(k, ensure_ascii=False),
                          dumps_inline(v, indent, level + 1)) for k, v in obj.items()
        ) + '\n' + pad + '}'
    if isinstance(obj, list):
        if not obj:
            return '[]'
        if all(isinstance(x, int) and not isinstance(x, bool) for x in obj):
            return '[' + ', '.join(str(x) for x in obj) + ']'
        return '[\n' + ',\n'.join(pad2 + dumps_inline(v, indent, level + 1)
                                  for v in obj) + '\n' + pad + ']'
    return json.dumps(obj, ensure_ascii=False)


def dump2(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False).replace('\n', '\r\n')


def dump_zone(obj):
    return dumps_inline(obj).replace('\n', '\r\n') + '\r\n'


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()


def run_check():
    u"""跑 `check185`，返回 (红判据编号集合, 红行列表, 全输出)。"""
    p = subprocess.run([sys.executable, CHECK], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    reds, ids = [], set()
    for line in out.split('\n'):
        if line.startswith('[FAIL]'):
            reds.append(line.strip())
            body = line[6:].strip()
            ids.add(body.split(u' ')[0].split(u'：')[0])
    return ids, reds, out


# ----------------------------------------------------------------- 快照
BASE = {k: sha(v) for k, v in F.items() if os.path.isfile(v)}
SNAP = {k: rd(v) for k, v in F.items() if os.path.isfile(v)}


def restore():
    for k, s in SNAP.items():
        wr(F[k], s)


# ----------------------------------------------------------------- 变异体
def m_routes(mut):
    d = json.loads(rd(F['routes']))
    mut(d)
    wr(F['routes'], dump2(d))


def m_zone(mut):
    d = json.loads(rd(F['zone']))
    mut(d)
    wr(F['zone'], dump_zone(d))


def m_index(mut):
    d = json.loads(rd(F['index']))
    mut(d)
    wr(F['index'], dump2(d))


def p_src(key, old, new, count=1):
    u"""在源码里做**字面替换**（只换第一处，锚点必须唯一）。

    ★★★ 两侧都要 `lf()` 归一（第185轮踩到的真坑）：`main.py` / `item_interact.py`
      在盘上是 **CRLF**，而夹具里的锚点写的是 `\n` ⇒ `old in s` 恒假、
      报"锚点没命中"——那是**夹具的错**，不是判据的错。
      ★ 归一后**按 LF 落盘**：这里只是临时态，`restore()` 从 `SNAP`（按 `newline=''`
        原样读的字节忠实文本）写回，EOL 会还原。判据侧只做 AST / import，不吃 EOL。
    """
    s = lf(rd(F[key]))
    o, n = lf(old), lf(new)
    assert o in s, u'锚点没命中：%s / %r' % (key, o[:70])
    assert s.count(o) == count, u'锚点出现 %d 次（期望 %d）：%s / %r' % (
        s.count(o), count, key, o[:50])
    wr(F[key], s.replace(o, n, count))


def _hid(d, i=0):
    return d['_hidden_rooms'][i]


MAN = u'ch1.forest.room_man'
BAKE = u'ch1.forest.forest_bake_sale'
AREA5 = u'ch1.forest.forest_area5'

MUTS = [
    # ---------------- 数据侧
    ('M1 隐藏房 `when_door` 由 X 改成 A',
     lambda: m_routes(lambda d: _hid(d).__setitem__('when_door', u'A')), ['B1']),
    ('M2 隐藏房 `when_door` 改成 `*`（任意门都掷）',
     lambda: m_routes(lambda d: _hid(d).__setitem__('when_door', u'*')), ['B2']),
    ('M3 删掉 `room_man` 场景（zone）',
     lambda: m_zone(lambda d: d['scenes'].pop(MAN, None)), ['A2']),
    ('M4 `room_man` 少一个物件',
     lambda: m_zone(lambda d: d['scenes'][MAN]['objects'].pop()), ['A2']),
    ('M5 `(area5, X)` 的 to 改成 bake_sale',
     lambda: m_routes(lambda d: [
         r.__setitem__('to', u'ch1.forest.forest_bake_sale')
         for r in d['routes'] if r.get('when_scene') == AREA5
         and r.get('when_door') == u'X']), ['A8']),
    ('M6 ★ 动了那条**本来就对**的 `(area5, A)`（priority 662→663）',
     lambda: m_routes(lambda d: [
         r.__setitem__('priority', 663) for r in d['routes']
         if r.get('when_scene') == AREA5 and r.get('when_door') == u'A']), ['A10']),
    ('M7 `_original.code` 抄错一个字（starwalker→starwalke）',
     lambda: m_routes(lambda d: [
         r['_original'].__setitem__(
             'code', r['_original']['code'].replace('starwalker', 'starwalke'))
         for r in d['routes'] if r.get('when_scene') == AREA5
         and r.get('when_door') == u'X']), ['A11']),
    ('M8 `_hidden_rooms[0]` 关掉（enabled=False）',
     lambda: m_routes(lambda d: _hid(d).__setitem__('enabled', False)), ['B1']),
    ('M16 ★ ch5 那条 Any 门的 priority 改成 9002（与本轮手工边**撞号**）',
     # ★ 挑"别人撞过来"而不是"改本轮那条"，是为了让 A13 **单独**红：
     #   改本轮那条的话 A9 也会一起红，就看不出 A13 到底有没有鉴别力了。
     lambda: m_routes(lambda d: [
         r.__setitem__('priority', 9002) for r in d['routes']
         if r.get('when_scene') == u'ch5.flower_castle.dw_fcastle_gloves_tower'
         and r.get('when_door') is None and r.get('to') ==
         u'ch5.flower_castle.flower_castle_right_diner']), ['A13']),
    ('M17 ★★ 把 `bake_sale` 也塞进 zone（**重复载体**，第185轮真犯过的错）',
     # ★ 这条就是"施工事故复现"：`bake_sale` 有自己的独立文件，再进 zone 物件就被数两遍。
     #   变异体只塞一个空 objects 的占位 —— A14 判的是**载体唯一性**，不是物件内容。
     lambda: m_zone(lambda d: d['scenes'].__setitem__(
         BAKE, {'name': u'猩红森林·savepoint2', 'name_raw': 'room_forest_savepoint2',
                'name_derived': True, 'original_room_id': 82, 'bg': None,
                'bg_source': 'none', 'objects': []})), ['A14']),
    # ---------------- 代码侧
    ('M9 `pick_hidden` 缺门信息就当成"这扇门"（fail-closed 拆掉）',
     lambda: p_src('sr',
                   u'            if not (isinstance(door, str) and door):\n'
                   u'                continue          # ★ 缺门信息 ⇒ 不掷（见 docstring）\n',
                   u'            if not (isinstance(door, str) and door):\n'
                   u'                door = want_door\n'),
     ['B3']),
    ('M10 `pick_hidden` 不比门字母（只判有没有门信息）',
     # ★ 锚点必须带上上一行的注释：`gate_for` 里有**逐字相同**的两行
     #   （`if want_door != '*' and want_door != door:` + `continue`，缩进也一样），
     #   只靠这两行会命中 2 次。`continue  # ★ …不掷…` 那一行才是 `pick_hidden` 独有的。
     lambda: p_src('sr',
                   u'                continue          # ★ 缺门信息 ⇒ 不掷（见 docstring）\n'
                   u"            if want_door != '*' and want_door != door:\n"
                   u"                continue\n",
                   u'                continue          # ★ 缺门信息 ⇒ 不掷（见 docstring）\n'
                   u"            if False:\n"
                   u"                continue\n"),
     ['B2']),
    ('M11 `_maybe_divert_to_hidden` 不把 door 传下去',
     lambda: p_src('main',
                   u'            hit = scene_routing.pick_hidden(hidden, from_scene, self._hidden_seen(),\n'
                   u'                                            door=door)',
                   u'            hit = scene_routing.pick_hidden(hidden, from_scene, self._hidden_seen())'),
     ['C4']),
    ('M12 `_item_enter_scene` 把掷骰挪到 `switch` 之后',
     lambda: p_src('main',
                   u'            target = scene_id\n'
                   u'            try:\n'
                   u'                before = self.__dict__.get(\'current_scene\')\n'
                   u'                target = self._maybe_divert_to_hidden(before, scene_id, door=door)\n'
                   u'            except Exception:\n'
                   u'                _log.exception(\'门/暗之泉：隐藏房判定异常（已忽略，照常走原目标）\')\n'
                   u'                target = scene_id\n'
                   u'            ok = bool(self.scene.switch(target))\n',
                   u'            ok = bool(self.scene.switch(scene_id))\n'
                   u'            self._maybe_divert_to_hidden(\'x\', scene_id, door=door)\n'
                   u'            target = scene_id\n'),
     ['C6']),
    ('M13 `_item_enter_scene` 不再走 `_travel_feedback_done`（记账断了）',
     lambda: p_src('main',
                   u'            if ok:\n'
                   u'                try:\n'
                   u'                    self._travel_feedback_done()\n'
                   u'                except Exception:\n'
                   u'                    _log.exception(\'门/暗之泉：到达收尾异常（已忽略）\')\n',
                   u'            if ok:\n'
                   u'                pass\n'),
     ['C7']),
    ('M14 `DoorProp.on_interact` 改回旧签名（门字母不传）',
     lambda: p_src('ii',
                   u'        ok = bool(_call_enter(self.on_enter, target, self.door_letter))',
                   u'        ok = bool(self.on_enter(target))'),
     ['C8']),
    ('M15 `_accepts_door_kw` 恒 True（1 参桩会炸）',
     lambda: p_src('ii',
                   u"    try:\n"
                   u"        sig = inspect.signature(fn)\n"
                   u"    except (TypeError, ValueError):\n"
                   u"        return False\n",
                   u"    return True\n"
                   u"    try:\n"
                   u"        sig = inspect.signature(fn)\n"
                   u"    except (TypeError, ValueError):\n"
                   u"        return False\n"),
     ['D4']),
]

print('')
print('=' * 72)
print(u'基线与快照')
print('=' * 72)
print(u'  被跟踪文件 %d 个' % len(SNAP))
_ids, _reds, _out = run_check()
print(u'  基线：红=%d 条' % len(_reds))
if _reds:
    for r in _reds:
        print(u'    %s' % r)
    print(u'★ 基线不绿 ⇒ 变异没有意义。中止。')
    sys.exit(3)

print('')
print('=' * 72)
print(u'变异 %d 条（每条：期望红 + 双跑一致 + 0<红<%d）' % (len(MUTS), TOTAL))
print('=' * 72)

_bad = []
for i, (desc, fn, want) in enumerate(MUTS, 1):
    restore()
    try:
        fn()
    except Exception as e:
        print(u'[夹具错] %s ⇒ %s' % (desc, e))
        _bad.append(desc + u'（夹具没改成）')
        restore()
        continue
    ids1, reds1, _ = run_check()
    ids2, reds2, _ = run_check()
    hit = [w for w in want if w in ids1]
    ok = bool(hit) and len(reds1) > 0 and len(reds1) < TOTAL and ids1 == ids2
    print(u'%s %02d/%02d %s' % ('[ OK ]' if ok else '[FAIL]', i, len(MUTS), desc))
    print(u'        期望红 %r → 命中 %r；红数 %d；双跑一致=%s'
          % (want, sorted(ids1), len(reds1), ids1 == ids2))
    if not ok:
        _bad.append(desc)
        if ids1 != ids2:
            print(u'        ★ 双跑不一致：%r vs %r' % (sorted(ids1), sorted(ids2)))
        for r in reds1[:6]:
            print(u'        %s' % r)
    restore()

print('')
print('=' * 72)
print(u'还原核验')
print('=' * 72)
_restore_ok = True
for k, h in BASE.items():
    now = sha(F[k])
    same = now == h
    _restore_ok &= same
    if not same:
        print(u'[FAIL] %s sha1 未还原：%s vs %s' % (k, h[:12], now[:12]))
print(u'  %d 个文件逐个 sha1 与快照一致 = %s' % (len(BASE), _restore_ok))

_ids, _reds, _ = run_check()
print(u'  还原后复跑：红=%d（应为 0）' % len(_reds))
_final = _restore_ok and not _reds and not _bad

print('')
print('=' * 72)
print(u'结论：%s（变异 %d 条，全抓 %d 条）'
      % ('PASS' if _final else 'FAIL', len(MUTS), len(MUTS) - len(_bad)))
if _bad:
    for d in _bad:
        print(u'  ★ %s' % d)
print('=' * 72)
sys.exit(0 if _final else 1)
