# -*- coding: utf-8 -*-
"""第105轮 · 端到端演示：OneShot 现在能「逐门走通」，且有真实理由。

它回答一个问题（也是本轮唯一的用户可见目标）：
    接进 420 条原作传送边之后，宠物在 OneShot 里还能不能像 Deltarune 里那样
    「说一句『去某处』→ 拿出一条可朗读的逐步路线」？

覆盖三件事：
  ① OneShot 章内 18 跳路线（`oneshot.mainline.INIT` → `oneshot.mainline.S1`）
     —— `plan_from_text` 全链（② 定位 → ③ 寻路 → 逐跳 reason → describe_plan）；
  ② 每一步的 `door` / `reason` 都非空（能喂给 AI 说因果）；
  ③ **既有 Deltarune 未受影响** —— 同一门面在 ch1 上仍给 7 跳，且 `kind='delta'`
     的 reason 仍是「走 obj_doorA 出去」原措辞。

★ 本脚本是**演示 / 留痕**，不是回归锁（回归锁是 `check105.py`）。
★ 零外部盘依赖：只读仓库内 `_routes.json` / `_index.json` / `_room_graph.json`。
用法（输出落 `_evidence/e2e105.txt`）：
    C:\\Python311\\python.exe _tools\\demo105_e2e.py > _evidence\\e2e105.txt 2>&1
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')            # 仓库根
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_system as SS          # noqa: E402
import scene_pathfind as SP        # noqa: E402


def _p(label, value):
    print('%s = %r' % (label, value))


def main():
    idx = SS.load_index()
    rg = SP.load_room_graph()
    al = SP.load_aliases()

    print('=' * 72)
    print('① 房间图规模（第105轮把 oneshot 章并了进来）')
    print('=' * 72)
    _p('load_room_graph n_edges', rg.get('n_edges'))
    per = {ch: len(v) for ch, v in (rg.get('edges_by_chapter') or {}).items()}
    _p('逐章边数', per)

    print()
    print('=' * 72)
    print('② OneShot 章内端到端：oneshot.mainline.INIT → oneshot.mainline.S1')
    print('=' * 72)
    plan = SP.plan_from_text(
        'oneshot.mainline.S1',
        idx, rg, al.get('entries') or {},
        current_scene_id='oneshot.mainline.INIT',
    )
    _p('plan ok', plan.get('ok'))
    _p('goal', plan.get('goal'))
    _p('scene_id', plan.get('scene_id'))
    _p('hops', plan.get('hops'))
    _p('error', plan.get('error'))
    print('path =', plan.get('path'))
    for st in plan.get('steps') or []:
        print('   %r' % (st,))

    empty = [i for i, st in enumerate(plan.get('steps') or [])
             if not st.get('door') or not st.get('reason')]
    _p('door/reason 为空的步数', empty)

    print()
    print('--- describe_plan（真正注入给 AI 的那段中文）---')
    print(SP.describe_plan(plan))

    print()
    print('=' * 72)
    print('③ 既有 Deltarune 未受影响（对照）')
    print('=' * 72)
    p2 = SP.plan_from_text('教堂', idx, rg, al.get('entries') or {},
                           current_scene_id='ch1.kris_room.kris_s_room')
    _p('D 端到端 ok', p2.get('ok'))
    _p('D hops', p2.get('hops'))
    _p('D scene_id', p2.get('scene_id'))
    _p('D error', p2.get('error'))
    for st in (p2.get('steps') or [])[:2]:
        print('   前两步 %r' % (st,))
    # 直接问「门位移 vs code201 传送」两种 kind 的措辞是否分得开
    _p("kind='delta' 的 reason 仍是原措辞",
       SP._step_reason({}, {'dst': 3, 'door': 'obj_doorA', 'kind': 'delta'}, [2]))
    _p("kind='oneshot_transfer' 的 reason 走通用分支",
       SP._step_reason({}, {'dst': 3, 'door': 'west_door',
                            'kind': 'oneshot_transfer'}, [2]))

    print()
    print('=' * 72)
    print('④ OneShot 普通房间之间的连通抽样')
    print('=' * 72)
    for src, dst in (('oneshot.mainline.INIT', 'oneshot.mainline.Start'),
                     ('oneshot.glen.Village', 'oneshot.glen.Green'),
                     ('oneshot.glen.Village', 'oneshot.glen.House_3'),
                     ('oneshot.glen.Dock', 'oneshot.glen.Fishing_hut'),
                     ('oneshot.refuge.Hall1', 'oneshot.refuge.Hall2'),
                     ('oneshot.refuge.Cafe', 'oneshot.refuge.Cafe_inside')):
        pl = SP.plan_from_text(dst, idx, rg, al.get('entries') or {},
                               current_scene_id=src)
        print('%-32s -> %-34s ok=%s hops=%s err=%s'
              % (src, dst, pl.get('ok'), pl.get('hops'), pl.get('error')))
        for st in pl.get('steps') or []:
            print('        %s → %s：%s' % (st['from'], st['to'], st['reason']))
    print()
    print('--- 负控制：原作拓扑确实不通的一对，必须**如实**说走不到 ---')
    pl = SP.plan_from_text('oneshot.barrens.Cabin', idx, rg, al.get('entries') or {},
                           current_scene_id='oneshot.barrens.Dormitories')
    print('oneshot.barrens.Dormitories -> oneshot.barrens.Cabin  ok=%s hops=%s err=%s'
          % (pl.get('ok'), pl.get('hops'), pl.get('error')))
    print('  ★ 这不是缺陷：门候选本身不含这条边，判据 D1/D6 也守着'
          '「只由剧情传送支撑的房间不许混进来」。')

    print()
    print('=' * 72)
    print('⑤ 枢纽（原作 warp 房）—— 如实登记，不美化')
    print('=' * 72)
    import collections
    adj = collections.defaultdict(list)
    for e in (rg.get('edges_by_chapter') or {}).get('oneshot') or []:
        adj[e.get('src')].append(e.get('dst'))
    _p('oneshot.mainline.DEBUG 的出边数', len(adj.get(11, [])))
    _p('oneshot.mainline.INIT 的出边数', len(adj.get(1, [])))

    def _reach(start, ban=()):
        seen = {start}
        q = collections.deque([start])
        while q:
            u = q.popleft()
            for v in adj.get(u, []):
                if v in ban or v in seen:
                    continue
                seen.add(v)
                q.append(v)
        return len(seen)

    _p('从 INIT 出发可达房间数（全图）', _reach(1))
    _p('从 INIT 出发可达房间数（禁 DEBUG / IGNORE）', _reach(1, (11, 256)))
    print('  ★ 结论：OneShot 原作自己把 DEBUG 房做成**总枢纽**（64 个 warp），')
    print('    所以「跨区可达」大半经它。这是**原作事实**，不是我们的捷径 ——')
    print('    数据面照抄了 826 条 code-201，一条没加、一条没减。')

    print()
    print('[DONE] 第105轮 OneShot 房间连接 · 端到端演示结束')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'buffer'):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                          errors='replace', newline='')
        except Exception:
            pass
    main()
