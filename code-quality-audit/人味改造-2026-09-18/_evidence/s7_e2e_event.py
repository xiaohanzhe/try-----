# -*- coding: utf-8 -*-
"""S7 端到端验证：事件台词走 AI 之后，延迟 / 变化度 / 长度合规到底如何。

两段：
  P1 **纯链路**（复刻真实调用顺序，量数值）：
       真实 build_prompt → 真实 HTTPLocalAI.chat → 真实 _clean_ai_reply（护栏）
         → 真实 first_sentence（S7 的截断）→ 与罐头基线对照
     量的东西：每个事件从发起到"屏幕上出现第一句话"的耗时、8 次事件里有没有重样、
     长度是否守 EVENT_MAX_CHARS、markdown 残渣。
  P2 **真对象**（真的 `RalseiPet()`，验"接线到 B"）：
     在真窗口上直接调 `speak_event`，确认台词真的落进 dialogue_ui
     （AI 关：走罐头；AI 开：走模型）。这是"函数写对了 ≠ 产品用上了"的独立验收项。

读运行时真源 `E:\\RalseiMemory\\config.json`。输出自写 UTF-8（不经 PowerShell 管道）。
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
# 证据落仓库（项目内产物留项目目录）；临时中间件才放 E:\Download\_tmp
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s7_e2e_event.txt")
lines = []


def log(s=""):
    lines.append(str(s))


cfg = json.load(io.open(LIVE_CFG, encoding="utf-8"))
api_cfg = dict(cfg["api"])

import types                                                     # noqa: E402
from api_client import HTTPLocalAI                               # noqa: E402
import main as M                                                 # noqa: E402
from event_speech import (EVENT_MAX_CHARS, build_prompt, first_sentence,  # noqa: E402
                          tier_of, TIER_AI)

R = M.RalseiPet
stub = types.SimpleNamespace()
stub._clean_ai_reply = types.MethodType(R._clean_ai_reply, stub)
stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
stub._build_persona_prompt = types.MethodType(R._build_persona_prompt, stub)
stub._ai_chat_options = types.MethodType(R._ai_chat_options, stub)
stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
stub._persona_cache = None
stub.api_config = api_cfg

cli = HTTPLocalAI(api_cfg)
persona = stub._build_persona_prompt()
CONTEXT = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
system = persona + "\n\n" + CONTEXT
opts = stub._ai_chat_options()

log("=" * 78)
log("S7 端到端：事件台词 → AI（真配置 + 真实例 + 真 persona + 真护栏 + 真截断）")
log("=" * 78)
log("端点 = %s   model = %s" % (cli.chat_endpoint(), cli.model))
log("persona = %d 字   options = %s   api.event_speech = %r"
    % (len(persona), opts, api_cfg.get("event_speech")))
log("EVENT_MAX_CHARS = %d   首字兜底时限 EVENT_SPEAK_FIRST_TOKEN_MS = %dms（露头字就不算超时）"
    % (EVENT_MAX_CHARS, R.EVENT_SPEAK_FIRST_TOKEN_MS))
log()

t0 = time.time()
cli.chat("在吗", system_prompt=system, history=[], max_tokens=8)
log("预热 %.2fs（冷加载一次性成本；之后单次请求才是用户真实体感）" % (time.time() - t0))
log()

# 事件 → 改造前的罐头基线（用来对照"AI 是不是真的换了句话"）
EVENTS = [
    ("poke_body", ["嗯？怎么啦？", "诶？有什么事吗？", "嘿嘿~ 你戳我啦"]),
    ("pinch_ear", ["哎呀！别捏我的耳朵！好痒呀！"]),
    ("pet_hair", ["嘿嘿~ 摸我的头发好舒服呀！", "谢谢你的抚摸！"]),
    ("pat_belly", ["嘿嘿~ 我的肚子很软哦！"]),
    ("double_hair", ["嘿嘿~ 摸头杀好舒服！"]),
    ("pull_shoulder", ["谢谢你拉我的肩膀！"]),
    ("poke_default", ["嘿嘿！", "你好呀！", "很高兴见到你！"]),
    ("feed", ["谢谢你喂我！肚子饱饱的，好幸福~"]),
]

log("-" * 78)
log("P1 纯链路：8 次事件（spoken 累积成 recent，复刻真实对话历史）")
log("  ※ 走真实 HTTPLocalAI.chat_stream（S7 定稿后的通路）：兜底只卡首字，整句不设限")
log("-" * 78)
spoken = []
rows = []
todo = []
for kind, canned in EVENTS:
    assert tier_of(kind) == TIER_AI, kind
    prompt = build_prompt(kind)
    # 首字时刻：chat_stream 的第一个非空分片
    marks = []
    t1 = time.time()

    def on_delta(piece):
        if piece and not marks:
            marks.append(time.time() - t1)   # 闭包按引用捕获 t1，本行在 def 之前已绑定

    raw = cli.chat_stream(prompt, system_prompt=system, history=[],
                          on_delta=on_delta, **opts)
    dt = time.time() - t1
    first_ms = marks[0] * 1000.0 if marks else None
    clean = stub._clean_ai_reply(raw, recent=spoken)
    shown = first_sentence(clean or "", EVENT_MAX_CHARS) if clean else ""
    if shown:
        spoken.append(shown)
    rows.append({"kind": kind, "dt": dt, "first_ms": first_ms, "raw": raw,
                 "clean": clean, "shown": shown, "canned": canned})
    log("事件 %-14s 首字 %s / 整句 %.2fs（首字时限 %dms → %s）"
        % (kind,
           ("%.2fs" % (first_ms / 1000.0)) if first_ms is not None else "（没出字）",
           dt, R.EVENT_SPEAK_FIRST_TOKEN_MS,
           "出字，走 AI" if (first_ms is not None
                           and first_ms <= R.EVENT_SPEAK_FIRST_TOKEN_MS) else "★超时，会说罐头"))
    log("   提示词   = %s" % prompt)
    log("   模型原文 = %r" % (raw or "")[:140])
    log("   护栏定稿 = %r" % (clean,))
    log("   屏幕显示 = %r   （%d 字 / 上限 %d）" % (shown, len(shown), EVENT_MAX_CHARS))
    log("   罐头基线 = %r" % (canned,))
    log("   换说法   = %s" % ("是" if shown and shown not in canned else "否（撞了罐头句）"))
    log()

dts = [r["dt"] for r in rows]
firsts = [r["first_ms"] for r in rows if r["first_ms"] is not None]
showns = [r["shown"] for r in rows]
problems = []
for r in rows:
    shown = r["shown"]
    if not shown:
        problems.append(("%s 没产出可用台词（真实运行时会说罐头兜底）" % r["kind"], r["raw"]))
    elif len(shown) > EVENT_MAX_CHARS:
        problems.append(("%s 超长" % r["kind"], shown))
    elif "**" in shown or "`" in shown or "#" in shown:
        problems.append(("%s markdown 残渣" % r["kind"], shown))
    elif any(m in shown for m in ("主人：", "你：", "Assistant:", "User:")):
        problems.append(("%s 自问自答续写" % r["kind"], shown))
    if r["first_ms"] is None or r["first_ms"] > R.EVENT_SPEAK_FIRST_TOKEN_MS:
        problems.append(("%s 首字超过兜底时限（%s）"
                         % (r["kind"], "未出字" if r["first_ms"] is None
                            else "%.2fs" % (r["first_ms"] / 1000.0)), None))

log("-" * 78)
log("P1 汇总")
log("  调用 %d 次 / 产出可用台词 %d 次" % (len(rows), len(showns)))
if dts:
    log("  整句耗时 中位 %.2fs / 平均 %.2fs / 最快 %.2fs / 最慢 %.2fs"
        % (sorted(dts)[len(dts) // 2], sum(dts) / len(dts), min(dts), max(dts)))
if firsts:
    log("  首字耗时 中位 %.2fs / 最快 %.2fs / 最慢 %.2fs   （首字时限 %.2fs）"
        % (sorted(firsts)[len(firsts) // 2] / 1000.0, min(firsts) / 1000.0,
           max(firsts) / 1000.0, R.EVENT_SPEAK_FIRST_TOKEN_MS / 1000.0))
log("  完全重样 = %d 条（%d 条台词里）" % (len(showns) - len(set(showns)), len(showns)))
log("  平均长度 = %.1f 字（上限 %d）"
    % (sum(len(x) for x in showns) / len(showns) if showns else 0, EVENT_MAX_CHARS))
log("  撞罐头基线 = %d 条" % sum(1 for r in rows if r["shown"] and r["shown"] in r["canned"]))
log("  问题 = %s" % ("无" if not problems else problems))
log()

# ---------------------------------------------------------------- P2
log("-" * 78)
log("P2 真对象：真的 RalseiPet()，直接调 speak_event（验「接线到 B」）")
log("-" * 78)
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    pet = R()
    dui = pet.dialogue_ui
    log("真对象构造成功：dialogue_ui=%s  api_enabled=%r  event_speech=%r"
        % (type(dui).__name__, pet.api_enabled, pet._event_speech_enabled()))

    def pump(ms):
        t = time.time()
        while (time.time() - t) * 1000 < ms:
            app.processEvents()
            time.sleep(0.004)

    # 「一次事件一个气泡」要用**单源**判据来测。
    # 不能数 `dialogue_ui._ai_history` 的增量：`pump()` 真跑 Qt 事件循环数秒，
    # 期间"桌面元素反应"（"这是未知文件类型呢！"）与"自主开口"（"工作了一段时间…"）
    # 会各自 add_dialogue 进来 —— 第一版就因此把 1 条数成 3 条（假的"多气泡"）。
    # 正解：包住唯一出口 `_event_say`，只数"本次事件自己说了几次"。
    _say_calls = []
    _orig_say = pet._event_say

    def _wrapped_say(text, face="happy", streamed=False):
        _say_calls.append((text, streamed))
        return _orig_say(text, face, streamed=streamed)

    pet._event_say = _wrapped_say

    # (a) AI 关闭 → 立刻罐头
    pet.api_enabled = False
    _say_calls.clear()
    t1 = time.time()
    got = pet.speak_event("poke_body", ["甲罐头", "乙罐头"], "curious")
    dt = time.time() - t1
    pump(60)
    log("  (a) AI 关：speak_event 返回 %r，耗时 %.3fs（应≈0，且不发请求）" % (got, dt))
    log("      本事件的气泡 = %r（%d 个；一次事件只应一个）" % (_say_calls, len(_say_calls)))
    log("      去重窗口 = %r" % (pet._event_line_picker._recent,))

    # (b) AI 开 → 走模型（线程 + 跨线程 signal）
    # 隔离：`pump()` 会真跑 Qt 事件循环数秒，期间"自主开口"与"桌面元素反应"会各自
    # 发一笔 chat_with_ai —— 它们与我们的请求**抢同一个模型实例**，会把首字挤到
    # 1200ms 之外，让事件看起来"总是回落罐头"（第一版就误判过一次）。
    # 所以这里把这两个来源直接封掉；它们本身有各自的回归套件，不需要在这个探针里跑。
    pet.start_autonomous_speech = lambda *a, **k: False
    pet._react_to_desktop_element = lambda *a, **k: None
    pet.AUTONOMOUS_SPEECH_MIN_INTERVAL = 10 ** 9
    pet._last_autonomous_speech_time = time.time()
    pet.api_enabled = True

    # 量"走完整 App 链路"的首字（纯链路 P1 是 0.82s；App 链路还要建上下文）
    # 同时插桩 API 层，拆开"建上下文"与"等模型"各花多少
    _delta_log = []
    _cli_log = []
    _orig_sd = dui.stream_delta

    def _wrapped_sd(chunk):
        _delta_log.append((round(time.time() - _t_event, 3), chunk))
        return _orig_sd(chunk)

    dui.stream_delta = _wrapped_sd

    _orig_cs = pet.api_client.chat_stream

    def _wrapped_cs(prompt, system_prompt=None, on_delta=None, **kw):
        # 首字必须在**这里**量，不能在 `dui.stream_delta` 上量：
        # 兜底说罐头之后 `speak_event._on_delta` 会按设计丢弃迟到分片，
        # 于是 `dui.stream_delta` 一次都不会被调到 —— 上一版就是在那里量的，
        # 结果"分片 = []"，把"首字到底几秒"这个问题留成了空白。
        _t0 = time.time()
        _first = {}
        _n = [0]

        def _probe_delta(chunk):
            _n[0] += 1
            if 't' not in _first:
                _first['t'] = time.time() - _t0
                _first['chunk'] = chunk
            if callable(on_delta):
                return on_delta(chunk)
            return None

        try:
            return _orig_cs(prompt, system_prompt=system_prompt,
                            on_delta=_probe_delta if callable(on_delta) else on_delta, **kw)
        finally:
            _cli_log.append({'发请求耗时': round(time.time() - _t0, 3),
                             '首分片耗时': round(_first.get('t', -1), 3),
                             '分片数': _n[0],
                             '首分片内容': _first.get('chunk'),
                             'prompt字数': len(prompt or ''),
                             'system字数': len(system_prompt or ''),
                             'history条数': len(kw.get('history') or [])})

    pet.api_client.chat_stream = _wrapped_cs

    before2 = len(getattr(dui, "_ai_history", []))
    _say_calls.clear()
    pet._event_speak_last = None            # 去掉频率闸，便于测量
    _t_event = time.time()
    pet.speak_event("pet_hair", ["罐头兜底句"], "happy")
    pump(int(R.EVENT_SPEAK_FIRST_TOKEN_MS) + 6000)
    dt = time.time() - _t_event
    dui.stream_delta = _orig_sd
    pet.api_client.chat_stream = _orig_cs
    other = [h for h in getattr(dui, "_ai_history", [])[before2:]]
    log("  (b) AI 开：%.2fs 内本事件的气泡 = %r" % (dt, _say_calls))
    log("      本事件收到的分片（时刻, 内容）= %r" % (_delta_log[:4],))
    if _cli_log:
        _f = _cli_log[0].get('首分片耗时', -1)
        log("      ★App 链路首字 = %.2fs（纯链路 P1 中位 0.82s；时限 %dms → %s）"
            % (_f, int(R.EVENT_SPEAK_FIRST_TOKEN_MS),
               "来得及" if 0 <= _f <= R.EVENT_SPEAK_FIRST_TOKEN_MS / 1000.0 else "超时，走罐头"))
    log("      API 层插桩 = %r" % (_cli_log,))
    log("      同期其它来源的台词（桌面反应/自主开口，与本事件无关）= %r"
        % [m for m in other if m not in [t for t, _ in _say_calls]])
    if _say_calls:
        first = _say_calls[0][0]
        log("      首个气泡 = %r（%d 字 / 上限 %d）" % (first, len(first), EVENT_MAX_CHARS))
        log("      是否罐头兜底 = %s" % ("是（AI 超时/失败）" if first == "罐头兜底句" else "否（走的是 AI）"))
        log("      气泡数 = %d（一次事件只应一个）" % len(_say_calls))
        log("  P2 结论 = %s" % ("接线成立：事件台词确实经 speak_event 落进 dialogue_ui"
                             if _say_calls else "!! 没落进对话"))
    else:
        log("  !! P2：speak_event 没有产生任何气泡 —— 接线可疑")

    # (c) 稳态复测：紧接着再打一次事件。用来区分"App 链路本来就慢"与
    #     "进程内第一次模型调用要付一次性成本（加载/预热）"——这个区别决定
    #     兜底时限该定多少（首字时限只对**稳态**负责，冷启动另算）。
    _delta_log.clear()
    _cli_log.clear()
    dui.stream_delta = _wrapped_sd
    pet.api_client.chat_stream = _wrapped_cs
    _say_calls.clear()
    _t_event = time.time()
    pet.speak_event("pat_belly", ["罐头兜底句2"], "happy")
    pump(int(R.EVENT_SPEAK_FIRST_TOKEN_MS) + 6000)
    dui.stream_delta = _orig_sd
    pet.api_client.chat_stream = _orig_cs
    log("  (c) 稳态复测（本进程第 2 次事件请求）：气泡 = %r" % (_say_calls,))
    log("      分片时刻 = %r" % (_delta_log[:3],))
    log("      API 层插桩 = %r" % (_cli_log,))
    if _cli_log:
        _f = _cli_log[0].get('首分片耗时', -1)
        log("      ★稳态 App 链路首字 = %.2fs → %s"
            % (_f, "在时限内，走 AI" if 0 <= _f <= R.EVENT_SPEAK_FIRST_TOKEN_MS / 1000.0
               else "超出时限，回落罐头"))
    pet.close()
except Exception as e:
    import traceback
    log("P2 异常（真机环境问题，不掩盖）：%r" % e)
    log(traceback.format_exc())

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("WROTE", OUT)
