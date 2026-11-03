# -*- coding: utf-8 -*-
u"""第150轮 · 破坏性负控制：逐条拆掉"差事"，**指定**判据必须报红。

`check150` 全绿本身证明不了什么 —— 全绿也可能因为判据恒真（第 85/129 轮的教训）。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check150`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|------|----------|
| M1 | `_npc_errand_tick` 挪到 `_npc_roam_tick` **之前** | `F2` |
| M2 | 往 `npc_errand.py` 塞一个 `scene.switch` | `H1` |
| M3 | **删掉** `assign_errand` 里的门控调用 | `F6` `F7` `D1` `D2` |
| M3b | 门控**挪到** `board.assign` **之后** | `F6` `D1` `D2` |
| M4 | 删掉 tick 里的 `board.abort(nid)` | `E7` `F5` |
| M5 | 让 `_npc_errand_load` 改走 `npc_plan_store.load` | `G4` `G9` `G10` |
| M6 | `working_positions()` 把 `traveling` 也算进去 | `A24` `E1` `E2` |
| M7 | `scene_now()` 对 `traveling` 也返目的地 | `A1` `A2` |
| M8 | `same_chapter` 退回逐字相等 | `B3` `B5` `C6` |
| M9 | `_npc_errand_world` 的兜底从 `dark` 改成 `light` | `C1` |
| M10 | `abort` 改成把作废那条塞进 `done` | `A18` `E7` |
| M11 | 已完成留存 FIFO 改 LIFO | `A17` |
| M12 | `NPC_ERRAND_ENABLED` 默认改 `False` | `F4` + E 段大面积 |

## 期望写窄过三次（三次都是**判据对、期望错**）

- **`M4` 多红了 `F5`**：`F5` 断的是"`_npc_errand_tick` 体内七件事齐全"，
  其中一件就是 `abort` ⇒ 把 `abort` 删了，`F5` **当然**该红。
  我第一版按"只有行为判据 `E7` 会红"去写，是忘了自己还写了条结构判据盯着同一件事。
  （这两条**不是复读**：`E7` 断"后果"，`F5` 断"有没有那个调用"，删了/挪了/写歪了才分得开。）
- **`M6` 多红了 `E2`**：`E2` 断的是"到点那一拍 `put` **恰好一次**"。
  路上先被 put 过一次 ⇒ 到点时已经是第 2 次 ⇒ `E2` 红得对。
  顺带说明 `E1` 的单条盲区（见文件头 ③）在这里被 `E2` 补上了。
- **`M7` 多红了 `A2`**：`A2` 断的是"半路一拍（t=5）仍是 `None`" —— 与 `A1`
  同一个性质、**不同时间点**。`scene_now()` 一改，两条都塌 ⇒ 一起红。

⇒ 三次都不是"多了一条无关的红"，而是**同一个性质的第二处观测点**。
登记在这里，下次别再把它当判据坏了。

## 三处"红得这么多是应该的"（省得以后误当判据坏了）

**① `M3` 与 `M3b` 的区别是刻意的 —— 它们证明 `F6`/`F7` 断的不是同一件事。**
`M3` 把门控**删掉** ⇒ `F7`（"调用点精确三处"）红；`M3b` 把门控**挪到 assign 之后**
⇒ `F7` 仍绿、`F6`（顺序）红。两条变异合起来才说明：`F6` 抓的是"顺序"，
`F7` 抓的是"处数"，不是同一个信号的两种说法。

**② `M5` 连带 `G9`/`G10` 红，正是 `G4` 存在的理由。**
`npc_plan_store.load()` 走 `Book.from_dict`，它只认 `schema_version == 1`
⇒ 差事档被整本判成"版本不符"，读回来是**空看板**。`G4` 只是"别这么写"，
`G9`/`G10` 才是"这么写会怎样" —— 两条都得有。

**③ `M12` 红一片是**对的**：总开关就是根。**
`E2`~`E8` 全红是因为它们断的是"差事真的被推进了"；根一断，它们当然都不成立。
唯一**没**红的是 `E1` —— 因为它断的是"这一拍**什么都没发生**"（`puts == []`），
而"整个功能关掉"恰好也满足它。这是 `E1` 结构性的盲区（**只靠它一条就是恒真**），
所以它旁边必须有 `E2` 这个正控制。**承认盲区，别假装覆盖到了。**
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
ERRAND = os.path.join(PKG, 'modules', 'npc_errand.py')
NPC_SYS = os.path.join(PKG, 'modules', 'npc_system.py')
CHECK150 = os.path.join(HERE, 'check150.py')
PY = u'C:\\Python311\\python.exe'

_n_ok = 0
_n_bad = 0
_failed = []


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def _read(p):
    # ★ 字节忠实：`newline=''` 保住 CRLF，否则还原时整份文件的 EOL 都被改写
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


#: 开工前的字节指纹。Z2 拿它当对照 —— 不许写成"再读一遍跟自己比"（恒真）。
_SHA0 = ((MAIN, _sha1(MAIN)), (ERRAND, _sha1(ERRAND)), (NPC_SYS, _sha1(NPC_SYS)))


def _run150():
    u"""跑 `check150`，返回 (变红的判据编号集合, 退出码, 原始输出)。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK150], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    txt = out.decode('utf-8', 'replace')
    toks = set()
    for line in txt.splitlines():
        if not line.startswith(u'[FAIL] '):
            continue
        toks.add(line[len(u'[FAIL] '):].split(u' ')[0])
    return toks, p.returncode, txt


