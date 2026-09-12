# -*- coding: utf-8 -*-
"""dialogue_system.py 修复（第4区块）：问号判断分支恒不可达"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\dialogue_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """        else:
            # 更智能的随机回复选择
            # 根据对话历史选择合适的回复类型
            if len(self.dialogue_history) > 0:
                # 如果上一条是用户的问题，选择问题类型的回复
                last_speaker, last_message = self.dialogue_history[-1]
                if last_speaker == "user" and ("？" in last_message or "?" in last_message):
                    response = random.choice(self.response_templates["question"])
                else:"""

new = """        else:
            # 更智能的随机回复选择
            # 根据对话历史选择合适的回复类型
            # 修复：dialogue_history 每次追加顺序固定为 (user, ralsei)，
            # [-1] 恒为 Ralsei 自己的回复 → "上一条是用户的问题"分支永远
            # 不可达，用户问什么都不会得到问题类回复。直接判断当前输入
            # 是否带问号（语义正确且不受历史结构影响）。
            if "？" in user_input or "?" in user_input:
                response = random.choice(self.response_templates["question"])
            else:"""
assert old in src, "old not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("dialogue_system.py patched OK")
