# -*- coding: utf-8 -*-
"""修正：get_all_visible_windows 首次调用也返回深拷贝（防止本体引用外泄污染缓存）"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\desktop_interaction.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """        if use_cache:
            self._visible_windows_cache = (time.time(), visible_windows)
        return visible_windows"""
new = """        if use_cache:
            self._visible_windows_cache = (time.time(), visible_windows)
            # 修复：首次调用若返回本体，调用方修改会直接污染缓存内容；
            # 统一返回深拷贝，缓存内对象永不外泄。
            return copy.deepcopy(visible_windows)
        return visible_windows"""
assert old in src, "old not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("desktop_interaction.py fixed (first-call deepcopy)")
