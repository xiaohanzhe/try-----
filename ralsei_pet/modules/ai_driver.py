# -*- coding: utf-8 -*-
"""
本地 AI 行动驱动（行为大脑）
==========================
让本地模型（Ollama 的 ralsei / OpenAI 兼容模型）不只是"聊天"，还能周期性地
给 Ralsei 挑一个动作（跳舞/唱歌/挥手/睡觉/散步/说句话……），把宠物的自主
行为也交给你培养的模型来驱动，而不是只能回复对话框。

设计原则（用户视角"永远不出错"）：
1. 白名单动作：全部无副作用 —— 不碰用户文件、不关窗口、不碰鼠标。
   "想出去走走"只触发现有的 AutonomousAgent 去桌面逛（它自己有全套守卫）。
2. 节奏克制 + 退避：默认 ~35 秒才问一次模型；模型不可用/超时/输出看不懂时
   间隔自动翻倍（上限 5 分钟），绝不让失败打扰到用户。
3. 静默失败：模型没开、请求超时、返回无法解析 → 什么都不做。Ralsei 原有
   规则行为（randomize_movement_pattern / AutonomousAgent）照常跑，用户
   看不出差别。
4. 绝不打断关键流程：施法/游戏/拖拽/追鼠标/跳跃掉落中不触发；正在给用户
   打字/模型正在回话时不插话。
5. 全部 owner 访问走 getattr 守卫：任何接口缺失都退化为"本拍什么都不做"。

接入：main.py 创建 `self.ai_driver = AiActionDriver(self)`，然后在
update_ai（每 3 秒）里调用 `self.ai_driver.tick(time.time())`。
"""

import json
import random
import re
import threading
import time
from collections import deque

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

# 模型可挑选的动作动画 —— 必须真实存在于 sprite_loader 动画组里
ANIMATION_ACTIONS = {
    "dance", "sing", "wave", "bow", "laugh", "look_up", "pose",
    "curtsy", "spin", "hug", "tea", "stretch",
}
# stretch 没有独立动画组时回退到 pose
ANIMATION_FALLBACK = {"stretch": "pose"}

# 睡觉中只允许这些（不能睡着睡着突然跳起舞来）
SLEEP_SAFE_ACTIONS = {"idle", "rest", "nothing", "sleep", "wake"}

# 走路类动作：触发 AutonomousAgent 立即决策一轮桌面漫游（安全复用其守卫）
WANDER_ACTIONS = {"wander", "explore", "observe", "move", "walk"}

# 无动作类：模型认为"就这么待着"也算有效决策
PASSIVE_ACTIONS = {"idle", "rest", "nothing", "wait"}

# say 表情提示白名单（dialogue_ui 的 _FACE_MAP 能解析的 key）
SAY_FACES = {
    "happy": "happy", "excited": "excited", "curious": "curious",
    "peaceful": "peaceful", "sleepy": "sleepy", "shy": "shy",
    "thinking": "thinking", "content": "content", "caring": "caring",
    "playful": "playful", "touched": "touched", "surprised": "surprised",
}

BASE_INTERVAL = 35.0        # 正常节奏：两次问模型的最小间隔（秒）
MAX_INTERVAL = 300.0        # 连续失败后最多退避到 5 分钟
RETRY_SHORT = 10.0          # 与关键流程冲突时，稍后（10 秒）再试
DIALOGUE_COOLDOWN = 8.0     # 模型正在回复用户时，等它回完再试
SAY_COOLDOWN = 90.0         # AI 自主"开口说话"的最小间隔（防吵）

