# -*- coding: utf-8 -*-
"""dialogue_system.py 修复（第4区块补充）：'怎么' 过宽导致"怎么样"误判为求助"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\dialogue_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """        elif any(word in user_input_lower for word in ['帮助', '怎么', '如何']):
            return "help_request\""""
new = """        elif any(word in user_input_lower for word in ['帮助', '怎么办', '怎么做', '怎么用', '怎么弄', '如何']):
            # 修复：原关键词 '怎么' 太宽泛，"怎么样/怎么啦/怎么不睡"等口语
            # 全被误判为求助 → 用户问"你今天过得怎么样？"会得到
            # "我很乐意伸出援手！" 这类答非所问的回复。收敛为明确的求助表达。
            return "help_request\""""
assert old in src, "old not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("dialogue_system.py help_request patched OK")
