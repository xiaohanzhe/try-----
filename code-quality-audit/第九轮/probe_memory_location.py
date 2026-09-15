# -*- coding: utf-8 -*-
"""真机探测：记忆到底会存在哪儿（只读 + 一次可写性探测，不写记忆内容）。

用法：C:\\Python311\\python.exe probe_memory_location.py
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

print(json.dumps(out, ensure_ascii=False, indent=2))
