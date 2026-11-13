# -*- coding: utf-8 -*-
u"""第186轮 · 变异测试：**每一条判据都得能被拆红**。

做法：逐条把"本轮真做的那件事"破坏掉（改数据 / 改产品代码），跑 `check186`，
要求它 **FAIL > 0**；然后**立即恢复**。全部恢复后再跑一遍，要求回到 0 FAIL
（证明恢复是干净的 —— 这是第 164 轮起的老规矩：恢复不干净会让后面的变异全部失真）。

★ 破坏性脚本的两条铁律（第 180 轮）：
  ① **幂等**：启动时先把所有目标文件按"备份 → 比对"恢复一遍（上一轮中途崩了也能自愈）；
  ② **备份不落工作区**：`D:\\_tmp186\\mut_bak186\\`，别让 `git add -A` 把备份记成新增文件。
"""
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
MODS = os.path.join(PET, 'modules')
MAINPY = os.path.join(PET, 'src', 'main.py')
CTRLPY = os.path.join(MODS, 'scene_controller.py')
ITEMPY = os.path.join(MODS, 'item_interact.py')
CHECK = os.path.join(HERE, 'check186.py')
BAK = r'D:\_tmp186\mut_bak186'

P_ROUTES = os.path.join(SCENES, '_routes.json')
P_INDEX = os.path.join(SCENES, '_index.json')
P_ZH = os.path.join(SCENES, '_zone.ch1.hometown.json')

sys.path.insert(0, HERE)
import apply186 as A                                  # noqa: E402

FMT = {
    P_ROUTES: (False, 2, False),
    P_INDEX: (False, 2, True),
    P_ZH: (True, 1, True),
}

TARGETS = [P_ROUTES, P_INDEX, P_ZH, ITEMPY, MAINPY, CTRLPY]

MAZE = u'ch1.forest.forest_maze_susie'
ELEV = u'ch1.card_castle.cc_prisonelevator'
CHASE2 = u'ch1.dark_world.dark_chase2'
ALPHYS = u'ch1.hometown.alphysclass'
FOUNTAIN = u'ch1.card_castle.cc_fountain'
NEW = u'ch1.hometown.school_unusedroom'
BEFORE_MAZE = u'ch1.forest.forest_before_maze'
CASTLE1F = u'ch1.card_castle.card_castle_1f'
CASTLE5F = u'ch1.card_castle.card_castle_5f'
PRISON = u'ch1.card_castle.card_castle_prison'


# ------------------------------------------------------------------ 备份/恢复
def _bak_path(p):
    return os.path.join(BAK, os.path.basename(p) + '.bak')


def backup_all():
    os.makedirs(BAK, exist_ok=True)
    for p in TARGETS:
        shutil.copyfile(p, _bak_path(p))


def restore_all():
    n = 0
    for p in TARGETS:
        b = _bak_path(p)
        if not os.path.isfile(b):
            raise SystemExit(u'缺备份 %s —— 拒绝在"不知道原样"的情况下继续' % b)
        cur = io.open(p, 'rb').read()
        if cur != io.open(b, 'rb').read():
            shutil.copyfile(b, p)
            n += 1
    return n


# -------------------------------------------------------------------- 变异器
def _jload(p):
    return json.loads(io.open(p, 'rb').read().decode('utf-8'))


def _jwrite(p, obj):
    trail, ind, inl = FMT[p]
    blob = A.dump(obj, trail, ind, inl)
    io.open(p, 'wb').write(blob)


def m_drop_edge(spec):
    def f():
        d = _jload(P_ROUTES)
        keep = []
        for r in d['routes']:
            if all(r.get(k) == v for k, v in spec.items()):
                continue
            keep.append(r)
        assert len(keep) == len(d['routes']) - 1, '删除点没命中唯一一条'
        d['routes'] = keep
        _jwrite(P_ROUTES, d)
    return f


