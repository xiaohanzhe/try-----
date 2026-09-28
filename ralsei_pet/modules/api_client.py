"""
本地 AI 接入端口
================

设计目标：为"培养本地 AI"预留一个清晰、可插拔、运行时可热启用的接入点。

分层：
    LocalAIBase        —— 抽象基类（4 个方法：chat/get_commands/send_status/execute_command）
    LocalAIStub        —— enabled=False 时的空实现（不发请求、不报错）
    HTTPLocalAI        —— 默认的 OpenAI 兼容 HTTP 实现（协议骨架，端点可被子类覆盖）
    create_client()    —— 唯一工厂：所有代码通过它拿实例，将来接入真实模型只需改一处
    register_provider()—— 用户"培养的本地 AI"注册入口（传入 factory 即接管）

为什么这样设计：
    1. main.py 里 self.api_client 是运行时快照——改配置不重建 = 热启用失败。
       现在统一走 create_client(config)，保存配置后调用
       self.api_client = create_client(api_config) 即可热生效（协议后定时协议细节不变）。
    2. 协议留白：HTTPLocalAI 只实现 /v1/chat/completions 的对话（OpenAI 兼容），
       get_commands/send_status/execute_command 默认返回 None 并打印一条可关闭的提示，
       留给你在子类里按自己的 agent 协议补全（方法签名即端口）。
    3. register_provider(factory) 让你不用改 main.py 就能把"培养好的模型/agent server"
       接进来。

示例（接入一个跑在 localhost:8000 的自定义 agent）：
    from modules import api_client

    class MyAgent(api_client.HTTPLocalAI):
        # 覆盖端点到你的 agent 协议
        def commands_endpoint(self): return "http://localhost:8000/api/ralsei/commands"
        def send_status_endpoint(self): return "http://localhost:8000/api/ralsei/status"

    api_client.register_provider(lambda cfg: MyAgent(cfg))
"""

import json
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# 修复：原先 _logger 只 setLevel(INFO) 却没有 handler——模块级 logger 不经
# logger_utils 配置时，INFO 级日志会被 Python 内置 lastResort 丢弃（只输出
# WARNING+），排查"AI 为什么没回复"时关键线索全部丢失。现在优先挂接项目
# 统一日志（logger_utils），独立导入时补一个控制台 handler。
_logger = logging.getLogger('LocalAI')
if not _logger.handlers:
    try:
        from logger_utils import get_logger
        _logger = get_logger('LocalAI')
    except ImportError:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
        _logger.addHandler(_h)
        _logger.setLevel(logging.INFO)


