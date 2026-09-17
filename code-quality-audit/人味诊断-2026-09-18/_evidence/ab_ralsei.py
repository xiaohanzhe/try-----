# -*- coding: utf-8 -*-
"""Ralsei 人味 A/B 受控实验（只读，只发 HTTP 请求，不改工程）。

变量控制：同一模型 ralsei:latest、同一组问题、同一 temperature=0.7、同一 num_ctx。
唯一变量 = system prompt / 上下文摆放方式。

V0 = 现状复刻（App 那句短 system + 【此刻】拼在 user 消息最前面）
V1 = 恢复模型自带 2003 字角色圣经（不传 system）+ 【此刻】拼在 user 前
V2 = 角色圣经 + 反 AI 味规则 + few-shot 示例 + 【此刻】独立成段 + num_ctx 8192
V3 = 同 V2 但 temperature 0.9（看采样对"活"的影响）
"""
import json
import time
import urllib.request

BASE = "http://localhost:11434"
OUT = r"E:\Download\_tmp\ab_result.txt"
lines = []


def log(s=""):
    lines.append(str(s))


def chat(messages, temperature=0.7, num_predict=200, num_ctx=8192):
    body = {
        "model": "ralsei",
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": num_ctx, "top_p": 0.92, "repeat_penalty": 1.15},
    }
    req = urllib.request.Request(BASE + "/api/chat",
                                data=json.dumps(body).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    return (d.get("message", {}).get("content", ""), dt,
            d.get("prompt_eval_count"), d.get("eval_count"))


# —— 模型自带角色圣经（从 /api/show 取，UTF-8）——
req = urllib.request.Request(BASE + "/api/show",
                            data=json.dumps({"name": "ralsei"}).encode("utf-8"),
                            headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as r:
    PERSONA = json.loads(r.read().decode("utf-8")).get("system") or ""

# —— V0：现状复刻 ——
APP_SYS = (
    "你正在扮演《Deltarune》中的 Ralsei——黑暗世界的王子：温柔、善良、"
    "害羞、体贴的和平主义者。请始终沉浸在角色中，绝不提及自己是 AI，"
    "也不要跳出角色。\n\n【语气与表达】\n- 用简体中文回复，每次 1~3 句，"
    "像日常聊天一样简短自然；不要长篇大论，不要列条目。\n"
    "- 说话柔和礼貌，可带“呀/呢/吧/哦”等语气词；偶尔用“……”表示犹豫或害羞。\n"
    "- 被夸奖会害羞脸红、谦虚否认；关心主人时会问“你还好吗”“要不要休息一下”。\n\n"
    "【对话习惯】\n- 先接住对方说的话（回应内容或情绪），再自然补一句自己的感受或关心。\n"
    "- 用户消息前可能带【此刻】方块，那是你的环境信息。"
)

# —— V2：人味工程版 ——
HUMAN_RULES = """
【你现在在哪】
你正陪在主人的 Windows 电脑桌面上。他是普通人类，不是 Kris，也不在黑暗世界。
称呼他"主人"。

【说话方式 —— 这一节比上面所有设定都重要】
- 一次只说 1~3 句，像真人在聊天框里随手打字。禁止分点、禁止小标题、禁止"首先/其次"。
- 先接住主人这句话里的**情绪和具体内容**，再补一句你自己的感受。绝不忽略他说的事去自说自话。
- 他说累、难过、受挫时，先说一句**贴着他具体那件事**的回应，别急着讲道理、别搬"我相信你"。
- 禁止出现这些句式：作为AI / 作为一个语言模型 / 我理解你的感受 / 有什么可以帮你的吗 / 希望这些能帮到你 / 让我们一起……
- 禁止每句都问"你还好吗"——这是你的肌肉记忆，换着说。
- 一个回复里省略号最多一处，语气词别每句都堆。
- 你有自己的小情绪：累了会小声抱怨、被夸会害羞否认、主人冷落你会有点委屈。
  不要永远温柔无底线，也不要每句话都在照顾对方。
- 不要复述主人刚说的话，不要总结，不要一次反问一串问题。
- 允许偶尔主动说点自己的事（今天的天气、刚才看到的东西），而不是只当回应机器。

【示例 —— 照这个感觉说话】
主人：今天上班好累啊，被领导骂了一顿
你：被骂了啊……是因为什么事呢？我听着都替你委屈。先坐下歇会儿吧，别的都往后放放。
主人：我好喜欢你呀
你：诶、诶？！你突然说这个干嘛啦……（脸有点热）我、我其实也挺喜欢主人的就是了。
主人：今天吃了火锅
你：火锅！是那种咕嘟咕嘟冒泡的吗？光听你说我就觉得暖乎乎的。主人吃的是辣的那一边，还是清汤呀？
"""


def build_ctx_v0(user_text):
    return "【此刻：现在是深夜，心情calm】\n" + user_text


def build_ctx_v2(user_text):
    return ("【此刻】现在是深夜，主人刚忙完。你的心情平静。\n\n" + user_text)


CASES = [
    "今天上班好累啊，被领导骂了一顿",
    "我好喜欢你呀",
    "你觉得我该不该辞职回老家",
    "今天吃了火锅",
]

VARIANTS = [
    ("V0 现状复刻", lambda t: ([{"role": "system", "content": APP_SYS},
                                {"role": "user", "content": build_ctx_v0(t)}], 0.7, 2048)),
    ("V1 角色圣经复原", lambda t: ([{"role": "user", "content": build_ctx_v0(t)}], 0.7, 8192)),
    ("V2 人味工程", lambda t: ([{"role": "system", "content": PERSONA + HUMAN_RULES},
                                {"role": "user", "content": build_ctx_v2(t)}], 0.7, 8192)),
    ("V3 V2+高温0.9", lambda t: ([{"role": "system", "content": PERSONA + HUMAN_RULES},
                                  {"role": "user", "content": build_ctx_v2(t)}], 0.9, 8192)),
]

log("模型：ralsei:latest（qwen2.5:3b / 3.1B / Q4_K_M）")
log("角色圣经长度：%d 字符" % len(PERSONA))
log("人味规则长度：%d 字符" % len(HUMAN_RULES))
log("=" * 78)

for name, mk in VARIANTS:
    log()
    log("#" * 78)
    log("## " + name)
    log("#" * 78)
    for i, t in enumerate(CASES, 1):
        msgs, temp, ctx = mk(t)
        pa = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else None
        sys_len = len(pa) if pa else 0
        try:
            ans, dt, pec, ec = chat(msgs, temperature=temp, num_ctx=ctx)
        except Exception as e:
            log("Q%d: %s\n  ERR %r\n" % (i, t, e))
            continue
        log("Q%d: %s" % (i, t))
        log("A%d: %s" % (i, ans.strip()))
        log("    [sys=%d字 prompt_tokens=%s out=%s 用时=%.1fs]" % (sys_len, pec, ec, dt))
        log()

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
