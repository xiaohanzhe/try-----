# -*- coding: utf-8 -*-
"""列出 OneShot 的 facepics / npc / pictures，得到角色与道具素材清单。"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

C = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\OneShot.World.Machine.Edition.Build.16512634\content'

for sub in ('facepics', 'npc'):
    d = os.path.join(C, sub)
    if not os.path.isdir(d):
        print('[%s] 不存在' % sub)
        continue
    fs = sorted(os.listdir(d))
    stems = sorted({os.path.splitext(f)[0] for f in fs})
    print('=' * 78)
    print('[%s] %d 个文件 / %d 个不同名' % (sub, len(fs), len(stems)))
    # 按"主名"（去掉 _xxx 变体后缀）归并
    base = {}
    for s in stems:
        k = s.split('_')[0]
        base.setdefault(k, []).append(s)
    print('  主名 %d 个：' % len(base))
    for k in sorted(base):
        vs = base[k]
        print('    %-22s %s' % (k, ('(%d 变体)' % len(vs)) if len(vs) > 1
                                else vs[0]))

print()
print('=' * 78)
for sub in ('pictures', 'panoramas', 'item_icons'):
    d = os.path.join(C, sub)
    if os.path.isdir(d):
        fs = sorted(os.listdir(d))
        print('[%s] %d 个' % (sub, len(fs)))
        print('   ', ', '.join(os.path.splitext(f)[0] for f in fs[:60])
              + (' ...' if len(fs) > 60 else ''))
        print()
