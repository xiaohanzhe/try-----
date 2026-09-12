# -*- coding: utf-8 -*-
"""api_client.py 边界修复（第2区块）"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\api_client.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# 1) rebuild() 防御非 dict 配置（create_client 只保证 None，不保证 dict）
patch(
"""    def rebuild(self, config: Dict[str, Any]):
        config = config or {}
        self.config = config""",
"""    def rebuild(self, config: Dict[str, Any]):
        # 修复：config 可能是列表/字符串等非 dict（配置文件被手改），
        # 直接 .get() 会 AttributeError 导致 create_client 崩溃。
        if not isinstance(config, dict):
            config = {}
        self.config = config""")

# 2) chat() 中 history 元素解包防御（畸形条目不应让整次请求失败）
patch(
"""            if isinstance(history, (list, tuple)):
                for _role, _content in history:
                    if _role not in ("user", "assistant"):
                        continue
                    if not isinstance(_content, str) or not _content.strip():
                        continue
                    messages.append({"role": _role, "content": _content})""",
"""            if isinstance(history, (list, tuple)):
                for item in history:
                    # 修复：history 元素可能是非二元组/不可解包对象，原实现
                    # for _role, _content in history 会抛 ValueError/TypeError
                    # 使整次对话失败。畸形条目直接跳过。
                    if not isinstance(item, (list, tuple)) or len(item) != 2:
                        continue
                    _role, _content = item
                    if _role not in ("user", "assistant"):
                        continue
                    if not isinstance(_content, str) or not _content.strip():
                        continue
                    messages.append({"role": _role, "content": _content})""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("api_client.py patched OK")