def mutate(tag, path, pairs, expect):
    u"""按 `pairs` 改 → 跑 → 断言恰好 `expect` 变红 → 按字节还原。"""
    src = _read(path)
    bad = [(o, src.count(o)) for o, _n in pairs if src.count(o) != 1]
    if bad:
        check(u'%s 每处锚点都唯一' % tag, False,
              u'；'.join(u'%r 出现 %d 次' % (o[:30], c) for o, c in bad))
        return
    sha0 = _sha1(path)
    try:
        new_src = src
        for o, n in pairs:
            new_src = new_src.replace(o, n, 1)
        if new_src == src:
            check(u'%s 破坏确实改动了源码' % tag, False, u'替换后与原文相同')
            return
        _write(path, new_src)
        got, rc, txt = _run150()
        ok = (got == set(expect)) and rc != 0
        check(u'%s 破坏后**恰好** %s 变红' % (tag, u'+'.join(expect)),
              ok, u'实得 %s' % (u'+'.join(sorted(got)) or u'（无）'))
        if not ok:
            for line in txt.splitlines():
                if line.startswith(u'[FAIL] '):
                    print(u'        %s' % line)
    finally:
        _write(path, src)
        check(u'%s 已按字节还原（sha1 一致）' % tag, _sha1(path) == sha0)


print(u'=' * 78)
print(u'M 破坏性负控制（每处都断言**恰好**指定的判据变红）')
print(u'=' * 78)

# M1 顺序颠倒：差事先推，随后 `npc_roam` 又把人摇走 ⇒ "派他出门" 偶发失效
mutate(u'M1', MAIN,
       [(u'        self._npc_errand_tick(current_time)\r\n', u''),
        (u'        self._npc_roam_tick(current_time)\r\n',
         u'        self._npc_errand_tick(current_time)\r\n'
         u'        self._npc_roam_tick(current_time)\r\n')],
       [u'F2'])

# M2 机制层偷偷碰显示（H1 是结构判据，只能靠"塞进去必须红"来证伪）
_src_err = _read(ERRAND)
mutate(u'M2', ERRAND,
       [(_src_err,
         _src_err + u'\ndef _display_leak(self):\n    self.scene.switch("x")\n')],
       [u'H1'])

# M3 门控**被删**（不是挪）：去别的世界变成特权
_GATE_BLOCK = (
    u'        ok, why = self._npc_errand_gate(npc_id, dest_scene)\r\n'
    u'        if not ok:\r\n'
    u"            _log.info('差事被门控拒绝：%s → %s（%s）', npc_id, dest_scene, why)\r\n"
    u'            self._npc_errand_note(npc_id,\r\n'
    u"                                  '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))\r\n"
    u'            return None\r\n'
)
mutate(u'M3', MAIN,
       [(_GATE_BLOCK, u"        ok, why = True, ''\r\n")],
       [u'F6', u'F7', u'D1', u'D2'])

