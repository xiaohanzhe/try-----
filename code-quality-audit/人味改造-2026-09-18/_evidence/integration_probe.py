# -*- coding: utf-8 -*-
"""第十八轮 · 真机「真实 api_client」集成探针（不是裸 HTTP）。

为什么必须单独跑这一条：本轮的核心主张是"**接线**修对了"。前面 `e2e_final.py` 用的是
裸 `urllib` 自己拼 `/v1/chat/completions`，它证明了"提示词+护栏有效"，
但**没有经过产品真正用的那条路**（`modules/api_client.py::HTTPLocalAI.chat`）。
本项目最贵的坑就是"改了 A 却没接线到 B"（已第 3 次），所以这里用
**真实配置 + 真实 HTTPLocalAI 实例 + 真实 persona 文件**打一发，
把 `base_url / api_version / model / payload / 响应解析` 全串起来。

读的是运行时真源 `E:\\RalseiMemory\\config.json`（仓库里那份只是默认模板）。
"""
import io
import json
import os
import sys
import time

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for _p in (PET, os.path.join(PET, "src"), os.path.join(PET, "modules")):
    if _p not in sys.path:
        sys.path.append(_p)

LIVE_CFG = r"E:\RalseiMemory\config.json"
OUT = r"E:\Download\_tmp\integration_probe.txt"
lines = []


def log(s=""):
    lines.append(str(s))


cfg = json.load(io.open(LIVE_CFG, encoding="utf-8"))
api_cfg = dict(cfg["api"])
log("=" * 76)
log("真实 api_client 集成探针")
log("=" * 76)
log("配置源 = %s" % LIVE_CFG)
log("api 节 = %s" % json.dumps(
    {k: v for k, v in api_cfg.items() if k != "api_key"}, ensure_ascii=False))
log()

from api_client import HTTPLocalAI                       # noqa: E402
import main as M                                          # noqa: E402

cli = HTTPLocalAI(api_cfg)
log("实例化：enabled=%s  base_url=%s  api_version=%s  model=%s"
    % (cli.enabled, cli.base_url, cli.api_version, cli.model))
log("chat 端点 = %s" % cli.chat_endpoint())
log()

# 与 chat_with_ai 完全一致的取值路径
import types                                              # noqa: E402
stub = types.SimpleNamespace()
for name in ("_build_persona_prompt", "_ai_chat_options", "_clean_ai_reply",
             "_is_repeat_of_recent"):
    setattr(stub, name, types.MethodType(getattr(M.RalseiPet, name), stub))
stub._persona_cache = None
stub.api_config = api_cfg

persona = stub._build_persona_prompt()
opts = stub._ai_chat_options()
log("persona 读到的文件内容 = %d 字" % len(persona))
log("_ai_chat_options() = %s   ← 必须来自 config 的 api.options，不是硬编码缺省" % opts)
log()

CTX = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
system = persona + "\n\n" + CTX
spoken = []
for q in ["今天上班好累啊，被领导骂了一顿", "我好喜欢你呀", "今天吃了火锅"]:
    t0 = time.time()
    raw = cli.chat(q, system_prompt=system, history=[], **opts)
    dt = time.time() - t0
    cleaned = stub._clean_ai_reply(raw, recent=spoken)
    if cleaned is None and raw and raw.strip():
        log("  （护栏判退 → 走重采样，与 chat_with_ai 同款）")
        t0 = time.time()
        raw2 = cli.chat(q, system_prompt=system + "\n\n" + M.RalseiPet._RETRY_NUDGE,
                        history=[], temperature=min(1.0, float(opts["temperature"]) + 0.1),
                        max_tokens=opts["max_tokens"])
        dt += time.time() - t0
        cleaned = stub._clean_ai_reply(raw2, recent=spoken)
    if cleaned:
        spoken.append(cleaned)
    log("Q: %s" % q)
    log("   原始 = %r" % (raw or "")[:120])
    log("   采用 = %r   （%.1fs）" % (cleaned, dt))
    log()
log("产出 %d 条，完重 %d 条" % (len(spoken), len(spoken) - len(set(spoken))))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