_ACTION_SYSTEM_PROMPT = (
    "你是桌面宠物 Ralsei 的行为决策器。根据玩家给你的状态，只输出一个 JSON "
    "对象，不要输出任何别的文字、解释或 markdown 代码块。\n\n"
    "输出格式（严格）：\n"
    '{"action":"动作名","say":"可选的一句想对主人说的话(简体中文,没有就空)",'
    '"emotion":"可选的当前心情(如 happy/curious/peaceful/sleepy/shy)"}\n\n'
    "动作只能是下面之一：\n"
    "- idle 或 rest：安静待着休息一下\n"
    "- wander：在桌面上随意走走、看看周围\n"
    "- dance / sing / wave / bow / laugh / look_up / pose / curtsy / spin / "
    "hug / tea：做对应的小表演动作\n"
    "- sleep：累了才选睡觉\n"
    "- wake：醒来活动\n"
    "- say：只想跟主人说句话（say 字段填内容）\n\n"
    "Ralsei 性格温柔、害羞、善良，动作要轻柔、频率要低，除非状态显示很疲惫，"
    "否则不要频繁睡觉；也不要总是说话。根据当前状态选一个最符合当下心情的动作。"
    "另外：如果上次动作是 idle/rest/wait 这类发呆，这次请尽量换一个有行动感的"
    "动作（比如 wander 出去走走，或 dance/sing/wave 这样的小表演），"
    "让桌面宠物看起来有活力、像个活着的小家伙。\n\n"
    "【时段感】状态里会给出现在是什么时段，请顺着时段选动作：\n"
    "- 清晨/上午：精神好，可以 wander 走走或做个小表演，say 里道声早安。\n"
    "- 中午：可以 say 关心主人有没有好好吃饭。\n"
    "- 下午：散步或小表演都合适。\n"
    "- 傍晚/晚上：适合安静的活动（tea、look_up、idle），say 可以关心主人累不累。\n"
    "- 深夜：主人还在用电脑就安静陪着，别再提议跳舞唱歌；"
    "自己很累（精力<25）时选 sleep。\n\n"
    "【防重复】状态里会给出最近几次动作。如果最近已经做过某个动作，"
    "尽量换一个不同的；不要连续三次做同一个动作，也不要连续说两次话。\n\n"
    "【say 的要求】要说就说有内容、贴合当下的话（一句关心、分享、或邀请），"
    "不要空泛客套（如“你好呀”）；没有想说的就把 say 留空，不要硬凑。"
)