def m_set_field(match, field, value):
    def f():
        d = _jload(P_ROUTES)
        hit = 0
        for r in d['routes']:
            if all(r.get(k) == v for k, v in match.items()):
                r[field] = value
                hit += 1
        assert hit == 1, '改写点命中 %d 条（应为 1）' % hit
        _jwrite(P_ROUTES, d)
    return f


def m_set_orig(match, key, value):
    def f():
        d = _jload(P_ROUTES)
        hit = 0
        for r in d['routes']:
            if all(r.get(k) == v for k, v in match.items()):
                r.setdefault('_original', {})[key] = value
                hit += 1
        assert hit == 1, '改写点命中 %d 条' % hit
        _jwrite(P_ROUTES, d)
    return f


def m_del_scene():
    def f():
        d = _jload(P_INDEX)
        sc = d['chapters']['ch1']['areas']['hometown']['scenes']
        assert NEW in sc, '新场景不在索引里'
        sc.pop(NEW)
        _jwrite(P_INDEX, d)
    return f


def m_del_obj(scene_id, src):
    def f():
        d = _jload(P_ZH)
        objs = d['scenes'][scene_id]['objects']
        n0 = len(objs)
        d['scenes'][scene_id]['objects'] = [o for o in objs if o.get('src') != src]
        assert len(d['scenes'][scene_id]['objects']) == n0 - 1, '物件没删掉'
        _jwrite(P_ZH, d)
    return f


def m_move_obj(scene_id, src, pos):
    def f():
        d = _jload(P_ZH)
        hit = 0
        for o in d['scenes'][scene_id]['objects']:
            if o.get('src') == src:
                o['pos'] = pos
                hit += 1
        assert hit == 1, '物件命中 %d 个' % hit
        _jwrite(P_ZH, d)
    return f


def m_text(path, old, new):
    def f():
        s = io.open(path, 'rb').read().decode('utf-8')
        # ★★★ 第186轮：产品源码是 **CRLF**（`main.py` 实测 20,478 个 `\r\n`），
        #   而变异锚点按 LF 写 ⇒ 多行锚点 `count()` **恒为 0**，M12 首次跑就崩在
        #   "锚点出现 0 次"。单行锚点（M05）不受影响，所以前面 11 个全绿 —— 这正是
        #   "判据/夹具的坑只在特定形状上暴露"的典型。
        #   ★ 处置：**只把锚点归一成文件自身的 EOL**，绝不把整文件换成 LF
        #     （那会破坏原 EOL，记忆铁律）。单行锚点经两步 replace 后 == 原样。
        o, nw = old, new
        if '\r\n' in s:
            o = o.replace('\r\n', '\n').replace('\n', '\r\n')
            nw = nw.replace('\r\n', '\n').replace('\n', '\r\n')
        n = s.count(o)
        assert n == 1, '锚点出现 %d 次（应为 1）：%r' % (n, o[:60])
        io.open(path, 'wb').write(s.replace(o, nw, 1).encode('utf-8'))
    return f


