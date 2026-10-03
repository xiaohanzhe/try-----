# -*- coding: utf-8 -*-
"""验证 build_targets 吃 NpcRegistry 对象（真机路径）。

★ 判据自证：先用 dict 形状（已知真值）跑一次，再用 NpcRegistry 对象跑一次，
  两次结果必须**逐字相等**（A/B 锚点，防"提取成功≠提取正确"）。
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

from modules import possession as P
from modules import npc_system as N

root = os.path.join(ROOT, 'ralsei_pet')
reg_obj = N.load_registry(root)
print('NpcRegistry 对象:', type(reg_obj).__name__, 'len =', len(reg_obj))

# A: 对象形状（真机）
ta = P.build_targets(reg_obj)
# B: 纯 dict 形状（已知真值，手工构造）
raw = {'npcs': [{'id': n.id, 'name': n.name, 'name_cn': n.name_cn}
                for n in reg_obj.all()]}
tb = P.build_targets(raw)

ka = [(t.npc_id, t.name, t.kind) for t in ta]
kb = [(t.npc_id, t.name, t.kind) for t in tb]
print('对象形状 ->', ka)
print('dict 形状 ->', kb)
print('A == B ?', ka == kb)

# 正控制：必须**非空**（否则"两次都空也相等"= 恒真判据）
print('非空断言 :', len(ka) > 0, '(期望 True)')
# 负控制：喂一个没有 all() 也没 npcs 的东西 ⇒ 必须空
print('负控制(空) :', P.build_targets(object()) == [], '(期望 True)')
# 负控制：唯 id 乱造的 ⇒ 必须空
print('负控制(乱id) :', P.build_targets({'npcs': [{'id': 'not_a_id'}]}) == [], '(期望 True)')

# scene_of 注入仍生效
ts = P.build_targets(reg_obj, scene_of=lambda nid: 'desktop' if nid == 'kris' else None)
got = {t.npc_id: t.scene for t in ts}
print('scene_of 注入:', got.get('kris'), '(期望 desktop)')

print('RESULT', 'PASS' if (ka == kb and len(ka) > 0) else 'FAIL')
