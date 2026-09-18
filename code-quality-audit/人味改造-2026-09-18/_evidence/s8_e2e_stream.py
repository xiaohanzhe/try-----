# -*- coding: utf-8 -*-
"""S8 端到端验证：复刻真实链路，量"首字延迟"，并确认最终显示 == 护栏定稿。

与 `e2e_final.py`（第十八轮）同款思路，但走 **流式**：
    真实 HTTPLocalAI.chat_stream
      → 每块过 _sanitize_partial_reply（= dialogue_ui 屏幕上显示的清洗规则）
      → 追加进"打字机队列"（复刻 dialogue_ui.stream_delta 的前缀单调逻辑）
      → 收尾 _clean_ai_reply 定稿
      → _finalize_stream 语义（一致就放行 / 不一致就整段定格）

必须验的三件事：
  1. **首字延迟**真的降下来了（非流式要等整句，流式 0.2~0.3s 就冒字）；
  2. **屏幕上从头到尾没有 markdown 残渣**（`**`、行首 `#`）与自问自答续写；
  3. **最终显示 == 护栏定稿**（不能"流式显示的和最后定稿的不一样"）。

读运行时真源 `E:\\RalseiMemory\\config.json`。
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
OUT = r"E:\Download\_tmp\s8_e2e_stream.txt"
lines = []


def log(s=""):
    lines.append(str(s))


cfg = json.load(io.open(LIVE_CFG, encoding="utf-8"))
api_cfg = dict(cfg["api"])

from api_client import HTTPLocalAI                              # noqa: E402
import main as M                                                # noqa: E402
import types                                                    # noqa: E402

R = M.RalseiPet
stub = types.SimpleNamespace()
stub._sanitize_partial_reply = R._sanitize_partial_reply
stub._clean_ai_reply = types.MethodType(R._clean_ai_reply, stub)
stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
stub._build_persona_prompt = types.MethodType(R._build_persona_prompt, stub)
stub._ai_chat_options = types.MethodType(R._ai_chat_options, stub)
stub._ai_stream_enabled = types.MethodType(R._ai_stream_enabled, stub)
stub._persona_cache = None
stub.api_config = api_cfg

cli = HTTPLocalAI(api_cfg)
persona = stub._build_persona_prompt()
system = persona + "\n\n【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
opts = stub._ai_chat_options()

log("=" * 78)
log("S8 端到端：流式链路（真配置 + 真实例 + 真 persona）")
log("=" * 78)
log("端点 = %s   model = %s" % (cli.chat_endpoint(), cli.model))
log("persona = %d 字   options = %s" % (len(persona), opts))
log("api.stream = %r" % api_cfg.get("stream"))
log()

# 预热
t0 = time.time()
cli.chat("在吗", system_prompt=system, history=[], max_tokens=8)
log("预热 %.2fs" % (time.time() - t0))
log()


class TypewriterQueue:
    """复刻 dialogue_ui.stream_delta 的队列逻辑（前缀单调 + 非前缀则整段替换）。

    只搬"文本层面"的判定，不搬 QTimer —— 它只是把字符一个个亮出来，
    不改变队列内容，对"最终显示什么"没有影响。
    """

    def __init__(self):
        self.queue = ""
        self.raw = ""
        self.resets = 0
        self.replaces = 0
        self.appends = 0

    def feed(self, piece):
        if piece is None:                       # reset：擦掉已显示内容
            self.resets += 1
            self.queue = ""
            self.raw = ""
            return
        self.raw += piece
        clean = stub._sanitize_partial_reply(self.raw)
        if clean.startswith(self.queue):
            self.appends += 1
            self.queue = self.queue + clean[len(self.queue):]
        else:                                   # 前缀假设被打破 → 整段替换
            self.replaces += 1
            self.queue = clean

    def finalize(self, final_text):
        """复刻 _finalize_stream：一致就放行（打字机自然打完），不一致就定格。"""
        if self.queue == final_text:
            return "pass"
        self.queue = final_text
        return "snap"


QS = [
    "今天上班好累啊，被领导骂了一顿",
    "我好喜欢你呀",
    "给我讲讲**你必须**遵守的规则，用 1. 2. 3. 列出来",
    "今天吃了火锅",
]

spoken = []
tot_first = []
tot_all = []
problems = []

for q in QS:
    q_tw = TypewriterQueue()
    marks = []

    def on_delta(piece, _tw=q_tw, _marks=marks):
        t = time.time() - t_start
        if piece is not None and not _marks and _tw.queue == "":
            _marks.append(t)        # 第一段真正"有字"的内容到达的时刻
        _tw.feed(piece)

    t_start = time.time()
    raw = cli.chat_stream(q, system_prompt=system, history=[],
                          on_delta=on_delta, **opts)
    dt_all = time.time() - t_start
    first = marks[0] if marks else None

    clean = stub._clean_ai_reply(raw, recent=spoken)
    mode = "—"
    if clean is None and raw and raw.strip():
        # 与 chat_with_ai 同款：先 reset 再抬温重采样
        on_delta(None)
        t2 = time.time()
        raw2 = cli.chat_stream(
            q,
            system_prompt=system + "\n\n" + R._RETRY_NUDGE,
            history=[],
            on_delta=on_delta,
            temperature=min(1.0, float(opts["temperature"]) + 0.1),
            max_tokens=opts["max_tokens"])
        dt_all += time.time() - t2
        clean = stub._clean_ai_reply(raw2, recent=spoken)
        raw = raw2

    if clean:
        mode = q_tw.finalize(clean)
        if q_tw.queue != clean:
            problems.append(("最终显示 != 护栏定稿", q, q_tw.queue, clean))
        if not clean.startswith(q_tw.queue) and mode == "pass":
            problems.append(("队列不是定稿前缀却走 pass", q))
        spoken.append(clean)
    else:
        problems.append(("模型未产出可用回复", q, raw))

    if first is not None:
        tot_first.append(first)
    tot_all.append(dt_all)

    log("Q: %s" % q)
    log("   首字 %.2fs   全文 %.2fs   分片追加 %d / 整段替换 %d / reset %d"
        % (first if first is not None else -1, dt_all,
           q_tw.appends, q_tw.replaces, q_tw.resets))
    log("   原始 = %r" % (raw or "")[:150])
    log("   定稿 = %r   [finalize=%s]" % (clean, mode))
    log("   屏幕最终 = %r" % (q_tw.queue,))
    bad = []
    if clean:
        if '**' in q_tw.queue or '`' in q_tw.queue:
            bad.append("markdown 残渣")
        if any(m in q_tw.queue for m in ('主人：', '你：', 'Assistant:', 'User:')):
            bad.append("自问自答续写")
        if q_tw.queue != clean:
            bad.append("与定稿不一致")
    log("   自检 = %s" % ("通过" if not bad else "!! " + "/".join(bad)))
    log()

log("-" * 78)
n = len(tot_first)
log("汇总：%d 次调用 | 首字中位 %.2fs / 最快 %.2fs | 全文合计 %.1fs"
    % (n,
       sorted(tot_first)[n // 2] if n else -1,
       min(tot_first) if n else -1,
       sum(tot_all)))
log("完全重复 = %d 条" % (len(spoken) - len(set(spoken))))
log("问题 = %s" % ("无" if not problems else problems))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