# M3b 门控**挪到** assign 之后：仍然判，但已经派出去了（F7 绿、F6 红 ⇒ 见文件头 ①）
mutate(u'M3b', MAIN,
       [(_GATE_BLOCK, u''),
        (u'            return board.assign(now, npc_id, dest_scene, what, **kw)\r\n',
         u'            _r0 = board.assign(now, npc_id, dest_scene, what, **kw)\r\n'
         u'            self._npc_errand_gate(npc_id, dest_scene)\r\n'
         u'            return _r0\r\n')],
       [u'F6', u'D1', u'D2'])

# M4 门控拦下时只"跳过这一拍"，不作废 ⇒ 差事永远留在表里，人被困在进不去的场景
mutate(u'M4', MAIN,
       [(u'                    board.abort(nid)\r\n', u'')],
       [u'E7', u'F5'])

# M5 读走 `npc_plan_store.load()`（它只认 schema_version == 1 ⇒ 整本判版本不符）
mutate(u'M5', MAIN,
       [(u'                raw = json.load(fh)\r\n',
         u'                raw = json.load(fh)\r\n'
         u'            raw = npc_plan_store_mod.load(path).to_dict()\r\n')],
       [u'G4', u'G9', u'G10'])

# M6 `working_positions()` 把路上的人也算 ⇒ 出门变瞬移
mutate(u'M6', ERRAND,
       [(u'        return [(e.npc_id, e.dest_scene) for e in self._active.values()\r\n'
         u'                if e.status == WORKING]\r\n',
         u'        return [(e.npc_id, e.dest_scene) for e in self._active.values()]\r\n')],
       [u'A24', u'E1', u'E2'])

# M7 `scene_now()` 对路上的人也返目的地（`None` 这个"明确交接"没了）
mutate(u'M7', ERRAND,
       [(u'        return self.dest_scene if self.status in (WORKING, DONE) else None\r\n',
         u'        return self.dest_scene\r\n')],
       [u'A1', u'A2'])

# M8 章名归一退回逐字相等 ⇒ 29 位 UT/UTY 角色被关在自己家门外
mutate(u'M8', NPC_SYS,
       [(u'    return bool(chapter_names(ch) & chapter_names(name))\r\n',
         u'    return ch == name\r\n')],
       [u'B3', u'B5', u'C6'])

# M9 兜底从"判不出 ⇒ 不许去"翻成"判不出 ⇒ 当光世界放行"
mutate(u'M9', MAIN,
       [(u"            _log.debug('差事目的地世界判定失败（按暗世界处理）: %s', e)\r\n"
         u'        return npc_system_mod.WORLD_DARK\r\n',
         u"            _log.debug('差事目的地世界判定失败（按暗世界处理）: %s', e)\r\n"
         u'        return npc_system_mod.WORLD_LIGHT\r\n')],
       [u'C1'])

# M10 作废被当成办完（两种收尾混了）
mutate(u'M10', ERRAND,
       [(u'        return self._active.pop(npc_id, None)\r\n',
         u'        _e = self._active.pop(npc_id, None)\r\n'
         u'        if _e is not None:\r\n'
         u'            self.done[npc_id] = _e\r\n'
         u'        return _e\r\n')],
       [u'A18', u'E7'])

# M11 已完成留存 FIFO → LIFO（丢最新的，留下最老的）
mutate(u'M11', ERRAND,
       [(u'            self.done.popitem(last=False)\r\n',
         u'            self.done.popitem(last=True)\r\n')],
       [u'A17'])

# M12 总开关默认关（根一断，行为判据全红 —— 见文件头 ③）
mutate(u'M12', MAIN,
       [(u'    NPC_ERRAND_ENABLED = True\r\n',
         u'    NPC_ERRAND_ENABLED = False\r\n')],
       [u'F4', u'E2', u'E3', u'E4', u'E5', u'E6', u'E7', u'E8'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run150()
check(u'Z1 收口全绿（FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))
check(u'Z2 三个被改过的文件都已按字节还原（与**开工前**指纹一致）',
      all(_sha1(p) == s for p, s in _SHA0),
      u'%s' % ([(os.path.basename(p), _sha1(p) == s) for p, s in _SHA0],))

print(u'')
print(u'=' * 78)
print(u'mutate150：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
