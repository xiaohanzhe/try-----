# -*- coding: utf-8 -*-
"""S8 验证①：真实 HTTPLocalAI.chat_stream 通路 + 首字延迟对照。

与 integration_probe.py 同款环境（真实例 + 运行时真源 config），
但打的是**流式**那条路，量的是"第一个字什么时候到"。
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
OUT = r"E:\Download\_tmp\s8_client_probe.txt"
lines = []


def log(s=""):
    lines.append(str(s))


cfg = json.load(io.open(LIVE_CFG, encoding="utf-8"))
api_cfg = dict(cfg["api"])

from api_client import HTTPLocalAI, LocalAIStub, LocalAIBase   # noqa: E402

cli = HTTPLocalAI(api_cfg)
log("=" * 78)
log("S8 真机探针：HTTPLocalAI.chat_stream")
log("=" * 78)
log("端点 = %s" % cli.chat_endpoint())
log("model = %s  timeout = %s" % (cli.model, cli.timeout))

SYS = ("你是 Ralsei，一只住在电脑桌面上的温柔小羊。说话口语化，1~3 句，不要分点。")
Q = "今天上班好累啊，被领导骂了一顿"
OPTS = {"temperature": 0.85, "max_tokens": 256}


def warm():
    """先热一次：ralsei:v2 冷加载要十几秒，会和真实首字延迟混在一起。"""
    t0 = time.time()
    cli.chat("在吗", system_prompt=SYS, history=[], max_tokens=8)
    return time.time() - t0


log()
log("--- 预热（把模型加载进来，避免冷启动污染计时）---")
log("预热耗时 = %.2fs" % warm())
log()

# ---------------- ① 非流式对照 ----------------
log("--- ① 非流式 chat()（对照）---")
t0 = time.time()
full = cli.chat(Q, system_prompt=SYS, history=[], **OPTS)
dt_chat = time.time() - t0
log("耗时 = %.2fs（首字节 == 全文，用户全程看到「……」）" % dt_chat)
log("文本 = %r" % (full or ""))
log()

# ---------------- ② 流式 ----------------
log("--- ② 流式 chat_stream() ---")
seen = []
t0 = time.time()
first_at = [None]


def on_delta(piece):
    if first_at[0] is None:
        first_at[0] = time.time() - t0
    seen.append(piece)


joined = cli.chat_stream(Q, system_prompt=SYS, history=[], on_delta=on_delta, **OPTS)
dt_stream = time.time() - t0
log("首字延迟 = %s" % ("%.2fs" % first_at[0] if first_at[0] else "N/A"))
log("全文耗时 = %.2fs" % dt_stream)
log("分片数 = %d" % len(seen))
log("累积返回 = %r" % (joined or ""))
log("回调拼接 = %r" % "".join(seen))
log("累积 == 回调拼接 ? %s" % (joined == "".join(seen)))
log()
log(">>> 首字延迟改善：%.2fs -> %s" % (
    dt_chat, ("%.2fs" % first_at[0]) if first_at[0] else "N/A"))

# ---------------- ③ 基类默认实现（不支持流式的 provider 不得被破坏） ----------
log()
log("--- ③ 基类默认 chat_stream（回落 chat + 单次回调）---")


class DummyProvider(LocalAIBase):
    """模拟"用户自己 register_provider 注册的、只有 chat 的实现"。"""

    def chat(self, prompt, system_prompt=None, **kwargs):
        return "我是只实现了 chat 的老实现"

    def get_commands(self, context):
        return None

    def send_status(self, status):
        return None

    def execute_command(self, command):
        return None


d = DummyProvider({"enabled": True})
d_seen = []
d_ret = d.chat_stream("你好", system_prompt="s", on_delta=d_seen.append)
log("返回值 = %r" % d_ret)
log("回调次数 = %d（应为 1：整段作为单分片）" % len(d_seen))
log("未被迫改造 = %s" % (d_ret == "我是只实现了 chat 的老实现" and d_seen == [d_ret]))

stub = LocalAIStub({"enabled": False})
s_seen = []
s_ret = stub.chat_stream("你好", on_delta=s_seen.append)
log("禁用状态下 LocalAIStub.chat_stream = %r，回调 %d 次（应 None / 0）" % (s_ret, len(s_seen)))

# ---------------- ④ on_delta=None 应回落 chat（不走流式） ----------------
log()
log("--- ④ on_delta=None → 回落 chat() ---")
t0 = time.time()
r4 = cli.chat_stream(Q, system_prompt=SYS, history=[], on_delta=None, **OPTS)
log("返回非空 = %s  耗时 %.2fs（与非流式同量级即说明走的是 chat）"
    % (bool(r4), time.time() - t0))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
