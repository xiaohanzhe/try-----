# -*- coding: utf-8 -*-
"""真机探测：记忆到底会存在哪儿（只读 + 一次可写性探测，不写记忆内容）。

用法：
  C:\\Python311\\python.exe probe_memory_location.py              # 只读探测
  C:\\Python311\\python.exe probe_memory_location.py --write-test # 真的写一次再复原
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import memory_store as S     # noqa: E402

out = {}
out['drives'] = []
for root in S.list_drive_roots():
    out['drives'].append({'root': root, 'label': S._volume_label(root)})
out['describe'] = S.describe()
d, on_device, device_dir = S.default_memory_dir()
out['resolved_dir'] = d
out['resolved_on_device'] = on_device
out['resolved_device_dir'] = device_dir
out['memory_file'] = S.memory_file_in(d)
out['file_exists_now'] = os.path.exists(out['memory_file'])
out['desktop_fallback'] = S.fallback_dir()

if '--write-test' in sys.argv:
    from memory_system import MemorySystem

    class _P(object):
        pass

    ms = MemorySystem(_P())
    out['write_test'] = {}
    out['write_test']['dir'] = ms.memory_dir
    out['write_test']['on_device'] = ms._on_device
    ms.add_fragment('这是一条验证写入的临时片段（随后会被清掉）', who='user')
    ms.remember_key('probe', '写入自检留痕（随后会被清掉）')
    ms.save_memory()
    out['write_test']['file_written'] = os.path.exists(ms.memory_file)
    out['write_test']['stats'] = ms.get_memory_stats()
    try:
        with open(ms.memory_file, encoding='utf-8') as fh:
            raw = json.load(fh)
        out['write_test']['schema'] = raw.get('schema')
        out['write_test']['storage_kind'] = raw.get('storage_kind')
        out['write_test']['fragments_in_file'] = len(raw.get('fragments') or [])
        out['write_test']['keys_in_file'] = len(raw.get('keys') or [])
    except Exception as e:
        out['write_test']['read_back_error'] = str(e)
    # 复原：清掉刚才的测试数据，不污染主人的真记忆
    ms.reset_all()
    out['write_test']['file_after_reset'] = os.path.exists(ms.memory_file)

print(json.dumps(out, ensure_ascii=False, indent=2))

