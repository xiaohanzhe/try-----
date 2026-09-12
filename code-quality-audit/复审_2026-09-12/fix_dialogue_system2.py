# -*- coding: utf-8 -*-
"""dialogue_system.py 修正缩进（第4区块补充）"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\dialogue_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """            if "？" in user_input or "?" in user_input:
                response = random.choice(self.response_templates["question"])
            else:
                    # 根据Ralsei的性格随机选择回复
                    categories = list(self.response_templates.keys())
                    # 根据性格权重调整选择概率
                    category_weights = {
                        "happy": 2,
                        "caring": 2,
                        "helpful": 2,
                        "supportive": 1.5,
                        "thoughtful": 1.5,
                        "empathetic": 1.5,
                        "curious": 1,
                        "playful": 1,
                        "knowledgeable": 1,
                        "shy": 1,
                        "question": 1,
                        "excited": 0.8,
                        "sad": 0.5,
                    }
                    # 根据权重随机选择
                    weighted_categories = []
                    for category, weight in category_weights.items():
                        weighted_categories.extend([category] * int(weight * 10))
                    category = random.choice(weighted_categories)
                    response = random.choice(self.response_templates[category])
            else:
                # 第一次对话，选择问候或好奇的回复
                response = random.choice(self.greetings)"""

new = """            if "？" in user_input or "?" in user_input:
                response = random.choice(self.response_templates["question"])
            else:
                # 根据Ralsei的性格随机选择回复
                categories = list(self.response_templates.keys())
                # 根据性格权重调整选择概率
                category_weights = {
                    "happy": 2,
                    "caring": 2,
                    "helpful": 2,
                    "supportive": 1.5,
                    "thoughtful": 1.5,
                    "empathetic": 1.5,
                    "curious": 1,
                    "playful": 1,
                    "knowledgeable": 1,
                    "shy": 1,
                    "question": 1,
                    "excited": 0.8,
                    "sad": 0.5,
                }
                # 根据权重随机选择
                weighted_categories = []
                for category, weight in category_weights.items():
                    weighted_categories.extend([category] * int(weight * 10))
                category = random.choice(weighted_categories)
                response = random.choice(self.response_templates[category])"""
assert old in src, "old not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("dialogue_system.py re-patched OK")
