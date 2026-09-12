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

    def chat(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.enabled:
            return None
        try:
            import requests
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
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if self.agent_id:
                payload["agent_id"] = self.agent_id
            # 修复：原先 chat() 与 _post_json() 各写一份 POST/状态码/异常处理逻辑
            # （重复编码），统一走 _post_json，非 200 也统一记 warning 日志。
            data = self._post_json(self.chat_endpoint(), payload)
            if not data:
                return None
            choices = data.get("choices") or []
            if not choices:
                return None
            return (choices[0].get("message", {}) or {}).get("content")
        except Exception as e:
            _logger.info("本地 AI chat 请求失败（忽略）: %s", e)
            return None

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

    def _post_json(self, url: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST JSON；网络异常/5xx 按 max_retries/retry_delay 重试（4xx 不重试）。"""
        try:
            import requests
        except Exception:
            return None
        max_retries = max(0, int(getattr(self, "max_retries", 0) or 0))
        retry_delay = max(0.0, float(getattr(self, "retry_delay", 0.0) or 0.0))
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(url, json=body, headers=self._auth_headers(),
                                     timeout=self.timeout)
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
