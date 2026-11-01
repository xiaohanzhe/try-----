# -*- coding: utf-8 -*-
"""探测人设文件的编码细节：EOL / BOM / 引号码位 / 字节数。只读。"""
import io, os

P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\ralsei_persona.md"
raw = open(P, "rb").read()
t = raw.decode("utf-8")
print("bytes =", len(raw), " chars =", len(t))
print("bom =", raw.startswith(b"\xef\xbb\xbf"), " crlf =", raw.count(b"\r\n"),
      " lf =", raw.count(b"\n"), " fffd =", t.count("\ufffd"))
print("尾部 3 字符 =", repr(t[-3:]))
# 引号码位
for ch in ("\u201c", "\u201d", '"', "\u2014", "-"):
    print("U+%04X %r count=%d" % (ord(ch), ch, t.count(ch)))
# 现有分节标题
print("--- sections ---")
for ln in t.splitlines():
    if ln.startswith("——"):
        print(repr(ln))