class LocalAIBase(ABC):
    """本地 AI 抽象基类。对接本地模型的实现都必须继承此类。"""

    def __init__(self, config: Dict[str, Any]):
        self.rebuild(config)

    # ---- 运行时可热启用：换配置后调用此方法更新内部状态（不重建实例也行） ----
    def rebuild(self, config: Dict[str, Any]):
        # 修复：config 可能是列表/字符串等非 dict（配置文件被手改），
        # 直接 .get() 会 AttributeError 导致 create_client 崩溃。
        if not isinstance(config, dict):
            config = {}
        self.config = config
        self.enabled = bool(config.get('enabled', False))
        # 修复：base_url 为空字符串/纯空格时，chat_endpoint() 会拼出相对路径
        # "/v1/chat/completions"（requests 视为非法 URL 直接抛 MissingSchema），
        # 且空串绕过了原来的默认值逻辑。剥离空白后为空一律回退默认地址。
        _base_url = str(config.get('base_url', '') or '').strip().rstrip('/')
        self.base_url = _base_url or 'http://localhost:8000'
        self.model = config.get('model', 'local-model')
        self.agent_id = config.get('agent_id', '')
        self.api_version = config.get('api_version', 'v1')
        # 修复：配置文件手改/类型错误（如 "timeout": "abc"）会让 create_client
        # 直接抛异常 → api_client 变 None、AI 热启用失败。逐个做防御性转换。
        def _num(v, default):
            try:
                f = float(v)
                return f if f > 0 else default
            except (TypeError, ValueError):
                return default
        self.timeout = _num(config.get('timeout', 30), 30.0)
        self.max_retries = int(_num(config.get('max_retries', 3), 3.0))
        self.retry_delay = _num(config.get('retry_delay', 1.0), 1.0)

    @abstractmethod
    def chat(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """向本地 AI 发送自然语言请求，返回文字回复；失败返回 None。"""
        ...

    # ---- 流式对话：**基类给具体实现**，不是抽象方法 ----
    def chat_stream(self, prompt: str, system_prompt: Optional[str] = None,
                    on_delta=None, **kwargs) -> Optional[str]:
        """流式对话的默认实现：一次性拿完整回复，再作为**单个分片**回调。

        为什么基类给具体实现而不是 abstractmethod：`LocalAIStub` 和用户通过
        `register_provider()` 注册的自定义实现都不该被迫改造 —— 否则 App 一升级，
        调用方按"一定有 chat_stream"来写，就会崩在用户那边的实现上。
        有这个默认实现，"流式"对调用方就永远可用：不支持真流式的实现退化成
        "憋完整句再一次性给出"（首字延迟没改善，但行为与语义都正确）。

        `on_delta` 为 None 时等价于 `chat()`。
        """
        text = self.chat(prompt, system_prompt=system_prompt, **kwargs)
        if text and on_delta is not None:
            try:
                on_delta(text)
            except Exception as e:
                _logger.debug("chat_stream 默认实现回调异常（已忽略）: %s", e)
        return text

    @abstractmethod
    def get_commands(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """让 AI 基于当前上下文生成控制命令；无命令/未实现返回 None。"""
        ...

    @abstractmethod
    def send_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """把 Ralsei / 电脑状态同步给 AI；返回 AI 反馈或 None。"""
        ...

    @abstractmethod
    def execute_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """让 AI 审查/扩展一个命令；返回结果或 None。"""
        ...


class LocalAIStub(LocalAIBase):
    """空实现：enabled=False 时不产生任何请求；enabled=True 且未接入真实实现时打一条
    警告并返回 None（让调用方的 `if not x: return` 天然兼容，绝不崩溃）。"""

    def chat(self, prompt, system_prompt=None, **kwargs):
        if self.enabled:
            self._warn()
        return None

    def get_commands(self, context):
        if self.enabled:
            self._warn()
        return None

    def send_status(self, status):
        if self.enabled:
            self._warn()
        return None

    def execute_command(self, command):
        if self.enabled:
            self._warn()
        return None

    def _warn(self):
        _logger.warning(
            "本地 AI 已启用但尚未接入真实实现：请继承 api_client.HTTPLocalAI（或注册 "
            "register_provider）后在配置里重新启用，命令轮询才会真正生效。")


class HTTPLocalAI(LocalAIBase):
    """默认的 OpenAI 兼容 HTTP 实现（协议骨架）。

    - chat: POST {base_url}/v1/chat/completions（OpenAI 兼容），可用覆盖 _chat_endpoint()。
    - get_commands / send_status / execute_command：默认返回 None（未定协议），
      覆盖对应 *_endpoint() 并在 _post_json() 基础上补全即可。
    所有请求失败/超时/结构不对都返回 None，绝不让 Ralsei 崩溃。
    """

    # ---------------- 可覆盖的端点（= 你 agent 协议留白处） ----------------
    def chat_endpoint(self) -> str:
        return f"{self.base_url}/{self.api_version}/chat/completions"

    def commands_endpoint(self) -> Optional[str]:
        return None          # 未定协议：返回 None 表示本轮不轮询

    def status_endpoint(self) -> Optional[str]:
        return None

    def command_execute_endpoint(self) -> Optional[str]:
        return None

    # ---------------- 对话（OpenAI 兼容） ----------------
    def _auth_headers(self) -> Dict[str, str]:
        """构造请求头；api_key 非空时带 Authorization: Bearer（云端/需鉴权的
        OpenAI 兼容端点必需，否则每次 401 静默失败；本地 Ollama 空 key 不受影响）。"""
        headers = {"Content-Type": "application/json"}
        api_key = str(self.config.get("api_key", "") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _chat_messages(self, prompt, system_prompt, kwargs):
        """把 (prompt, system, kwargs) 归一成 (messages, temperature, max_tokens)。

        `chat()` 与 `chat_stream()` 共用这一份"组装 messages + 参数钳位"的逻辑。
        **为什么必须共用**：两处各写一份的话，改了钳位规则却只改了一边 ——
        本项目已经因为"同一逻辑两份实现"出过好几次问题（见文件头注释第 1 条）。
        """
        # 修复：temperature / max_tokens 原先无范围校验，调用方传入负数或
        # 0 会让部分 OpenAI 兼容后端直接 400 且难以排查。这里做防御性钳位。
        def _clamp(v, lo, hi, default):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return default
            return max(lo, min(v, hi))
        temperature = _clamp(kwargs.get("temperature", 0.7), 0.0, 2.0, 0.7)
        max_tokens = int(_clamp(kwargs.get("max_tokens", 500), 1, 100000, 500))
        # 修复：新增 history 参数 —— 调用方可传入最近几轮对话
        # [(role, content), ...]（role ∈ user/assistant），让模型拥有上下文，
        # 对话不再"每句都是第一次见面"。角色非法/内容非字符串的条目静默丢弃。
        history = kwargs.get("history") or []
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if isinstance(history, (list, tuple)):
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
                messages.append({"role": _role, "content": _content})
        messages.append({"role": "user", "content": prompt})
        return messages, temperature, max_tokens

    def _chat_payload(self, prompt, system_prompt, kwargs, stream):
        """构造请求体。`chat` / `chat_stream` 共用，只有 stream 标志不同。

        ★ 第55轮：允许**按请求**覆盖模型名（`model=` 走 kwargs）。
          为什么必须有这一条：`self.model` 是**构造时**从 config 定下的全局值，
          而每个 NPC 在 `assets/npc/_registry.json` 里都有自己的 `model` 字段 ——
          不做覆盖的话，"NPC 自己的模型"就是一纸空文：**登记了，但没人读**
          （本项目最贵的那类坑：「函数写对了 ≠ 产品用上了」）。
          语义（刻意这样定）：
            · `model` 给了**非空字符串** ⇒ 覆盖 payload 里的 `model`；
            · `None` / 空串 / 非字符串 ⇒ **不覆盖**，逐字沿用 `self.model`
              —— 老路径（Ralsei 对话 / 事件台词）行为**零变化**，这是硬要求。
          注意：`kwargs` 是 `**kwargs` 生成的**局部**字典，pop 掉 `model`
          不会影响调用方；且必须**先 pop 再**喂给 `_chat_messages`，
          免得它把这个键当成采样参数继续往下传。
        """
        _override = kwargs.pop('model', None)
        _model = (_override if isinstance(_override, str) and _override.strip()
                  else self.model)
        messages, temperature, max_tokens = self._chat_messages(
            prompt, system_prompt, kwargs)
        payload = {
            "model": _model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": bool(stream),
        }
        if self.agent_id:
            payload["agent_id"] = self.agent_id
        return payload

    def chat(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """向本地 AI 发送对话请求，返回文字回复；失败返回 None。

        注意：此方法为**阻塞调用**，内部使用 requests.post() 同步发送 HTTP 请求，
        超时时间由配置项 timeout 控制（默认 30 秒）。**严禁在主线程/UI 线程直接调用**，
        否则会导致界面冻结。应在工作线程中调用（如 main.py 的 _async_api_request）。
        """
        if not self.enabled:
            return None
        try:
            # ★ 第58轮新增：**按请求超时**（`timeout=` 走 kwargs）。
            #   为什么必须能按请求给：启动预热要发一个"人设满长"的请求，冷 prefill
            #   实测 55.8~64.3s（2371 token），而对话用的 `self.timeout` 默认只有 30s
            #   —— 拿对话的超时去发预热请求，会被自己的客户端判成超时（假失败）。
            #   语义与 `model=` 一致：给了才覆盖，不给逐字沿用 self.timeout（老路径零变化）。
            _timeout = kwargs.pop('timeout', None)
            payload = self._chat_payload(prompt, system_prompt, kwargs, False)
            # 修复：原先 chat() 与 _post_json() 各写一份 POST/状态码/异常处理逻辑
            # （重复编码），统一走 _post_json，非 200 也统一记 warning 日志。
            data = self._post_json(self.chat_endpoint(), payload, timeout=_timeout)
            if not data:
                return None
            choices = data.get("choices") or []
            if not choices:
                return None
            return (choices[0].get("message", {}) or {}).get("content")
        except Exception as e:
            _logger.info("本地 AI chat 请求失败（忽略）: %s", e)
            return None

    # ---------------- 流式对话（S8） ----------------
    # 收益全在"首字延迟"：实测 ralsei:v2 非流式首字节 6.02s（首字也是 6.02s），
    # 流式首字 0.23s、全文 1.34s。非流式时用户盯着"……"空等，正是"假人感"来源。
    def chat_stream(self, prompt: str, system_prompt: Optional[str] = None,
                    on_delta=None, **kwargs) -> Optional[str]:
        """流式对话：边收边把增量交给 `on_delta`，返回**累积的完整文本**。

        返回完整文本而不是 None，是因为调用方仍要拿它过一遍输出护栏
        （剥 markdown / 截断自问自答 / 判车轱辘话）—— 护栏必须看到全文。

        `on_delta` 为 None → 直接回落 `chat()`（没必要走流式解析）。

        注意：**同样是阻塞调用**（会一直读到流结束），必须在工作线程里调。
        """
        if not self.enabled:
            return None
        if on_delta is None:
            return self.chat(prompt, system_prompt=system_prompt, **kwargs)
        try:
            import requests
            payload = self._chat_payload(prompt, system_prompt, kwargs, True)
            # 故意**不重试**：流式一旦已经开始往外吐字，重试会让同一句被说两遍。
            # 网络抖动交给上层（护栏判退后的重采样）兜底。
            resp = requests.post(self.chat_endpoint(), json=payload,
                                 headers=self._auth_headers(),
                                 timeout=self.timeout, stream=True)
            if resp.status_code != 200:
                _logger.warning("本地 AI 流式 HTTP %s: %s",
                                resp.status_code, resp.text[:200])
                return None
            return self._consume_stream(resp, on_delta)
        except Exception as e:
            _logger.info("本地 AI 流式请求失败（忽略）: %s", e)
            return None

    @staticmethod
    def _delta_of(payload: str) -> str:
        """从一条 SSE 的 data 负载中取出增量文本；取不到返回 ''。"""
        try:
            obj = json.loads(payload)
        except Exception:
            return ""
        choices = obj.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        return piece if isinstance(piece, str) else ""

    def _consume_stream(self, resp, on_delta) -> Optional[str]:
        """逐行消费 SSE，边收边回调，返回累积全文；一个字都没收到则 None。

        两个实测要点：
        1) **`chunk_size=1` 是必须的**。`requests.iter_lines()` 默认按 512 字节攒批，
           实测首字延迟 0.45s，而 `chunk_size=1` 是 0.23s —— 攒批把流式收益吃掉一半。
           （同一探针里 `resp.raw.readline()` 也是 0.23s，说明瓶颈就在攒批。）
        2) 单行畸形（非 `data:` / JSON 坏 / delta 结构不对）一律**跳过而不是中断**：
           一次解析失败不该把已经收到的半句话一起丢掉。
        """
        parts = []
        try:
            for raw in resp.iter_lines(chunk_size=1):
                if raw is None:
                    continue
                line = (raw.decode("utf-8", "replace")
                        if isinstance(raw, (bytes, bytearray)) else raw)
                s = line.strip()
                if not s or not s.startswith("data:"):
                    continue
                payload = s[5:].strip()
                if payload == "[DONE]":
                    break
                piece = self._delta_of(payload)
                if not piece:
                    continue
                parts.append(piece)
                try:
                    on_delta(piece)
                except Exception as e:
                    # 回调抛异常（如对话框已被销毁）不能中断接收，
                    # 否则"用户关掉了对话框"会连带把整条回复也丢掉。
                    _logger.debug("流式回调异常（已忽略）: %s", e)
        except Exception as e:
            _logger.info("本地 AI 流式读取中断（保留已收到的内容）: %s", e)
        finally:
            try:
                resp.close()
            except Exception:
                pass
        return "".join(parts) or None

    # ---------------- 命令轮询 / 状态同步 / 命令执行（协议留白） ----------------
    def get_commands(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        endpoint = self.commands_endpoint()
        if not endpoint:
            return None          # 协议未定：不轮询
        return self._post_json(endpoint, context)

    def send_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        endpoint = self.status_endpoint()
        if not endpoint:
            return None
        return self._post_json(endpoint, status)

    def execute_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        endpoint = self.command_execute_endpoint()
        if not endpoint:
            return None
        return self._post_json(endpoint, command)

    def _post_json(self, url: str, body: Dict[str, Any],
                   timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """POST JSON；网络异常/5xx 按 max_retries/retry_delay 重试（4xx 不重试）。

        ★ 第58轮：新增可选 `timeout`（秒）。**不给就逐字沿用 `self.timeout`**
          —— 老路径（get_commands/send_status/execute_command，全都只传两个参数）
          行为零变化；给了只影响这一次请求。用途见 `chat()` 里那段注释。

        注意：此方法为**阻塞调用**，使用 requests.post() 同步发送 HTTP 请求，
        超时时间由 self.timeout 控制（从配置读取，默认 30 秒）。
        所有调用此方法的公共方法（chat/get_commands/send_status/execute_command）
        均为阻塞调用，严禁在主线程/UI 线程直接调用。
        """
        try:
            import requests
        except Exception:
            return None
        try:
            _to = self.timeout if timeout is None else max(1.0, float(timeout))
        except (TypeError, ValueError):
            _to = self.timeout
        max_retries = max(0, int(getattr(self, "max_retries", 0) or 0))
        retry_delay = max(0.0, float(getattr(self, "retry_delay", 0.0) or 0.0))
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(url, json=body, headers=self._auth_headers(),
                                     timeout=_to)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code < 500:
                    # 4xx 是请求本身的问题，重试无意义（如 401/400/404）
                    _logger.warning("本地 AI HTTP %s: %s", resp.status_code,
                                    resp.text[:200])
                    return None
                # 5xx：服务端临时故障，按配置退避重试
                _logger.warning("本地 AI HTTP %s（服务端错误，重试 %d/%d）: %s",
                                resp.status_code, attempt + 1, max_retries + 1,
                                resp.text[:200])
            except Exception as e:
                _logger.info("本地 AI %s 请求失败（重试 %d/%d）: %s", url,
                             attempt + 1, max_retries + 1, e)
            if attempt < max_retries and retry_delay > 0:
                time.sleep(retry_delay)
        return None


    # ---------------- 保温（第58轮）：keep_alive 只能靠**原生端点**设 ----------------
    # 实测证据：code-quality-audit/第58轮-模型常驻与预热/_evidence/keepalive_semantics.json
    #   · `/v1/chat/completions` **静默丢弃** `keep_alive` ——
    #     设 30m 之后 `ollama ps` 的 expires_at 增量仍是 300s，
    #     与"不传"那一档**完全相等**（|Δ差| = 0s）；
    #   · `/api/chat` 采纳（10m ⇒ Δ=600s）；
    #   · 且 keep_alive **黏在"模型载入实例"上**：之后每个请求（走兼容端点的普通对话也算）
    #     都用它刷新截止时刻 —— 静置时窗口真的在倒计时（599.96s → 529.96s / 70s），
    #     而随便来一个普通请求就跳回 599.80s。
    # ⇒ 结论：**不需要周期性心跳**，只要在"模型新载入"时设一次。
    #   （同型的既有事实：这个兼容端点也丢 num_ctx / repeat_penalty，
    #     见 assets/ralsei_v4.modelfile 的 PARAMETER 注释。）
    def native_chat_endpoint(self) -> str:
        """Ollama **原生**对话端点。非 Ollama 后端没有它 —— 调用方必须容错。"""
        return f"{self.base_url}/api/chat"

    def ps_endpoint(self) -> str:
        return f"{self.base_url}/api/ps"

    def loaded_models(self) -> Optional[list]:
        """GET `{base_url}/api/ps` 里的已载入模型列表。

        ★ **不触发推理** —— 不会拉模型、也不会刷新 keep_alive 窗口。
          正因为这样，看门狗才敢 30 秒轮询一次（开销≈0）。
        连不上 / 不是 Ollama（404 等）⇒ 返回 **None**（"探测不通"），
        与空列表（"Ollama 在，但没载入任何模型"）**语义严格区分**：
        看门狗据此"退让"而不是"以为没载入就去拉起模型"。
        """
        try:
            import requests
        except Exception:
            return None
        try:
            to = min(10.0, float(getattr(self, 'timeout', 10.0) or 10.0))
        except (TypeError, ValueError):
            to = 10.0
        try:
            resp = requests.get(self.ps_endpoint(), headers=self._auth_headers(),
                                timeout=to)
            if resp.status_code != 200:
                return None
            data = resp.json() or {}
            return list(data.get('models') or [])
        except Exception as e:
            _logger.debug("本地 AI /api/ps 探测失败（忽略）: %s", e)
            return None

    def ensure_keep_alive(self, keep_alive) -> bool:
        """用**原生端点**发一个 1-token 极小请求，把 `keep_alive` 立到当前载入实例上。

        为什么敢真发请求：它只有 1 个 token 输出；模型已载入时实测 0.1~0.3s，
        而且它顺带把窗口往后推 —— 这正是目的，不是副作用。
        失败（端点不存在 / 服务没开 / 超时）一律返回 False，**不抛异常**。
        """
        if not self.enabled:
            return False
        try:
            import requests
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "…"}],
                "stream": False,
                "keep_alive": keep_alive,
                "options": {"num_predict": 1, "temperature": 0.0},
            }
            resp = requests.post(self.native_chat_endpoint(), json=payload,
                                 headers=self._auth_headers(), timeout=self.timeout)
            if resp.status_code != 200:
                _logger.info("保温请求 HTTP %s（忽略）: %s", resp.status_code,
                             resp.text[:120])
                return False
            return True
        except Exception as e:
            _logger.info("保温请求失败（忽略）: %s", e)
            return False


class WarmKeeper:
    """保温看门狗（第58轮）：别让 5 分钟自动卸载把"已经热起来"的前缀缓存抹掉。

    第58轮实测的代价（同一个人设前缀，2371 token）::

        冷 55.79s（23.5 ms/token） → 热 0.149s（**快 375 倍**）
        显式卸载后再发      → 61.07s（**缓存随卸载全丢**）

    ⇒ 保温买的不是"更快"，是"别每次见面都从零重算一遍"。
      它**不会**让 CPU 一直忙：只在"模型是新载入的"那一次发一个 1-token 请求。

    设计要点（都是实测逼出来的）：
      · **不做周期心跳**：keep_alive 黏在载入实例上、普通请求自带续期（见
        `ensure_keep_alive` 上方注释），所以"新载入时设一次"就够；
      · **不主动拉起模型**：`/api/ps` 为空时什么都不做 —— 用户没在用，就不该占内存；
      · **非 Ollama 后端自动退让**：探测连续失败 N 次就自己停掉（不下发任何请求）；
      · **`/api/ps` 只是探测**，不触发推理，所以 30 秒一轮没有代价。

    用法::

        keeper = WarmKeeper(client, keep_alive='30m', interval=30.0)
        keeper.start()
        ...
        keeper.stop()          # 退出时务必停，否则守护线程还在发请求
    """

    def __init__(self, client, keep_alive='30m', interval=30.0):
        self.client = client
        self.keep_alive = keep_alive
        try:
            self.interval = max(5.0, float(interval))
        except (TypeError, ValueError):
            self.interval = 30.0
        self._stop = threading.Event()
        self._thread = None
        self._fails = 0
        #: 当前这个"载入实例"是否已经立过规。卸载（ps 变空）时清 False，
        #: 于是"卸载 → 再载入"会被识别成一次新的载入 ⇒ 补设一次。
        self._armed = False
        #: 观测用：一共设了几次 / 为什么停的（给判据和日志用，不参与逻辑判断）
        self.armed_count = 0
        self.disabled_reason = ''

    # ---- 生命周期 ----
    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name='WarmKeeper',
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout=2.0):
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            try:
                t.join(timeout=timeout)
            except Exception:                                     # noqa: BLE001
                pass

    # ---- 主循环 ----
    def tick(self) -> str:
        """跑一轮，返回本轮动作（`'idle'` / `'armed'` / `'unloaded'` / `'probe_fail'`）。

        单独抽出来是为了**可离线测**：判据可以直接喂一个假 client 调 tick()，
        不必真起 Ollama、不必真发请求。
        """
        models = self.client.loaded_models()
        if models is None:
            self._fails += 1
            return 'probe_fail'
        self._fails = 0
        if not models:
            self._armed = False
            return 'unloaded'
        if self._armed:
            return 'idle'
        if self.client.ensure_keep_alive(self.keep_alive):
            self._armed = True
            self.armed_count += 1
            return 'armed'
        return 'idle'

    def _loop(self):
        while not self._stop.is_set():
            try:
                act = self.tick()
            except Exception as e:                                # noqa: BLE001
                _logger.debug("保温看门狗本轮异常（忽略）: %s", e)
                act = 'probe_fail'
            if act == 'probe_fail':
                self._fails += 1
                if self._fails >= 5:
                    self.disabled_reason = 'ps_unreachable'
                    _logger.info("保温看门狗：连续 %d 次探测不到 /api/ps ⇒ 停用"
                                 "（非 Ollama 后端或服务未启动，属正常退让）",
                                 self._fails)
                    return
                self._stop.wait(self.interval * 2)
                continue
            if act == 'armed':
                _logger.info("保温：模型是新载入的 ⇒ 已设 keep_alive=%s"
                             "（之后每个请求都会自动续期）", self.keep_alive)
            self._stop.wait(self.interval)


# ---------------- 可插拔 provider 注册 ----------------
_provider_factory = None   # 用户培养的 AI 的工厂：callable(config) -> LocalAIBase


def register_provider(factory):
    """注册你的本地 AI 工厂：factory(config) 返回一个 LocalAIBase 实例。
    注册后 create_client() 会优先用它，代码里不必再改任何 main.py 逻辑。"""
    global _provider_factory
    _provider_factory = factory


def create_client(config: Optional[Dict[str, Any]]) -> LocalAIBase:
    """唯一工厂：拿一个"按配置就绪"的 client。

    - enabled=False              → LocalAIStub（空转）
    - 已 register_provider       → 你的工厂实现
    - 否则                       → HTTPLocalAI（OpenAI 兼容骨架）
    """
    # 修复：config 可能是列表/字符串等非 dict（配置被手改），
    # 直接 .get('enabled') 会 AttributeError 使 AI 热启用失败。
    if not isinstance(config, dict):
        config = {}
    if not config.get('enabled'):
        return LocalAIStub(config)
    if _provider_factory is not None:
        try:
            return _provider_factory(config)
        except Exception as e:
            _logger.error("provider 工厂调用失败，回退 HTTPLocalAI: %s", e)
    return HTTPLocalAI(config)


# 向后兼容别名：老代码可能 import APIClient
APIClient = LocalAIStub
