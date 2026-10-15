# -*- coding: utf-8 -*-
"""
第115轮 · 步骤 1 元信息（走 REST API，显式 UTF-8；★ 必绕 HTTP_PROXY）

★ 铁律（本轮 probe115a 已经栽过）：本机环境变量里有
  HTTP_PROXY=http://127.0.0.1:54715 ⇒ urllib 默认连 localhost 也丢给代理
  ⇒ 得到 HTTPError 502 Bad Gateway 这种**假故障**。
  一律 build_opener(ProxyHandler({})) 显式绕代理。

只读：只发 HTTP 请求，不改任何文件。输出同时落 txt（别只靠 shell stdout）。
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:11434"
MODELS = ["ralsei:v4", "ralsei:v3", "qwen2.5:7b-instruct-q4_K_M", "qwen3:4b-instruct-2507-q4_K_M"]

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BUF = io.StringIO()


def say(msg):
    print(msg)
    BUF.write(msg + "\n")


def req(method, path, payload=None, timeout=120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with _OPENER.open(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    say("=== 0. 绕代理自证 ===")
    say("  HTTP_PROXY(env) = %r" % os.environ.get("HTTP_PROXY"))
    say("  已用 ProxyHandler({}) 显式绕代理")

    say("\n=== 1. /api/tags ===")
    try:
        tags = req("GET", "/api/tags")
    except Exception as exc:  # noqa: BLE001
        say("  [FAIL] %r" % (exc,))
        say("  ⇒ 服务没起来，先跑 start115_ollama.py")
        return 2
    for m in tags.get("models", []):
        say("  %-40s %10s bytes  modified=%s" % (m.get("name"), m.get("size"), (m.get("modified_at") or "")[:19]))

    for name in MODELS:
        say("\n=== 2. /api/show  %s ===" % name)
        try:
            info = req("POST", "/api/show", {"name": name})
        except urllib.error.HTTPError as exc:
            say("  [SKIP] HTTP %s %s" % (exc.code, exc.reason))
            continue
        except Exception as exc:  # noqa: BLE001
            say("  [FAIL] %r" % (exc,))
            continue

        det = info.get("details") or {}
        mi = info.get("model_info") or {}
        for k in ("parent_model", "family", "format", "parameter_size", "quantization_level"):
            say("  details.%-20s = %r" % (k, det.get(k)))

        ctx_keys = [k for k in mi if k.endswith(".context_length")]
        for k in ctx_keys:
            say("  model_info.%-32s = %r" % (k, mi.get(k)))

        params = info.get("parameters")
        say("  parameters          = %r" % (params,))
        if params is None:
            say("  ⇒ ★ None = Modelfile 里没有任何 PARAMETER 覆盖 ⇒ 采样参数与 num_ctx 全走服务端默认")

        sysmsg = info.get("system")
        say("  system 长度          = %s 字符" % (len(sysmsg) if sysmsg else 0))
        if sysmsg:
            head = sysmsg[:300].replace("\n", " / ")
            say("  system 前 300 字      = %s" % head)

    return 0


if __name__ == "__main__":
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        say("[EXCEPTION] %r" % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            out_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(out_dir, "probe115e_out.txt"), "w",
                      encoding="utf-8", newline="") as f:
                f.write(BUF.getvalue())
        except BaseException:  # noqa: BLE001
            pass
    sys.exit(rc)