def extract_json(text):
    """从模型输出里宽容提取 JSON 对象。

    支持：纯 JSON、被 ```json 围栏包住、前后带解释碎话（如"好的！{...}这样"）。
    提取失败返回 None。
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    # 去掉 markdown 代码围栏
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```$", "", t)
    t = t.strip()
    # 直接尝试
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception as e:
        _log.debug("ai_driver 防御性异常（已忽略）: %s", e)
    # 找第一组配平的 { ... }
    start = t.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(t[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


class AiActionDriver:
    """本地 AI 行为大脑。线程安全：只在主线程 tick/回调里改状态。"""

    def __init__(self, owner, base_interval: float = BASE_INTERVAL):
        self._owner = owner
        self._base_interval = float(base_interval)
        self._current_interval = float(base_interval)
        self._next_at = time.time() + float(base_interval) + random.uniform(0, 10)
        self._busy = False                 # 上一拍还在等模型
        self._last_say_at = 0.0
        self._last_action = "无"
        self._last_action_at = 0.0
        # 最近几次已执行的动作（防重复：让模型知道别老做同一个）
        self._recent_actions = deque(maxlen=6)

    # ------------------------------------------------------------ 主入口
    def tick(self, now: float):
        """update_ai（约每 3 秒）调用。一切失败都静默。"""
        try:
            if not getattr(self._owner, "api_enabled", False):
                return
            if self._busy:
                # 防卡死：请求挂了太久（超时+重试可能拖到 2 分钟），
                # 强制复位让规则行为继续跑，迟到回复由 _on_reply 再排期
                if now - getattr(self, "_fire_started_at", 0.0) > 90.0:
                    self._busy = False
                return
            if now < self._next_at:
                return
            cli = getattr(self._owner, "api_client", None)
            if cli is None or not getattr(cli, "enabled", False):
                return
            if not callable(getattr(cli, "chat", None)):
                return

            # 模型正在回复用户 → 等它回完再问（避免同模型排队、让对话优先）
            dlg = getattr(self._owner, "dialogue_ui", None)
            if dlg is not None and getattr(dlg, "_ai_inflight", False):
                self._next_at = now + DIALOGUE_COOLDOWN
                return
            if not self._safe_to_act():
                self._next_at = now + RETRY_SHORT
                return
            self._fire(now)
        except Exception as e:
            _log.debug("[AI行动] tick 异常(已忽略): %s", e)
            self._busy = False
            self._backoff(now)

    # ------------------------------------------------------------ 发起请求
    def _fire(self, now: float):
        self._busy = True
        self._fire_started_at = now
        owner = self._owner
        cli = owner.api_client
        prompt = self._build_prompt()

        def _worker():
            try:
                text = cli.chat(prompt, system_prompt=_ACTION_SYSTEM_PROMPT,
                                temperature=0.7)
            except Exception:
                text = None
            try:
                # 复用 main.py 的跨线程 API 信号：主线程 _on_api_result 会回调
                owner._api_result.emit(text, self._on_reply)
            except Exception:
                self._busy = False

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------ 结果回调（主线程）
    def _on_reply(self, reply):
        now = time.time()
        self._busy = False
        parsed = extract_json(reply) if reply else None
        if not parsed:
            _log.debug("[AI行动] 模型回复无法解析，退避")
            self._backoff(now)
            return
        acted = self._execute(parsed)
        if acted:
            self._current_interval = self._base_interval
        else:
            # 模型给了 JSON 但内容当前不可执行（比如想跳舞时正在睡觉）→ 温和退避
            self._current_interval = min(self._current_interval * 1.5,
                                         MAX_INTERVAL)
        self._next_at = (now + self._current_interval
                         + random.uniform(0, 12))

    def _backoff(self, now: float):
        self._current_interval = min(self._current_interval * 2.0,
                                     MAX_INTERVAL)
        self._next_at = now + self._current_interval

    # ------------------------------------------------------------ 冲突守卫
    def _safe_to_act(self):
        o = self._owner
        if getattr(o, "_spell_stage", None) is not None:
            return False
        gs = getattr(o, "game_state", None) or {}
        if gs.get("is_playing"):
            return False
        if (getattr(o, "is_dragging_mouse", False)
                or getattr(o, "_is_being_dragged", False)):
            return False
        if getattr(o, "is_following_mouse", False):
            return False
        if (getattr(o, "is_jumping", False) or getattr(o, "is_falling", False)
                or getattr(o, "is_gravity_falling", False)
                or getattr(o, "is_recovering", False)):
            return False
        return True

    # ------------------------------------------------------------ 执行白名单动作
    def _execute(self, d: dict) -> bool:
        o = self._owner
        action = str(d.get("action") or d.get("act") or "").strip().lower()
        say = d.get("say") or d.get("speak") or d.get("message") or ""
        emotion_hint = str(d.get("emotion") or "").strip().lower()
        now = time.time()
        self._last_action = action or "无"
        self._last_action_at = now
        if action:
            self._recent_actions.append(action)

        if not action:
            # 没给动作但有话想说
            if say and isinstance(say, str) and say.strip():
                self._say(say, emotion_hint)
                return True
            return False

        sleeping = bool(getattr(o, "is_sleeping", False))

        # ---- 1) 睡觉 / 醒来（有专用流程，自带台词与动画，say 忽略避免重复）
        if action == "sleep" and not sleeping:
            fn = getattr(o, "enter_sleep_mode", None)
            if callable(fn):
                try:
                    fn()
                    return True
                except Exception:
                    return False
            return False
        if action == "wake" and sleeping:
            fn = getattr(o, "wake_up", None)
            if callable(fn):
                try:
                    fn()
                    return True
                except Exception:
                    return False
            return False

        # 睡觉中：除了 sleep/wake，其它一律不动（让模型安静的睡）
        if sleeping:
            if action in PASSIVE_ACTIONS:
                return True
            return False

        # ---- 2) 走走 / 观察桌面 → 交给 AutonomousAgent 决策一轮（安全）
        if action in WANDER_ACTIONS:
            agent = getattr(o, "autonomous_agent", None)
            if agent is not None and not agent.is_busy():
                try:
                    # 清掉它的决策节流，让它在下一个 tick 重新选目标走过去
                    agent._last_decision_time = 0.0
                except Exception as e:
                    _log.debug("ai_driver 防御性异常（已忽略）: %s", e)
            if say and isinstance(say, str) and say.strip():
                self._say(say, emotion_hint or "curious")
            return True

        # ---- 3) 一次性小表演动画
        if action in ANIMATION_ACTIONS:
            anim = ANIMATION_FALLBACK.get(action, action)
            play_once = getattr(o, "play_animation_once", None)
            if callable(play_once):
                # 正在走路时也打断不太好 → 让 change_animation 的守卫决定
                try:
                    ok = play_once(anim)
                except Exception:
                    ok = False
                if not ok:
                    # 动画切换被 spell/游戏守卫拦下：动作作废但不算模型错误
                    return False
            if say and isinstance(say, str) and say.strip():
                self._say(say, emotion_hint or "happy")
            return True

        # ---- 4) 只想说话
        if action == "say":
            if say and isinstance(say, str) and say.strip():
                self._say(say, emotion_hint)
                return True
            return False

        # ---- 5) 安静待着（有效决策）
        if action in PASSIVE_ACTIONS:
            return True

        # 未知动作：模型幻觉了 → 当失败处理（会触发退避）
        return False

    # ------------------------------------------------------------ 说话（带防打断 + 冷却）
    def _say(self, text: str, emotion_hint: str = ""):
        o = self._owner
        dlg = getattr(o, "dialogue_ui", None)
        if dlg is None:
            return
        # 正在给用户打字/用户正在输入 → 不插话（动作仍可执行）
        try:
            if getattr(dlg, "is_typing", False):
                return
            if getattr(dlg, "_is_user_inputting", lambda: False)():
                return
        except Exception as e:
            _log.debug("ai_driver 防御性异常（已忽略）: %s", e)
        if time.time() - self._last_say_at < SAY_COOLDOWN:
            return
        face = SAY_FACES.get(emotion_hint, "happy") if emotion_hint else "happy"
        text = str(text).strip()
        if not text:
            return
        try:
            dlg.add_dialogue("ralsei", text, face)
            if not dlg.isVisible():
                dlg.show_dialogue()
            self._last_say_at = time.time()
        except Exception as e:
            _log.debug("ai_driver 防御性异常（已忽略）: %s", e)

    # ------------------------------------------------------------ 构造状态提示词
    def _build_prompt(self) -> str:
        o = self._owner
        try:
            e, ev = o.emotion_system.get_current_emotion()
            emotion_str = f"{e}（强度{int(abs(ev))}）"
        except Exception:
            emotion_str = "peaceful"
        try:
            energy = o.energy_hunger.get_energy()
            hunger = o.energy_hunger.get_hunger()
        except Exception:
            energy = hunger = 50
        try:
            px, py = int(o.pos().x()), int(o.pos().y())
        except Exception:
            px = py = 0
        try:
            weather = o.weather_system.get_current_weather()
        except Exception:
            weather = ""
        seconds_since_last = int(time.time() - self._last_action_at) \
            if self._last_action_at else -1
        last_desc = (f"{self._last_action}（约{seconds_since_last}秒前）"
                     if seconds_since_last >= 0 else "还没有")
        # 时段描述（训练调优：让行为决策带"时段感"，晚上安静、深夜想睡）
        try:
            _h = time.localtime().tm_hour
            if 5 <= _h < 8:
                tod = "清晨"
            elif 8 <= _h < 11:
                tod = "上午"
            elif 11 <= _h < 13:
                tod = "中午"
            elif 13 <= _h < 17:
                tod = "下午"
            elif 17 <= _h < 19:
                tod = "傍晚"
            elif 19 <= _h < 23:
                tod = "晚上"
            else:
                tod = "深夜"
        except Exception:
            tod = ""
        # 最近动作序列（防重复）
        recent_desc = "、".join(self._recent_actions) if self._recent_actions else "还没有"
        lines = [
            "当前状态：",
            f"- 时段：{tod}" if tod else "- 时段：未知",
            f"- 心情：{emotion_str}",
            f"- 精力：{energy}/100，饥饿：{hunger}/100",
            f"- 位置：屏幕({px},{py})",
            f"- 天气：{weather}" if weather else "- 天气：晴",
            f"- 当前动画：{getattr(o, 'current_animation', 'idle')}",
            f"- 正在移动：{'是' if getattr(o, 'is_moving', False) else '否'}",
            f"- 上次动作：{last_desc}",
            f"- 最近动作序列：{recent_desc}",
            "",
            "请只输出一个 JSON 动作对象（见格式要求）。",
        ]
        return "\n".join(lines)
