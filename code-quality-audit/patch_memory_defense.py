# -*- coding: utf-8 -*-
"""修补 memory_system.get_associated_memories 对非字符串 content 的防御（保留 CRLF）"""
import io

p = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\memory_system.py"
with io.open(p, "r", encoding="utf-8", newline="") as f:
    src = f.read()

NL = "\r\n"

old = (
    "            mem_content = memory['content'].lower()" + NL
)
new = (
    "            _raw_c = memory.get('content', '')" + NL
    + "            mem_content = _raw_c.lower() if isinstance(_raw_c, str) else str(_raw_c)" + NL
)
assert src.count(old) == 1, "old count=%d" % src.count(old)
src = src.replace(old, new)

with io.open(p, "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("PATCH OK")
