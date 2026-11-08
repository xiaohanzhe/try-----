# -*- coding: utf-8 -*-
u"""第175轮 · 给 87 个独立场景文件补 `original_room_id`（**文本级行插入，零重排**）。

为什么这轮要做
------------
88 个独立场景文件里 **87 个没有 `original_room_id`**，而 `_index.json` 里
2166 条登记行**全都有**（例：`card_castle_1f -> 114`）。

产品现在是靠 `scene_system.load_scene()` 的一层**回退**兜住的：

    # scene_system.py:498
    if scene.original_room_id is None and isinstance(entry, dict):
        _oid = entry.get('original_room_id')
        if isinstance(_oid, int):
            scene.original_room_id = _oid

⇒ 行为没错，但**文件本身不自足**：任何绕过 `load_scene` 直接读文件的地方
（`SceneState.from_dict(raw)`、将来的导出/校验/编辑器）都会看到 `None`。
本轮把值从 index **抄进文件**，让文件自己说得清自己是谁。

★ 值一律从 `_index.json` 抄同一份 —— **不重算、不猜**。理由：产品运行时
  本来就以 index 为准（`MainWindow._scene_rooms()` 只读 index），从文件抄
  同一个数才不会造出"文件与索引两个真相"。

★ 为什么是**行插入**而不是 `json.dump` 整写
--------------------------------------------
  这些文件是 2 空格缩进 + **CRLF**；整体 dump 相当于把 87 个文件全部重写，
  diff 里每个文件都是全红——而它们缺的只是一个 int。
  实测 87/87 都能用「在 `"area_name": "...",` 那行之后插一行」无损往返：
  键顺序正确、其余键值逐字不变。只动一行，EOL 也不会被 Python 的
  universal-newline 悄悄改掉（全程 `newline=''`）。

用法
----
    python apply175.py            # 演练（不写盘）
    python apply175.py --apply    # 真写
    python apply175.py --apply    # 再跑一次 ⇒ 幂等，`新增 0`
"""
import hashlib
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
INDEX = os.path.join(SCENES, '_index.json')
SNAP = os.path.join(EV, 'before175.json')      # 改前快照（判据要用）

#: 锚点：顶层 `area_name` 那一行。缩进 2 空格、值里不会有引号。
ANCHOR = re.compile(u'^  "area_name": "[^"\\r\\n]*",\\r?\\n', re.M)
FIRST = u'  "area_name"'

APPLY = '--apply' in sys.argv


def rd(p):
    # newline='' ⇒ 字节忠实，不把 CRLF 变成 LF
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def load(p):
    return json.loads(rd(p))


def h_rest(d):
    """除 `original_room_id` 以外的内容指纹（判"其余一字未改"用）。"""
    x = {k: v for k, v in d.items() if k != 'original_room_id'}
    raw = json.dumps(x, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha1(raw).hexdigest()


def index_rooms():
    """`_index.json` → `{scene_id: original_room_id}`（只认 int，其余跳过）。"""
    idx = load(INDEX)
    out, ch_of = {}, {}
    for cid, ch in ((idx or {}).get('chapters') or {}).items():
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            for sid, sc in ((ar or {}).get('scenes') or {}).items():
                rid = (sc or {}).get('original_room_id')
                if isinstance(rid, int) and not isinstance(rid, bool):
                    out[sid] = rid
                    ch_of[sid] = cid
    return out, ch_of


def scene_files():
    return sorted(f for f in os.listdir(SCENES)
                  if f.endswith('.json') and not f.startswith('_'))


def insert_line(text, rid):
    """在 `area_name` 行后插一行；返回新文本。锚点必须恰好一处。"""
    hits = ANCHOR.findall(text)
    if len(hits) != 1:
        raise RuntimeError(u'锚点命中 %d 处（要求恰好 1）' % len(hits))
    m = ANCHOR.search(text)
    if m.start() != text.find(FIRST):
        raise RuntimeError(u'锚点不是第一个 area_name 行')
    eol = '\r\n' if '\r\n' in text else '\n'
    line = u'  "original_room_id": %d,' % rid + eol
    return text[:m.end()] + line + text[m.end():]


def selfcheck(old_text, new_text, rid):
    """插入后的四条铁验，任一不过就拒写。"""
    d0 = json.loads(old_text)
    d1 = json.loads(new_text)
    assert set(d1) - set(d0) == {'original_room_id'}, u'多出别的键'
    assert d1['original_room_id'] == rid, u'值不符'
    for k in d0:
        assert d0[k] == d1[k], u'键 %s 的值被改了' % k
    keys = list(d1)
    assert keys[keys.index('area_name') + 1] == 'original_room_id', u'键顺序不对'
    # 只多一行、且是紧贴锚点的那一行
    eol = '\r\n' if '\r\n' in old_text else '\n'
    assert new_text == old_text.replace(
        old_text[ANCHOR.search(old_text).start():ANCHOR.search(old_text).end()],
        old_text[ANCHOR.search(old_text).start():ANCHOR.search(old_text).end()]
        + u'  "original_room_id": %d,' % rid + eol, 1), u'不是纯粹的加一行'


def main():
    rooms, ch_of = index_rooms()
    files = scene_files()
    print(u'index 可解析房间号 = %d' % len(rooms))
    print(u'独立场景文件      = %d' % len(files))

    snap, todo, skip, noidx = {}, [], [], []
    for fn in files:
        p = os.path.join(SCENES, fn)
        text = rd(p)
        d = json.loads(text)
        sid = d.get('scene_id')
        # 快照：改前的"除 rid 外"指纹 + 行数 + 字节数
        snap[fn] = {
            'scene_id': sid,
            'had_rid': 'original_room_id' in d,
            'rid': d.get('original_room_id'),
            'h_rest': h_rest(d),
            'lines': text.count('\n'),
            'bytes': len(text.encode('utf-8')),
        }
        if 'original_room_id' in d:
            skip.append(fn)
            continue
        if sid not in rooms:
            noidx.append((fn, sid))
            continue
        todo.append((fn, sid, rooms[sid]))

    print(u'已有字段（跳过）  = %d  %s' % (len(skip), skip))
    print(u'待补              = %d' % len(todo))
    print(u'index 里查不到    = %d  %s' % (len(noidx), noidx))

    by_ch = {}
    for _fn, _sid, _rid in todo:
        by_ch[ch_of[_sid]] = by_ch.get(ch_of[_sid], 0) + 1
    for ch in sorted(by_ch):
        print(u'   %s: %d' % (ch, by_ch[ch]))

    if not todo:
        print(u'\n[幂等] 没有要补的，未改动任何文件。')
        return 0

    done = 0
    for fn, sid, rid in todo:
        p = os.path.join(SCENES, fn)
        text = rd(p)
        new = insert_line(text, rid)
        selfcheck(text, new, rid)
        if APPLY:
            tmp = p + '.new'
            wr(tmp, new)
            got = rd(tmp)
            assert got == new, u'往返不一致'
            assert not got.startswith(u'\ufeff'), u'写出了 BOM'
            os.replace(tmp, p)
        done += 1

    if APPLY:
        os.makedirs(EV, exist_ok=True)
        with io.open(SNAP, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(snap, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(u'\n[写入] %d 个文件；改前快照 -> %s' % (done, SNAP))
    else:
        print(u'\n[演练] %d 个文件通过自检（未写盘）。加 --apply 才真写。' % done)
    return 0


if __name__ == '__main__':
    sys.exit(main())
