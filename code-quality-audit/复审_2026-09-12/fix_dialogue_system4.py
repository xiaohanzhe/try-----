# -*- coding: utf-8 -*-
"""dialogue_system.py 修复（第4区块补充2）：generate_response 内 '怎么' 分支同样过宽"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\dialogue_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """        elif "帮助" in user_input_lower or "怎么" in user_input_lower or "如何" in user_input_lower:
            response = random.choice(["""
new = """        elif "帮助" in user_input_lower or any(w in user_input_lower for w in
                ["怎么办", "怎么做", "怎么用", "怎么弄", "如何"]):
            # 修复：与 _detect_intent 相同的过宽问题——'怎么' 会让
            # "怎么样/怎么啦" 等口语被误判为求助，答非所问。
            response = random.choice(["""
assert old in src, "old not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("dialogue_system.py help branch patched OK")
