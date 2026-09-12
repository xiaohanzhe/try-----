# -*- coding: utf-8 -*-
"""api_client.py create_client 工厂层防御（第2区块补充）"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\api_client.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """def create_client(config: Optional[Dict[str, Any]]) -> LocalAIBase:
    \"\"\"唯一工厂：拿一个"按配置就绪"的 client。

    - enabled=False              → LocalAIStub（空转）
    - 已 register_provider       → 你的工厂实现
    - 否则                       → HTTPLocalAI（OpenAI 兼容骨架）
    \"\"\"
    config = config or {}"""
new = """def create_client(config: Optional[Dict[str, Any]]) -> LocalAIBase:
    \"\"\"唯一工厂：拿一个"按配置就绪"的 client。

    - enabled=False              → LocalAIStub（空转）
    - 已 register_provider       → 你的工厂实现
    - 否则                       → HTTPLocalAI（OpenAI 兼容骨架）
    \"\"\"
    # 修复：config 可能是列表/字符串等非 dict（配置被手改），
    # 直接 .get('enabled') 会 AttributeError 使 AI 热启用失败。
    if not isinstance(config, dict):
        config = {}"""
assert old in src
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("api_client create_client patched OK")