CASES = [
    ('M01 删掉 maze_susie 下门那条边',
     m_drop_edge(dict(when_scene=MAZE, to=BEFORE_MAZE))),
    ('M02 把 maze_susie 下门坐标 665 改成 1（坐标错则落不到 savepoint）',
     m_set_orig(dict(when_scene=MAZE, to=BEFORE_MAZE), 'door_y', 1)),
    ('M03 把电梯"来路=一层"那条的 when_prev 改成五层',
     m_set_field(dict(when_scene=ELEV, to=CASTLE1F, when_prev=CASTLE1F),
                 'when_prev', CASTLE5F)),
    ('M04 删掉电梯默认支（flag 缺省 0 那条）',
     m_drop_edge(dict(when_scene=ELEV, to=PRISON))),
    ('M05 拆掉 `_prev_ok` 的"不相等就拒"（一律放行）',
     m_text(ITEMPY,
            "        return want == '*' or want == prev",
            "        return True")),
    ('M06 把 dark_chase2 的目标改成 chase1',
     m_set_field(dict(when_scene=CHASE2), 'to', u'ch1.dark_world.dark_chase1')),
    ('M07 删掉 alphysclass 那扇运行时 B 门物件',
     m_del_obj(ALPHYS, 'obj_doorB')),
    ('M08 把 alphysclass 的 B 门改成回自己（自环）',
     m_set_field(dict(when_scene=ALPHYS), 'to', ALPHYS)),
    ('M09 把 cc_fountain 的落点改成城堡镇（产品的通用泉目标）',
     m_set_field(dict(when_scene=FOUNTAIN), 'to', u'ch1.castle_town.castle_town')),
    ('M10 删掉 `_index.json` 里的新场景登记',
     m_del_scene()),
    ('M11 把新场景 D 门坐标挪走',
     m_move_obj(NEW, 'obj_doorD', [999, 999])),
    ('M12 删掉 main.py 里 `self._scene_prev` 的预声明',
     m_text(MAINPY,
            "        self._scene_prev = None                     # 上一个场景 id（换场景时由 switch 记）\n",
            "")),
    ('M13 删掉 `_rebuild_item_props` 传的 `prev=`',
     m_text(MAINPY,
            "                prev=self.__dict__.get('_scene_prev'),\n",
            "")),
    ('M14 删掉 `switch` 里写 `_scene_prev` 那两行',
     m_text(CTRLPY,
            "            _prev = pet.__dict__.get('current_scene')\n"
            "            if isinstance(_prev, str) and _prev and _prev != scene_id:\n"
            "                pet._scene_prev = _prev\n",
            "")),
]


def run_check():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, CHECK], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env, cwd=REPO)
    out = p.stdout.decode('utf-8', 'replace')
    fails = out.count('[FAIL]')
    return p.returncode, fails, out


def main():
    # ★★★ 顺序是命门（第180轮"破坏性脚本必幂等"铁律）：**先恢复、后备份**。
    #   反过来写 = 崩过一次之后，`backup_all()` 把"已被改坏的现状"当成"原样"存进
    #   备份 ⇒ 后面的 `restore_all()` 全是空转，14 个变异全在错的基准上跑（假绿）。
    #   本脚本第一版就是 `backup_all(); restore_all()`，看着像自愈，实则只自愈一次。
    if all(os.path.isfile(_bak_path(p)) for p in TARGETS):
        n = restore_all()
        print(u'[0] 起手恢复 %d 个文件（幂等自愈：用上次的干净备份盖回现状）' % n)
    else:
        print(u'[0] 无完整既有备份 ⇒ 首次运行，直接取现状做备份')
    backup_all()

    rc, fails, out = run_check()
    print(u'[1] 基准：rc=%d FAIL=%d' % (rc, fails))
    if rc != 0 or fails:
        print(out[-3000:])
        raise SystemExit(u'基准就不绿 —— ★ 若这发生在"恢复"之后，说明**备份本身已被污染**'
                         u'（把改坏的现状当原样存了）：先删 %s 再跑，别在这儿硬修' % BAK)

    bad = []
    for name, fn in CASES:
        try:
            restore_all()
            fn()
            rc, fails, out = run_check()
            ok = (rc != 0 and fails > 0)
            print(u'  %-56s %s  rc=%d FAIL=%d'
                  % (name, u'报红 OK' if ok else u'★没报红', rc, fails))
            if not ok:
                bad.append(name)
                print(out[-1500:])
        finally:
            restore_all()

    rc, fails, out = run_check()
    print(u'[3] 恢复后：rc=%d FAIL=%d' % (rc, fails))
    if rc != 0 or fails:
        print(out[-2000:])
        raise SystemExit(u'恢复不干净 —— 后面的变异结果都不可信')

    print(u'')
    print(u'合计：%d 个变异，报红 %d，漏网 %d'
          % (len(CASES), len(CASES) - len(bad), len(bad)))
    if bad:
        print(u'★ 漏网：')
        for b in bad:
            print(u'   %s' % b)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
